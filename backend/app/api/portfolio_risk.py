"""
P2-3: 组合级风控 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from app.services.portfolio_risk import (
    merge_multi_strategy_signals,
    analyze_portfolio_risk,
    calculate_portfolio_metrics,
    generate_portfolio_report,
)

router = APIRouter()


class MergeSignalsRequest(BaseModel):
    """合并信号请求"""
    strategy_ids: list[str] | None = None
    trade_date: str | None = None


class AnalyzeRiskRequest(BaseModel):
    """分析风险请求"""
    signals: list[dict[str, Any]]
    max_positions: int = 10


class PortfolioReportRequest(BaseModel):
    """组合报告请求"""
    strategy_ids: list[str] | None = None
    trade_date: str | None = None
    max_positions: int = 10


@router.post("/merge-signals")
async def merge_signals(request: MergeSignalsRequest):
    """
    合并多策略信号

    将多个策略的选股信号合并，识别重叠股票和信号强度

    Returns:
        - merged_signals: 合并后的信号列表（按信号数量和评分排序）
        - overlap_analysis: 重叠度分析
        - total_strategies: 参与合并的策略数量
        - total_symbols: 候选股票总数
    """
    try:
        result = merge_multi_strategy_signals(
            strategy_ids=request.strategy_ids,
            trade_date=request.trade_date,
        )

        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"信号合并失败: {str(e)}")


@router.post("/analyze-risk")
async def analyze_risk(request: AnalyzeRiskRequest):
    """
    分析组合风险

    对选定的信号组合进行风险分析：
    - 行业集中度风险
    - 风格集中度风险
    - 单股权重风险

    Returns:
        - concentration_risk: 集中度风险等级（low/medium/high）
        - industry_distribution: 行业分布
        - style_distribution: 风格分布
        - warnings: 风险警告列表
        - recommendations: 改进建议列表
    """
    try:
        result = analyze_portfolio_risk(
            signals=request.signals,
            max_positions=request.max_positions,
        )

        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"风险分析失败: {str(e)}")


@router.post("/calculate-metrics")
async def calculate_metrics(request: AnalyzeRiskRequest):
    """
    计算组合指标

    计算组合级别的综合指标：
    - 持仓数量
    - 平均信号强度
    - 多样性评分
    - 高/中/低置信度信号数量

    Returns:
        - position_count: 持仓数量
        - avg_signal_strength: 平均信号强度
        - diversity_score: 多样性评分（0-100）
        - confidence_distribution: 置信度分布
    """
    try:
        result = calculate_portfolio_metrics(
            signals=request.signals,
            max_positions=request.max_positions,
        )

        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"指标计算失败: {str(e)}")


@router.post("/generate-report")
async def generate_report(request: PortfolioReportRequest):
    """
    生成完整组合报告

    综合多策略信号合并、风险分析、组合指标，生成完整报告

    适用场景：
    - 每日选股决策
    - 组合再平衡评估
    - 风险监控报告

    Returns:
        - merged_signals: 合并信号列表
        - overlap_analysis: 重叠分析
        - risk_analysis: 风险分析结果
        - portfolio_metrics: 组合指标
        - overall_risk_level: 综合风险等级
        - warnings: 所有警告
        - recommendations: 所有建议
    """
    try:
        result = generate_portfolio_report(
            strategy_ids=request.strategy_ids,
            trade_date=request.trade_date,
            max_positions=request.max_positions,
        )

        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")


@router.get("/portfolio-summary")
async def get_portfolio_summary(
    strategy_ids: str | None = None,
    trade_date: str | None = None,
):
    """
    获取组合摘要

    快速获取组合关键指标，不包含详细信号列表

    Query Params:
        - strategy_ids: 策略 ID 列表（逗号分隔，None 表示所有活跃策略）
        - trade_date: 交易日期（None 表示最新）

    Returns:
        - total_strategies: 策略数量
        - total_candidates: 候选股票数量
        - selected_positions: 选中持仓数量
        - overall_risk_level: 综合风险等级
        - key_warnings: 关键警告（最多 3 条）
    """
    try:
        # 解析策略 ID 列表
        strategy_list = None
        if strategy_ids:
            strategy_list = strategy_ids.split(",")

        report = generate_portfolio_report(
            strategy_ids=strategy_list,
            trade_date=trade_date,
            max_positions=10,
        )

        # 只返回摘要信息
        return {
            "status": "success",
            "report_date": report["report_date"],
            "total_strategies": report["total_strategies"],
            "total_candidates": report["total_candidates"],
            "selected_positions": report["selected_positions"],
            "max_positions": report["max_positions"],
            "overall_risk_level": report["overall_risk_level"],
            "key_warnings": report["warnings"][:3],  # 最多 3 条警告
            "diversity_score": report["portfolio_metrics"]["diversity_score"],
            "high_confidence_count": report["portfolio_metrics"]["high_confidence_count"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"摘要获取失败: {str(e)}")


@router.get("/overlap-analysis")
async def get_overlap_analysis(
    strategy_ids: str | None = None,
    trade_date: str | None = None,
):
    """
    获取策略重叠分析

    分析多个策略之间的信号重叠情况

    Query Params:
        - strategy_ids: 策略 ID 列表（逗号分隔）
        - trade_date: 交易日期

    Returns:
        - overlap_counts: 重叠度统计（1个策略、2个策略、3个及以上）
        - high_confidence_symbols: 高置信度股票（3个及以上策略重叠）
        - overlap_matrix: 策略两两重叠矩阵（可选）
    """
    try:
        strategy_list = None
        if strategy_ids:
            strategy_list = strategy_ids.split(",")

        result = merge_multi_strategy_signals(
            strategy_ids=strategy_list,
            trade_date=trade_date,
        )

        # 提取高置信度股票（3个及以上策略）
        high_confidence = [
            sig for sig in result["merged_signals"]
            if sig["signal_count"] >= 3
        ]

        return {
            "status": "success",
            "trade_date": result["trade_date"],
            "total_strategies": result["total_strategies"],
            "overlap_analysis": result["overlap_analysis"],
            "high_confidence_count": len(high_confidence),
            "high_confidence_symbols": [
                {
                    "symbol": sig["symbol"],
                    "signal_count": sig["signal_count"],
                    "strategies": sig["strategies"],
                    "total_score": sig["total_score"],
                }
                for sig in high_confidence[:10]  # 最多返回 10 个
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重叠分析失败: {str(e)}")
