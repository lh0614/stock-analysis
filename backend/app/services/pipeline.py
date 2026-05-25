"""Analysis pipeline orchestrator (ingest → present) with optional SSE streaming."""
from __future__ import annotations

import json
import time
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Generator

from app.core.data_fetcher import StockDataFetcher
from app.core.config import settings
from app.core.db import get_conn, init_db
from app.core.source_priority import get_ordered_source_names
from app.services.technical import compute_indicators
from app.services.price_levels import compute_price_levels
from app.services.direction import build_directions, simple_forecast
from app.services.workflow_memory import get_workflow_service
from app.services.strategy_store import get_strategy_store
from app.services.strategy_runtime import run_strategy
from app.services import pipeline_checkpoint as cp
from app.services.interpretation import build_interpretation

_RUNS: dict[str, dict[str, Any]] = {}
STAGE_ORDER = ("ingest", "validate", "feature", "strategy", "predict", "direction", "present")


class AnalysisPipeline:
    def __init__(self) -> None:
        init_db()
        self.fetcher = StockDataFetcher(cache_dir=settings.CACHE_DIR)

    def run(
        self,
        symbol: str,
        workflow_id: str | None = None,
        strategy_id: str | None = None,
    ) -> dict[str, Any]:
        final: dict[str, Any] | None = None
        for event in self.iter_run(symbol, workflow_id, strategy_id):
            if event.get("event") in ("complete", "error"):
                final = event.get("result")
        return final or {"success": False, "error": "流水线未返回结果"}

    def run_resume(self, run_id: str) -> dict[str, Any]:
        final: dict[str, Any] | None = None
        for event in self.iter_resume(run_id):
            if event.get("event") in ("complete", "error"):
                final = event.get("result")
        return final or {"success": False, "error": "续跑未返回结果"}

    def get_resumable(self, symbol: str) -> dict[str, Any] | None:
        checkpoint = cp.get_resumable(symbol)
        if not checkpoint:
            return None
        return {
            "run_id": checkpoint["run_id"],
            "symbol": checkpoint["symbol"],
            "next_stage": checkpoint.get("next_stage"),
            "failed_stage": checkpoint.get("failed_stage"),
            "saved_at": checkpoint.get("saved_at"),
            "stages": checkpoint.get("stage_logs", []),
        }

    def iter_run(
        self,
        symbol: str,
        workflow_id: str | None = None,
        strategy_id: str | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        run_id = str(uuid.uuid4())
        started = datetime.now().isoformat()
        stage_logs: list[dict[str, Any]] = []
        t0 = time.perf_counter()

        wf_svc = get_workflow_service()
        workflow = wf_svc.get(workflow_id) if workflow_id else None
        if not workflow:
            workflow = wf_svc.get_default()
        workflow_id = workflow["id"] if workflow else workflow_id
        indicator_names = (
            workflow.get("indicators", ["ma", "macd", "rsi"]) if workflow else ["ma", "macd", "rsi"]
        )
        if not strategy_id:
            strategy_id = "builtin_momentum"

        yield from self._run_stages(
            run_id=run_id,
            symbol=symbol,
            started=started,
            stage_logs=stage_logs,
            t0=t0,
            workflow=workflow,
            workflow_id=workflow_id,
            strategy_id=strategy_id,
            indicator_names=indicator_names,
            records=None,
            meta=None,
            indicators=None,
            price_levels=None,
            start_at="ingest",
            resumed=False,
        )

    def iter_resume(self, run_id: str) -> Generator[dict[str, Any], None, None]:
        checkpoint = cp.load_checkpoint(run_id)
        if not checkpoint or not checkpoint.get("records"):
            yield {
                "event": "error",
                "result": {"success": False, "error": "无可恢复的断点"},
            }
            return

        stage_logs = deepcopy(checkpoint.get("stage_logs") or [])
        while stage_logs and stage_logs[-1].get("status") in ("failed", "running"):
            stage_logs.pop()
        next_stage = checkpoint.get("next_stage") or "feature"
        t0 = time.perf_counter()

        yield {
            "event": "start",
            "run_id": checkpoint["run_id"],
            "symbol": checkpoint["symbol"],
            "resumed": True,
            "next_stage": next_stage,
        }
        yield {
            "event": "stage",
            "run_id": checkpoint["run_id"],
            "symbol": checkpoint["symbol"],
            "stages": deepcopy(stage_logs),
        }

        yield from self._run_stages(
            run_id=checkpoint["run_id"],
            symbol=checkpoint["symbol"],
            started=checkpoint.get("started_at", datetime.now().isoformat()),
            stage_logs=stage_logs,
            t0=t0,
            workflow=checkpoint.get("workflow"),
            workflow_id=checkpoint.get("workflow_id"),
            strategy_id=checkpoint.get("strategy_id", "builtin_momentum"),
            indicator_names=checkpoint.get("indicator_names", ["ma", "macd", "rsi"]),
            records=checkpoint["records"],
            meta=checkpoint.get("meta"),
            indicators=checkpoint.get("indicators"),
            price_levels=checkpoint.get("price_levels"),
            start_at=next_stage,
            resumed=True,
        )

    def _run_stages(
        self,
        *,
        run_id: str,
        symbol: str,
        started: str,
        stage_logs: list[dict[str, Any]],
        t0: float,
        workflow: dict[str, Any] | None,
        workflow_id: str | None,
        strategy_id: str,
        indicator_names: list[str],
        records: list[dict[str, Any]] | None,
        meta: dict[str, Any] | None,
        indicators: dict[str, Any] | None,
        price_levels: dict[str, Any] | None,
        start_at: str,
        resumed: bool,
    ) -> Generator[dict[str, Any], None, None]:
        wf_svc = get_workflow_service()
        strategy_output = None
        directions = None
        forecasts = None

        def emit_stage() -> dict[str, Any]:
            return {
                "event": "stage",
                "run_id": run_id,
                "symbol": symbol,
                "stages": deepcopy(stage_logs),
            }

        def log_stage(name: str, label: str, status: str, detail: dict | None = None) -> None:
            stage_logs.append(
                {
                    "id": name,
                    "label": label,
                    "status": status,
                    "duration_ms": int((time.perf_counter() - t0) * 1000),
                    "detail": detail or {},
                }
            )

        def fail_and_return(failed_id: str, error_detail: dict | None = None) -> Generator[dict[str, Any], None, None]:
            if records and self._validate_passed(stage_logs):
                failed = stage_logs[-1] if stage_logs else {"id": failed_id}
                cp.save_checkpoint(
                    {
                        "run_id": run_id,
                        "symbol": symbol,
                        "workflow_id": workflow_id,
                        "strategy_id": strategy_id,
                        "stage_logs": stage_logs,
                        "records": records,
                        "meta": meta,
                        "indicators": indicators,
                        "price_levels": price_levels,
                        "indicator_names": indicator_names,
                        "workflow": workflow,
                        "started_at": started,
                        "next_stage": failed.get("id", failed_id),
                        "failed_stage": failed.get("id", failed_id),
                    }
                )
            payload = self._fail_payload(run_id, symbol, started, stage_logs, workflow_id)
            payload["resumable"] = bool(records and self._validate_passed(stage_logs))
            if error_detail:
                payload["error"] = error_detail.get("error", payload["error"])
            self._save_run(payload)
            yield {"event": "error", "result": payload}

        if not resumed:
            yield {
                "event": "start",
                "run_id": run_id,
                "symbol": symbol,
                "source_order": get_ordered_source_names(),
            }

        start_idx = STAGE_ORDER.index(start_at) if start_at in STAGE_ORDER else 0

        # 1 ingest
        if start_idx <= 0:
            log_stage("ingest", "采集", "running")
            yield emit_stage()
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            result = self.fetcher.get_stock_data(symbol, start_date, end_date)
            if not result.get("success"):
                stage_logs[-1]["status"] = "failed"
                stage_logs[-1]["detail"] = {"error": result.get("error"), **result.get("metadata", {})}
                yield emit_stage()
                yield from fail_and_return("ingest")
                return
            records = result["data"]
            meta = result.get("metadata", {})
            stage_logs[-1]["status"] = "success"
            stage_logs[-1]["detail"] = {
                "rows": len(records),
                "data_source": meta.get("data_source"),
                "cached": meta.get("cached", False),
                "source_order": meta.get("source_order"),
            }
            yield emit_stage()

        assert records is not None

        # 2 validate
        if start_idx <= 1:
            log_stage("validate", "质检", "running")
            yield emit_stage()
            closes = [r.get("close") for r in records if r.get("close") is not None]
            ok = len(closes) >= 20
            stage_logs[-1]["status"] = "success" if ok else "failed"
            stage_logs[-1]["detail"] = {"valid_bars": len(closes), "min_required": 20}
            yield emit_stage()
            if not ok:
                yield from fail_and_return("validate")
                return

        # 3 feature
        if start_idx <= 2 and (indicators is None or price_levels is None):
            log_stage("feature", "特征", "running")
            yield emit_stage()
            indicators = compute_indicators(records, indicator_names)
            price_levels = compute_price_levels(records)
            stage_logs[-1]["status"] = "success"
            stage_logs[-1]["detail"] = {
                "indicators": list(indicators.keys()),
                "workflow": workflow["name"] if workflow else None,
            }
            yield emit_stage()

        if indicators is None or price_levels is None:
            yield from fail_and_return("feature", {"error": "特征计算未完成"})
            return

        # 4 strategy
        if start_idx <= 3:
            log_stage("strategy", "策略", "running")
            yield emit_stage()
            store = get_strategy_store()
            strat = store.get(strategy_id)
            params = store.get_latest_params(strategy_id)
            if strat:
                path = strat["storage_path"]
                ctx = {
                    "symbol": symbol,
                    "ohlcv": records[-60:],
                    "indicators": indicators,
                    "price_levels": price_levels,
                    "params": params,
                }
                exec_result = run_strategy(path, ctx)
                if exec_result.get("success"):
                    strategy_output = exec_result.get("output")
                    stage_logs[-1]["status"] = "success"
                    stage_logs[-1]["detail"] = {
                        "strategy_id": strategy_id,
                        "name": strat["name"],
                        "params": params,
                        "output": strategy_output,
                    }
                else:
                    stage_logs[-1]["status"] = "failed"
                    stage_logs[-1]["detail"] = {
                        "strategy_id": strategy_id,
                        "error": exec_result.get("error"),
                    }
                    yield emit_stage()
                    yield from fail_and_return("strategy")
                    return
            else:
                stage_logs[-1]["status"] = "failed"
                stage_logs[-1]["detail"] = {"error": f"策略 {strategy_id} 不存在"}
                yield emit_stage()
                yield from fail_and_return("strategy")
                return
            yield emit_stage()

        # 5 predict
        if start_idx <= 4:
            log_stage("predict", "预测", "running")
            yield emit_stage()
            forecasts = {
                "short": simple_forecast(records, "short"),
                "medium": simple_forecast(records, "medium"),
                "long": simple_forecast(records, "long"),
            }
            stage_logs[-1]["status"] = "success"
            yield emit_stage()

        # 6 direction
        if start_idx <= 5:
            log_stage("direction", "方向", "running")
            yield emit_stage()
            directions = build_directions(records, indicators, price_levels)
            stage_logs[-1]["status"] = "success"
            stage_logs[-1]["detail"] = {
                "short": directions["short"]["bias"] if directions.get("short") else None,
                "medium": directions["medium"]["bias"] if directions.get("medium") else None,
                "long": directions["long"]["bias"] if directions.get("long") else None,
            }
            yield emit_stage()

        # 7 present
        log_stage("present", "呈现", "success")
        yield emit_stage()

        cp.clear_checkpoint(symbol, run_id)
        interpretation = None
        if wf_svc.get_preference("ai_interpretation_enabled"):
            interpretation = build_interpretation(
                symbol, directions, indicators, price_levels, forecasts
            )
        payload = {
            "success": True,
            "run_id": run_id,
            "symbol": symbol,
            "workflow_id": workflow_id,
            "workflow": workflow,
            "strategy_id": strategy_id,
            "strategy_output": strategy_output,
            "started_at": started,
            "finished_at": datetime.now().isoformat(),
            "stages": stage_logs,
            "metadata": meta,
            "indicators": indicators,
            "price_levels": price_levels,
            "directions": directions,
            "forecasts": forecasts,
            "interpretation": interpretation,
            "disclaimer": "分析结论仅供参考，不构成投资建议",
            "resumed": resumed,
        }
        self._save_run(payload)
        wf_svc.set_preference("last_symbol", symbol)
        wf_svc.set_preference("last_workflow_id", workflow_id)
        yield {"event": "complete", "result": payload}

    @staticmethod
    def _validate_passed(stage_logs: list[dict[str, Any]]) -> bool:
        return any(s.get("id") == "validate" and s.get("status") == "success" for s in stage_logs)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        if run_id in _RUNS:
            return _RUNS[run_id]
        with get_conn() as conn:
            row = conn.execute(
                "SELECT result_json FROM pipeline_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row and row["result_json"]:
            return json.loads(row["result_json"])
        return None

    def list_runs(self, symbol: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            if symbol:
                rows = conn.execute(
                    """
                    SELECT run_id, symbol, workflow_id, success, created_at
                    FROM pipeline_runs WHERE symbol = ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (symbol, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT run_id, symbol, workflow_id, success, created_at
                    FROM pipeline_runs
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [{**dict(r), "success": bool(r["success"])} for r in rows]

    def _save_run(self, payload: dict[str, Any]) -> None:
        _RUNS[payload["run_id"]] = payload
        self._persist_run(payload)

    def _persist_run(self, payload: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pipeline_runs (run_id, symbol, workflow_id, success, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["run_id"],
                    payload["symbol"],
                    payload.get("workflow_id"),
                    1 if payload.get("success") else 0,
                    json.dumps(payload, default=str),
                    payload.get("finished_at", datetime.now().isoformat()),
                ),
            )

    def _fail_payload(
        self,
        run_id: str,
        symbol: str,
        started: str,
        stages: list[dict[str, Any]],
        workflow_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "run_id": run_id,
            "symbol": symbol,
            "workflow_id": workflow_id,
            "started_at": started,
            "finished_at": datetime.now().isoformat(),
            "stages": stages,
            "error": "流水线未完成",
        }


_pipeline = AnalysisPipeline()


def get_pipeline() -> AnalysisPipeline:
    return _pipeline
