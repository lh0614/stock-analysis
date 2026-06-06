"""策略评级系统 - A/B/C/D 评级"""
from __future__ import annotations

from typing import Any


def rate_strategy(
    in_sample_metrics: dict[str, Any],
    out_sample_metrics: dict[str, Any],
    overfit_flag: bool = False,
) -> dict[str, Any]:
    """
    策略评级 - 根据样本内外表现评级

    评级标准（PRD 定义）：
    - A 级：样本外稳定、回撤可控、参数不敏感
    - B 级：收益较好但存在阶段性衰减
    - C 级：样本内好、样本外弱，疑似过拟合
    - D 级：风险过大或长期无效

    Args:
        in_sample_metrics: 样本内指标
        out_sample_metrics: 样本外指标
        overfit_flag: 是否疑似过拟合
    """
    out_return = out_sample_metrics.get("annual_return", 0)
    out_mdd = out_sample_metrics.get("max_drawdown", 1)
    out_sharpe = out_sample_metrics.get("sharpe_ratio", 0)
    out_win_rate = out_sample_metrics.get("win_rate", 0)

    in_return = in_sample_metrics.get("annual_return", 0)

    reasons = []

    # D 级：风险过大或无效
    if out_return < -0.05:  # 样本外年化收益 < -5%
        return {
            "rating": "D",
            "reason": "样本外收益为负，策略长期无效",
            "recommendation": "废弃",
            "reasons": ["样本外年化收益 < -5%"],
        }

    if out_mdd > 0.3:  # 最大回撤 > 30%
        return {
            "rating": "D",
            "reason": "最大回撤过大，风险不可控",
            "recommendation": "废弃",
            "reasons": [f"最大回撤 {out_mdd:.1%} > 30%"],
        }

    # C 级：疑似过拟合
    if overfit_flag:
        return {
            "rating": "C",
            "reason": "样本内好、样本外弱，疑似过拟合",
            "recommendation": "观察或优化",
            "reasons": [
                f"样本内年化收益 {in_return:.2%}",
                f"样本外年化收益 {out_return:.2%}",
                "样本外收益显著低于样本内",
            ],
        }

    # A 级：样本外稳定、回撤可控
    if (
        out_return > 0.15  # 样本外年化 > 15%
        and out_mdd < 0.15  # 最大回撤 < 15%
        and out_sharpe > 1.0  # 夏普 > 1
        and out_win_rate > 0.5  # 胜率 > 50%
    ):
        return {
            "rating": "A",
            "reason": "样本外表现优秀，回撤可控，风险收益比佳",
            "recommendation": "启用",
            "reasons": [
                f"样本外年化收益 {out_return:.2%}",
                f"最大回撤 {out_mdd:.1%}",
                f"夏普比率 {out_sharpe:.2f}",
                f"胜率 {out_win_rate:.1%}",
            ],
        }

    # B 级：收益较好但有一定风险
    if out_return > 0.08 and out_mdd < 0.25:  # 年化 > 8%, 回撤 < 25%
        degradation_reasons = []
        if out_sharpe < 0.8:
            degradation_reasons.append(f"夏普比率偏低 {out_sharpe:.2f}")
        if out_win_rate < 0.45:
            degradation_reasons.append(f"胜率偏低 {out_win_rate:.1%}")
        if in_return > 0 and out_return < in_return * 0.7:
            degradation_reasons.append("样本外收益有所衰减")

        return {
            "rating": "B",
            "reason": "收益较好但存在阶段性衰减或波动",
            "recommendation": "谨慎启用或继续观察",
            "reasons": [
                f"样本外年化收益 {out_return:.2%}",
                f"最大回撤 {out_mdd:.1%}",
            ]
            + degradation_reasons,
        }

    # 其他情况归为 C 级
    return {
        "rating": "C",
        "reason": "样本外表现一般，需进一步优化",
        "recommendation": "观察或优化",
        "reasons": [
            f"样本外年化收益 {out_return:.2%}",
            f"最大回撤 {out_mdd:.1%}",
            "未达到 A/B 级标准",
        ],
    }


def evaluate_strategy_health(
    recent_trades: list[dict[str, Any]], historical_metrics: dict[str, Any]
) -> dict[str, Any]:
    """
    评估策略健康度 - 用于监控已启用策略

    检查策略是否出现衰减信号
    """
    if not recent_trades:
        return {
            "health_status": "unknown",
            "degradation_detected": False,
            "recommendation": "无足够数据评估",
        }

    # 计算最近交易的胜率
    recent_wins = [t for t in recent_trades if t.get("pnl", 0) > 0]
    recent_win_rate = len(recent_wins) / len(recent_trades) if recent_trades else 0

    # 与历史指标对比
    historical_win_rate = historical_metrics.get("win_rate", 0.5)

    degradation_signals = []

    # 胜率显著下降（超过 20%）
    if historical_win_rate > 0 and recent_win_rate < historical_win_rate * 0.8:
        degradation_signals.append(
            f"胜率下降: {historical_win_rate:.1%} → {recent_win_rate:.1%}"
        )

    # 连续亏损
    losing_streak = 0
    for trade in reversed(recent_trades):
        if trade.get("pnl", 0) < 0:
            losing_streak += 1
        else:
            break

    if losing_streak >= 5:
        degradation_signals.append(f"连续亏损 {losing_streak} 次")

    if degradation_signals:
        return {
            "health_status": "degraded",
            "degradation_detected": True,
            "signals": degradation_signals,
            "recommendation": "暂停策略或重新优化",
        }

    return {
        "health_status": "healthy",
        "degradation_detected": False,
        "signals": [],
        "recommendation": "继续使用",
    }
