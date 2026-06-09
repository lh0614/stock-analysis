#!/usr/bin/env python3
"""
P1 阶段完成度验证脚本
检查策略研发能力增强相关功能
"""
import os
import sys

def check_file_exists(path, description):
    """检查文件是否存在"""
    if os.path.exists(path):
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description}: 不存在")
        return False

def check_file_contains(path, pattern, description):
    """检查文件是否包含特定内容"""
    if not os.path.exists(path):
        print(f"❌ {description}: 文件不存在")
        return False

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            if pattern in content:
                print(f"✅ {description}")
                return True
            else:
                print(f"❌ {description}: 未找到")
                return False
    except Exception as e:
        print(f"❌ {description}: 读取失败 - {e}")
        return False

def main():
    print("=" * 70)
    print("P1 阶段完成度验证 - 策略研发能力增强")
    print("=" * 70)
    print()

    base_path = "/Users/liuhan/Documents/AI/local-stock-analysis"
    all_checks = []

    # ========== P1-1: DeepSeek 策略生成增强 ==========
    print("【P1-1: DeepSeek 策略生成增强】")
    p1_1_checks = []

    p1_1_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/intents.py",
        "generate-strategies",
        "策略生成 API 端点"
    ))

    p1_1_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/intent_parser.py",
        "generate_strategies",
        "策略生成服务函数"
    ))

    p1_1_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/intent_parser.py",
        "clarify",
        "澄清问题机制"
    ))

    p1_1_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/intent_parser.py",
        "validate_spec",
        "规格验证函数"
    ))

    print()
    all_checks.extend(p1_1_checks)
    p1_1_passed = sum(p1_1_checks)
    p1_1_total = len(p1_1_checks)
    print(f"P1-1 检查: {p1_1_passed}/{p1_1_total} 项通过 ({p1_1_passed/p1_1_total*100:.0f}%)")
    print()

    # ========== P1-2: 策略批量回测与筛选 ==========
    print("【P1-2: 策略批量回测与筛选】")
    p1_2_checks = []

    p1_2_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_backtest.py",
        "batch_backtest",
        "批量回测函数"
    ))

    p1_2_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/backtest.py",
        "batch",
        "批量回测 API"
    ))

    p1_2_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_backtest.py",
        "ranking",
        "策略排行榜功能"
    ))

    p1_2_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_backtest.py",
        "filter_overfitting",
        "过拟合过滤"
    ))

    print()
    all_checks.extend(p1_2_checks)
    p1_2_passed = sum(p1_2_checks)
    p1_2_total = len(p1_2_checks)
    print(f"P1-2 检查: {p1_2_passed}/{p1_2_total} 项通过 ({p1_2_passed/p1_2_total*100:.0f}%)")
    print()

    # ========== P1-3: 策略版本对比增强 ==========
    print("【P1-3: 策略版本对比增强】")
    p1_3_checks = []

    p1_3_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/strategy_library.py",
        "compare",
        "版本对比 API"
    ))

    p1_3_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/strategy_library.py",
        "rollback",
        "版本回滚 API"
    ))

    p1_3_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_library.py",
        "compare_versions",
        "版本对比服务函数"
    ))

    p1_3_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_library.py",
        "rollback_version",
        "版本回滚服务函数"
    ))

    print()
    all_checks.extend(p1_3_checks)
    p1_3_passed = sum(p1_3_checks)
    p1_3_total = len(p1_3_checks)
    print(f"P1-3 检查: {p1_3_passed}/{p1_3_total} 项通过 ({p1_3_passed/p1_3_total*100:.0f}%)")
    print()

    # ========== 前端检查 ==========
    print("【P1 前端界面】")
    frontend_checks = []

    frontend_checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/IntelligentScreenerView.vue",
        "generate-strategies",
        "策略生成界面集成"
    ))

    frontend_checks.append(check_file_exists(
        f"{base_path}/frontend/src/views/BatchBacktestView.vue",
        "批量回测视图"
    ))

    frontend_checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/StrategyLibraryView.vue",
        "compare",
        "版本对比界面"
    ))

    frontend_checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/StrategyLibraryView.vue",
        "rollback",
        "版本回滚界面"
    ))

    print()
    all_checks.extend(frontend_checks)
    frontend_passed = sum(frontend_checks)
    frontend_total = len(frontend_checks)
    print(f"前端检查: {frontend_passed}/{frontend_total} 项通过 ({frontend_passed/frontend_total*100:.0f}%)")
    print()

    # ========== 总结 ==========
    print("=" * 70)
    total_passed = sum(all_checks)
    total_checks = len(all_checks)
    percentage = (total_passed / total_checks * 100) if total_checks > 0 else 0

    print(f"总计: {total_passed}/{total_checks} 项检查通过 ({percentage:.1f}%)")
    print(f"  - P1-1 DeepSeek 增强: {p1_1_passed}/{p1_1_total} ({p1_1_passed/p1_1_total*100:.0f}%)")
    print(f"  - P1-2 批量回测: {p1_2_passed}/{p1_2_total} ({p1_2_passed/p1_2_total*100:.0f}%)")
    print(f"  - P1-3 版本对比: {p1_3_passed}/{p1_3_total} ({p1_3_passed/p1_3_total*100:.0f}%)")
    print(f"  - 前端界面: {frontend_passed}/{frontend_total} ({frontend_passed/frontend_total*100:.0f}%)")
    print("=" * 70)
    print()

    if total_passed == total_checks:
        print("🎉 P1 阶段 100% 完成！")
        print()
        print("核心功能状态:")
        print("  ✅ DeepSeek 策略生成增强")
        print("  ✅ 策略批量回测与筛选")
        print("  ✅ 策略版本对比增强")
        print()
        return 0
    elif total_passed == 0:
        print("ℹ️  P1 阶段尚未开始")
        print()
        print("P1 阶段目标:")
        print("  🎯 DeepSeek 策略生成增强")
        print("     - 生成多个候选策略")
        print("     - 澄清问题机制")
        print("     - 规格验证")
        print()
        print("  🎯 策略批量回测与筛选")
        print("     - 批量回测多个策略")
        print("     - 策略排行榜")
        print("     - 过拟合检测")
        print()
        print("  🎯 策略版本对比增强")
        print("     - 版本详细对比")
        print("     - 版本回滚")
        print("     - 审计记录")
        print()
        return 1
    else:
        print(f"🚧 P1 阶段进行中 ({percentage:.1f}%)")
        print(f"   还有 {total_checks - total_passed} 项待完成")
        print()

        # 显示未完成的模块
        if p1_1_passed < p1_1_total:
            print(f"  ⚠️  P1-1 DeepSeek 增强: {p1_1_total - p1_1_passed} 项待完成")
        if p1_2_passed < p1_2_total:
            print(f"  ⚠️  P1-2 批量回测: {p1_2_total - p1_2_passed} 项待完成")
        if p1_3_passed < p1_3_total:
            print(f"  ⚠️  P1-3 版本对比: {p1_3_total - p1_3_passed} 项待完成")
        if frontend_passed < frontend_total:
            print(f"  ⚠️  前端界面: {frontend_total - frontend_passed} 项待完成")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
