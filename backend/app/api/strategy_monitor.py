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
from app.services.strategy_library import get_strategy, list_strategies, list_strategy_signals

router = APIRouter()


@router.get("/health")
async def get_all_strategies_health():
    """
    获取所有活跃策略的健康度
    """
    try:
        report = await run_daily_monitoring()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取健康度失败: {str(e)}")


@router.get("/strategies")
async def get_strategies_health_overview(status: str = "active", limit: int = 100):
    """
    获取策略健康度概览列表。

    默认只读取活跃策略；传 status=all 可读取全部策略。该接口不持久化健康检查。
    """
    try:
        items = list_strategies(status=None if status == "all" else status, limit=limit)
        healths = []
        errors = []
        for item in items:
            try:
                healths.append(check_strategy_health(item["id"], persist=False).model_dump(mode="json"))
            except Exception as exc:
                errors.append({
                    "strategy_id": item.get("id"),
                    "strategy_name": item.get("name"),
                    "error": str(exc),
                })
        return {
            "strategies": healths,
            "errors": errors,
            "total": len(healths),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取健康度概览失败: {str(e)}")


@router.get("/strategies/{strategy_id}")
async def get_strategy_health_status(strategy_id: str):
    """
    获取单个策略的健康度（简化版）
    """
    try:
        health = check_strategy_health(strategy_id, persist=False)
        return health
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取健康度失败: {str(e)}")


@router.get("/strategies/{strategy_id}/detailed")
async def get_strategy_health_detailed(strategy_id: str):
    """
    获取单个策略的详细健康度（包含子分项）
    """
    try:
        from app.services.strategy_library import get_latest_strategy_baseline
        from app.services.strategy_monitor import _recent_signal_performance, list_strategy_signals
        from app.services.health_scoring import calculate_comprehensive_health
        from app.services.data_quality import get_quality_summary_for_symbols

        strategy = get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"策略{strategy_id}不存在")

        # 获取数据
        historical_baseline = get_latest_strategy_baseline(strategy_id)
        recent_performance = _recent_signal_performance(strategy_id, days=60)

        # 获取数据质量
        signals = list_strategy_signals(strategy_id, days=60)
        signal_symbols = list(set([s.get("symbol") for s in signals if s.get("symbol")]))
        quality_summary = get_quality_summary_for_symbols(signal_symbols) if signal_symbols else {"quality_grade": "D"}

        # 计算详细健康度
        health_detail = calculate_comprehensive_health(
            strategy_id=strategy_id,
            recent_performance=recent_performance,
            historical_baseline=historical_baseline,
            data_quality_grade=quality_summary.get("quality_grade", "B")
        )

        return {
            "strategy_id": strategy_id,
            "strategy_name": strategy.get("name"),
            "health_detail": health_detail.model_dump(mode="json"),
            "data_quality": quality_summary,
            "recent_performance": recent_performance,
            "baseline": historical_baseline
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取详细健康度失败: {str(e)}")


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
async def run_strategy_signals_endpoint(strategy_id: str):
    """
    手动运行单个策略并保存选股信号
    """
    try:
        strategy = get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"策略{strategy_id}不存在")
        result = record_strategy_signals(strategy_id, StrategySpec(**strategy["spec"]))
        health = check_strategy_health(strategy_id, persist=True)
        return {"strategy_id": strategy_id, "run": result, "health": health}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"运行策略信号失败: {str(e)}")


@router.post("/run-daily-check")
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
