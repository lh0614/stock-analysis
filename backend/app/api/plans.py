from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.alerts import get_alert_service
from app.services.trade_plans import create_plan, get_plan, list_plans, update_plan

router = APIRouter()


class PlanCreate(BaseModel):
    symbol: str
    horizon: str = "medium"
    trigger_price: Optional[float] = None
    invalid_price: Optional[float] = None
    target_price_1: Optional[float] = None
    target_price_2: Optional[float] = None
    max_position_pct: float = 0.2
    rationale: str = ""
    risks: list[Any] = []
    status: str = "draft"
    source_run_id: Optional[str] = None


class PlanPatch(BaseModel):
    horizon: Optional[str] = None
    trigger_price: Optional[float] = None
    invalid_price: Optional[float] = None
    target_price_1: Optional[float] = None
    target_price_2: Optional[float] = None
    max_position_pct: Optional[float] = None
    status: Optional[str] = None


@router.get("")
async def get_plans(status: Optional[str] = None):
    return {"plans": list_plans(status)}


@router.post("")
async def post_plan(body: PlanCreate):
    return create_plan(body.model_dump())


@router.get("/{plan_id}")
async def get_plan_api(plan_id: str):
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    return plan


@router.patch("/{plan_id}")
async def patch_plan(plan_id: str, body: PlanPatch):
    plan = update_plan(plan_id, body.model_dump(exclude_unset=True))
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    return plan


@router.post("/{plan_id}/alerts")
async def plan_alerts(plan_id: str):
    plan = get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="计划不存在")
    svc = get_alert_service()
    created = []
    if plan.get("trigger_price"):
        created.append(
            svc.create(
                {
                    "symbol": plan["symbol"],
                    "name": f"计划触发-{plan_id[:8]}",
                    "rule_type": "price_above",
                    "threshold": plan["trigger_price"],
                }
            )
        )
    if plan.get("invalid_price"):
        created.append(
            svc.create(
                {
                    "symbol": plan["symbol"],
                    "name": f"计划失效-{plan_id[:8]}",
                    "rule_type": "price_below",
                    "threshold": plan["invalid_price"],
                }
            )
        )
    return {"created": created}
