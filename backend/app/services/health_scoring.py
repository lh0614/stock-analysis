"""
健康度评分重构 - 结构化多维度评分模型

将策略健康度拆分为多个可解释的子分，提供更精准的策略状态评估。
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class HealthSubScores(BaseModel):
    """健康度子分项"""
    signal_activity: float = Field(..., ge=0, le=100, description="信号活跃度")
    signal_maturity: float = Field(..., ge=0, le=100, description="信号成熟度")
    win_rate: float = Field(..., ge=0, le=100, description="胜率")
    return_score: float = Field(..., ge=0, le=100, description="收益率")
    drawdown: float = Field(..., ge=0, le=100, description="回撤控制")
    data_quality: float = Field(..., ge=0, le=100, description="数据质量")
    market_fit: float = Field(..., ge=0, le=100, description="市场环境适配度")


class HealthScoreDetail(BaseModel):
    """健康度详细评分"""
    health_score: float = Field(..., ge=0, le=100, description="总健康度评分")
    status: str = Field(..., description="状态: healthy/degraded/failing")
    sub_scores: HealthSubScores
    degradation_reasons: List[str] = Field(default_factory=list, description="衰减原因")
    recommended_actions: List[str] = Field(default_factory=list, description="推荐操作")
    confidence_level: str = Field(..., description="置信度: high/medium/low")
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())


def calculate_signal_activity_score(recent_signals_count: int, expected_signals: int = 30) -> float:
    """
    计算信号活跃度得分

    Args:
        recent_signals_count: 最近信号数量
        expected_signals: 期望信号数量（默认30个/月）

    Returns:
        活跃度得分 0-100
    """
    if recent_signals_count == 0:
        return 0.0

    # 信号数量达到期望值时得满分，超过期望值不加分
    ratio = min(recent_signals_count / expected_signals, 1.0)
    return ratio * 100


def calculate_signal_maturity_score(
    total_signals: int,
    matured_signals: int
) -> float:
    """
    计算信号成熟度得分

    Args:
        total_signals: 总信号数
        matured_signals: 已成熟（有收益数据）的信号数

    Returns:
        成熟度得分 0-100
    """
    if total_signals == 0:
        return 0.0

    maturity_ratio = matured_signals / total_signals
    return maturity_ratio * 100


def calculate_win_rate_score(
    recent_win_rate: float | None,
    baseline_win_rate: float = 0.5
) -> float:
    """
    计算胜率得分

    Args:
        recent_win_rate: 最近胜率
        baseline_win_rate: 基准胜率

    Returns:
        胜率得分 0-100
    """
    if recent_win_rate is None:
        return 50.0  # 无数据时给中等分

    # 以基准胜率为中心，上下浮动评分
    if recent_win_rate >= baseline_win_rate:
        # 胜率达到或超过基准，得分 70-100
        excess = (recent_win_rate - baseline_win_rate) / (1 - baseline_win_rate)
        return 70 + excess * 30
    else:
        # 胜率低于基准，得分 0-70
        return (recent_win_rate / baseline_win_rate) * 70


def calculate_return_score(
    recent_avg_return: float | None,
    baseline_return: float = 0.05
) -> float:
    """
    计算收益率得分

    Args:
        recent_avg_return: 最近平均收益率
        baseline_return: 基准收益率（默认5%）

    Returns:
        收益率得分 0-100
    """
    if recent_avg_return is None:
        return 50.0

    if recent_avg_return < 0:
        # 负收益，根据亏损程度扣分
        loss_ratio = min(abs(recent_avg_return) / 0.1, 1.0)  # -10% 为最差
        return 50 * (1 - loss_ratio)

    # 正收益，根据超过基准的程度加分
    if recent_avg_return >= baseline_return:
        excess = min((recent_avg_return - baseline_return) / baseline_return, 1.0)
        return 70 + excess * 30
    else:
        return 50 + (recent_avg_return / baseline_return) * 20


def calculate_drawdown_score(
    recent_mdd: float,
    baseline_mdd: float = 0.15
) -> float:
    """
    计算回撤控制得分

    Args:
        recent_mdd: 最近最大回撤
        baseline_mdd: 基准最大回撤（默认15%）

    Returns:
        回撤控制得分 0-100
    """
    if recent_mdd <= 0:
        return 100.0  # 无回撤

    if recent_mdd <= baseline_mdd:
        # 回撤在基准范围内，得分 70-100
        ratio = recent_mdd / baseline_mdd
        return 100 - ratio * 30
    else:
        # 回撤超过基准，得分 0-70
        excess_ratio = min((recent_mdd - baseline_mdd) / baseline_mdd, 2.0)
        return max(0, 70 - excess_ratio * 35)


def calculate_data_quality_score(quality_grade: str) -> float:
    """
    计算数据质量得分

    Args:
        quality_grade: 数据质量等级 A/B/C/D

    Returns:
        数据质量得分 0-100
    """
    quality_scores = {
        "A": 100.0,
        "B": 80.0,
        "C": 50.0,
        "D": 20.0
    }
    return quality_scores.get(quality_grade, 50.0)


def calculate_market_fit_score(
    recent_performance: Dict[str, Any],
    market_environment: Dict[str, Any] | None = None
) -> float:
    """
    计算市场环境适配度得分

    Args:
        recent_performance: 最近表现
        market_environment: 市场环境数据（可选）

    Returns:
        市场适配度得分 0-100
    """
    # 暂时使用简化逻辑：基于连续亏损次数判断
    consecutive_losses = recent_performance.get("consecutive_losses", 0)

    if consecutive_losses == 0:
        return 100.0
    elif consecutive_losses <= 2:
        return 80.0
    elif consecutive_losses <= 4:
        return 60.0
    elif consecutive_losses <= 6:
        return 40.0
    else:
        return 20.0


def calculate_comprehensive_health(
    strategy_id: str,
    recent_performance: Dict[str, Any],
    historical_baseline: Dict[str, Any],
    data_quality_grade: str = "B"
) -> HealthScoreDetail:
    """
    计算综合健康度评分

    Args:
        strategy_id: 策略ID
        recent_performance: 最近表现数据
        historical_baseline: 历史基准数据
        data_quality_grade: 数据质量等级

    Returns:
        详细健康度评分
    """
    # 1. 计算各子分项
    signal_activity = calculate_signal_activity_score(
        recent_signals_count=recent_performance.get("signals_count", 0)
    )

    signal_maturity = calculate_signal_maturity_score(
        total_signals=recent_performance.get("signals_count", 0),
        matured_signals=recent_performance.get("matured_signals_count", 0)
    )

    win_rate = calculate_win_rate_score(
        recent_win_rate=recent_performance.get("win_rate"),
        baseline_win_rate=historical_baseline.get("win_rate", 0.5)
    )

    return_score = calculate_return_score(
        recent_avg_return=recent_performance.get("avg_return"),
        baseline_return=historical_baseline.get("avg_return", 0.05)
    )

    drawdown = calculate_drawdown_score(
        recent_mdd=recent_performance.get("max_drawdown", 0),
        baseline_mdd=historical_baseline.get("max_drawdown", 0.15)
    )

    data_quality = calculate_data_quality_score(data_quality_grade)

    market_fit = calculate_market_fit_score(recent_performance)

    sub_scores = HealthSubScores(
        signal_activity=signal_activity,
        signal_maturity=signal_maturity,
        win_rate=win_rate,
        return_score=return_score,
        drawdown=drawdown,
        data_quality=data_quality,
        market_fit=market_fit
    )

    # 2. 计算加权总分
    weights = {
        "signal_activity": 0.10,
        "signal_maturity": 0.10,
        "win_rate": 0.25,
        "return_score": 0.25,
        "drawdown": 0.15,
        "data_quality": 0.10,
        "market_fit": 0.05
    }

    total_score = (
        signal_activity * weights["signal_activity"] +
        signal_maturity * weights["signal_maturity"] +
        win_rate * weights["win_rate"] +
        return_score * weights["return_score"] +
        drawdown * weights["drawdown"] +
        data_quality * weights["data_quality"] +
        market_fit * weights["market_fit"]
    )

    # 3. 确定状态
    if total_score >= 70:
        status = "healthy"
    elif total_score >= 50:
        status = "degraded"
    else:
        status = "failing"

    # 4. 生成衰减原因
    degradation_reasons = []
    if signal_activity < 50:
        degradation_reasons.append(f"信号活跃度较低（{signal_activity:.0f}分）")
    if signal_maturity < 50:
        degradation_reasons.append(f"信号成熟度不足（{signal_maturity:.0f}分），需等待更多数据")
    if win_rate < 50:
        degradation_reasons.append(f"胜率偏低（{win_rate:.0f}分）")
    if return_score < 50:
        degradation_reasons.append(f"收益率不佳（{return_score:.0f}分）")
    if drawdown < 50:
        degradation_reasons.append(f"回撤控制较差（{drawdown:.0f}分）")
    if data_quality < 70:
        degradation_reasons.append(f"数据质量{data_quality_grade}级，影响评估可信度")
    if market_fit < 50:
        degradation_reasons.append(f"市场环境不适配（{market_fit:.0f}分）")

    # 5. 生成推荐操作
    recommended_actions = []
    if signal_activity < 50:
        recommended_actions.append("放宽筛选条件以增加信号数量")
    if win_rate < 60:
        recommended_actions.append("优化入场条件以提高信号质量")
    if return_score < 60:
        recommended_actions.append("调整仓位管理和退出规则")
    if drawdown < 60:
        recommended_actions.append("收紧止损以控制回撤")
    if data_quality < 70:
        recommended_actions.append("刷新数据源以提高数据质量")
    if market_fit < 50:
        recommended_actions.append("评估市场环境变化，考虑暂停策略")
    if total_score >= 70 and not degradation_reasons:
        recommended_actions.append("策略表现健康，继续观察")

    # 6. 确定置信度
    if data_quality >= 80 and signal_maturity >= 70:
        confidence = "high"
    elif data_quality >= 60 and signal_maturity >= 50:
        confidence = "medium"
    else:
        confidence = "low"

    return HealthScoreDetail(
        health_score=round(total_score, 1),
        status=status,
        sub_scores=sub_scores,
        degradation_reasons=degradation_reasons,
        recommended_actions=recommended_actions,
        confidence_level=confidence
    )
