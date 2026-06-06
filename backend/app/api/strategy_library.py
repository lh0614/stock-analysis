# backend/app/api/strategy_library.py
"""策略库 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.strategy_library import (
    get_strategy_version,
    get_strategy,
    init_strategy_library_tables,
    list_strategy_versions,
    list_strategies,
    save_strategy,
    update_strategy_status,
)

router = APIRouter()

# 确保表已创建
init_strategy_library_tables()


class SaveStrategyRequest(BaseModel):
    spec: dict


class UpdateStatusRequest(BaseModel):
    status: str
    rating: str | None = None


@router.get("")
async def get_strategies(status: str | None = None, limit: int = 50):
    """
    获取策略列表

    Query参数:
    - status: 筛选状态 (idea/generated/backtested/validated/active/watch/degraded/retired)
    - limit: 返回数量限制
    """
    strategies = list_strategies(status=status, limit=limit)
    return {"strategies": strategies, "total": len(strategies)}


@router.get("/{strategy_id}")
async def get_strategy_detail(strategy_id: str):
    """获取策略详情"""
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    return strategy


@router.get("/{strategy_id}/versions")
async def get_strategy_versions(strategy_id: str, limit: int = 50):
    """获取策略版本快照列表"""
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    versions = list_strategy_versions(strategy_id, limit=limit)
    return {"strategy_id": strategy_id, "versions": versions, "total": len(versions)}


@router.get("/{strategy_id}/versions/{version_id}")
async def get_strategy_version_detail(strategy_id: str, version_id: str):
    """获取策略版本详情"""
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    version = get_strategy_version(version_id)
    if not version or version["strategy_id"] != strategy_id:
        raise HTTPException(status_code=404, detail="策略版本不存在")
    return version


@router.post("")
async def create_strategy(request: SaveStrategyRequest):
    """创建新策略"""
    strategy_id = save_strategy(request.spec)
    return {"strategy_id": strategy_id, "message": "策略已保存"}


@router.patch("/{strategy_id}/status")
async def update_status(strategy_id: str, request: UpdateStatusRequest):
    """更新策略状态"""
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    update_strategy_status(strategy_id, request.status, request.rating)
    return {"message": "状态已更新"}


@router.post("/{strategy_id}/activate")
async def activate_strategy(strategy_id: str):
    """启用策略"""
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    update_strategy_status(strategy_id, "active")
    return {"message": "策略已启用"}


@router.post("/{strategy_id}/pause")
async def pause_strategy(strategy_id: str):
    """暂停策略"""
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    update_strategy_status(strategy_id, "watch")
    return {"message": "策略已暂停"}


@router.post("/{strategy_id}/retire")
async def retire_strategy(strategy_id: str):
    """废弃策略"""
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    update_strategy_status(strategy_id, "retired")
    return {"message": "策略已废弃"}
