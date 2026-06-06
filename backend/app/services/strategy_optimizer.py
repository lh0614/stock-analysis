"""
策略优化引擎

自动优化策略参数，生成新版本并验证
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import itertools
import random
from pydantic import BaseModel, Field
import uuid

from app.models.strategy_spec import StrategySpec, ConditionSpec
from app.services.strategy_backtest import run_in_sample_out_sample_backtest
from app.services.intelligent_screener import run_intelligent_screening


class ParameterRange(BaseModel):
    """参数范围"""
    param_path: str = Field(..., description="参数路径，如 'conditions.0.value'")
    param_name: str = Field(..., description="参数名称")
    current_value: Any = Field(..., description="当前值")
    min_value: Optional[float] = Field(None, description="最小值")
    max_value: Optional[float] = Field(None, description="最大值")
    step: Optional[float] = Field(None, description="步长")
    candidates: Optional[List[Any]] = Field(None, description="候选值列表")


class OptimizationConfig(BaseModel):
    """优化配置"""
    objective: str = Field(default="sharpe", description="优化目标: sharpe/return/drawdown/stability")
    max_trials: int = Field(default=50, description="最大尝试次数")
    search_method: str = Field(default="grid", description="搜索方法: grid/random")
    param_ranges: List[ParameterRange] = Field(default_factory=list, description="参数范围")


class OptimizationChange(BaseModel):
    """优化变更"""
    param_path: str
    param_name: str
    from_value: Any
    to_value: Any


class OptimizationResult(BaseModel):
    """优化结果"""
    optimization_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str
    from_version: str
    to_version: str

    objective: str
    search_method: str
    trials_count: int

    changes: List[OptimizationChange] = Field(default_factory=list)
    reason: str = Field(default="", description="优化原因")

    # 优化前后指标
    metrics_before: Dict[str, Any] = Field(default_factory=dict)
    metrics_after: Dict[str, Any] = Field(default_factory=dict)

    # 改进情况
    improvement: Dict[str, float] = Field(default_factory=dict)

    # 决策
    decision: str = Field(..., description="promoted/candidate/rejected")
    decision_reason: str = Field(default="", description="决策原因")
    candidate_spec: Dict[str, Any] = Field(default_factory=dict, description="候选策略规格")

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


def extract_optimizable_params(spec: StrategySpec) -> List[ParameterRange]:
    """
    从策略规格中提取可优化参数
    """
    ranges = []

    # 1. 条件中的数值参数
    for idx, condition in enumerate(spec.entry_conditions):
        if isinstance(condition.value, (int, float)):
            # 根据因子类型推断合理范围
            if 'ratio' in condition.factor.lower() or 'volume_ratio' in condition.factor:
                # 量比类
                ranges.append(ParameterRange(
                    param_path=f"entry_conditions.{idx}.value",
                    param_name=f"{condition.factor}_threshold",
                    current_value=condition.value,
                    min_value=max(0.5, condition.value * 0.7),
                    max_value=condition.value * 1.5,
                    step=0.1
                ))
            elif 'return' in condition.factor:
                # 收益率类
                ranges.append(ParameterRange(
                    param_path=f"entry_conditions.{idx}.value",
                    param_name=f"{condition.factor}_threshold",
                    current_value=condition.value,
                    min_value=condition.value * 0.5,
                    max_value=condition.value * 2.0,
                    step=0.01
                ))
            elif 'rsi' in condition.factor.lower():
                # RSI类
                ranges.append(ParameterRange(
                    param_path=f"entry_conditions.{idx}.value",
                    param_name=f"{condition.factor}_threshold",
                    current_value=condition.value,
                    min_value=20,
                    max_value=80,
                    step=5
                ))

    # 2. 退出规则参数
    for idx, exit_rule in enumerate(spec.exit_conditions):
        if exit_rule.type == 'stop_loss' and 'stop_loss_pct' in exit_rule.params:
            ranges.append(ParameterRange(
                param_path=f"exit_conditions.{idx}.params.stop_loss_pct",
                param_name="stop_loss",
                current_value=exit_rule.params['stop_loss_pct'],
                min_value=0.03,
                max_value=0.15,
                step=0.01
            ))

        if exit_rule.type == 'stop_profit' and 'take_profit_pct' in exit_rule.params:
            ranges.append(ParameterRange(
                param_path=f"exit_conditions.{idx}.params.take_profit_pct",
                param_name="take_profit",
                current_value=exit_rule.params['take_profit_pct'],
                min_value=0.05,
                max_value=0.30,
                step=0.02
            ))

    # 3. 仓位规则
    if spec.position and hasattr(spec.position, 'max_positions'):
        ranges.append(ParameterRange(
            param_path="position.max_positions",
            param_name="max_positions",
            current_value=spec.position.max_positions,
            candidates=[5, 8, 10, 15, 20]
        ))

    return ranges


def generate_param_combinations(
    ranges: List[ParameterRange],
    method: str = "grid",
    max_trials: int = 50
) -> List[Dict[str, Any]]:
    """
    生成参数组合

    Args:
        ranges: 参数范围列表
        method: 搜索方法 grid/random
        max_trials: 最大尝试次数

    Returns:
        参数组合列表
    """
    if not ranges:
        return []

    if method == "grid":
        # 网格搜索
        all_values = []
        for r in ranges:
            if r.candidates:
                all_values.append([(r.param_path, v) for v in r.candidates])
            elif r.min_value is not None and r.max_value is not None and r.step:
                # 生成数值范围
                values = []
                current = r.min_value
                while current <= r.max_value:
                    values.append((r.param_path, current))
                    current += r.step
                all_values.append(values)
            else:
                # 只有当前值
                all_values.append([(r.param_path, r.current_value)])

        # 生成笛卡尔积
        combinations = list(itertools.product(*all_values))

        # 限制数量
        if len(combinations) > max_trials:
            # 随机采样
            combinations = random.sample(combinations, max_trials)

        # 转换为字典列表
        return [dict(combo) for combo in combinations]

    elif method == "random":
        # 随机搜索
        combinations = []
        for _ in range(max_trials):
            combo = {}
            for r in ranges:
                if r.candidates:
                    combo[r.param_path] = random.choice(r.candidates)
                elif r.min_value is not None and r.max_value is not None:
                    if isinstance(r.current_value, int):
                        combo[r.param_path] = random.randint(int(r.min_value), int(r.max_value))
                    else:
                        combo[r.param_path] = random.uniform(r.min_value, r.max_value)
                else:
                    combo[r.param_path] = r.current_value
            combinations.append(combo)
        return combinations

    return []


def apply_params_to_spec(spec: StrategySpec, params: Dict[str, Any]) -> StrategySpec:
    """
    将参数应用到策略规格
    """
    spec_dict = spec.model_dump()

    for path, value in params.items():
        keys = path.split('.')
        current = spec_dict

        for key in keys[:-1]:
            if key.isdigit():
                current = current[int(key)]
            else:
                current = current[key]

        last_key = keys[-1]
        if last_key.isdigit():
            current[int(last_key)] = value
        else:
            current[last_key] = value

    return StrategySpec(**spec_dict)


def calculate_objective_score(metrics: Dict[str, Any], objective: str) -> float:
    """
    根据优化目标计算得分
    """
    if objective == "sharpe":
        return metrics.get('out_sample_sharpe', 0)
    elif objective == "return":
        return metrics.get('out_sample_annual_return', 0)
    elif objective == "drawdown":
        # 回撤越小越好，取负数
        return -metrics.get('out_sample_max_drawdown', 1.0)
    elif objective == "stability":
        # 综合稳定性：样本外收益 - 回撤
        return_val = metrics.get('out_sample_annual_return', 0)
        mdd = metrics.get('out_sample_max_drawdown', 1.0)
        return return_val - mdd * 0.5
    else:
        return metrics.get('out_sample_sharpe', 0)


def flatten_evaluation_metrics(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """Convert nested in/out-sample backtest result to optimizer metric keys."""
    if "out_sample" not in evaluation:
        return evaluation
    in_m = (evaluation.get("in_sample") or {}).get("metrics") or {}
    out_m = (evaluation.get("out_sample") or {}).get("metrics") or {}
    return {
        "in_sample_annual_return": in_m.get("annual_return", 0),
        "in_sample_sharpe": in_m.get("sharpe_ratio", 0),
        "in_sample_max_drawdown": in_m.get("max_drawdown", 1),
        "out_sample_annual_return": out_m.get("annual_return", 0),
        "out_sample_sharpe": out_m.get("sharpe_ratio", 0),
        "out_sample_max_drawdown": out_m.get("max_drawdown", 1),
        "out_sample_win_rate": out_m.get("win_rate", 0),
        "overfit_suspected": bool(evaluation.get("overfit_flag")),
    }


def make_optimization_decision(
    metrics_before: Dict[str, Any],
    metrics_after: Dict[str, Any],
    objective: str
) -> Tuple[str, str, Dict[str, float]]:
    """
    做出优化决策

    Returns:
        (decision, reason, improvement)
    """
    # 计算改进
    improvement = {}

    out_return_before = metrics_before.get('out_sample_annual_return', 0)
    out_return_after = metrics_after.get('out_sample_annual_return', 0)
    improvement['out_sample_return'] = out_return_after - out_return_before

    out_sharpe_before = metrics_before.get('out_sample_sharpe', 0)
    out_sharpe_after = metrics_after.get('out_sample_sharpe', 0)
    improvement['out_sample_sharpe'] = out_sharpe_after - out_sharpe_before

    out_mdd_before = metrics_before.get('out_sample_max_drawdown', 1.0)
    out_mdd_after = metrics_after.get('out_sample_max_drawdown', 1.0)
    improvement['out_sample_mdd'] = out_mdd_before - out_mdd_after  # 回撤减少为正

    # 检查过拟合
    in_return_after = metrics_after.get('in_sample_annual_return', 0)
    overfit_flag = metrics_after.get('overfit_suspected', False)

    # 决策逻辑
    if overfit_flag:
        return "rejected", "样本外表现显著弱于样本内，疑似过拟合", improvement

    if out_return_after < 0:
        return "rejected", "样本外收益为负，策略无效", improvement

    # 根据目标判断
    score_before = calculate_objective_score(metrics_before, objective)
    score_after = calculate_objective_score(metrics_after, objective)

    if score_before == 0:
        if score_after > 0:
            return "promoted", f"{objective}指标由0提升至{score_after:.4f}", improvement
        return "rejected", f"{objective}指标未改善", improvement

    if score_after > score_before * 1.1:  # 提升10%以上
        return "promoted", f"{objective}指标显著提升{((score_after/score_before - 1)*100):.1f}%", improvement
    elif score_after > score_before * 1.05:  # 提升5%以上
        return "candidate", f"{objective}指标有所提升{((score_after/score_before - 1)*100):.1f}%，建议观察", improvement
    else:
        return "rejected", f"{objective}指标提升不明显或变差", improvement


async def optimize_strategy(
    strategy_spec: StrategySpec,
    config: OptimizationConfig,
    baseline_metrics: Optional[Dict[str, Any]] = None
) -> OptimizationResult:
    """
    优化策略

    Args:
        strategy_spec: 原始策略规格
        config: 优化配置
        baseline_metrics: 基准指标（如果已有）

    Returns:
        OptimizationResult: 优化结果
    """
    # 1. 提取可优化参数
    if not config.param_ranges:
        config.param_ranges = extract_optimizable_params(strategy_spec)

    if not config.param_ranges:
        # 没有可优化参数
        return OptimizationResult(
            strategy_id=strategy_spec.id or "unknown",
            from_version=strategy_spec.version,
            to_version=strategy_spec.version,
            objective=config.objective,
            search_method=config.search_method,
            trials_count=0,
            decision="rejected",
            decision_reason="没有可优化的参数"
        )

    # 2. 获取基准指标
    if baseline_metrics is None:
        # 先对原始策略进行回测
        screening_result = run_intelligent_screening(strategy_spec)
        if not screening_result.candidates:
            return OptimizationResult(
                strategy_id=strategy_spec.id or "unknown",
                from_version=strategy_spec.version,
                to_version=strategy_spec.version,
                objective=config.objective,
                search_method=config.search_method,
                trials_count=0,
                decision="rejected",
                decision_reason="选股结果为空，无法回测"
            )

        baseline_metrics = run_in_sample_out_sample_backtest(
            strategy_spec,
            screening_result.candidates
        )
    baseline_score_metrics = flatten_evaluation_metrics(baseline_metrics)

    # 3. 生成参数组合
    param_combinations = generate_param_combinations(
        config.param_ranges,
        config.search_method,
        config.max_trials
    )

    # 4. 遍历参数组合，寻找最优
    best_score = calculate_objective_score(baseline_score_metrics, config.objective)
    best_params = None
    best_metrics = baseline_metrics
    best_spec = strategy_spec

    for params in param_combinations:
        # 应用参数
        new_spec = apply_params_to_spec(strategy_spec, params)

        # 选股
        screening_result = run_intelligent_screening(new_spec)
        if not screening_result.candidates:
            continue

        # 回测
        metrics = run_in_sample_out_sample_backtest(
            new_spec,
            screening_result.candidates
        )

        # 计算得分
        score = calculate_objective_score(flatten_evaluation_metrics(metrics), config.objective)

        # 更新最优
        if score > best_score:
            best_score = score
            best_params = params
            best_metrics = metrics
            best_spec = new_spec

    # 5. 生成优化结果
    if best_params is None:
        # 没有找到更优的参数
        return OptimizationResult(
            strategy_id=strategy_spec.id or "unknown",
            from_version=strategy_spec.version,
            to_version=strategy_spec.version,
            objective=config.objective,
            search_method=config.search_method,
            trials_count=len(param_combinations),
            metrics_before=baseline_metrics,
            metrics_after=baseline_metrics,
            decision="rejected",
            decision_reason="未找到更优参数组合"
        )

    # 6. 记录变更
    changes = []
    for path, new_value in best_params.items():
        # 找到原始值
        old_value = None
        param_name = path
        for r in config.param_ranges:
            if r.param_path == path:
                old_value = r.current_value
                param_name = r.param_name
                break

        changes.append(OptimizationChange(
            param_path=path,
            param_name=param_name,
            from_value=old_value,
            to_value=new_value
        ))

    # 7. 做出决策
    decision, reason, improvement = make_optimization_decision(
        baseline_score_metrics,
        flatten_evaluation_metrics(best_metrics),
        config.objective
    )

    # 8. 生成新版本号
    current_version = strategy_spec.version
    version_parts = current_version.split('.')
    if len(version_parts) == 3:
        new_version = f"{version_parts[0]}.{int(version_parts[1]) + 1}.0"
    else:
        new_version = "1.1.0"
    candidate_spec = best_spec.model_dump(mode="json")
    candidate_spec["version"] = new_version
    candidate_spec["source"] = "optimized"
    candidate_spec["status"] = "validated" if decision in {"promoted", "candidate"} else "watch"
    candidate_spec["updated_at"] = datetime.now().isoformat()

    return OptimizationResult(
        strategy_id=strategy_spec.id or "unknown",
        from_version=current_version,
        to_version=new_version,
        objective=config.objective,
        search_method=config.search_method,
        trials_count=len(param_combinations),
        changes=changes,
        reason=f"通过{config.search_method}搜索优化{config.objective}指标",
        metrics_before=baseline_metrics,
        metrics_after=best_metrics,
        improvement=improvement,
        decision=decision,
        decision_reason=reason,
        candidate_spec=candidate_spec
    )
