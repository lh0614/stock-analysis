from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.services.portfolio_sim import add_trade, list_trades, portfolio_summary

router = APIRouter()


class SimTradeCreate(BaseModel):
    plan_id: Optional[str] = None
    symbol: str
    side: str
    price: float
    quantity: float = 100
    fee: float = 0
    traded_at: Optional[str] = None
    note: str = ""


@router.post("/simulated-trades")
async def post_simulated_trade(body: SimTradeCreate):
    return add_trade(body.model_dump())


@router.get("/simulated")
async def get_simulated_portfolio():
    return {
        "trades": list_trades(),
        **portfolio_summary(),
    }
