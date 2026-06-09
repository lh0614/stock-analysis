"""
P2-3: 组合级风控 - 多策略信号合并和组合风险分析
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

import pandas as pd


def merge_multi_strategy_signals(
    strategy_ids: list[str] | None = None,
    trade_date: str | None = None,
) -> dict[str, Any]:
    """
    合并多个策略的信号

    Args:
        strategy_ids: 策略 ID 列表（None 表示所有活跃策略）
        trade_date: 信号日期（None 表示最新）

    Returns:
        合并后的信号列表和统计信息
    """
    from app.services.strategy_library import list_strategies, list_strategy_signals

    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    # 获取策略列表
    if strategy_ids is None:
        all_strategies = list_strategies(status="active")
        strategy_ids = [s["id"] for s in all_strategies]

    if not strategy_ids:
        return {
            "trade_date": trade_date,
            "total_strategies": 0,
            "merged_signals": [],
            "overlap_analysis": {},
        }

    # 收集所有信号
    symbol_signals = defaultdict(list)

    for strategy_id in strategy_ids:
        signals = list_strategy_signals(strategy_id, days=1)

        for signal in signals:
            if signal.get("signal_date") == trade_date:
                symbol = signal.get("symbol")
                if symbol:
                    symbol_signals[symbol].append({
                        "strategy_id": strategy_id,
                        "strategy_name": signal.get("strategy_name", ""),
                        "rank": signal.get("rank", 999),
                        "score": signal.get("score", 0),
                    })

    # 合并信号
    merged = []
    for symbol, signals in symbol_signals.items():
        # 计算综合评分
        total_score = sum(s["score"] for s in signals)
        avg_score = total_score / len(signals) if signals else 0
        best_rank = min(s["rank"] for s in signals)

        merged.append({
            "symbol": symbol,
            "signal_count": len(signals),
            "strategies": [s["strategy_id"] for s in signals],
            "strategy_names": [s["strategy_name"] for s in signals],
            "total_score": total_score,
            "avg_score": avg_score,
            "best_rank": best_rank,
            "confidence": "high" if len(signals) >= 3 else ("medium" if len(signals) == 2 else "low"),
        })

    # 按信号数量和评分排序
    merged.sort(key=lambda x: (x["signal_count"], x["total_score"]), reverse=True)

    # 重叠分析
    overlap_counts = defaultdict(int)
    for sig in merged:
        overlap_counts[sig["signal_count"]] += 1

    return {
        "trade_date": trade_date,
        "total_strategies": len(strategy_ids),
        "total_symbols": len(merged),
        "merged_signals": merged,
        "overlap_analysis": dict(overlap_counts),
    }


def analyze_portfolio_risk(
    signals: list[dict[str, Any]],
    max_positions: int = 10,
) -> dict[str, Any]:
    """
    分析组合风险

    Args:
        signals: 信号列表
        max_positions: 最大持仓数

    Returns:
        风险分析结果
    """
    from app.services.stock_pool import get_stock_info

    if not signals:
        return {
            "total_signals": 0,
            "selected_count": 0,
            "concentration_risk": "low",
            "warnings": [],
            "recommendations": [],
        }

    # 选择前 N 个信号
    selected = signals[:max_positions]

    # 获取股票信息
    symbols = [s.get("symbol") for s in selected if s.get("symbol")]
    stock_infos = {}

    for symbol in symbols:
        try:
            info = get_stock_info(symbol)
            if info:
                stock_infos[symbol] = info
        except Exception:
            pass

    # 行业集中度分析
    industry_counts = defaultdict(int)
    for symbol, info in stock_infos.items():
        industry = info.get("industry", "未知")
        industry_counts[industry] += 1

    max_industry_count = max(industry_counts.values()) if industry_counts else 0
    max_industry_ratio = max_industry_count / len(selected) if selected else 0

    # 单股集中度
    if selected:
        # 假设等权重
        single_stock_weight = 1.0 / len(selected)
    else:
        single_stock_weight = 0

    # 风格分析（简化版）
    styles = defaultdict(int)
    for symbol, info in stock_infos.items():
        # 根据市值判断风格
        market_cap = info.get("market_cap", 0)
        if market_cap > 100_000_000_000:  # 1000亿以上
            styles["大盘"] += 1
        elif market_cap > 30_000_000_000:  # 300亿-1000亿
            styles["中盘"] += 1
        else:
            styles["小盘"] += 1

    # 评估集中度风险
    if max_industry_ratio > 0.5:
        concentration_risk = "high"
        warnings = [f"行业过度集中：{max(industry_counts, key=industry_counts.get)} 占比 {max_industry_ratio*100:.1f}%"]
    elif max_industry_ratio > 0.3:
        concentration_risk = "medium"
        warnings = [f"行业集中度较高：最大行业占比 {max_industry_ratio*100:.1f}%"]
    else:
        concentration_risk = "low"
        warnings = []

    # 生成建议
    recommendations = []
    if concentration_risk in ["high", "medium"]:
        recommendations.append("建议分散行业配置，降低集中度风险")

    if single_stock_weight > 0.15:
        recommendations.append(f"单股权重 {single_stock_weight*100:.1f}% 较高，建议增加持仓数量")

    return {
        "total_signals": len(signals),
        "selected_count": len(selected),
        "concentration_risk": concentration_risk,
        "industry_distribution": dict(industry_counts),
        "max_industry_ratio": max_industry_ratio,
        "style_distribution": dict(styles),
        "single_stock_weight": single_stock_weight,
        "warnings": warnings,
        "recommendations": recommendations,
        "selected_symbols": [s.get("symbol") for s in selected],
    }


def calculate_portfolio_metrics(
    signals: list[dict[str, Any]],
    max_positions: int = 10,
) -> dict[str, Any]:
    """
    计算组合级指标

    Args:
        signals: 信号列表
        max_positions: 最大持仓数

    Returns:
        组合指标
    """
    selected = signals[:max_positions]

    if not selected:
        return {
            "position_count": 0,
            "avg_signal_strength": 0,
            "diversity_score": 0,
        }

    # 平均信号强度
    scores = [s.get("total_score", 0) for s in selected]
    avg_score = sum(scores) / len(scores) if scores else 0

    # 多样性评分（基于信号来源数量）
    signal_counts = [s.get("signal_count", 1) for s in selected]
    avg_signal_count = sum(signal_counts) / len(signal_counts) if signal_counts else 1

    # 多样性评分：信号数量越多，多样性越高
    diversity_score = min(100, avg_signal_count * 30)

    return {
        "position_count": len(selected),
        "avg_signal_strength": avg_score,
        "diversity_score": diversity_score,
        "high_confidence_count": sum(1 for s in selected if s.get("confidence") == "high"),
        "medium_confidence_count": sum(1 for s in selected if s.get("confidence") == "medium"),
        "low_confidence_count": sum(1 for s in selected if s.get("confidence") == "low"),
    }


def generate_portfolio_report(
    strategy_ids: list[str] | None = None,
    trade_date: str | None = None,
    max_positions: int = 10,
) -> dict[str, Any]:
    """
    生成完整的组合报告

    Args:
        strategy_ids: 策略列表
        trade_date: 交易日期
        max_positions: 最大持仓数

    Returns:
        完整组合报告
    """
    # 1. 合并信号
    merged_result = merge_multi_strategy_signals(
        strategy_ids=strategy_ids,
        trade_date=trade_date,
    )

    signals = merged_result["merged_signals"]

    # 2. 风险分析
    risk_analysis = analyze_portfolio_risk(
        signals=signals,
        max_positions=max_positions,
    )

    # 3. 组合指标
    metrics = calculate_portfolio_metrics(
        signals=signals,
        max_positions=max_positions,
    )

    # 4. 综合评估
    overall_risk = "low"
    if risk_analysis["concentration_risk"] == "high":
        overall_risk = "high"
    elif risk_analysis["concentration_risk"] == "medium" or metrics["diversity_score"] < 50:
        overall_risk = "medium"

    return {
        "report_date": trade_date or datetime.now().strftime("%Y-%m-%d"),
        "total_strategies": merged_result["total_strategies"],
        "total_candidates": merged_result["total_symbols"],
        "selected_positions": risk_analysis["selected_count"],
        "max_positions": max_positions,
        "merged_signals": signals,
        "overlap_analysis": merged_result["overlap_analysis"],
        "risk_analysis": risk_analysis,
        "portfolio_metrics": metrics,
        "overall_risk_level": overall_risk,
        "warnings": risk_analysis["warnings"],
        "recommendations": risk_analysis["recommendations"],
    }
