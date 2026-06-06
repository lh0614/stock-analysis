from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.factors import get_factor_catalog, recompute

router = APIRouter()


class RecomputeRequest(BaseModel):
    symbols: Optional[List[str]] = None


@router.get("/catalog")
async def factor_catalog():
    return {"factors": get_factor_catalog()}


@router.post("/recompute")
async def factor_recompute(body: RecomputeRequest):
    return recompute(body.symbols)
