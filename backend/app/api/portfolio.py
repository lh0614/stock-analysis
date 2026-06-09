from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel
from typing import Optional

from app.services.portfolio_sim import add_trade, import_trades_csv, list_trades, portfolio_summary

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


@router.post("/simulated-trades/import-csv")
async def import_simulated_trades(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8-sig")
    return import_trades_csv(content)


@router.get("/simulated")
async def get_simulated_portfolio():
    return {
        "trades": list_trades(),
        **portfolio_summary(),
    }
