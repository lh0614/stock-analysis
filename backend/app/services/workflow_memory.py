"""Workflow template CRUD and user preferences."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from app.core.db import get_conn, init_db, row_to_workflow


class WorkflowMemoryService:
    def __init__(self) -> None:
        init_db()

    def list_workflows(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM workflows ORDER BY is_default DESC, name ASC"
            ).fetchall()
        return [row_to_workflow(r) for r in rows]

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
            ).fetchone()
        return row_to_workflow(row) if row else None

    def get_default(self) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM workflows WHERE is_default = 1 LIMIT 1"
            ).fetchone()
            if not row:
                row = conn.execute("SELECT * FROM workflows LIMIT 1").fetchone()
        return row_to_workflow(row) if row else None

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        wf_id = data.get("id") or str(uuid.uuid4())
        now = datetime.now().isoformat()
        indicators = json.dumps(data.get("indicators", ["ma", "macd", "rsi"]))
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO workflows (id, name, workflow_type, horizon, indicators, chart_period, is_default, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wf_id,
                    data["name"],
                    data.get("workflow_type", "custom"),
                    data.get("horizon", "short"),
                    indicators,
                    data.get("chart_period", "1y"),
                    1 if data.get("is_default") else 0,
                    json.dumps(data.get("config", {})),
                    now,
                    now,
                ),
            )
        if data.get("is_default"):
            self._clear_default_except(wf_id)
        return self.get(wf_id)  # type: ignore

    def update(self, workflow_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        existing = self.get(workflow_id)
        if not existing:
            return None
        if existing.get("workflow_type") == "builtin" and data.get("name"):
            # builtin: only allow config / default flag updates
            pass
        now = datetime.now().isoformat()
        name = data.get("name", existing["name"])
        horizon = data.get("horizon", existing["horizon"])
        indicators = json.dumps(data.get("indicators", existing["indicators"]))
        chart_period = data.get("chart_period", existing["chart_period"])
        is_default = data.get("is_default", existing["is_default"])
        config = json.dumps(data.get("config", existing.get("config", {})))
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE workflows SET name=?, horizon=?, indicators=?, chart_period=?, is_default=?, config_json=?, updated_at=?
                WHERE id=?
                """,
                (name, horizon, indicators, chart_period, 1 if is_default else 0, config, now, workflow_id),
            )
        if is_default:
            self._clear_default_except(workflow_id)
        return self.get(workflow_id)

    def delete(self, workflow_id: str) -> bool:
        wf = self.get(workflow_id)
        if not wf or wf.get("workflow_type") == "builtin":
            return False
        with get_conn() as conn:
            conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
        return True

    def set_default(self, workflow_id: str) -> dict[str, Any] | None:
        return self.update(workflow_id, {"is_default": True})

    def _clear_default_except(self, keep_id: str) -> None:
        with get_conn() as conn:
            conn.execute(
                "UPDATE workflows SET is_default = 0 WHERE id != ?", (keep_id,)
            )

    def get_preference(self, key: str) -> Any:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM user_preferences WHERE key = ?", (key,)
            ).fetchone()
        if not row:
            return None
        return json.loads(row["value"])

    def set_preference(self, key: str, value: Any) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, json.dumps(value)),
            )

    def export_all(self) -> dict[str, Any]:
        return {
            "workflows": self.list_workflows(),
            "default_id": (self.get_default() or {}).get("id"),
            "preferences": {
                "last_symbol": self.get_preference("last_symbol"),
                "last_workflow_id": self.get_preference("last_workflow_id"),
            },
        }

    def import_workflows(self, payload: dict[str, Any]) -> int:
        count = 0
        for wf in payload.get("workflows", []):
            if wf.get("workflow_type") == "builtin":
                continue
            if self.get(wf.get("id", "")):
                self.update(wf["id"], wf)
            else:
                self.create(wf)
            count += 1
        if payload.get("default_id"):
            self.set_default(payload["default_id"])
        return count


_service: WorkflowMemoryService | None = None


def get_workflow_service() -> WorkflowMemoryService:
    global _service
    if _service is None:
        _service = WorkflowMemoryService()
    return _service
