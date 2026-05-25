from fastapi import APIRouter, Query

from app.services.news import get_events_timeline

router = APIRouter()


@router.get("/{symbol}/timeline")
async def symbol_timeline(symbol: str, limit: int = Query(30, ge=1, le=50)):
    return get_events_timeline(symbol.strip(), limit)
