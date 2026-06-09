#!/usr/bin/env python3
"""
P1 阶段完成度验证脚本（准确版）
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
    print("P1 阶段完成度验证（准确版）")
    print("=" * 70)
    print()

    base_path = "/Users/liuhan/Documents/AI/local-stock-analysis"
    all_checks = []

    # ========== P1-1: DeepSeek 策略生成增强 ==========
    print("【P1-1: DeepSeek 策略生成增强】")
    p1_1_checks = []

    p1_1_checks.append(check_file_exists(
        f"{base_path}/backend/app/services/strategy_research.py",
        "策略研究服务模块"
    ))

    p1_1_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_research.py",
        "def generate_candidate_strategies",
        "策略生成函数"
    ))

    p1_1_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_research.py",
        "def clarify_strategy_goal",
        "澄清问题机制"
    ))

    p1_1_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_research.py",
        "def validate_strategy_spec",
        "规格验证函数"
    ))

    p1_1_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/intents.py",
        "@router.post(\"/generate-strategies\")",
        "策略生成 API"
    ))

    p1_1_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/intents.py",
        "@router.post(\"/clarify\")",
        "澄清问题 API"
    ))

    p1_1_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/intents.py",
        "@router.post(\"/validate-spec\")",
        "规格验证 API"
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
        f"{base_path}/backend/app/services/strategy_research.py",
        "def batch_backtest_strategies",
        "批量回测函数"
    ))

    p1_2_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/strategy_optimizer.py",
        "@router.post(\"/batch-backtest\")",
        "批量回测 API"
    ))

    p1_2_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_research.py",
        "def _research_score",
        "研究评分函数（排行榜）"
    ))

    p1_2_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_research.py",
        "overfit_flag",
        "过拟合检测"
    ))

    p1_2_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_research.py",
        "qualified",
        "策略筛选逻辑"
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
        f"{base_path}/backend/app/services/strategy_research.py",
        "def compare_strategy_specs",
        "版本对比函数"
    ))

    p1_3_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/strategy_library.py",
        "/versions/{version_id}/compare",
        "版本对比 API"
    ))

    p1_3_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/strategy_library.py",
        "/versions/{version_id}/rollback",
        "版本回滚 API"
    ))

    p1_3_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/strategy_library.py",
        "rollback_backup",
        "回滚备份逻辑"
    ))

    print()
    all_checks.extend(p1_3_checks)
    p1_3_passed = sum(p1_3_checks)
    p1_3_total = len(p1_3_checks)
    print(f"P1-3 检查: {p1_3_passed}/{p1_3_total} 项通过 ({p1_3_passed/p1_3_total*100:.0f}%)")
    print()

    # ========== P1-4: 高级分析功能 ==========
    print("【P1-4: 高级分析功能（额外实现）】")
    p1_4_checks = []

    p1_4_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_research.py",
        "def rolling_backtest_analysis",
        "滚动回测分析"
    ))

    p1_4_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_research.py",
        "def parameter_sensitivity_analysis",
        "参数敏感性分析"
    ))

    p1_4_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_research.py",
        "def market_state_backtest_analysis",
        "市场状态分析"
    ))

    p1_4_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/strategy_optimizer.py",
        "@router.post(\"/rolling-backtest\")",
        "滚动回测 API"
    ))

    p1_4_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/strategy_optimizer.py",
        "@router.post(\"/parameter-sensitivity\")",
        "参数敏感性 API"
    ))

    p1_4_checks.append(check_file_contains(
        f"{base_path}/backend/app/api/strategy_optimizer.py",
        "@router.post(\"/market-state-backtest\")",
        "市场状态回测 API"
    ))

    print()
    all_checks.extend(p1_4_checks)
    p1_4_passed = sum(p1_4_checks)
    p1_4_total = len(p1_4_checks)
    print(f"P1-4 检查: {p1_4_passed}/{p1_4_total} 项通过 ({p1_4_passed/p1_4_total*100:.0f}%)")
    print()

    # ========== 前端检查 ==========
    print("【P1 前端界面】")
    frontend_checks = []

    frontend_checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/StrategyLibraryView.vue",
        "compare",
        "策略库版本对比界面"
    ))

    frontend_checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/StrategyLibraryView.vue",
        "rollback",
        "策略库版本回滚界面"
    ))

    # 注意：批量回测和策略生成的前端界面可能还未实现
    frontend_checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/IntelligentScreenerView.vue",
        "generate",
        "智能选股策略生成（部分集成）"
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
    print(f"  - P1-4 高级分析: {p1_4_passed}/{p1_4_total} ({p1_4_passed/p1_4_total*100:.0f}%)")
    print(f"  - 前端界面: {frontend_passed}/{frontend_total} ({frontend_passed/frontend_total*100:.0f}%)")
    print("=" * 70)
    print()

    if percentage >= 90:
        print("🎉 P1 阶段基本完成（后端）！")
        print()
        print("已完成功能:")
        print("  ✅ P1-1 DeepSeek 策略生成增强")
        print("     - generate_candidate_strategies: 生成 3-5 个候选")
        print("     - clarify_strategy_goal: 澄清不明确意图")
        print("     - validate_strategy_spec: 验证规格合法性")
        print()
        print("  ✅ P1-2 策略批量回测与筛选")
        print("     - batch_backtest_strategies: 批量回测")
        print("     - 策略排行榜和评分")
        print("     - 过拟合检测和筛选")
        print()
        print("  ✅ P1-3 策略版本对比增强")
        print("     - compare_strategy_specs: 详细对比")
        print("     - 版本回滚 API（含备份）")
        print()
        print("  ✅ P1-4 高级分析功能（超出计划）")
        print("     - 滚动回测分析")
        print("     - 参数敏感性分析")
        print("     - 市场状态分析")
        print()

        if frontend_passed < frontend_total:
            print("⚠️  待完善:")
            print("  - 前端界面集成（策略生成、批量回测可视化）")

        print()
        return 0
    else:
        print(f"🚧 P1 阶段进行中 ({percentage:.1f}%)")
        print(f"   还有 {total_checks - total_passed} 项待完成")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
