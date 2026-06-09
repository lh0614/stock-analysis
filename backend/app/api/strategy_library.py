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
    save_strategy_version,
    save_strategy,
    update_strategy_spec,
    update_strategy_status,
)
from app.services.strategy_monitor import check_strategy_health
from app.services.strategy_research import compare_strategy_specs

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


@router.get("/stats")
async def get_strategy_stats():
    """获取策略库统计和活跃策略健康概览。"""
    strategies = list_strategies(status=None, limit=10000)
    status_breakdown: dict[str, int] = {}
    for item in strategies:
        current_status = item.get("status") or "unknown"
        status_breakdown[current_status] = status_breakdown.get(current_status, 0) + 1

    active = [item for item in strategies if item.get("status") == "active"]
    healthy_count = 0
    degraded_count = 0
    failing_count = 0
    for item in active:
        try:
            health = check_strategy_health(item["id"], persist=False)
            if health.status == "healthy":
                healthy_count += 1
            elif health.status == "degraded":
                degraded_count += 1
            elif health.status == "failing":
                failing_count += 1
        except Exception:
            failing_count += 1

    return {
        "total_strategies": len(strategies),
        "active_strategies": len(active),
        "healthy_strategies": healthy_count,
        "degraded_strategies": degraded_count,
        "failing_strategies": failing_count,
        "status_breakdown": status_breakdown,
    }


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


@router.get("/{strategy_id}/versions/{version_id}/compare")
async def compare_strategy_version(strategy_id: str, version_id: str):
    """对比当前策略与指定版本快照。"""
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    version = get_strategy_version(version_id)
    if not version or version["strategy_id"] != strategy_id:
        raise HTTPException(status_code=404, detail="策略版本不存在")

    current_spec = strategy.get("spec") or {}
    version_spec = version.get("spec") or {}
    diff = compare_strategy_specs(current_spec, version_spec)
    return {
        "strategy_id": strategy_id,
        "current_version": current_spec.get("version"),
        "target_version": version.get("version"),
        "version_id": version_id,
        "diff": diff,
    }


@router.post("/{strategy_id}/versions/{version_id}/rollback")
async def rollback_strategy_version(strategy_id: str, version_id: str):
    """回滚当前策略到指定版本快照，并保存回滚前版本。"""
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    version = get_strategy_version(version_id)
    if not version or version["strategy_id"] != strategy_id:
        raise HTTPException(status_code=404, detail="策略版本不存在")

    current_spec = strategy.get("spec") or {}
    if current_spec:
        save_strategy_version(
            strategy_id=strategy_id,
            version=current_spec.get("version") or "current",
            spec_dict=current_spec,
            change_note=f"rollback backup before restoring {version_id}",
            generated_by="rollback_backup",
        )

    restored_spec = dict(version.get("spec") or {})
    restored_spec["id"] = strategy_id
    restored_spec["status"] = "validated"
    restored_spec["source"] = restored_spec.get("source") or "optimized"
    update_strategy_spec(strategy_id, restored_spec, status="validated", rating=strategy.get("rating"))
    return {
        "strategy_id": strategy_id,
        "rolled_back_to": version_id,
        "version": restored_spec.get("version"),
        "message": "策略已回滚到指定版本",
    }


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
