"""系统功能演示 - 创建一个评级为 B 或 A 的策略"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.models.strategy_spec import StrategySpec, ConditionSpec, RankingSpec
from app.services.intelligent_screener import run_intelligent_screening
from app.services.strategy_backtest import run_in_sample_out_sample_backtest
from app.services.strategy_rating import rate_strategy
from app.services.strategy_library import save_strategy, update_strategy_status, save_evaluation

print("=" * 80)
print("智能选股与策略自进化系统 - 功能演示")
print("=" * 80)
print()

# 创建一个简单但更合理的策略
print("📊 创建演示策略...")
strategy = StrategySpec(
    name="均线多头策略",
    description="寻找收盘价站上MA20且量比适中的股票",
    horizon="medium",
    intent_text="找收盘价高于MA20、量比在正常范围的股票",
    entry_conditions=[
        ConditionSpec(factor="close_above_ma20", op="eq", value=True, weight=1.0),
    ],
    ranking=[
        RankingSpec(factor="return_20d", direction="desc", weight=0.7),
        RankingSpec(factor="volume_ratio_5_20", direction="desc", weight=0.3),
    ],
)

print(f"✓ 策略: {strategy.name}")
print(f"  说明: {strategy.description}")
print()

# 执行选股
print("🔍 执行智能选股...")
screener_result = run_intelligent_screening(strategy)
print(f"✓ 扫描 {screener_result.total_scanned} 只，命中 {screener_result.total_matched} 只")
print()

if screener_result.total_matched == 0:
    print("❌ 未找到符合条件的股票，演示结束")
    sys.exit(0)

# 显示候选股
print(f"📋 候选股列表（前5名）:")
for candidate in screener_result.candidates[:5]:
    print(f"  {candidate.rank}. {candidate.symbol} {candidate.name:8s} - 得分: {candidate.score:5.1f} - 质量: {candidate.quality_level}")
print()

# 执行回测
print("⏱️  执行样本内外回测...")
candidates_dict = [c.model_dump() for c in screener_result.candidates]
backtest_result = run_in_sample_out_sample_backtest(strategy, candidates_dict)

print()
print("📈 回测结果:")
print("-" * 80)

# 样本内
in_m = backtest_result["in_sample"]["metrics"]
print(f"样本内表现:")
print(f"  年化收益: {in_m['annual_return']:7.2%} | 最大回撤: {in_m['max_drawdown']:7.2%}")
print(f"  夏普比率: {in_m['sharpe_ratio']:7.2f} | 胜率: {in_m['win_rate']:7.1%}")
print(f"  盈亏比: {in_m['profit_loss_ratio']:7.2f} | 交易次数: {in_m['total_trades']}")

print()

# 样本外
out_m = backtest_result["out_sample"]["metrics"]
print(f"样本外表现:")
print(f"  年化收益: {out_m['annual_return']:7.2%} | 最大回撤: {out_m['max_drawdown']:7.2%}")
print(f"  夏普比率: {out_m['sharpe_ratio']:7.2f} | 胜率: {out_m['win_rate']:7.1%}")
print(f"  盈亏比: {out_m['profit_loss_ratio']:7.2f} | 交易次数: {out_m['total_trades']}")

if backtest_result["overfit_flag"]:
    print(f"\n⚠️  过拟合警告: {backtest_result['overfit_reason']}")

print("-" * 80)
print()

# 策略评级
print("🏆 策略评级...")
rating_result = rate_strategy(
    backtest_result["in_sample"]["metrics"],
    backtest_result["out_sample"]["metrics"],
    backtest_result["overfit_flag"]
)

rating_emoji = {"A": "🥇", "B": "🥈", "C": "🥉", "D": "❌"}
print(f"{rating_emoji.get(rating_result['rating'], '❓')} 评级: {rating_result['rating']}")
print(f"  原因: {rating_result['reason']}")
print(f"  建议: {rating_result['recommendation']}")
print()

# 保存策略
if rating_result["rating"] in ["A", "B", "C"]:
    print("💾 保存策略到库...")
    strategy_dict = strategy.model_dump()
    strategy_dict["status"] = "backtested"
    strategy_dict["rating"] = rating_result["rating"]

    strategy_id = save_strategy(strategy_dict)
    print(f"✓ 策略已保存: {strategy_id}")

    # 保存评估
    eval_id = save_evaluation(
        strategy_id,
        "in_out_sample",
        {
            "in_sample": backtest_result["in_sample"]["metrics"],
            "out_sample": backtest_result["out_sample"]["metrics"],
        },
        rating_result["rating"],
        backtest_result["overfit_flag"]
    )
    print(f"✓ 评估结果已保存: {eval_id}")

    # 如果是 A/B 级，设为已验证
    if rating_result["rating"] in ["A", "B"]:
        update_strategy_status(strategy_id, "validated", rating_result["rating"])
        print(f"✓ 策略状态: validated")
else:
    print("⚠️  策略评级为 D，不予保存")

print()
print("=" * 80)
print("演示完成！")
print("=" * 80)
print()
print("📌 下一步:")
print("  1. 访问策略库查看已保存的策略")
print("  2. 访问智能选股页面创建新策略")
print("  3. 使用 ./start.sh 启动完整系统")
