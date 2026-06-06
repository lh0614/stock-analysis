"""模拟成交与组合统计。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.core.db import get_conn, init_db


def add_trade(data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    tid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO simulated_trades
            (id, plan_id, symbol, side, price, quantity, fee, traded_at, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tid,
                data.get("plan_id"),
                data["symbol"],
                data["side"],
                data["price"],
                data.get("quantity", 100),
                data.get("fee", 0),
                data.get("traded_at", now),
                data.get("note", ""),
            ),
        )
    return get_trade(tid)


def get_trade(trade_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM simulated_trades WHERE id = ?", (trade_id,)).fetchone()
    return dict(row) if row else None


def list_trades(plan_id: str | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if plan_id:
            rows = conn.execute(
                "SELECT * FROM simulated_trades WHERE plan_id = ? ORDER BY traded_at",
                (plan_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM simulated_trades ORDER BY traded_at DESC LIMIT 500"
            ).fetchall()
    return [dict(r) for r in rows]


def portfolio_summary() -> dict[str, Any]:
    trades = list_trades()
    positions: dict[str, dict] = {}
    realized = 0.0
    for t in trades:
        sym = t["symbol"]
        qty = float(t["quantity"] or 0)
        price = float(t["price"] or 0)
        if t["side"] == "buy":
            pos = positions.setdefault(sym, {"qty": 0.0, "cost": 0.0})
            pos["cost"] = (pos["cost"] * pos["qty"] + price * qty) / (pos["qty"] + qty) if pos["qty"] + qty else price
            pos["qty"] += qty
        elif t["side"] == "sell" and sym in positions:
            pos = positions[sym]
            realized += (price - pos["cost"]) * min(qty, pos["qty"])
            pos["qty"] = max(0, pos["qty"] - qty)
    holdings = [
        {"symbol": s, "quantity": p["qty"], "avg_cost": round(p["cost"], 2)}
        for s, p in positions.items()
        if p["qty"] > 0
    ]
    return {"holdings": holdings, "realized_pnl": round(realized, 2), "trade_count": len(trades)}
