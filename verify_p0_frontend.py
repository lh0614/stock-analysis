#!/usr/bin/env python3
"""
P0 前端完成度验证脚本
"""
import os
import sys

def check_file_exists(path, description):
    """检查文件是否存在"""
    if os.path.exists(path):
        print(f"✅ {description}: {path}")
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
                print(f"❌ {description}: 未找到 '{pattern}'")
                return False
    except Exception as e:
        print(f"❌ {description}: 读取失败 - {e}")
        return False

def main():
    print("=" * 60)
    print("P0 前端完成度验证")
    print("=" * 60)
    print()

    base_path = "/Users/liuhan/Documents/AI/local-stock-analysis"
    checks = []

    print("【1. 组件文件检查】")
    checks.append(check_file_exists(
        f"{base_path}/frontend/src/components/StrategyCycleStatus.vue",
        "策略闭环状态组件"
    ))
    checks.append(check_file_exists(
        f"{base_path}/frontend/src/components/HealthScoreDetail.vue",
        "健康度详情组件"
    ))
    checks.append(check_file_exists(
        f"{base_path}/frontend/src/components/DataQualityCard.vue",
        "数据质量卡片组件"
    ))
    checks.append(check_file_exists(
        f"{base_path}/frontend/src/views/SystemStatusView.vue",
        "系统状态视图"
    ))
    print()

    print("【2. 组件集成检查】")
    checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/StrategyLibraryView.vue",
        "import HealthScoreDetail from '@/components/HealthScoreDetail.vue'",
        "StrategyLibraryView 导入 HealthScoreDetail"
    ))
    checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/StrategyLibraryView.vue",
        "<HealthScoreDetail :health=\"currentHealth\" />",
        "StrategyLibraryView 使用 HealthScoreDetail"
    ))
    checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/SystemStatusView.vue",
        "import StrategyCycleStatus from '@/components/StrategyCycleStatus.vue'",
        "SystemStatusView 导入 StrategyCycleStatus"
    ))
    print()

    print("【3. 路由配置检查】")
    checks.append(check_file_contains(
        f"{base_path}/frontend/src/router/index.js",
        "system-status",
        "路由包含 system-status"
    ))
    checks.append(check_file_contains(
        f"{base_path}/frontend/src/router/index.js",
        "SystemStatusView",
        "路由引用 SystemStatusView"
    ))
    print()

    print("【4. 菜单配置检查】")
    checks.append(check_file_contains(
        f"{base_path}/frontend/src/config/menu.js",
        "{ index: '/system-status', title: '系统状态', route: '/system-status' }",
        "菜单包含系统状态入口"
    ))
    checks.append(check_file_contains(
        f"{base_path}/frontend/src/config/menu.js",
        "'/system-status': {",
        "菜单 meta 包含系统状态"
    ))
    print()

    print("【5. API 端点检查】")
    checks.append(check_file_contains(
        f"{base_path}/frontend/src/components/StrategyCycleStatus.vue",
        "/api/v1/strategy-cycle/status",
        "StrategyCycleStatus 调用状态 API"
    ))
    checks.append(check_file_contains(
        f"{base_path}/frontend/src/components/StrategyCycleStatus.vue",
        "/api/v1/strategy-cycle/trigger",
        "StrategyCycleStatus 调用触发 API"
    ))
    checks.append(check_file_contains(
        f"{base_path}/frontend/src/views/SystemStatusView.vue",
        "/api/v1/strategy-library/stats",
        "SystemStatusView 调用统计 API"
    ))
    print()

    print("=" * 60)
    passed = sum(checks)
    total = len(checks)
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"总计: {passed}/{total} 项检查通过 ({percentage:.1f}%)")
    print("=" * 60)
    print()

    if passed == total:
        print("🎉 P0 前端任务 100% 完成！")
        print()
        print("已完成的功能:")
        print("  ✅ 策略闭环状态组件 (StrategyCycleStatus.vue)")
        print("  ✅ 健康度详情组件 (HealthScoreDetail.vue)")
        print("  ✅ 数据质量卡片组件 (DataQualityCard.vue)")
        print("  ✅ 系统状态视图 (SystemStatusView.vue)")
        print("  ✅ StrategyLibraryView 集成新组件")
        print("  ✅ 路由和菜单配置")
        print()
        return 0
    else:
        print(f"⚠️  还有 {total - passed} 项未完成")
        return 1

if __name__ == "__main__":
    sys.exit(main())
