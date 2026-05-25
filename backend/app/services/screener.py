"""Stock screener with preset filters and scan progress."""
from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timedelta
from typing import Any, Generator

from app.core.board import BOARD_BSE, BOARD_CHINEXT, BOARD_MAIN, BOARD_STAR, classify_board
from app.core.config import settings
from app.core.db import get_conn, init_db
from app.core.data_fetcher import StockDataFetcher
from app.services.technical import compute_indicators
from app.services.universe import get_universe_service

PRESETS: dict[str, dict[str, Any]] = {
    "rsi_oversold": {
        "id": "rsi_oversold",
        "name": "RSI 超卖",
        "description": "RSI12 < 30，寻找超卖反弹候选",
        "conditions": [{"field": "rsi12", "op": "lt", "value": 30}],
    },
    "rsi_overbought": {
        "id": "rsi_overbought",
        "name": "RSI 超买",
        "description": "RSI12 > 70",
        "conditions": [{"field": "rsi12", "op": "gt", "value": 70}],
    },
    "macd_bullish": {
        "id": "macd_bullish",
        "name": "MACD 多头",
        "description": "MACD 柱 > 0",
        "conditions": [{"field": "macd", "op": "gt", "value": 0}],
    },
    "ma_golden": {
        "id": "ma_golden",
        "name": "均线多头",
        "description": "收盘价 > MA20 且 MA5 > MA20",
        "conditions": [
            {"field": "close_above_ma20", "op": "eq", "value": True},
            {"field": "ma5_above_ma20", "op": "eq", "value": True},
        ],
    },
    "volume_surge": {
        "id": "volume_surge",
        "name": "放量上涨",
        "description": "近 5 日量均量 > 20 日均量 1.5 倍且收涨",
        "conditions": [{"field": "volume_surge", "op": "eq", "value": True}],
    },
}


def list_presets() -> list[dict[str, Any]]:
    return list(PRESETS.values())


def _count_boards(stocks: list[dict]) -> dict[str, int]:
    counts = {BOARD_MAIN: 0, BOARD_CHINEXT: 0, BOARD_STAR: 0, BOARD_BSE: 0}
    for stock in stocks:
        b = stock.get("board") or classify_board(stock["symbol"])
        counts[b] = counts.get(b, 0) + 1
    return counts


def _build_scan_universe(
    max_scan: int | None = None,
    *,
    include_chinext: bool = True,
    include_star: bool = True,
    include_bse: bool = True,
    exclude_st: bool = True,
    use_custom_pool: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    svc = get_universe_service()
    if use_custom_pool:
        symbols = svc.get_custom_pool()
        filtered = svc.query(symbols=symbols) if symbols else []
        pool_total = len(symbols)
    else:
        stats = svc.get_stats()
        pool_total = stats.get("total") or 0
        # 先筛板块/ST，再截断扫描数量（不再每次扫描请求 AKShare）
        filtered = svc.query(
            include_chinext=include_chinext,
            include_star=include_star,
            include_bse=include_bse,
            exclude_st=exclude_st,
        )
    pool_counts = _count_boards(filtered)
    meta = {
        "pool_total": pool_total,
        "pool_after_filter": len(filtered),
        "pool_counts": pool_counts,
        "board_filter": {
            "include_chinext": include_chinext,
            "include_star": include_star,
            "include_bse": include_bse,
            "exclude_st": exclude_st,
            "use_custom_pool": use_custom_pool,
        },
        "source": "local_db",
        "last_sync": svc.get_stats().get("last_sync"),
    }
    scan_list = filtered[:max_scan] if max_scan and max_scan > 0 else filtered
    meta["scan_count"] = len(scan_list)
    return scan_list, meta


def _eval_op(actual: float | bool, op: str, expected: float | bool) -> bool:
    if op == "lt":
        return float(actual) < float(expected)
    if op == "gt":
        return float(actual) > float(expected)
    if op == "eq":
        return bool(actual) == bool(expected)
    return False


def _extract_metrics(records: list[dict], indicators: dict[str, Any]) -> dict[str, Any]:
    if not records:
        return {}
    close = float(records[-1].get("close") or 0)
    ma = indicators.get("ma") or {}
    macd = indicators.get("macd") or {}
    rsi = indicators.get("rsi") or {}
    volumes = [r.get("volume") or 0 for r in records[-25:]]
    vol5 = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else 0
    vol20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 0
    prev_close = float(records[-2].get("close") or close) if len(records) > 1 else close
    return {
        "rsi12": rsi.get("rsi12"),
        "macd": macd.get("macd"),
        "close": close,
        "close_above_ma20": close > (ma.get("ma20") or close + 1),
        "ma5_above_ma20": (ma.get("ma5") or 0) > (ma.get("ma20") or 0),
        "volume_surge": vol20 > 0 and vol5 > vol20 * 1.5 and close > prev_close,
        "change_pct": ((close - prev_close) / prev_close * 100) if prev_close else 0,
    }


def _match_conditions(metrics: dict[str, Any], conditions: list[dict]) -> bool:
    """单预设内条件为且（AND）。"""
    for c in conditions:
        field = c["field"]
        val = metrics.get(field)
        if val is None:
            return False
        if not _eval_op(val, c["op"], c["value"]):
            return False
    return True


def resolve_preset_entries(
    preset_id: str | None = None,
    preset_ids: list[str] | None = None,
    conditions: list[dict] | None = None,
) -> tuple[list[tuple[str, str, list[dict]]], str]:
    """
    解析选股条件组。多预设为交集（AND，须全部满足），组内条件也为 AND。
    返回 [(preset_id, preset_name, conditions), ...], 展示名
    """
    ids: list[str] = []
    if preset_ids:
        ids = [p for p in preset_ids if p in PRESETS]
    elif preset_id and preset_id in PRESETS:
        ids = [preset_id]

    if ids:
        entries = [(i, PRESETS[i]["name"], PRESETS[i]["conditions"]) for i in ids]
        label = " ∩ ".join(e[1] for e in entries)
        return entries, label
    if conditions:
        return [("custom", "自定义", conditions)], "自定义"
    default = "rsi_oversold"
    return [(default, PRESETS[default]["name"], PRESETS[default]["conditions"])], PRESETS[default]["name"]


def _match_preset_intersection(
    metrics: dict[str, Any], entries: list[tuple[str, str, list[dict]]]
) -> list[str]:
    """交集：勾选的预设须全部满足，才入选。"""
    hit: list[str] = []
    for pid, _name, conds in entries:
        if _match_conditions(metrics, conds):
            hit.append(pid)
        else:
            return []
    return hit


class ScreenerService:
    def __init__(self) -> None:
        init_db()
        self.fetcher = StockDataFetcher(cache_dir=settings.CACHE_DIR)

    def iter_scan(
        self,
        preset_id: str | None = None,
        preset_ids: list[str] | None = None,
        conditions: list[dict] | None = None,
        limit: int = 50,
        max_scan: int | None = None,
        include_chinext: bool = True,
        include_star: bool = True,
        include_bse: bool = True,
        exclude_st: bool = True,
        use_custom_pool: bool = False,
        prefer_local_cache: bool = True,
    ) -> Generator[dict[str, Any], None, None]:
        run_id = str(uuid.uuid4())
        preset_entries, preset_name = resolve_preset_entries(
            preset_id, preset_ids, conditions
        )

        universe, pool_meta = _build_scan_universe(
            max_scan,
            include_chinext=include_chinext,
            include_star=include_star,
            include_bse=include_bse,
            exclude_st=exclude_st,
            use_custom_pool=use_custom_pool,
        )
        total = len(universe)
        results: list[dict[str, Any]] = []
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

        yield {
            "event": "start",
            "run_id": run_id,
            "total": total,
            "preset": preset_name,
            "preset_ids": [e[0] for e in preset_entries],
            "match_mode": "intersection",
            "prefer_local_cache": prefer_local_cache,
            "pool": pool_meta,
        }

        for idx, stock in enumerate(universe, start=1):
            symbol = stock["symbol"]
            name = stock.get("name", "")
            yield {
                "event": "scanning",
                "run_id": run_id,
                "current": idx,
                "total": total,
                "symbol": symbol,
                "name": name,
            }
            item = self._evaluate_stock(
                stock,
                preset_entries,
                start_date,
                end_date,
                prefer_local_cache=prefer_local_cache,
            )
            yield {"event": "scan_item", "run_id": run_id, **item}
            if item.get("matched") and item.get("hit"):
                results.append(item["hit"])
                yield {
                    "event": "match",
                    "run_id": run_id,
                    "item": item["hit"],
                    "matched_total": len(results),
                }

        payload = {
            "run_id": run_id,
            "preset_id": preset_entries[0][0] if len(preset_entries) == 1 else None,
            "preset_ids": [e[0] for e in preset_entries],
            "conditions": preset_entries[0][2] if len(preset_entries) == 1 else None,
            "preset_name": preset_name,
            "match_mode": "intersection",
            "results": results,
            "scanned": total,
            "matched": len(results),
            "pool": pool_meta,
            "created_at": datetime.now().isoformat(),
        }
        self._save_run(payload)
        yield {
            "event": "complete",
            "result": {
                **payload,
                "results_page": self.paginate_results(results, 1, 20),
            },
        }

    def _evaluate_stock(
        self,
        stock: dict,
        preset_entries: list[tuple[str, str, list[dict]]],
        start_date: str,
        end_date: str,
        *,
        prefer_local_cache: bool,
    ) -> dict[str, Any]:
        symbol = stock["symbol"]
        name = stock.get("name", "")
        base = {
            "symbol": symbol,
            "name": name,
            "matched": False,
            "status": "no_data",
            "message": "",
            "data_source": None,
        }
        try:
            res = self.fetcher.get_stock_data(
                symbol,
                start_date,
                end_date,
                cache_only=prefer_local_cache,
                quiet=True,
            )
        except Exception as e:
            base["message"] = str(e)
            return base

        meta = res.get("metadata") or {}
        base["data_source"] = meta.get("data_source")

        if not res.get("success") or len(res.get("data") or []) < 30:
            base["message"] = res.get("error") or "数据不足"
            return base

        records = res["data"]
        indicators = compute_indicators(records, ["ma", "macd", "rsi"])
        metrics = _extract_metrics(records, indicators)
        hit_ids = _match_preset_intersection(metrics, preset_entries)
        if hit_ids:
            hit = {
                "symbol": symbol,
                "name": name,
                "metrics": {k: v for k, v in metrics.items() if v is not None},
                "matched_presets": [
                    {"id": pid, "name": PRESETS[pid]["name"] if pid in PRESETS else pid}
                    for pid in hit_ids
                ],
            }
            base["matched"] = True
            base["status"] = "matched"
            base["message"] = "符合条件"
            base["hit"] = hit
        else:
            base["status"] = "not_matched"
            base["message"] = "未满足所选预设"
        return base

    @staticmethod
    def paginate_results(
        results: list[dict[str, Any]], page: int, page_size: int
    ) -> dict[str, Any]:
        total = len(results)
        page_size = max(1, min(int(page_size), 100))
        page = max(1, int(page))
        pages = max(1, math.ceil(total / page_size)) if total else 1
        if page > pages:
            page = pages
        start = (page - 1) * page_size
        return {
            "items": results[start : start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    def get_run_results(
        self, run_id: str, page: int = 1, page_size: int = 20
    ) -> dict[str, Any]:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT result_json FROM screener_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if not row:
            raise ValueError("扫描记录不存在")
        payload = json.loads(row["result_json"])
        results = payload.get("results") or []
        page_data = self.paginate_results(results, page, page_size)
        return {
            "run_id": run_id,
            "preset_name": payload.get("preset_name"),
            "matched": payload.get("matched", len(results)),
            "scanned": payload.get("scanned"),
            **page_data,
        }

    def run_scan(self, **kwargs) -> dict[str, Any]:
        final = None
        for ev in self.iter_scan(**kwargs):
            if ev.get("event") == "complete":
                final = ev.get("result")
        return final or {"results": [], "matched": 0}

    def _save_run(self, payload: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO screener_runs (run_id, preset_id, filters_json, result_count, result_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["run_id"],
                    payload.get("preset_id"),
                    json.dumps(payload.get("conditions", [])),
                    payload.get("matched", 0),
                    json.dumps(payload, default=str),
                    payload["created_at"],
                ),
            )


_svc: ScreenerService | None = None


def get_screener_service() -> ScreenerService:
    global _svc
    if _svc is None:
        _svc = ScreenerService()
    return _svc
