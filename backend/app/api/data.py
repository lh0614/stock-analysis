import json
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.data_store import get_data_status
from app.services.data_sync import (
    get_coverage,
    get_job,
    get_raw_symbol,
    iter_sync_daily_bars,
    sync_universe_list,
)

router = APIRouter()


class DailyBarsSyncRequest(BaseModel):
    scope: str = "all"
    symbols: Optional[List[str]] = None
    mode: str = "incremental"


@router.get("/status")
async def data_status():
    return get_data_status()


@router.get("/coverage")
async def data_coverage():
    return get_coverage()


@router.get("/jobs/{job_id}")
async def data_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.post("/sync/universe")
async def sync_universe():
    return sync_universe_list()


@router.post("/sync/daily-bars")
async def sync_daily_bars(body: DailyBarsSyncRequest):
    final = None
    for ev in iter_sync_daily_bars(body.scope, body.symbols, body.mode):
        if ev.get("event") == "complete":
            final = ev
        if ev.get("event") == "error":
            raise HTTPException(status_code=409, detail=ev.get("error"))
    return final or {"success": False}


@router.post("/sync/daily-bars/stream")
async def sync_daily_bars_stream(body: DailyBarsSyncRequest):
    def stream():
        try:
            for item in iter_sync_daily_bars(body.scope, body.symbols, body.mode):
                yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/raw/{source}/{symbol}")
async def data_raw_symbol(source: str, symbol: str):
    return get_raw_symbol(source, symbol)
