from fastapi import APIRouter

from app.services.market_env import compute_regime, get_breadth, get_indices, get_sectors

router = APIRouter()


@router.get("/regime")
async def market_regime():
    return compute_regime()


@router.get("/indices")
async def market_indices():
    return {"indices": get_indices()}


@router.get("/breadth")
async def market_breadth():
    return get_breadth()


@router.get("/sectors")
async def market_sectors():
    return {"sectors": get_sectors()}
