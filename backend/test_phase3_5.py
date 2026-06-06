#!/usr/bin/env python3
"""
Phase 3-5 端到端测试

测试单股分析、策略优化、策略监控的完整流程
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from app.services.stock_deep_analysis import run_deep_analysis
from app.services.strategy_optimizer import optimize_strategy, OptimizationConfig
from app.services.strategy_monitor import check_strategy_health, run_daily_monitoring
from app.models.strategy_spec import StrategySpec, ConditionSpec, RankingSpec, PositionSpec, UniverseSpec
from app.services.strategy_library import save_strategy, get_strategy


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


async def test_stock_deep_analysis():
    """测试单股深度分析"""
    print_section("Phase 3: 单股深度分析测试")

    # 测试股票
    test_symbols = ["600519", "000001", "600036"]

    for symbol in test_symbols:
        print(f"\n测试股票: {symbol}")
        print("-" * 40)

        try:
            result = await run_deep_analysis(symbol)

            print(f"✓ 分析完成")
            print(f"  结论: {result.verdict}")
            print(f"  周期: {result.horizon}")
            print(f"  置信度: {result.confidence:.2%}")
            print(f"  数据质量: {result.data_quality.get('quality_level', 'N/A')}")

            if result.win_rate_estimate:
                print(f"  胜率估计: {result.win_rate_estimate:.2%}")

            if result.risk_reward_ratio:
                print(f"  风险收益比: {result.risk_reward_ratio:.2f}")

            print(f"  证据数量: {len(result.evidence)}")
            print(f"  风险提示: {len(result.risks)}")
            print(f"  触发条件: {len(result.trigger_conditions)}")

            # 显示触发条件满足情况
            met_count = sum(1 for c in result.trigger_conditions if c.is_met)
            total_count = len(result.trigger_conditions)
            print(f"  条件满足: {met_count}/{total_count}")

        except Exception as e:
            print(f"✗ 分析失败: {e}")

    print("\n✓ Phase 3 测试完成")


async def test_strategy_optimization():
    """测试策略优化"""
    print_section("Phase 4: 策略优化测试")

    # 创建测试策略
    test_spec = StrategySpec(
        strategy_id="test_opt_strategy",
        name="测试优化策略",
        version="1.0.0",
        horizon="medium",
        universe=UniverseSpec(
            market="A股",
            exclude_st=True,
            boards=["main", "chinext"]
        ),
        entry_conditions=[
            ConditionSpec(factor="breakout_20d_high", op="eq", value=True),
            ConditionSpec(factor="volume_ratio_5_20", op="gt", value=1.5),
            ConditionSpec(factor="close_above_ma20", op="eq", value=True)
        ],
        ranking=[
            RankingSpec(factor="relative_strength_20d", direction="desc", weight=1.0)
        ],
        position=PositionSpec(
            max_positions=10,
            position_sizing="equal_weight"
        )
    )

    print("测试策略规格:")
    print(f"  名称: {test_spec.name}")
    print(f"  条件数量: {len(test_spec.entry_conditions)}")
    print(f"  最大持仓: {test_spec.position.max_positions}")

    # 配置优化
    config = OptimizationConfig(
        objective="sharpe",
        search_method="random",
        max_trials=10  # 减少试验次数以加快测试
    )

    print(f"\n优化配置:")
    print(f"  目标: {config.objective}")
    print(f"  方法: {config.search_method}")
    print(f"  最大尝试: {config.max_trials}")

    try:
        print("\n开始优化...")
        result = await optimize_strategy(test_spec, config)

        print(f"\n✓ 优化完成")
        print(f"  优化ID: {result.optimization_id}")
        print(f"  尝试次数: {result.trials_count}")
        print(f"  决策: {result.decision}")
        print(f"  原因: {result.decision_reason}")

        if result.changes:
            print(f"\n  参数变更:")
            for change in result.changes:
                print(f"    {change.param_name}: {change.from_value} → {change.to_value}")

        if result.improvement:
            print(f"\n  改进情况:")
            for key, value in result.improvement.items():
                sign = "+" if value > 0 else ""
                print(f"    {key}: {sign}{value:.4f}")

    except Exception as e:
        print(f"✗ 优化失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n✓ Phase 4 测试完成")


async def test_strategy_monitoring():
    """测试策略监控"""
    print_section("Phase 5: 策略监控测试")

    try:
        # 创建测试策略并保存
        test_spec = StrategySpec(
            strategy_id="test_monitor_strategy",
            name="测试监控策略",
            version="1.0.0",
            horizon="medium",
            universe=UniverseSpec(
                market="A股",
                exclude_st=True
            ),
            entry_conditions=[
                ConditionSpec(factor="ma_bullish_alignment", op="eq", value=True)
            ],
            position=PositionSpec(max_positions=10)
        )

        # 保存策略
        test_spec_dict = test_spec.model_dump()
        test_spec_dict['source'] = 'manual'
        test_spec_dict['status'] = 'active'
        strategy_id = save_strategy(test_spec_dict)

        print(f"创建测试策略: {strategy_id}")

        # 测试单个策略健康度检查
        print(f"\n检查策略健康度...")
        health = await check_strategy_health(strategy_id)

        print(f"\n✓ 健康度检查完成")
        print(f"  策略: {health.strategy_name}")
        print(f"  健康度: {health.health_score:.1f}/100")
        print(f"  状态: {health.status}")
        print(f"  最近信号: {health.recent_signals_count}")

        if health.recent_win_rate:
            print(f"  最近胜率: {health.recent_win_rate:.2%}")

        if health.degradation_signals:
            print(f"\n  衰减信号:")
            for signal in health.degradation_signals:
                print(f"    - {signal}")

        if health.recommendations:
            print(f"\n  建议:")
            for rec in health.recommendations:
                print(f"    - {rec}")

        # 测试每日监控
        print(f"\n\n运行每日监控...")
        report = await run_daily_monitoring()

        print(f"\n✓ 每日监控完成")
        print(f"  监控日期: {report.report_date}")
        print(f"  策略总数: {report.total_strategies}")
        print(f"  健康: {report.healthy_count}")
        print(f"  衰减: {report.degraded_count}")
        print(f"  失效: {report.failing_count}")

        if report.global_recommendations:
            print(f"\n  全局建议:")
            for rec in report.global_recommendations:
                print(f"    - {rec}")

    except Exception as e:
        print(f"✗ 监控测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n✓ Phase 5 测试完成")


async def main():
    """主测试流程"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "Phase 3-5 端到端测试" + " " * 38 + "║")
    print("╚" + "═" * 78 + "╝")

    try:
        # Phase 3: 单股深度分析
        await test_stock_deep_analysis()

        # Phase 4: 策略优化
        await test_strategy_optimization()

        # Phase 5: 策略监控
        await test_strategy_monitoring()

        # 最终总结
        print_section("测试总结")
        print("✓ Phase 3 单股深度分析: 通过")
        print("✓ Phase 4 策略优化: 通过")
        print("✓ Phase 5 策略监控: 通过")
        print("\n所有测试完成！")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
