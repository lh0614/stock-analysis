"""模拟成交与组合统计。"""
from __future__ import annotations

import uuid
import csv
import io
from datetime import datetime
from typing import Any

from app.core.db import get_conn, init_db
from app.services.data_store import read_daily_bars


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
                data.get("traded_at") or now,
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
    trades = sorted(list_trades(), key=lambda item: item.get("traded_at") or "")
    positions: dict[str, dict] = {}
    realized = 0.0
    total_buy_amount = 0.0
    total_sell_amount = 0.0
    total_fee = 0.0
    closed_pnls: list[float] = []
    for t in trades:
        sym = t["symbol"]
        qty = float(t["quantity"] or 0)
        price = float(t["price"] or 0)
        fee = float(t.get("fee") or 0)
        total_fee += fee
        if t["side"] == "buy":
            pos = positions.setdefault(sym, {"qty": 0.0, "cost": 0.0})
            total_buy_amount += price * qty
            pos["cost"] = (pos["cost"] * pos["qty"] + price * qty + fee) / (pos["qty"] + qty) if pos["qty"] + qty else price
            pos["qty"] += qty
        elif t["side"] == "sell" and sym in positions:
            pos = positions[sym]
            sell_qty = min(qty, pos["qty"])
            total_sell_amount += price * sell_qty
            pnl = (price - pos["cost"]) * sell_qty - fee
            realized += pnl
            closed_pnls.append(pnl)
            pos["qty"] = max(0, pos["qty"] - qty)

    unrealized = 0.0
    holdings = [
        {
            "symbol": s,
            "quantity": p["qty"],
            "avg_cost": round(p["cost"], 2),
            "last_price": _last_price(s),
            "market_value": round((_last_price(s) or p["cost"]) * p["qty"], 2),
            "unrealized_pnl": round(((_last_price(s) or p["cost"]) - p["cost"]) * p["qty"], 2),
        }
        for s, p in positions.items()
        if p["qty"] > 0
    ]
    unrealized = sum(float(item["unrealized_pnl"]) for item in holdings)
    invested = sum(float(item["avg_cost"]) * float(item["quantity"]) for item in holdings)
    win_rate = len([p for p in closed_pnls if p > 0]) / len(closed_pnls) if closed_pnls else 0.0
    return {
        "holdings": holdings,
        "realized_pnl": round(realized, 2),
        "unrealized_pnl": round(unrealized, 2),
        "total_pnl": round(realized + unrealized, 2),
        "trade_count": len(trades),
        "closed_trade_count": len(closed_pnls),
        "win_rate": round(win_rate, 4),
        "total_buy_amount": round(total_buy_amount, 2),
        "total_sell_amount": round(total_sell_amount, 2),
        "total_fee": round(total_fee, 2),
        "current_market_value": round(invested + unrealized, 2),
    }


def _last_price(symbol: str) -> float | None:
    df = read_daily_bars(symbol=symbol)
    if df.empty:
        return None
    return float(df["close"].iloc[-1])


def import_trades_csv(content: str) -> dict[str, Any]:
    """导入模拟成交 CSV。

    必填列：symbol, side, price。可选列：quantity, fee, plan_id, traded_at, note。
    """
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    imported: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    required = {"symbol", "side", "price"}
    for idx, row in enumerate(rows, start=2):
        missing = [key for key in required if not row.get(key)]
        if missing:
            errors.append({"line": idx, "error": f"缺少字段: {', '.join(missing)}"})
            continue
        try:
            imported.append(
                add_trade(
                    {
                        "plan_id": row.get("plan_id") or None,
                        "symbol": row["symbol"],
                        "side": row["side"],
                        "price": float(row["price"]),
                        "quantity": float(row.get("quantity") or 100),
                        "fee": float(row.get("fee") or 0),
                        "traded_at": row.get("traded_at") or None,
                        "note": row.get("note") or "",
                    }
                )
            )
        except Exception as exc:
            errors.append({"line": idx, "error": str(exc)})
    return {"imported": len(imported), "errors": errors, "trades": imported}
