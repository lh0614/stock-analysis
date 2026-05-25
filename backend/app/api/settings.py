# backend/app/api/settings.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from app.core.config import settings
from app.services.workflow_memory import get_workflow_service
from app.services.cache_admin import cache_stats, clear_pickles, clear_all_cache

router = APIRouter()


class SettingsUpdate(BaseModel):
    data_source_priority: Optional[List[str]] = None
    default_workflow_id: Optional[str] = None
    ai_interpretation_enabled: Optional[bool] = None


@router.get("")
async def get_settings():
    svc = get_workflow_service()
    priority = svc.get_preference("data_source_priority") or settings.DATA_SOURCES
    ai_on = svc.get_preference("ai_interpretation_enabled")
    return {
        "data_source_priority": priority,
        "available_sources": settings.DATA_SOURCES,
        "default_workflow": svc.get_default(),
        "last_symbol": svc.get_preference("last_symbol"),
        "last_workflow_id": svc.get_preference("last_workflow_id"),
        "ai_interpretation_enabled": bool(ai_on) if ai_on is not None else False,
    }


@router.put("")
async def update_settings(body: SettingsUpdate):
    svc = get_workflow_service()
    if body.data_source_priority is not None:
        svc.set_preference("data_source_priority", body.data_source_priority)
    if body.default_workflow_id:
        svc.set_default(body.default_workflow_id)
    if body.ai_interpretation_enabled is not None:
        svc.set_preference("ai_interpretation_enabled", body.ai_interpretation_enabled)
    return await get_settings()


@router.get("/cache")
async def get_cache_stats():
    return cache_stats()


@router.post("/cache/clear-pickles")
async def post_clear_pickles():
    return clear_pickles()


@router.post("/cache/clear-all")
async def post_clear_all_cache():
    return clear_all_cache()
