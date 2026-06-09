"""
P2-2: 市场环境与策略适配 - 策略环境标签和适配系统
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from app.models.strategy_spec import StrategySpec


MarketStateType = Literal["trend", "oscillation", "high_volatility", "low_volatility"]
StyleType = Literal["growth", "value", "momentum", "mean_reversion"]


def classify_strategy_environment(
    spec: StrategySpec | dict[str, Any]
) -> dict[str, Any]:
    """
    给策略打环境标签

    Args:
        spec: 策略规格

    Returns:
        环境标签字典
    """
    if isinstance(spec, dict):
        spec = StrategySpec(**spec)

    # 分析策略特征
    market_states = []
    styles = []

    # 检查入场条件
    entry_conditions = spec.entry_conditions or []
    condition_factors = [c.factor for c in entry_conditions]

    # 检查排序规则
    ranking = spec.ranking or []
    ranking_factors = [r.factor for r in ranking]

    all_factors = set(condition_factors + ranking_factors)

    # 1. 判断市场状态适配

    # 趋势市特征：突破、均线多头、价格位置高
    trend_factors = {
        "breakout_20d_high", "breakout_60d_high",
        "ma_bullish_alignment", "price_position_60d"
    }
    if all_factors & trend_factors:
        market_states.append("trend")

    # 震荡市特征：RSI、回踩、支撑压力
    oscillation_factors = {
        "rsi6", "rsi12", "pullback_to_ma20",
        "support_distance", "resistance_distance"
    }
    if all_factors & oscillation_factors:
        market_states.append("oscillation")

    # 高波动特征：使用波动率指标
    high_vol_factors = {"volatility_20d", "volatility_60d", "atr"}
    if all_factors & high_vol_factors:
        # 检查是否有波动率阈值条件
        for cond in entry_conditions:
            if cond.factor in high_vol_factors:
                if cond.op in ["gt", "gte"] or (cond.op == "eq" and isinstance(cond.value, (int, float)) and cond.value > 0.05):
                    market_states.append("high_volatility")
                elif cond.op in ["lt", "lte"] or (cond.op == "eq" and isinstance(cond.value, (int, float)) and cond.value < 0.05):
                    market_states.append("low_volatility")

    # 2. 判断风格

    # 成长风格：收益率、动量
    growth_factors = {
        "return_20d", "return_60d", "return_120d",
        "volume_ratio_5_20", "momentum"
    }
    if all_factors & growth_factors:
        # 检查是否按收益排序
        if any(r.factor in growth_factors and r.direction == "desc" for r in ranking):
            styles.append("growth")

    # 价值风格：PE、PB、估值
    value_factors = {
        "pe_ratio", "pb_ratio", "ps_ratio",
        "dividend_yield", "roe"
    }
    if all_factors & value_factors:
        styles.append("value")

    # 动量风格：趋势、突破
    momentum_factors = {
        "breakout_20d_high", "ma_bullish_alignment",
        "return_5d", "return_20d"
    }
    if all_factors & momentum_factors:
        styles.append("momentum")

    # 均值回归风格：RSI、回踩
    mean_reversion_factors = {
        "rsi6", "pullback_to_ma20", "oversold"
    }
    if all_factors & mean_reversion_factors:
        styles.append("mean_reversion")

    # 默认值
    if not market_states:
        market_states = ["trend", "oscillation"]  # 通用
    if not styles:
        styles = ["momentum"]  # 默认动量

    return {
        "market_states": list(set(market_states)),
        "styles": list(set(styles)),
        "horizon": spec.horizon,
        "rebalance": spec.rebalance,
        "适用说明": generate_适用说明(list(set(market_states)), list(set(styles))),
    }


def generate_适用说明(market_states: list[str], styles: list[str]) -> str:
    """生成策略适用说明"""
    market_map = {
        "trend": "趋势市",
        "oscillation": "震荡市",
        "high_volatility": "高波动市场",
        "low_volatility": "低波动市场",
    }

    style_map = {
        "growth": "成长风格",
        "value": "价值风格",
        "momentum": "动量风格",
        "mean_reversion": "均值回归风格",
    }

    market_text = "、".join([market_map.get(s, s) for s in market_states])
    style_text = "、".join([style_map.get(s, s) for s in styles])

    return f"适合{market_text}，{style_text}"


def get_current_market_state(trade_date: str | None = None) -> dict[str, Any]:
    """
    获取当前市场环境

    Args:
        trade_date: 交易日期（None 表示最新）

    Returns:
        市场环境字典
    """
    from app.services.market_data import get_market_indicators

    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    try:
        market_data = get_market_indicators(trade_date)

        if not market_data:
            return {
                "trade_date": trade_date,
                "state": "unknown",
                "volatility_level": "medium",
                "trend": "neutral",
            }

        # 判断趋势
        trend_signal = market_data.get("trend_signal", 0)
        if trend_signal > 0:
            trend = "bullish"
        elif trend_signal < 0:
            trend = "bearish"
        else:
            trend = "neutral"

        # 判断波动
        volatility_percentile = market_data.get("volatility_percentile", 0.5)
        if volatility_percentile > 0.7:
            volatility_level = "high"
        elif volatility_percentile < 0.3:
            volatility_level = "low"
        else:
            volatility_level = "medium"

        # 判断市场状态
        if trend in ["bullish", "bearish"] and volatility_level in ["low", "medium"]:
            state = "trend"
        elif trend == "neutral" and volatility_level in ["medium", "high"]:
            state = "oscillation"
        elif volatility_level == "high":
            state = "high_volatility"
        else:
            state = "low_volatility"

        return {
            "trade_date": trade_date,
            "state": state,
            "volatility_level": volatility_level,
            "trend": trend,
            "raw_data": market_data,
        }

    except Exception:
        return {
            "trade_date": trade_date,
            "state": "unknown",
            "volatility_level": "medium",
            "trend": "neutral",
        }


def check_strategy_market_fit(
    strategy_labels: dict[str, Any],
    current_market: dict[str, Any]
) -> dict[str, Any]:
    """
    检查策略与当前市场的适配度

    Args:
        strategy_labels: 策略环境标签
        current_market: 当前市场环境

    Returns:
        适配度分析
    """
    market_states = strategy_labels.get("market_states", [])
    current_state = current_market.get("state", "unknown")

    # 适配度评分
    if current_state in market_states:
        fit_score = 1.0
        fit_status = "matched"
        fit_message = f"策略适合当前{current_state}市场"
    elif current_state == "unknown":
        fit_score = 0.5
        fit_status = "uncertain"
        fit_message = "无法判断市场环境，策略适配度未知"
    else:
        fit_score = 0.3
        fit_status = "mismatched"
        fit_message = f"策略不太适合当前{current_state}市场"

    return {
        "fit_score": fit_score,
        "fit_status": fit_status,
        "fit_message": fit_message,
        "strategy_适用": market_states,
        "current_market": current_state,
        "recommendation": get_fit_recommendation(fit_status, current_state, market_states),
    }


def get_fit_recommendation(
    fit_status: str,
    current_state: str,
    strategy_states: list[str]
) -> str:
    """获取适配度建议"""
    if fit_status == "matched":
        return "策略与市场环境匹配良好，可正常使用"
    elif fit_status == "mismatched":
        适用_text = "、".join(strategy_states)
        return f"当前为{current_state}市场，策略更适合{适用_text}，建议谨慎使用或暂停"
    else:
        return "市场环境不明确，建议观察后再决定"


def analyze_health_degradation_with_market(
    strategy_id: str,
    health_data: dict[str, Any],
    strategy_labels: dict[str, Any],
) -> dict[str, Any]:
    """
    结合市场环境分析策略健康度衰减原因

    Args:
        strategy_id: 策略 ID
        health_data: 健康度数据
        strategy_labels: 策略环境标签

    Returns:
        衰减原因分析
    """
    from app.services.strategy_monitor import list_strategy_signals

    # 获取近期信号及其市场环境
    signals = list_strategy_signals(strategy_id, days=60)

    if not signals or len(signals) < 10:
        return {
            "primary_cause": "data_insufficient",
            "cause_type": "unknown",
            "explanation": "信号数量不足，无法分析衰减原因",
        }

    # 分析信号在不同市场环境下的表现
    matched_performance = []
    mismatched_performance = []

    for signal in signals:
        signal_date = signal.get("signal_date")
        forward_return = signal.get("forward_return_20d")

        if forward_return is None:
            continue

        # 获取信号当日的市场环境
        market_state = get_current_market_state(signal_date)

        # 检查适配
        fit = check_strategy_market_fit(strategy_labels, market_state)

        if fit["fit_status"] == "matched":
            matched_performance.append(forward_return)
        elif fit["fit_status"] == "mismatched":
            mismatched_performance.append(forward_return)

    # 计算平均表现
    if len(matched_performance) > 0 and len(mismatched_performance) > 0:
        avg_matched = sum(matched_performance) / len(matched_performance)
        avg_mismatched = sum(mismatched_performance) / len(mismatched_performance)

        # 判断衰减原因
        if avg_matched > 0.02 and avg_mismatched < 0:
            return {
                "primary_cause": "market_mismatch",
                "cause_type": "environmental",
                "explanation": "策略在适配市场表现良好，但在不适配市场表现差，衰减主要由市场环境切换导致",
                "avg_matched_return": avg_matched,
                "avg_mismatched_return": avg_mismatched,
                "recommendation": "等待市场环境切换回适配状态，或考虑暂停策略",
            }
        elif avg_matched < 0 and avg_mismatched < 0:
            return {
                "primary_cause": "strategy_deterioration",
                "cause_type": "intrinsic",
                "explanation": "策略在适配和不适配市场均表现不佳，策略自身可能失效",
                "avg_matched_return": avg_matched,
                "avg_mismatched_return": avg_mismatched,
                "recommendation": "建议触发策略优化或重新生成候选",
            }

    # 默认：需要更多数据
    return {
        "primary_cause": "data_insufficient",
        "cause_type": "unknown",
        "explanation": "样本量不足，无法区分是策略失效还是市场不适配",
        "recommendation": "继续观察或收集更多信号数据",
    }
