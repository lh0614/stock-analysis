"""
策略优化API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.services.strategy_optimizer import (
    optimize_strategy,
    OptimizationConfig,
    ParameterRange,
    OptimizationResult
)
from app.models.strategy_spec import StrategySpec
from app.services.strategy_library import (
    get_optimization_result,
    get_strategy,
    list_optimization_results,
    promote_optimization_result,
    reject_optimization_result,
    save_optimization_result,
)

router = APIRouter()


class OptimizeRequest(BaseModel):
    """优化请求"""
    strategy_id: str
    objective: str = "sharpe"  # sharpe/return/drawdown/stability
    search_method: str = "grid"  # grid/random
    max_trials: int = 50
    param_ranges: Optional[List[ParameterRange]] = None


class OptimizeResponse(BaseModel):
    """优化响应"""
    job_id: str
    result: OptimizationResult


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_strategy_endpoint(request: OptimizeRequest):
    """
    优化策略

    自动搜索最优参数组合，生成新版本策略
    """
    try:
        # 1. 获取原始策略
        strategy = get_strategy(request.strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")

        # 解析策略规格
        spec = StrategySpec(**strategy['spec'])

        # 2. 配置优化
        config = OptimizationConfig(
            objective=request.objective,
            search_method=request.search_method,
            max_trials=request.max_trials,
            param_ranges=request.param_ranges or []
        )

        # 3. 执行优化
        result = await optimize_strategy(spec, config)

        # 4. 保存优化任务，候选版本由用户手动晋级或拒绝
        save_optimization_result(result, result.candidate_spec)

        return OptimizeResponse(
            job_id=result.optimization_id,
            result=result
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"优化失败: {str(e)}")


@router.get("/jobs")
async def list_optimization_jobs(strategy_id: str | None = None, limit: int = 50):
    """
    获取优化任务列表
    """
    return {"jobs": list_optimization_results(strategy_id=strategy_id, limit=limit)}


@router.get("/jobs/{job_id}")
async def get_optimization_job(job_id: str):
    """
    获取优化任务结果
    """
    job = get_optimization_result(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="优化任务不存在")
    return job


@router.post("/{job_id}/promote")
async def promote_optimization(job_id: str):
    """
    晋级优化版本为活跃策略
    """
    try:
        return promote_optimization_result(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/reject")
async def reject_optimization(job_id: str):
    """
    拒绝优化版本
    """
    try:
        return reject_optimization_result(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
