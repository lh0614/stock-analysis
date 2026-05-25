# backend/app/api/workflow.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional, List

from app.services.workflow_memory import get_workflow_service

router = APIRouter()


class WorkflowCreate(BaseModel):
    name: str
    horizon: str = "short"
    indicators: List[str] = ["ma", "macd", "rsi"]
    chart_period: str = "1y"
    is_default: bool = False
    config: dict[str, Any] = {}


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    horizon: Optional[str] = None
    indicators: Optional[List[str]] = None
    chart_period: Optional[str] = None
    is_default: Optional[bool] = None
    config: Optional[dict[str, Any]] = None


class ImportPayload(BaseModel):
    workflows: List[dict[str, Any]] = []
    default_id: Optional[str] = None


@router.get("")
async def list_workflows():
    return {"workflows": get_workflow_service().list_workflows()}


@router.get("/default")
async def get_default_workflow():
    wf = get_workflow_service().get_default()
    if not wf:
        raise HTTPException(status_code=404, detail="无工作流模板")
    return wf


@router.get("/export")
async def export_workflows():
    return get_workflow_service().export_all()


@router.post("/import")
async def import_workflows(body: ImportPayload):
    count = get_workflow_service().import_workflows(body.model_dump())
    return {"imported": count}


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    wf = get_workflow_service().get(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return wf


@router.post("")
async def create_workflow(body: WorkflowCreate):
    return get_workflow_service().create(body.model_dump())


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, body: WorkflowUpdate):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    wf = get_workflow_service().update(workflow_id, data)
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return wf


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    if not get_workflow_service().delete(workflow_id):
        raise HTTPException(status_code=400, detail="无法删除（不存在或为内置模板）")
    return {"ok": True}


@router.post("/{workflow_id}/default")
async def set_default_workflow(workflow_id: str):
    wf = get_workflow_service().set_default(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return wf
