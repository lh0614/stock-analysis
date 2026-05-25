from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.watchlist import get_watchlist_service

router = APIRouter()


class WatchlistAdd(BaseModel):
    symbol: str
    group_id: str = "default"
    name: str = ""
    note: str = ""


class WatchlistGroupCreate(BaseModel):
    name: str


@router.get("")
async def list_watchlist():
    try:
        return {"groups": get_watchlist_service().list_groups()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自选股读取失败: {e}") from e


@router.post("/items")
async def add_watchlist_item(body: WatchlistAdd):
    try:
        item = get_watchlist_service().add_item(
            body.symbol, body.group_id, body.name, body.note
        )
        return item
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/items/{symbol}")
async def remove_watchlist_item(symbol: str, group_id: str = "default"):
    if not get_watchlist_service().remove_item(symbol, group_id):
        raise HTTPException(status_code=404, detail="标的不在自选中")
    return {"ok": True}


@router.post("/groups")
async def create_group(body: WatchlistGroupCreate):
    return get_watchlist_service().create_group(body.name)
