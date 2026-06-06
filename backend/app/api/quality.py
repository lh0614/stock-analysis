from fastapi import APIRouter

from app.services.data_quality import (
    get_summary,
    get_symbol_quality,
    list_conflicts,
    list_missing_bars,
)

router = APIRouter()


@router.get("/summary")
async def quality_summary():
    return get_summary()


@router.get("/symbol/{symbol}")
async def quality_symbol(symbol: str):
    return get_symbol_quality(symbol)


@router.get("/conflicts")
async def quality_conflicts(limit: int = 100):
    return {"items": list_conflicts(limit)}


@router.get("/missing-bars")
async def quality_missing(limit: int = 100):
    return {"items": list_missing_bars(limit)}
