from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.sync_scheduler import get_sync_scheduler_service

router = APIRouter()


class SyncSchedulerConfigBody(BaseModel):
    enabled: Optional[bool] = None
    time_of_day: Optional[str] = None
    sync_mode: Optional[str] = None


@router.get("/status")
async def sync_scheduler_status():
    return get_sync_scheduler_service().get_status()


@router.put("/config")
async def sync_scheduler_save_config(body: SyncSchedulerConfigBody):
    svc = get_sync_scheduler_service()
    try:
        svc.save_config(
            enabled=body.enabled,
            time_of_day=body.time_of_day,
            sync_mode=body.sync_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return svc.get_status()


@router.post("/run")
async def sync_scheduler_run_now():
    return await get_sync_scheduler_service().trigger_run(trigger="manual")
