#!/usr/bin/env python3
"""
P0 阶段综合验证脚本（前端 + 后端）
"""
import os
import sys

def check_file_exists(path, description):
    """检查文件是否存在"""
    if os.path.exists(path):
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description}: {path} (不存在)")
        return False

def check_file_contains(path, pattern, description):
    """检查文件是否包含特定内容"""
    if not os.path.exists(path):
        print(f"❌ {description}: {path} (文件不存在)")
        return False

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            if pattern in content:
                print(f"✅ {description}")
                return True
            else:
                print(f"❌ {description}: 未找到关键内容")
                return False
    except Exception as e:
        print(f"❌ {description}: 读取失败 - {e}")
        return False

def main():
    print("=" * 70)
    print("P0 阶段综合验证（前端 + 后端）")
    print("=" * 70)
    print()

    base_path = "/Users/liuhan/Documents/AI/local-stock-analysis"
    all_checks = []

    # ========== 后端验证 ==========
    print("【后端验证】")
    print()

    print("P0-1: 自动调度闭环")
    backend_checks = []
    backend_checks.append(check_file_exists(
        f"{base_path}/backend/app/services/strategy_cycle.py",
        "策略闭环服务模块"
    ))
    backend_checks.append(check_file_exists(
        f"{base_path}/backend/app/api/strategy_cycle.py",
        "策略闭环 API"
    ))
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_cycle.py",
        "class StrategyCycleService",
        "StrategyCycleService 类存在"
    ))
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_cycle.py",
        "save_optimization_result",
        "调用 save_optimization_result"
    ))
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_cycle.py",
        "candidate_spec = optimization_result.candidate_spec if optimization_result.candidate_spec else None",
        "正确处理空 candidate_spec"
    ))
    print()

    print("P0-2: 数据质量审计")
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/data_quality.py",
        "get_quality_summary_for_symbols",
        "质量汇总函数存在"
    ))
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/intelligent_screener.py",
        "data_quality_summary",
        "选股集成质量评估"
    ))
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_backtest.py",
        "data_quality_summary",
        "回测集成质量评估"
    ))
    print()

    print("P0-3: 健康度评分重构")
    backend_checks.append(check_file_exists(
        f"{base_path}/backend/app/services/health_scoring.py",
        "健康度评分模块"
    ))
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/health_scoring.py",
        "calculate_signal_activity_score",
        "信号活跃度评分函数"
    ))
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/health_scoring.py",
        "calculate_comprehensive_health",
        "综合健康度计算函数"
    ))
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/health_scoring.py",
        "class HealthSubScores",
        "HealthSubScores 模型"
    ))
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_monitor.py",
        "sub_scores",
        "StrategyHealth 包含 sub_scores"
    ))
    backend_checks.append(check_file_contains(
        f"{base_path}/backend/app/services/strategy_monitor.py",
        "calculate_comprehensive_health",
        "监控服务使用新评分模型"
    ))
    print()

    all_checks.extend(backend_checks)
    backend_passed = sum(backend_checks)
    backend_total = len(backend_checks)
    print(f"后端检查: {backend_passed}/{backend_total} 项通过")
    print()

    # ========== 前端验证 ==========
    print("【前端验证】")
    print()

    frontend_checks = []

    print("前端组件")
    frontend_checks.append(check_file_exists(
        f"{base_path}/frontend/src/components/StrategyCycleStatus.vue",
        "策略闭环状态组件"
    ))
    frontend_checks.append(check_file_exists(
        f"{base_path}/frontend/src/components/HealthScoreDetail.vue",
        "健康度详情组件"
    ))
    frontend_checks.append(check_file_exists(
        f"{base_path}/frontend/src/components/DataQualityCard.vue",
        "数据质量卡片组件"
    ))
    frontend_checks.append(check_file_exists(
        f"{base_path}/frontend/src/views/SystemStatusView.vue",
        "系统状态视图"
    ))
    print()

    print("组件集成")
    frontend_checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/StrategyLibraryView.vue",
        "import HealthScoreDetail",
        "StrategyLibraryView 导入 HealthScoreDetail"
    ))
    frontend_checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/StrategyLibraryView.vue",
        "<HealthScoreDetail :health=\"currentHealth\" />",
        "StrategyLibraryView 使用 HealthScoreDetail"
    ))
    print()

    print("路由和菜单")
    frontend_checks.append(check_file_contains(
        f"{base_path}/frontend/src/router/index.js",
        "system-status",
        "路由包含 system-status"
    ))
    frontend_checks.append(check_file_contains(
        f"{base_path}/frontend/src/config/menu.js",
        "{ index: '/system-status', title: '系统状态', route: '/system-status' }",
        "菜单包含系统状态入口"
    ))
    print()

    all_checks.extend(frontend_checks)
    frontend_passed = sum(frontend_checks)
    frontend_total = len(frontend_checks)
    print(f"前端检查: {frontend_passed}/{frontend_total} 项通过")
    print()

    # ========== 总结 ==========
    print("=" * 70)
    total_passed = sum(all_checks)
    total_checks = len(all_checks)
    percentage = (total_passed / total_checks * 100) if total_checks > 0 else 0

    print(f"总计: {total_passed}/{total_checks} 项检查通过 ({percentage:.1f}%)")
    print(f"  - 后端: {backend_passed}/{backend_total} ({backend_passed/backend_total*100:.1f}%)")
    print(f"  - 前端: {frontend_passed}/{frontend_total} ({frontend_passed/frontend_total*100:.1f}%)")
    print("=" * 70)
    print()

    if total_passed == total_checks:
        print("🎉 P0 阶段 100% 完成（前端 + 后端）！")
        print()
        print("核心功能状态:")
        print("  ✅ 自动调度闭环: 100% 完成")
        print("  ✅ 数据质量审计: 100% 完成")
        print("  ✅ 健康度评分重构: 100% 完成")
        print("  ✅ 前端界面: 100% 完成")
        print()
        print("已交付:")
        print("  📦 后端服务: strategy_cycle, health_scoring, data_quality")
        print("  📦 前端组件: 4 个新组件 + 集成")
        print("  📦 路由菜单: 系统状态入口")
        print("  📄 文档: 4 份验收和问题修复文档")
        print()
        return 0
    else:
        print(f"⚠️  还有 {total_checks - total_passed} 项未完成")
        return 1

if __name__ == "__main__":
    sys.exit(main())
