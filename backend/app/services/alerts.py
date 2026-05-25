"""Price / indicator alert rules and evaluation."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.core.data_fetcher import StockDataFetcher
from app.core.config import settings
from app.core.db import get_conn, init_db
from app.services.technical import compute_indicators

RULE_LABELS = {
    "price_above": "收盘价高于",
    "price_below": "收盘价低于",
    "change_pct_above": "日涨幅超过(%)",
    "change_pct_below": "日跌幅超过(%)",
    "rsi_above": "RSI12 高于",
    "rsi_below": "RSI12 低于",
}


class AlertService:
    def __init__(self) -> None:
        init_db()
        self.fetcher = StockDataFetcher(cache_dir=settings.CACHE_DIR)

    def list_alerts(self, symbol: str | None = None) -> list[dict[str, Any]]:
        with get_conn() as conn:
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM alerts WHERE symbol = ? ORDER BY created_at DESC",
                    (symbol.strip(),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM alerts ORDER BY created_at DESC"
                ).fetchall()
        return [self._row_to_alert(r) for r in rows]

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        aid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        rule = data["rule_type"]
        if rule not in RULE_LABELS:
            raise ValueError(f"不支持的规则类型: {rule}")
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO alerts (id, symbol, name, rule_type, threshold, enabled, cooldown_minutes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    aid,
                    data["symbol"].strip(),
                    data.get("name") or RULE_LABELS[rule],
                    rule,
                    float(data["threshold"]),
                    1 if data.get("enabled", True) else 0,
                    int(data.get("cooldown_minutes", 60)),
                    now,
                ),
            )
        return self.get(aid)  # type: ignore

    def get(self, alert_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return self._row_to_alert(row) if row else None

    def update(self, alert_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        cur = self.get(alert_id)
        if not cur:
            return None
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE alerts SET name=?, threshold=?, enabled=?, cooldown_minutes=?
                WHERE id=?
                """,
                (
                    data.get("name", cur["name"]),
                    float(data.get("threshold", cur["threshold"])),
                    1 if data.get("enabled", cur["enabled"]) else 0,
                    int(data.get("cooldown_minutes", cur["cooldown_minutes"])),
                    alert_id,
                ),
            )
        return self.get(alert_id)

    def delete(self, alert_id: str) -> bool:
        with get_conn() as conn:
            conn.execute("DELETE FROM alert_events WHERE alert_id = ?", (alert_id,))
            cur = conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
            return cur.rowcount > 0

    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM alert_events ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("payload_json"):
                d["payload"] = json.loads(d["payload_json"])
            out.append(d)
        return out

    def evaluate_all(self) -> dict[str, Any]:
        alerts = [a for a in self.list_alerts() if a["enabled"]]
        triggered: list[dict[str, Any]] = []
        for alert in alerts:
            hit = self._evaluate_one(alert)
            if hit:
                triggered.append(hit)
        return {"checked": len(alerts), "triggered": triggered}

    def _evaluate_one(self, alert: dict[str, Any]) -> dict[str, Any] | None:
        if alert.get("last_triggered_at"):
            last = datetime.fromisoformat(alert["last_triggered_at"])
            if datetime.now() - last < timedelta(minutes=alert["cooldown_minutes"]):
                return None

        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
        res = self.fetcher.get_stock_data(alert["symbol"], start, end)
        if not res.get("success") or len(res.get("data") or []) < 2:
            return None

        records = res["data"]
        latest = records[-1]
        prev = records[-2]
        close = float(latest.get("close") or 0)
        prev_close = float(prev.get("close") or close)
        change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0
        indicators = compute_indicators(records, ["rsi"])
        rsi12 = (indicators.get("rsi") or {}).get("rsi12")

        rule = alert["rule_type"]
        th = alert["threshold"]
        fired = False
        detail = {}

        if rule == "price_above":
            fired = close > th
            detail = {"close": close, "threshold": th}
        elif rule == "price_below":
            fired = close < th
            detail = {"close": close, "threshold": th}
        elif rule == "change_pct_above":
            fired = change_pct > th
            detail = {"change_pct": round(change_pct, 2), "threshold": th}
        elif rule == "change_pct_below":
            fired = change_pct < -abs(th)
            detail = {"change_pct": round(change_pct, 2), "threshold": th}
        elif rule == "rsi_above" and rsi12 is not None:
            fired = rsi12 > th
            detail = {"rsi12": rsi12, "threshold": th}
        elif rule == "rsi_below" and rsi12 is not None:
            fired = rsi12 < th
            detail = {"rsi12": rsi12, "threshold": th}

        if not fired:
            return None

        msg = f"{alert['symbol']} {alert['name']} 已触发"
        now = datetime.now().isoformat()
        eid = str(uuid.uuid4())
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO alert_events (id, alert_id, symbol, message, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (eid, alert["id"], alert["symbol"], msg, json.dumps(detail), now),
            )
            conn.execute(
                "UPDATE alerts SET last_triggered_at = ? WHERE id = ?",
                (now, alert["id"]),
            )
        return {"alert_id": alert["id"], "symbol": alert["symbol"], "message": msg, "detail": detail}

    @staticmethod
    def _row_to_alert(row) -> dict[str, Any]:
        d = dict(row)
        d["enabled"] = bool(d["enabled"])
        d["rule_label"] = RULE_LABELS.get(d["rule_type"], d["rule_type"])
        return d

    @staticmethod
    def rule_types() -> list[dict[str, str]]:
        return [{"id": k, "label": v} for k, v in RULE_LABELS.items()]


_svc: AlertService | None = None


def get_alert_service() -> AlertService:
    global _svc
    if _svc is None:
        _svc = AlertService()
    return _svc
