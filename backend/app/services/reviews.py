"""复盘记录与统计。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from app.core.db import get_conn, init_db

REVIEW_TAGS = [
    "chased_high",
    "late_stop_loss",
    "ignored_market_regime",
    "signal_failed",
    "data_quality_issue",
    "news_shock",
    "position_too_large",
    "did_not_follow_plan",
]


def create_review(data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    rid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO reviews (id, plan_id, pnl, pnl_pct, tags_json, lesson, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid,
                data["plan_id"],
                data.get("pnl"),
                data.get("pnl_pct"),
                json.dumps(data.get("tags") or [], ensure_ascii=False),
                data.get("lesson", ""),
                now,
            ),
        )
    return get_review(rid)


def get_review(review_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "plan_id": row["plan_id"],
        "pnl": row["pnl"],
        "pnl_pct": row["pnl_pct"],
        "tags": json.loads(row["tags_json"] or "[]"),
        "lesson": row["lesson"],
        "created_at": row["created_at"],
    }


def list_reviews(limit: int = 100) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        {
            "id": r["id"],
            "plan_id": r["plan_id"],
            "pnl": r["pnl"],
            "pnl_pct": r["pnl_pct"],
            "tags": json.loads(r["tags_json"] or "[]"),
            "lesson": r["lesson"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def get_stats() -> dict[str, Any]:
    with get_conn() as conn:
        rows = conn.execute("SELECT tags_json, pnl FROM reviews").fetchall()
    tag_counts: dict[str, int] = {}
    total_pnl = 0.0
    for r in rows:
        total_pnl += float(r["pnl"] or 0)
        for t in json.loads(r["tags_json"] or "[]"):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    return {"review_count": len(rows), "total_pnl": round(total_pnl, 2), "tag_counts": tag_counts}
