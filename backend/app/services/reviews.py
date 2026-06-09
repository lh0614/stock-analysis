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
        rows = conn.execute("SELECT tags_json, pnl, pnl_pct FROM reviews").fetchall()
    tag_counts: dict[str, int] = {}
    pnl_by_tag: dict[str, float] = {}
    loss_tag_counts: dict[str, int] = {}
    total_pnl = 0.0
    pnl_pcts: list[float] = []
    for r in rows:
        pnl = float(r["pnl"] or 0)
        total_pnl += pnl
        if r["pnl_pct"] is not None:
            pnl_pcts.append(float(r["pnl_pct"]))
        for t in json.loads(r["tags_json"] or "[]"):
            tag_counts[t] = tag_counts.get(t, 0) + 1
            pnl_by_tag[t] = pnl_by_tag.get(t, 0.0) + pnl
            if pnl < 0:
                loss_tag_counts[t] = loss_tag_counts.get(t, 0) + 1
    deviation_tags = {
        "late_stop_loss",
        "ignored_market_regime",
        "position_too_large",
        "did_not_follow_plan",
        "chased_high",
    }
    deviation_count = sum(tag_counts.get(t, 0) for t in deviation_tags)
    suggestions = []
    if loss_tag_counts.get("late_stop_loss"):
        suggestions.append("止损执行偏差高，策略版本需强化失效条件与提醒。")
    if loss_tag_counts.get("ignored_market_regime"):
        suggestions.append("市场环境过滤失效，回测与实盘观察需按强/震荡/风险状态拆分。")
    if loss_tag_counts.get("position_too_large"):
        suggestions.append("仓位过大导致亏损，策略需降低单票上限或加入波动率仓位系数。")
    if loss_tag_counts.get("signal_failed"):
        suggestions.append("信号失败偏多，候选策略应降低同类因子权重或增加确认条件。")
    return {
        "review_count": len(rows),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl_pct": round(sum(pnl_pcts) / len(pnl_pcts), 4) if pnl_pcts else 0,
        "tag_counts": tag_counts,
        "pnl_by_tag": {k: round(v, 2) for k, v in pnl_by_tag.items()},
        "loss_tag_counts": loss_tag_counts,
        "deviation_count": deviation_count,
        "deviation_ratio": round(deviation_count / len(rows), 4) if rows else 0,
        "strategy_revision_suggestions": suggestions,
    }
