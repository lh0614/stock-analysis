"""数据同步 API 编排：范围解析、任务状态。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Generator

from app.core.db import get_conn, init_db
from app.services import sync_run
from app.services.curated_sync import ingest_symbols
from app.services.data_quality import build_quality_report
from app.services.data_store import get_data_status
from app.services.factors import recompute
from app.services.klines_registry import get_klines_registry
from app.services.klines_sync import KlinesSyncService
from app.services.universe import get_universe_service
from app.services.watchlist import get_watchlist_service
from app.core.data_paths import raw_klines_dir
import os


def resolve_scope_symbols(scope: str, symbols: list[str] | None = None) -> list[str]:
    scope = (scope or "all").lower()
    if scope == "symbols" and symbols:
        return [s.zfill(6)[:6] for s in symbols]
    if scope == "custom":
        return get_universe_service().get_custom_pool()
    if scope == "watchlist":
        wl = get_watchlist_service()
        items = wl.list_all_symbols() if hasattr(wl, "list_all_symbols") else []
        if not items:
            with get_conn() as conn:
                rows = conn.execute("SELECT DISTINCT symbol FROM watchlist_items").fetchall()
                items = [r["symbol"] for r in rows]
        return [s.zfill(6)[:6] for s in items]
    svc = get_universe_service()
    return [s["symbol"] for s in svc.query()]


def get_coverage() -> dict[str, Any]:
    status = get_data_status()
    return {**status, "universe_stats": get_universe_service().get_stats()}


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM klines_sync_jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def iter_sync_daily_bars(
    scope: str = "all",
    symbols: list[str] | None = None,
    mode: str = "incremental",
) -> Generator[dict[str, Any], None, None]:
    lease = sync_run.try_acquire_sync_run()
    if lease is None:
        yield {"event": "error", "error": "同步任务正在运行中"}
        return
    job_id = str(uuid.uuid4())
    sym_list = resolve_scope_symbols(scope, symbols)
    try:
        yield {
            "event": "pipeline_start",
            "job_id": job_id,
            "phases": ["raw", "klines", "curated", "quality", "factors"],
            "total": len(sym_list),
            "scope": scope,
        }
        yield {"event": "phase_start", "job_id": job_id, "phase": "raw", "message": "准备原始数据落盘"}
        yield {"event": "phase_complete", "job_id": job_id, "phase": "raw", "message": "raw 阶段随 K 线同步写入"}
        yield {"event": "phase_start", "job_id": job_id, "phase": "klines", "total": len(sym_list)}
        klines = KlinesSyncService()
        for ev in klines.iter_sync_full(sym_list, job_id=job_id, mode=mode):
            yield {**ev, "phase": "klines"}
        yield {"event": "phase_complete", "job_id": job_id, "phase": "klines"}
        yield {"event": "phase_start", "job_id": job_id, "phase": "curated", "message": "写入 curated Parquet"}
        curated = ingest_symbols(sym_list)
        yield {"event": "phase_complete", "job_id": job_id, "phase": "curated", **curated}
        yield {"event": "phase_start", "job_id": job_id, "phase": "quality", "message": "生成质量报告"}
        quality = build_quality_report(sym_list)
        yield {"event": "phase_complete", "job_id": job_id, "phase": "quality", **quality}
        factors = recompute(sym_list)
        yield {"event": "factors_complete", "phase": "factors", **factors}
        yield {
            "event": "complete",
            "job_id": job_id,
            "scope": scope,
            "symbols": len(sym_list),
            "curated": curated,
            "quality": quality,
        }
    finally:
        sync_run.release_sync_run()


def sync_universe_list() -> dict[str, Any]:
    return get_universe_service().sync_from_remote()


def get_raw_symbol(source: str, symbol: str) -> dict[str, Any]:
    code = symbol.zfill(6)[:6]
    d = os.path.join(raw_klines_dir(source), code)
    if not os.path.isdir(d):
        return {"source": source, "symbol": code, "files": []}
    files = sorted([x for x in os.listdir(d) if x.endswith(".json")], reverse=True)
    return {"source": source, "symbol": code, "files": files, "latest": files[0] if files else None}
