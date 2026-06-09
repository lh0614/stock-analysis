from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.factors import evaluate_factor_effectiveness, get_factor_catalog, monitor_factor_decay, recompute

router = APIRouter()


class RecomputeRequest(BaseModel):
    symbols: Optional[List[str]] = None


@router.get("/catalog")
async def factor_catalog():
    return {"factors": get_factor_catalog()}


@router.post("/recompute")
async def factor_recompute(body: RecomputeRequest):
    return recompute(body.symbols)


@router.get("/{factor_name}/effectiveness")
async def factor_effectiveness(factor_name: str, horizon: int = 20):
    return evaluate_factor_effectiveness(factor_name, horizon=horizon)


@router.get("/monitor/decay")
async def factor_decay_monitor(horizon: int = 20):
    return monitor_factor_decay(horizon=horizon)
