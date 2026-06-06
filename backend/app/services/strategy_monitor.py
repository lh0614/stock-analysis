"""
策略健康度监控引擎

每日跟踪策略表现，识别衰减，提出优化建议
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import numpy as np

from app.models.strategy_spec import StrategySpec
from app.services.intelligent_screener import run_intelligent_screening
from app.services.strategy_library import (
    get_latest_strategy_baseline,
    get_strategy,
    list_strategies,
    list_strategy_signals,
    save_screener_run,
    save_strategy_signals,
    update_signal_forward_returns,
    save_strategy_health_check,
    get_strategy_health_checks,
    list_optimization_results,
    save_optimization_result,
)


class StrategyHealth(BaseModel):
    """策略健康度"""
    strategy_id: str
    strategy_name: str
    health_score: float = Field(..., description="健康度评分 0-100")
    status: str = Field(..., description="状态: healthy/degraded/failing")

    # 最近表现
    recent_signals_count: int = Field(default=0, description="最近信号数量")
    recent_win_rate: Optional[float] = Field(None, description="最近胜率")
    recent_avg_return: Optional[float] = Field(None, description="最近平均收益")

    # 衰减信号
    degradation_signals: List[str] = Field(default_factory=list)

    # 建议
    recommendations: List[str] = Field(default_factory=list)

    last_check: str = Field(default_factory=lambda: datetime.now().isoformat())


class DegradationSignal(BaseModel):
    """衰减信号"""
    type: str = Field(..., description="信号类型")
    severity: str = Field(..., description="严重程度: low/medium/high")
    message: str = Field(..., description="信号描述")
    detected_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class MonitoringReport(BaseModel):
    """监控报告"""
    report_date: str = Field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d'))
    total_strategies: int
    healthy_count: int
    degraded_count: int
    failing_count: int

    strategy_healths: List[StrategyHealth] = Field(default_factory=list)

    # 全局建议
    global_recommendations: List[str] = Field(default_factory=list)


class MonitoringStepReport(BaseModel):
    """完整监控闭环步骤报告"""
    strategy_id: str
    strategy_name: str
    signal_run: dict[str, Any] | None = None
    health: StrategyHealth | None = None
    optimization: dict[str, Any] | None = None
    error: str | None = None


def calculate_health_score(
    strategy_id: str,
    recent_performance: Dict[str, Any],
    historical_baseline: Dict[str, Any]
) -> float:
    """
    计算健康度评分

    Args:
        strategy_id: 策略ID
        recent_performance: 最近表现
        historical_baseline: 历史基准

    Returns:
        健康度评分 0-100
    """
    score = 100.0

    # 1. 检查最近胜率
    recent_win_rate = recent_performance.get('win_rate')
    baseline_win_rate = historical_baseline.get('win_rate', 0.5)

    if recent_win_rate is not None:
        if recent_win_rate < baseline_win_rate * 0.7:
            score -= 30  # 胜率显著下降
        elif recent_win_rate < baseline_win_rate * 0.85:
            score -= 15  # 胜率有所下降

    # 2. 检查最近收益
    recent_return = recent_performance.get('avg_return')
    baseline_return = historical_baseline.get('avg_return', 0)

    if recent_return is not None:
        if recent_return < 0:
            score -= 25  # 最近收益为负
        elif recent_return < baseline_return * 0.5:
            score -= 15  # 收益显著下降

    # 3. 检查信号数量
    recent_signals = recent_performance.get('signals_count', 0)
    if recent_signals == 0:
        score -= 20  # 无信号

    # 4. 检查最大回撤
    recent_mdd = recent_performance.get('max_drawdown', 0)
    baseline_mdd = historical_baseline.get('max_drawdown', 0.1)

    if recent_mdd > baseline_mdd * 1.5:
        score -= 20  # 回撤显著扩大

    return max(0, min(100, score))


def detect_degradation_signals(
    recent_performance: Dict[str, Any],
    historical_baseline: Dict[str, Any]
) -> List[str]:
    """
    检测衰减信号
    """
    signals = []

    # 1. 胜率持续下降
    recent_win_rate = recent_performance.get('win_rate')
    baseline_win_rate = historical_baseline.get('win_rate', 0.5)

    if recent_win_rate is not None and recent_win_rate < baseline_win_rate * 0.7:
        signals.append(f"胜率从{baseline_win_rate*100:.1f}%下降至{recent_win_rate*100:.1f}%")

    # 2. 收益率下降
    recent_return = recent_performance.get('avg_return')
    baseline_return = historical_baseline.get('avg_return', 0)

    if recent_return is not None and recent_return < baseline_return * 0.5:
        signals.append(f"平均收益从{baseline_return*100:.2f}%下降至{recent_return*100:.2f}%")

    # 3. 连续亏损
    consecutive_losses = recent_performance.get('consecutive_losses', 0)
    if consecutive_losses >= 5:
        signals.append(f"连续{consecutive_losses}次亏损")

    # 4. 信号枯竭
    signals_count = recent_performance.get('signals_count', 0)
    if signals_count == 0:
        signals.append("最近30天无信号产生")
    elif recent_performance.get("matured_signals_count", 0) == 0:
        signals.append("最近信号尚未形成可评估收益，继续等待数据成熟")

    # 5. 回撤扩大
    recent_mdd = recent_performance.get('max_drawdown', 0)
    baseline_mdd = historical_baseline.get('max_drawdown', 0.1)

    if recent_mdd > baseline_mdd * 1.5:
        signals.append(f"最大回撤从{baseline_mdd*100:.1f}%扩大至{recent_mdd*100:.1f}%")

    return signals


def generate_recommendations(
    health_score: float,
    degradation_signals: List[str],
    strategy_spec: StrategySpec
) -> List[str]:
    """
    生成优化建议
    """
    recommendations = []

    if health_score < 50:
        recommendations.append("建议暂停该策略，进行全面复盘")

    if "胜率" in str(degradation_signals):
        recommendations.append("建议优化入场条件，提高信号质量")

    if any(signal.startswith("平均收益") for signal in degradation_signals):
        recommendations.append("建议调整仓位管理和退出规则")

    if "连续" in str(degradation_signals):
        recommendations.append("建议增加风控规则，控制连续亏损")

    if "无信号" in str(degradation_signals):
        recommendations.append("建议放宽筛选条件或更新因子")

    if "回撤" in str(degradation_signals):
        recommendations.append("建议收紧止损，降低单笔最大亏损")

    if health_score >= 70 and not degradation_signals:
        recommendations.append("策略表现健康，继续观察")

    if not recommendations:
        recommendations.append("建议运行参数优化，寻找更优配置")

    return recommendations


def _max_drawdown_from_returns(returns: List[float]) -> float:
    if not returns:
        return 0.0
    equity = np.cumprod(1 + np.array(returns, dtype=float))
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    return float(abs(drawdown.min())) if len(drawdown) else 0.0


def _consecutive_losses(returns: List[float]) -> int:
    count = 0
    for value in reversed(returns):
        if value < 0:
            count += 1
        else:
            break
    return count


def _recent_signal_performance(strategy_id: str, days: int = 60) -> Dict[str, Any]:
    """基于已保存且已成熟的策略信号计算近期表现。"""
    update_signal_forward_returns(strategy_id)
    signals = list_strategy_signals(strategy_id, days=days)
    matured: list[dict[str, Any]] = []
    for signal in signals:
        return_value = signal.get("forward_return_5d")
        if return_value is None:
            return_value = signal.get("forward_return_20d")
        if return_value is None:
            continue
        matured.append({**signal, "return_value": float(return_value)})

    returns = [
        item["return_value"]
        for item in sorted(matured, key=lambda x: (x.get("signal_date") or "", x.get("rank") or 9999))
    ]
    win_rate = None
    avg_return = None
    if returns:
        win_rate = sum(1 for value in returns if value > 0) / len(returns)
        avg_return = float(np.mean(returns))

    return {
        "signals_count": len(signals),
        "matured_signals_count": len(matured),
        "win_rate": win_rate,
        "avg_return": avg_return,
        "max_drawdown": _max_drawdown_from_returns(returns),
        "consecutive_losses": _consecutive_losses(returns),
    }


def record_strategy_signals(strategy_id: str, spec: StrategySpec) -> dict[str, Any]:
    """运行策略选股并保存当期信号。"""
    result = run_intelligent_screening(spec)
    result_dict = result.model_dump(mode="json")
    save_screener_run(
        {
            "run_id": result.run_id,
            "strategy_id": strategy_id,
            "intent_text": spec.intent_text,
            "strategy_spec": result_dict.get("strategy_spec", {}),
            "candidates": result_dict.get("candidates", []),
            "total_scanned": result.total_scanned,
            "total_matched": result.total_matched,
            "execution_time_ms": result.execution_time_ms,
            "created_at": result.created_at,
        }
    )
    saved = save_strategy_signals(
        strategy_id=strategy_id,
        run_id=result.run_id,
        candidates=result_dict.get("candidates", []),
    )
    return {
        "run_id": result.run_id,
        "total_scanned": result.total_scanned,
        "total_matched": result.total_matched,
        "saved_signals": saved,
    }


async def check_strategy_health(strategy_id: str, persist: bool = False) -> StrategyHealth:
    """
    检查单个策略健康度
    """
    # 1. 获取策略
    strategy = get_strategy(strategy_id)
    if not strategy:
        raise ValueError(f"策略{strategy_id}不存在")

    spec = StrategySpec(**strategy['spec'])

    # 2. 获取历史基准（优先使用最新回测/评估记录）
    historical_baseline = get_latest_strategy_baseline(strategy_id)

    # 3. 获取最近真实信号表现
    recent_performance = _recent_signal_performance(strategy_id, days=60)

    # 4. 计算健康度
    health_score = calculate_health_score(
        strategy_id,
        recent_performance,
        historical_baseline
    )

    # 5. 检测衰减信号
    degradation_signals = detect_degradation_signals(
        recent_performance,
        historical_baseline
    )

    # 6. 确定状态
    if health_score >= 70:
        status = "healthy"
    elif health_score >= 50:
        status = "degraded"
    else:
        status = "failing"

    # 7. 生成建议
    recommendations = generate_recommendations(
        health_score,
        degradation_signals,
        spec
    )

    if persist:
        save_strategy_health_check(
            strategy_id=strategy_id,
            health_score=health_score,
            status=status,
            recent_signals_count=recent_performance['signals_count'],
            recent_win_rate=recent_performance.get('win_rate'),
            recent_avg_return=recent_performance.get('avg_return'),
            degradation_signals=degradation_signals,
            recommendations=recommendations,
        )

    return StrategyHealth(
        strategy_id=strategy_id,
        strategy_name=strategy['name'],
        health_score=health_score,
        status=status,
        recent_signals_count=recent_performance['signals_count'],
        recent_win_rate=recent_performance.get('win_rate'),
        recent_avg_return=recent_performance.get('avg_return'),
        degradation_signals=degradation_signals,
        recommendations=recommendations
    )


async def run_daily_monitoring() -> MonitoringReport:
    """
    运行每日监控

    检查所有活跃策略的健康度
    """
    # 1. 获取所有活跃策略
    strategies = list_strategies(status="active")

    # 2. 逐个检查健康度
    healths = []
    for strategy in strategies:
        try:
            full_strategy = get_strategy(strategy['id'])
            if full_strategy:
                spec = StrategySpec(**full_strategy["spec"])
                record_strategy_signals(strategy["id"], spec)
            health = await check_strategy_health(strategy['id'], persist=True)
            healths.append(health)
        except Exception as e:
            print(f"检查策略{strategy['id']}健康度失败: {e}")
            continue

    # 3. 统计
    total = len(strategies)
    healthy_count = sum(1 for h in healths if h.status == "healthy")
    degraded_count = sum(1 for h in healths if h.status == "degraded")
    failing_count = sum(1 for h in healths if h.status == "failing")

    # 4. 生成全局建议
    global_recommendations = []

    if failing_count > 0:
        global_recommendations.append(f"有{failing_count}个策略表现不佳，建议优先处理")

    if degraded_count > total * 0.5:
        global_recommendations.append("超过一半策略出现衰减，可能市场环境发生变化")

    if total > 0 and healthy_count == total:
        global_recommendations.append("所有策略表现健康，继续监控")

    return MonitoringReport(
        total_strategies=total,
        healthy_count=healthy_count,
        degraded_count=degraded_count,
        failing_count=failing_count,
        strategy_healths=healths,
        global_recommendations=global_recommendations
    )


async def get_strategy_health_history(
    strategy_id: str,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    获取策略健康度历史

    Args:
        strategy_id: 策略ID
        days: 查询天数

    Returns:
        健康度历史记录
    """
    return get_strategy_health_checks(strategy_id, days)


async def run_optimization_if_needed(strategy_id: str) -> dict[str, Any]:
    """
    检查健康度并在有必要（评级衰减/失效）时自动触发或手动触发参数优化
    """
    # 1. 检查是否存在待处理的优化任务
    existing_jobs = list_optimization_results(strategy_id=strategy_id)
    pending_jobs = [j for j in existing_jobs if j.get("status") == "pending"]
    if pending_jobs:
        return {
            "status": "skipped",
            "reason": f"策略已有待处理的优化候选版本 {pending_jobs[0]['optimization_id']}，请先评审该版本",
            "job_id": pending_jobs[0]['optimization_id']
        }

    # 2. 检查当前策略健康状况
    health = await check_strategy_health(strategy_id, persist=True)
    matured_waiting = any("尚未形成可评估收益" in s for s in health.degradation_signals)
    if health.recent_signals_count == 0 or matured_waiting:
        return {
            "status": "skipped",
            "reason": "策略信号样本不足或尚未成熟，暂不触发参数自进化",
            "health_score": health.health_score,
            "recent_signals_count": health.recent_signals_count,
        }
    if health.health_score >= 70:
        return {
            "status": "skipped",
            "reason": f"策略当前健康度评分为 {health.health_score:.1f}，表现良好，暂无需进行参数自进化",
            "health_score": health.health_score
        }

    # 3. 评分为 degraded 或 failing，触发自进化优化任务
    from app.services.strategy_optimizer import optimize_strategy, OptimizationConfig

    strategy = get_strategy(strategy_id)
    if not strategy:
        raise ValueError(f"策略{strategy_id}不存在")

    spec = StrategySpec(**strategy['spec'])
    config = OptimizationConfig(
        objective="sharpe",
        search_method="grid",
        max_trials=30
    )

    # 异步执行网格寻优
    result = await optimize_strategy(spec, config)

    # 保存优化候选到数据库
    save_optimization_result(result, result.candidate_spec)

    return {
        "status": "triggered",
        "job_id": result.optimization_id,
        "from_version": result.from_version,
        "to_version": result.to_version,
        "decision": result.decision,
        "reason": result.decision_reason,
        "health_score": health.health_score
    }


async def run_full_monitoring_cycle(auto_optimize: bool = True) -> dict[str, Any]:
    """执行完整闭环：信号生成、收益回填、健康检查、必要时生成优化候选。"""
    strategies = list_strategies(status="active")
    steps: list[MonitoringStepReport] = []
    for strategy_summary in strategies:
        strategy_id = strategy_summary["id"]
        strategy_name = strategy_summary.get("name", strategy_id)
        step = MonitoringStepReport(strategy_id=strategy_id, strategy_name=strategy_name)
        try:
            strategy = get_strategy(strategy_id)
            if not strategy:
                step.error = "策略不存在"
                steps.append(step)
                continue
            spec = StrategySpec(**strategy["spec"])
            step.signal_run = record_strategy_signals(strategy_id, spec)
            update_signal_forward_returns(strategy_id)
            step.health = await check_strategy_health(strategy_id, persist=True)
            if auto_optimize and step.health.status in {"degraded", "failing"}:
                step.optimization = await run_optimization_if_needed(strategy_id)
        except Exception as exc:
            step.error = str(exc)
        steps.append(step)

    healthy_count = sum(1 for s in steps if s.health and s.health.status == "healthy")
    degraded_count = sum(1 for s in steps if s.health and s.health.status == "degraded")
    failing_count = sum(1 for s in steps if s.health and s.health.status == "failing")
    optimization_count = sum(1 for s in steps if s.optimization and s.optimization.get("status") == "triggered")
    return {
        "report_date": datetime.now().strftime("%Y-%m-%d"),
        "total_strategies": len(strategies),
        "healthy_count": healthy_count,
        "degraded_count": degraded_count,
        "failing_count": failing_count,
        "optimization_triggered_count": optimization_count,
        "steps": [s.model_dump(mode="json") for s in steps],
    }
