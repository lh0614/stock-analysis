"""完整 P1 能力验收：覆盖非 P0 的策略研究、数据、组合、复盘、报告、告警入口。"""
from __future__ import annotations

import csv
import io
import os
import sys
import atexit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.core.db import get_conn, init_db
from app.models.strategy_spec import ConditionSpec, RankingSpec, StrategySpec
from app.services.alerts import get_alert_service
from app.services.factors import get_factor_catalog
from app.services.fundamentals_sync import get_fundamental_summary
from app.services.intelligent_screener import explain_symbol_against_strategy
from app.services.portfolio_sim import import_trades_csv, portfolio_summary
from app.services.reviews import create_review, get_stats
from app.services.strategy_research import (
    market_state_backtest_analysis,
    parameter_sensitivity_analysis,
    rolling_backtest_analysis,
    validate_strategy_spec,
)


checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, ok, detail))
    print(("✅" if ok else "❌"), name, detail)


def make_spec() -> StrategySpec:
    return StrategySpec(
        name="P1验收策略",
        entry_conditions=[
            ConditionSpec(factor="return_20d", op="gt", value=-1, weight=1.0),
            ConditionSpec(factor="rsi12", op="lt", value=90, weight=0.6),
        ],
        ranking=[
            RankingSpec(factor="return_20d", direction="desc", weight=0.6),
            RankingSpec(factor="volume_ratio_5_20", direction="desc", weight=0.4),
        ],
    )


init_db()


def cleanup_verify_rows() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM reviews WHERE plan_id = ?", ("p1_verify",))
        conn.execute("DELETE FROM simulated_trades WHERE plan_id = ?", ("p1_verify",))


cleanup_verify_rows()
atexit.register(cleanup_verify_rows)

with get_conn() as conn:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(alerts)").fetchall()}
check("告警表支持 payload_json", "payload_json" in cols)

rules = {item["id"] for item in get_alert_service().rule_types()}
check("告警规则支持组合/质量/策略命中", {"composite", "quality_d", "screener_hit"}.issubset(rules))

alert = get_alert_service().create(
    {
        "symbol": "000001",
        "name": "P1组合告警验收",
        "rule_type": "composite",
        "threshold": 1,
        "payload": {"rsi_threshold": 30, "min_quality": "C"},
        "enabled": False,
    }
)
check("组合告警可创建并保存 payload", alert.get("payload", {}).get("min_quality") == "C")
get_alert_service().delete(alert["id"])

catalog = get_factor_catalog()
check("因子目录包含公式口径", bool(catalog and catalog[0].get("formula") is not None))

spec = make_spec()
validation = validate_strategy_spec(spec)
check("策略规格仍可执行校验", validation["valid"])

explain = explain_symbol_against_strategy("000001", spec)
check("选股未命中原因解释接口可返回结构", {"matched", "failed_conditions", "factor_values"}.issubset(explain.keys()))

summary = get_fundamental_summary("000001")
check("基本面查询明确数据可用状态", "data_available" in summary and "fundamentals" in summary and "valuation" in summary)

csv_buf = io.StringIO()
writer = csv.DictWriter(csv_buf, fieldnames=["plan_id", "symbol", "side", "price", "quantity", "fee", "note"])
writer.writeheader()
writer.writerow({"plan_id": "p1_verify", "symbol": "000001", "side": "buy", "price": "10", "quantity": "100", "fee": "1", "note": "p1_verify"})
writer.writerow({"plan_id": "p1_verify", "symbol": "000001", "side": "sell", "price": "11", "quantity": "50", "fee": "1", "note": "p1_verify"})
import_result = import_trades_csv(csv_buf.getvalue())
port = portfolio_summary()
check("模拟组合支持 CSV 导入", import_result["imported"] == 2)
check("模拟组合输出扩展统计", {"realized_pnl", "unrealized_pnl", "total_pnl", "win_rate"}.issubset(port.keys()))

review = create_review(
    {
        "plan_id": "p1_verify",
        "pnl": -100,
        "pnl_pct": -0.05,
        "tags": ["late_stop_loss", "ignored_market_regime"],
        "lesson": "P1验收",
    }
)
stats = get_stats()
check("复盘统计可反馈策略修正建议", bool(stats.get("strategy_revision_suggestions")))

rolling = rolling_backtest_analysis(spec, window_days=180, step_days=180)
check("滚动回测分析接口返回稳定性结构", "stability" in rolling and "windows" in rolling)

sensitivity = parameter_sensitivity_analysis(spec, factor="return_20d", multipliers=[0.9, 1.0])
check("参数敏感性分析接口返回结果结构", "rows" in sensitivity)

market_split = market_state_backtest_analysis(spec)
check("市场状态拆分回测接口返回结果结构", "states" in market_split)

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n完整 P1 验收: {passed}/{total} ({passed / total * 100:.1f}%)")
if passed != total:
    raise SystemExit(1)
