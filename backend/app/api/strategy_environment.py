"""
P2-2: 市场环境与策略适配 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from app.services.strategy_environment import (
    classify_strategy_environment,
    get_current_market_state,
    check_strategy_market_fit,
    analyze_health_degradation_with_market,
)
from app.services.strategy_library import get_strategy

router = APIRouter()


class ClassifyEnvironmentRequest(BaseModel):
    """环境分类请求"""
    spec: dict[str, Any]


class CheckFitRequest(BaseModel):
    """适配度检查请求"""
    strategy_labels: dict[str, Any]
    current_market: dict[str, Any]


class AnalyzeDegradationRequest(BaseModel):
    """衰减分析请求"""
    strategy_id: str
    health_data: dict[str, Any]
    strategy_labels: dict[str, Any]


@router.post("/classify")
async def classify_environment(request: ClassifyEnvironmentRequest):
    """
    给策略打环境标签

    根据策略的入场条件、排序规则、使用的因子，自动判断：
    - 适用的市场状态（trend/oscillation/high_volatility/low_volatility）
    - 适用的投资风格（growth/value/momentum/mean_reversion）

    Returns:
        - market_states: 适用市场状态列表
        - styles: 适用投资风格列表
        - horizon: 持有周期
        - rebalance: 调仓频率
        - 适用说明: 人类可读的说明文本
    """
    try:
        result = classify_strategy_environment(spec=request.spec)

        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"环境分类失败: {str(e)}")


@router.get("/market-state")
async def get_market_state(trade_date: str | None = None):
    """
    获取当前市场环境

    分析市场整体趋势、波动率，判断当前市场状态

    Query Params:
        - trade_date: 交易日期（None 表示最新）

    Returns:
        - state: 市场状态（trend/oscillation/high_volatility/low_volatility/unknown）
        - volatility_level: 波动水平（low/medium/high）
        - trend: 趋势方向（bullish/bearish/neutral）
        - raw_data: 原始市场指标数据
    """
    try:
        result = get_current_market_state(trade_date=trade_date)

        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"市场状态获取失败: {str(e)}")


@router.post("/check-fit")
async def check_fit(request: CheckFitRequest):
    """
    检查策略与市场的适配度

    将策略的环境标签与当前市场状态对比，评估适配程度

    Returns:
        - fit_score: 适配度评分（0-1）
        - fit_status: 适配状态（matched/mismatched/uncertain）
        - fit_message: 适配说明
        - recommendation: 使用建议
    """
    try:
        result = check_strategy_market_fit(
            strategy_labels=request.strategy_labels,
            current_market=request.current_market,
        )

        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"适配度检查失败: {str(e)}")


@router.get("/strategy-fit/{strategy_id}")
async def get_strategy_fit(
    strategy_id: str,
    trade_date: str | None = None,
):
    """
    获取策略当前市场适配度

    一站式接口：给定策略 ID，自动分类环境标签并检查与当前市场的适配度

    Path Params:
        - strategy_id: 策略 ID

    Query Params:
        - trade_date: 交易日期（None 表示最新）

    Returns:
        - strategy_id: 策略 ID
        - strategy_name: 策略名称
        - strategy_labels: 策略环境标签
        - current_market: 当前市场状态
        - fit_analysis: 适配度分析
    """
    try:
        # 获取策略规格
        strategy = get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_id}")

        # 分类策略环境
        strategy_labels = classify_strategy_environment(spec=strategy["spec"])

        # 获取当前市场状态
        current_market = get_current_market_state(trade_date=trade_date)

        # 检查适配度
        fit_analysis = check_strategy_market_fit(
            strategy_labels=strategy_labels,
            current_market=current_market,
        )

        return {
            "status": "success",
            "strategy_id": strategy_id,
            "strategy_name": strategy.get("name", ""),
            "strategy_labels": strategy_labels,
            "current_market": current_market,
            "fit_analysis": fit_analysis,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"适配度获取失败: {str(e)}")


@router.post("/analyze-degradation")
async def analyze_degradation(request: AnalyzeDegradationRequest):
    """
    分析策略健康度衰减原因

    区分策略表现下降是由于：
    1. 市场环境不匹配（环境性）
    2. 策略本身失效（内在性）

    通过分析策略在适配/不适配市场下的表现差异来判断

    Returns:
        - primary_cause: 主要原因（market_mismatch/strategy_deterioration/data_insufficient）
        - cause_type: 原因类型（environmental/intrinsic/unknown）
        - explanation: 详细解释
        - recommendation: 操作建议
        - avg_matched_return: 适配市场平均收益（如有）
        - avg_mismatched_return: 不适配市场平均收益（如有）
    """
    try:
        result = analyze_health_degradation_with_market(
            strategy_id=request.strategy_id,
            health_data=request.health_data,
            strategy_labels=request.strategy_labels,
        )

        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"衰减分析失败: {str(e)}")


@router.get("/batch-strategy-fit")
async def batch_strategy_fit(
    strategy_ids: str,
    trade_date: str | None = None,
):
    """
    批量获取策略适配度

    一次性检查多个策略与当前市场的适配情况

    Query Params:
        - strategy_ids: 策略 ID 列表（逗号分隔）
        - trade_date: 交易日期

    Returns:
        - results: 每个策略的适配度分析列表
        - current_market: 当前市场状态（共享）
        - summary: 汇总统计
    """
    try:
        strategy_list = strategy_ids.split(",")

        # 获取当前市场状态（只获取一次）
        current_market = get_current_market_state(trade_date=trade_date)

        results = []
        matched_count = 0
        mismatched_count = 0

        for strategy_id in strategy_list:
            try:
                # 获取策略规格
                strategy = get_strategy(strategy_id)
                if not strategy:
                    results.append({
                        "strategy_id": strategy_id,
                        "status": "not_found",
                        "error": "策略不存在",
                    })
                    continue

                # 分类策略环境
                strategy_labels = classify_strategy_environment(spec=strategy["spec"])

                # 检查适配度
                fit_analysis = check_strategy_market_fit(
                    strategy_labels=strategy_labels,
                    current_market=current_market,
                )

                results.append({
                    "strategy_id": strategy_id,
                    "strategy_name": strategy.get("name", ""),
                    "status": "success",
                    "strategy_labels": strategy_labels,
                    "fit_analysis": fit_analysis,
                })

                # 统计
                if fit_analysis["fit_status"] == "matched":
                    matched_count += 1
                elif fit_analysis["fit_status"] == "mismatched":
                    mismatched_count += 1

            except Exception as e:
                results.append({
                    "strategy_id": strategy_id,
                    "status": "error",
                    "error": str(e),
                })

        return {
            "status": "success",
            "current_market": current_market,
            "total": len(strategy_list),
            "matched_count": matched_count,
            "mismatched_count": mismatched_count,
            "uncertain_count": len(strategy_list) - matched_count - mismatched_count,
            "results": results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量适配度检查失败: {str(e)}")


@router.get("/market-suitable-strategies")
async def get_market_suitable_strategies(trade_date: str | None = None):
    """
    获取当前市场适合的策略列表

    根据当前市场状态，自动筛选适配度高的策略

    Query Params:
        - trade_date: 交易日期

    Returns:
        - current_market: 当前市场状态
        - suitable_strategies: 适合的策略列表（按适配度排序）
        - unsuitable_strategies: 不适合的策略列表
    """
    try:
        from app.services.strategy_library import list_strategies

        # 获取当前市场状态
        current_market = get_current_market_state(trade_date=trade_date)

        # 获取所有活跃策略
        all_strategies = list_strategies(status="active")

        suitable = []
        unsuitable = []

        for strategy in all_strategies:
            strategy_id = strategy["id"]

            # 分类策略环境
            strategy_labels = classify_strategy_environment(spec=strategy["spec"])

            # 检查适配度
            fit_analysis = check_strategy_market_fit(
                strategy_labels=strategy_labels,
                current_market=current_market,
            )

            strategy_info = {
                "strategy_id": strategy_id,
                "strategy_name": strategy.get("name", ""),
                "fit_score": fit_analysis["fit_score"],
                "fit_status": fit_analysis["fit_status"],
                "fit_message": fit_analysis["fit_message"],
                "market_states": strategy_labels["market_states"],
                "styles": strategy_labels["styles"],
            }

            if fit_analysis["fit_status"] == "matched":
                suitable.append(strategy_info)
            else:
                unsuitable.append(strategy_info)

        # 按适配度排序
        suitable.sort(key=lambda x: x["fit_score"], reverse=True)

        return {
            "status": "success",
            "current_market": current_market,
            "suitable_count": len(suitable),
            "unsuitable_count": len(unsuitable),
            "suitable_strategies": suitable,
            "unsuitable_strategies": unsuitable,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略筛选失败: {str(e)}")
