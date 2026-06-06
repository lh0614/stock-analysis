"""测试智能选股功能"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.models.strategy_spec import StrategySpec, ConditionSpec, RankingSpec
from app.services.intelligent_screener import run_intelligent_screening

# 测试策略：放量突破回踩策略
strategy = StrategySpec(
    name="放量突破回踩策略",
    description="寻找突破20日新高、放量、回踩MA20不破的股票",
    horizon="medium",
    entry_conditions=[
        ConditionSpec(factor="breakout_20d_high", op="eq", value=True, weight=1.0),
        ConditionSpec(factor="volume_ratio_5_20", op="gt", value=1.3, weight=0.8),
        ConditionSpec(factor="close_above_ma20", op="eq", value=True, weight=1.0),
    ],
    ranking=[
        RankingSpec(factor="return_20d", direction="desc", weight=0.6),
        RankingSpec(factor="volume_ratio_5_20", direction="desc", weight=0.4),
    ],
)

print("=" * 60)
print(f"策略名称: {strategy.name}")
print(f"投资周期: {strategy.horizon}")
print(f"筛选条件数: {len(strategy.entry_conditions)}")
print(f"排序规则数: {len(strategy.ranking)}")
print("=" * 60)

# 执行选股
result = run_intelligent_screening(strategy)

print(f"\n选股结果:")
print(f"- 扫描股票数: {result.total_scanned}")
print(f"- 命中股票数: {result.total_matched}")
print(f"- 执行耗时: {result.execution_time_ms:.0f}ms")
print(f"\n候选股列表:")
print("-" * 80)

for candidate in result.candidates[:10]:  # 只显示前10只
    print(f"排名 {candidate.rank:2d} | {candidate.symbol} {candidate.name:8s} | "
          f"得分: {candidate.score:5.1f} | 质量: {candidate.quality_level} | "
          f"命中条件数: {len(candidate.matched_conditions)}")

    # 显示命中的条件
    for cond in candidate.matched_conditions:
        print(f"         └─ {cond['factor']}: {cond['value']}")

print("-" * 80)
print(f"\n完成！共返回 {len(result.candidates)} 只候选股")
