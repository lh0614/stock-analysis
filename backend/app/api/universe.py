import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from app.services.universe import get_universe_service

router = APIRouter()


class CustomPoolBody(BaseModel):
    symbols: List[str] = []


class SyncStreamBody(BaseModel):
    """sync_mode: incremental=仅补已有全量；full=含断点续传首次全量。"""
    sync_mode: str = "incremental"


@router.get("")
async def list_universe(
    include_chinext: bool = Query(True),
    include_star: bool = Query(True),
    include_bse: bool = Query(True),
    exclude_st: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
):
    svc = get_universe_service()
    items = svc.query(
        include_chinext=include_chinext,
        include_star=include_star,
        include_bse=include_bse,
        exclude_st=exclude_st,
        limit=limit,
    )
    return {"items": items, "stats": svc.get_stats()}


@router.get("/stats")
async def universe_stats():
    return get_universe_service().get_stats()


@router.get("/sync/status")
async def universe_sync_status():
    """K 线全量同步进度（断点续传）。"""
    from app.services.klines_registry import get_klines_registry

    svc = get_universe_service()
    local = svc.load_local_map()
    plan = get_klines_registry().build_queue(sorted(local.keys()))
    return {
        "total_list": plan["total_list"],
        "klines_complete": plan["complete"],
        "klines_pending": plan["pending"],
        "failed_retry": plan["failed"],
        "stale_retry": plan["stale"],
        "registry": get_klines_registry().get_summary(),
        "stats": svc.get_stats(),
    }


@router.post("/sync")
async def sync_universe():
    """兼容：仅同步列表。完整全量请用 POST /sync/stream。"""
    return get_universe_service().sync_from_remote()


@router.post("/sync/stream")
async def sync_universe_stream(body: SyncStreamBody | None = None):
    """列表 + K 线同步。body.sync_mode: incremental | full。"""

    mode = (body.sync_mode if body else "incremental").strip().lower()
    if mode not in ("incremental", "full"):
        mode = "incremental"

    def event_stream():
        svc = get_universe_service()
        for item in svc.iter_sync_all(sync_mode=mode):
            yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/custom")
async def get_custom_pool():
    return {"symbols": get_universe_service().get_custom_pool()}


@router.put("/custom")
async def set_custom_pool(body: CustomPoolBody):
    symbols = get_universe_service().set_custom_pool(body.symbols)
    return {"symbols": symbols, "count": len(symbols)}
