"""交易计划 CRUD 与草稿生成。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from app.core.db import get_conn, init_db


STATUSES = ("draft", "watching", "triggered", "opened", "closed", "cancelled")


def build_plan_draft(
    symbol: str,
    directions: dict[str, Any] | None,
    price_levels: dict[str, Any] | None,
    horizon: str = "medium",
) -> dict[str, Any]:
    close = 0.0
    if price_levels:
        close = float(price_levels.get("current") or price_levels.get("close") or 0)
    support = float((price_levels or {}).get("support") or close * 0.95)
    resistance = float((price_levels or {}).get("resistance") or close * 1.05)
    bias = (directions or {}).get(horizon, {}).get("bias", "neutral")
    trigger = resistance if bias in ("bullish", "偏多") else close
    invalid = support
    target1 = resistance * 1.03 if resistance else close * 1.05
    target2 = resistance * 1.06 if resistance else close * 1.08
    return {
        "symbol": symbol.zfill(6)[:6],
        "horizon": horizon,
        "trigger_price": round(trigger, 2),
        "invalid_price": round(invalid, 2),
        "target_price_1": round(target1, 2),
        "target_price_2": round(target2, 2),
        "max_position_pct": 0.2,
        "risk_reward_ratio": round((target1 - trigger) / max(trigger - invalid, 0.01), 2),
        "rationale": (directions or {}).get(horizon, {}).get("summary", ""),
        "risks": (directions or {}).get(horizon, {}).get("risks", []),
        "status": "draft",
    }


def create_plan(data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    plan_id = data.get("id") or str(uuid.uuid4())
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO trade_plans
            (id, symbol, horizon, trigger_price, invalid_price, target_price_1, target_price_2,
             max_position_pct, rationale_json, risks_json, status, source_run_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                data["symbol"],
                data.get("horizon", "medium"),
                data.get("trigger_price"),
                data.get("invalid_price"),
                data.get("target_price_1"),
                data.get("target_price_2"),
                data.get("max_position_pct", 0.2),
                json.dumps({"text": data.get("rationale", "")}, ensure_ascii=False),
                json.dumps(data.get("risks") or [], ensure_ascii=False),
                data.get("status", "draft"),
                data.get("source_run_id"),
                now,
                now,
            ),
        )
    return get_plan(plan_id)


def get_plan(plan_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM trade_plans WHERE id = ?", (plan_id,)).fetchone()
    if not row:
        return None
    return _row_to_plan(row)


def list_plans(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM trade_plans WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trade_plans ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [_row_to_plan(r) for r in rows]


def update_plan(plan_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    plan = get_plan(plan_id)
    if not plan:
        return None
    fields = {
        "horizon": patch.get("horizon", plan["horizon"]),
        "trigger_price": patch.get("trigger_price", plan["trigger_price"]),
        "invalid_price": patch.get("invalid_price", plan["invalid_price"]),
        "target_price_1": patch.get("target_price_1", plan["target_price_1"]),
        "target_price_2": patch.get("target_price_2", plan["target_price_2"]),
        "max_position_pct": patch.get("max_position_pct", plan["max_position_pct"]),
        "status": patch.get("status", plan["status"]),
    }
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE trade_plans SET horizon=?, trigger_price=?, invalid_price=?,
            target_price_1=?, target_price_2=?, max_position_pct=?, status=?, updated_at=?
            WHERE id=?
            """,
            (
                fields["horizon"],
                fields["trigger_price"],
                fields["invalid_price"],
                fields["target_price_1"],
                fields["target_price_2"],
                fields["max_position_pct"],
                fields["status"],
                now,
                plan_id,
            ),
        )
    return get_plan(plan_id)


def _row_to_plan(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "horizon": row["horizon"],
        "trigger_price": row["trigger_price"],
        "invalid_price": row["invalid_price"],
        "target_price_1": row["target_price_1"],
        "target_price_2": row["target_price_2"],
        "max_position_pct": row["max_position_pct"],
        "rationale": json.loads(row["rationale_json"] or "{}"),
        "risks": json.loads(row["risks_json"] or "[]"),
        "status": row["status"],
        "source_run_id": row["source_run_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
