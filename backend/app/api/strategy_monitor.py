"""
策略监控API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.strategy_monitor import (
    check_strategy_health,
    run_daily_monitoring,
    get_strategy_health_history,
    record_strategy_signals,
    run_full_monitoring_cycle,
    run_optimization_if_needed,
    StrategyHealth,
    MonitoringReport
)
from app.models.strategy_spec import StrategySpec
from app.services.strategy_library import get_strategy, list_strategy_signals

router = APIRouter()


@router.get("/health", response_model=MonitoringReport)
async def get_all_strategies_health():
    """
    获取所有活跃策略的健康度
    """
    try:
        report = await run_daily_monitoring()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取健康度失败: {str(e)}")


@router.get("/strategies/{strategy_id}", response_model=StrategyHealth)
async def get_strategy_health_status(strategy_id: str):
    """
    获取单个策略的健康度
    """
    try:
        health = await check_strategy_health(strategy_id, persist=False)
        return health
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取健康度失败: {str(e)}")


@router.get("/strategies/{strategy_id}/signals")
async def get_strategy_signals(strategy_id: str, days: int = 60):
    """
    获取策略近期真实选股信号
    """
    try:
        strategy = get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"策略{strategy_id}不存在")
        signals = list_strategy_signals(strategy_id, days=days)
        return {"strategy_id": strategy_id, "days": days, "signals": signals, "total": len(signals)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取信号失败: {str(e)}")


@router.post("/strategies/{strategy_id}/run-signals")
async def run_strategy_signals(strategy_id: str):
    """
    手动运行单个策略并保存选股信号
    """
    try:
        strategy = get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"策略{strategy_id}不存在")
        result = record_strategy_signals(strategy_id, StrategySpec(**strategy["spec"]))
        health = await check_strategy_health(strategy_id, persist=True)
        return {"strategy_id": strategy_id, "run": result, "health": health}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"运行策略信号失败: {str(e)}")


@router.post("/run-daily-check", response_model=MonitoringReport)
async def trigger_daily_check():
    """
    手动触发每日健康检查
    """
    try:
        report = await run_daily_monitoring()
        # TODO: 保存报告到数据库
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行检查失败: {str(e)}")


@router.post("/run-full-cycle")
async def trigger_full_monitoring_cycle(auto_optimize: bool = True):
    """
    手动执行完整监控闭环：信号、收益回填、健康检查、可选自进化优化
    """
    try:
        return await run_full_monitoring_cycle(auto_optimize=auto_optimize)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行完整闭环失败: {str(e)}")


@router.get("/strategies/{strategy_id}/history")
async def get_health_history(strategy_id: str, days: int = 30):
    """
    获取策略健康度历史
    """
    try:
        history = await get_strategy_health_history(strategy_id, days)
        return {"strategy_id": strategy_id, "days": days, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史失败: {str(e)}")


@router.post("/strategies/{strategy_id}/optimize-if-needed")
async def optimize_strategy_if_needed(strategy_id: str):
    """
    健康度衰减时，触发策略自动优化自进化
    """
    try:
        result = await run_optimization_if_needed(strategy_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自进化触发失败: {str(e)}")
