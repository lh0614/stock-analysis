import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, List, Optional

from app.services.screener import get_screener_service, list_presets, PRESETS

router = APIRouter()


class ScreenerRunRequest(BaseModel):
    preset_id: Optional[str] = None
    preset_ids: Optional[List[str]] = None
    conditions: Optional[List[dict[str, Any]]] = None
    limit: int = 50
    max_scan: Optional[int] = None
    include_chinext: bool = True
    include_star: bool = True
    include_bse: bool = True
    exclude_st: bool = True
    use_custom_pool: bool = False
    prefer_local_cache: bool = True


@router.get("/presets")
async def get_presets():
    return {"presets": list_presets()}


def _validate_screener_request(body: ScreenerRunRequest) -> None:
    ids = body.preset_ids or ([body.preset_id] if body.preset_id else [])
    if ids:
        unknown = [p for p in ids if p not in PRESETS]
        if unknown:
            raise HTTPException(status_code=400, detail=f"未知预设: {', '.join(unknown)}")
        return
    if not body.conditions:
        raise HTTPException(status_code=400, detail="请至少选择一个预设或提供自定义条件")


@router.post("/run")
async def run_screener(body: ScreenerRunRequest):
    _validate_screener_request(body)
    return get_screener_service().run_scan(
        preset_id=body.preset_id,
        preset_ids=body.preset_ids,
        conditions=body.conditions,
        limit=min(body.limit, 500),
        max_scan=body.max_scan if body.max_scan and body.max_scan > 0 else None,
        include_chinext=body.include_chinext,
        include_star=body.include_star,
        include_bse=body.include_bse,
        exclude_st=body.exclude_st,
        use_custom_pool=body.use_custom_pool,
        prefer_local_cache=body.prefer_local_cache,
    )


@router.get("/runs/{run_id}/results")
async def get_screener_run_results(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        return get_screener_service().get_run_results(run_id, page, page_size)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/run/stream")
async def run_screener_stream(body: ScreenerRunRequest):
    _validate_screener_request(body)

    def event_stream():
        svc = get_screener_service()
        try:
            for item in svc.iter_scan(
                preset_id=body.preset_id,
                preset_ids=body.preset_ids,
                conditions=body.conditions,
                limit=min(body.limit, 500),
                max_scan=body.max_scan if body.max_scan and body.max_scan > 0 else None,
                include_chinext=body.include_chinext,
                include_star=body.include_star,
                include_bse=body.include_bse,
                exclude_st=body.exclude_st,
                use_custom_pool=body.use_custom_pool,
                prefer_local_cache=body.prefer_local_cache,
            ):
                yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            err = {"event": "error", "error": str(e)}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
