from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.services.alerts import get_alert_service

router = APIRouter()


class AlertCreate(BaseModel):
    symbol: str
    name: str = ""
    rule_type: str
    threshold: float
    enabled: bool = True
    cooldown_minutes: int = 60


class AlertUpdate(BaseModel):
    name: Optional[str] = None
    threshold: Optional[float] = None
    enabled: Optional[bool] = None
    cooldown_minutes: Optional[int] = None


@router.get("/rules")
async def list_rule_types():
    return {"rules": get_alert_service().rule_types()}


@router.get("")
async def list_alerts(symbol: Optional[str] = Query(None)):
    return {"alerts": get_alert_service().list_alerts(symbol)}


@router.post("")
async def create_alert(body: AlertCreate):
    try:
        return get_alert_service().create(body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{alert_id}")
async def update_alert(alert_id: str, body: AlertUpdate):
    updated = get_alert_service().update(alert_id, body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="预警不存在")
    return updated


@router.delete("/{alert_id}")
async def delete_alert(alert_id: str):
    if not get_alert_service().delete(alert_id):
        raise HTTPException(status_code=404, detail="预警不存在")
    return {"ok": True}


@router.get("/events")
async def list_events(limit: int = Query(50, ge=1, le=200)):
    return {"events": get_alert_service().list_events(limit)}


@router.post("/evaluate")
async def evaluate_alerts():
    return get_alert_service().evaluate_all()
