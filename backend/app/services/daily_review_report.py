"""每日复盘报告与导出（M14）。"""
from __future__ import annotations

import json
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


def build_strategy_evaluation_report(limit: int = 50) -> dict[str, Any]:
    try:
        from app.services.strategy_library import init_strategy_library_tables

        init_strategy_library_tables()
        with get_conn() as conn:
            strategies = conn.execute(
                """
                SELECT id, name, status, rating, active_version, updated_at
                FROM strategy_specs
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            evaluations = conn.execute(
                """
                SELECT strategy_id, sample_type, metrics_json, rating, overfit_flag, created_at
                FROM strategy_evaluations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit * 3,),
            ).fetchall()
            optimizations = conn.execute(
                """
                SELECT strategy_id, objective, decision, status, metrics_before_json, metrics_after_json, created_at
                FROM strategy_optimizations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit * 2,),
            ).fetchall()
    except Exception:
        return {
            "generated_at": datetime.now().isoformat(),
            "strategies": [],
            "summary": {"total": 0, "active": 0, "overfit_evaluations": 0},
            "recommendations": ["策略库尚未初始化或暂无评估数据。"],
        }

    eval_by_strategy: dict[str, list[dict[str, Any]]] = {}
    overfit_count = 0
    for row in evaluations:
        item = dict(row)
        try:
            item["metrics"] = json.loads(item.pop("metrics_json") or "{}")
        except Exception:
            item["metrics"] = {}
        item["overfit_flag"] = bool(item.get("overfit_flag"))
        if item["overfit_flag"]:
            overfit_count += 1
        eval_by_strategy.setdefault(item["strategy_id"], []).append(item)

    opt_by_strategy: dict[str, list[dict[str, Any]]] = {}
    for row in optimizations:
        item = dict(row)
        for key in ("metrics_before_json", "metrics_after_json"):
            try:
                item[key.replace("_json", "")] = json.loads(item.pop(key) or "{}")
            except Exception:
                item[key.replace("_json", "")] = {}
        opt_by_strategy.setdefault(item["strategy_id"], []).append(item)

    strategy_rows = []
    recommendations = []
    for row in strategies:
        item = dict(row)
        latest_eval = (eval_by_strategy.get(item["id"]) or [None])[0]
        latest_opt = (opt_by_strategy.get(item["id"]) or [None])[0]
        item["latest_evaluation"] = latest_eval
        item["latest_optimization"] = latest_opt
        if latest_eval and latest_eval.get("overfit_flag"):
            recommendations.append(f"{item['name']} 疑似过拟合，建议降低参数复杂度并做滚动窗口复核。")
        if not latest_eval:
            recommendations.append(f"{item['name']} 缺少最新回测评估。")
        strategy_rows.append(item)

    status_breakdown: dict[str, int] = {}
    for item in strategy_rows:
        status = item.get("status") or "unknown"
        status_breakdown[status] = status_breakdown.get(status, 0) + 1
    return {
        "generated_at": datetime.now().isoformat(),
        "strategies": strategy_rows,
        "summary": {
            "total": len(strategy_rows),
            "active": status_breakdown.get("active", 0),
            "overfit_evaluations": overfit_count,
            "status_breakdown": status_breakdown,
        },
        "recommendations": recommendations[:20],
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
