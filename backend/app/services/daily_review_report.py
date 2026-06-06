"""每日复盘报告与导出（M14）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.db import get_conn
from app.services.reviews import get_stats


def build_daily_review_report() -> dict[str, Any]:
    with get_conn() as conn:
        plans = conn.execute(
            "SELECT id, symbol, status FROM trade_plans ORDER BY updated_at DESC LIMIT 20"
        ).fetchall()
        alerts = conn.execute(
            "SELECT id, symbol, name, last_triggered_at FROM alerts WHERE enabled = 1 LIMIT 20"
        ).fetchall()
        watchlist = conn.execute("SELECT symbol, name FROM watchlist_items LIMIT 50").fetchall()
    return {
        "generated_at": datetime.now().isoformat(),
        "watchlist": [dict(r) for r in watchlist],
        "active_plans": [dict(r) for r in plans],
        "alerts": [dict(r) for r in alerts],
        "review_stats": get_stats(),
    }


def export_analysis_markdown(run: dict[str, Any]) -> str:
    lines = [
        f"# 分析报告 {run.get('symbol')}",
        "",
        f"**免责声明**：{run.get('disclaimer', '')}",
        "",
    ]
    q = run.get("quality") or {}
    lines.append(f"## 数据质量\n- 等级：{q.get('quality_level', 'N/A')}\n- 问题：{', '.join(q.get('issues') or [])}\n")
    m = run.get("market") or {}
    lines.append(f"## 市场环境\n- 状态：{m.get('market_regime', 'N/A')}\n- {m.get('summary', '')}\n")
    for h in ("short", "medium", "long"):
        d = (run.get("directions") or {}).get(h) or {}
        lines.append(f"## {h} 方向\n- 判断：{d.get('bias')}\n- {d.get('summary', '')}\n")
    plan = run.get("plan_draft") or {}
    if plan:
        lines.append(
            f"## 计划草稿\n- 触发：{plan.get('trigger_price')}\n- 失效：{plan.get('invalid_price')}\n- 目标：{plan.get('target_price_1')}\n"
        )
    return "\n".join(lines)
