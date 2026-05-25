"""Local watchlist groups and symbols."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.core.db import get_conn, init_db
import sqlite3


def _item_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "group_id": row["group_id"],
        "symbol": row["symbol"],
        "name": row["name"] or "",
        "note": row["note"] or "",
        "added_at": row["added_at"],
    }


def _group_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "sort_order": row["sort_order"],
    }


class WatchlistService:
    def __init__(self) -> None:
        init_db()

    def list_groups(self) -> list[dict[str, Any]]:
        try:
            return self._list_groups_impl()
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                init_db()
                return self._list_groups_impl()
            raise

    def _list_groups_impl(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            groups = conn.execute(
                "SELECT * FROM watchlist_groups ORDER BY sort_order, created_at"
            ).fetchall()
            if not groups:
                _seed_watchlist_inline(conn)
                groups = conn.execute(
                    "SELECT * FROM watchlist_groups ORDER BY sort_order, created_at"
                ).fetchall()
            result = []
            for g in groups:
                items = conn.execute(
                    """
                    SELECT * FROM watchlist_items WHERE group_id = ?
                    ORDER BY added_at DESC
                    """,
                    (g["id"],),
                ).fetchall()
                grp = _group_row(g)
                grp["items"] = [_item_row(i) for i in items]
                result.append(grp)
            return result

    def add_item(
        self, symbol: str, group_id: str = "default", name: str = "", note: str = ""
    ) -> dict[str, Any]:
        symbol = symbol.strip()
        now = datetime.now().isoformat()
        item_id = str(uuid.uuid4())
        with get_conn() as conn:
            exists = conn.execute(
                "SELECT 1 FROM watchlist_groups WHERE id = ?", (group_id,)
            ).fetchone()
            if not exists:
                raise ValueError("分组不存在")
            existing = conn.execute(
                "SELECT id FROM watchlist_items WHERE group_id = ? AND symbol = ?",
                (group_id, symbol),
            ).fetchone()
            if existing:
                item_id = existing["id"]
                conn.execute(
                    "UPDATE watchlist_items SET name = ?, note = ? WHERE id = ?",
                    (name, note, item_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO watchlist_items (id, group_id, symbol, name, note, added_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (item_id, group_id, symbol, name, note, now),
                )
        return {"id": item_id, "group_id": group_id, "symbol": symbol, "name": name, "note": note}

    def remove_item(self, symbol: str, group_id: str = "default") -> bool:
        with get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM watchlist_items WHERE group_id = ? AND symbol = ?",
                (group_id, symbol.strip()),
            )
            return cur.rowcount > 0

    def create_group(self, name: str) -> dict[str, Any]:
        gid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with get_conn() as conn:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM watchlist_groups"
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO watchlist_groups (id, name, sort_order, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (gid, name.strip(), max_order + 1, now),
            )
        return {"id": gid, "name": name, "items": []}


_svc: WatchlistService | None = None


def _seed_watchlist_inline(conn: sqlite3.Connection) -> None:
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO watchlist_groups (id, name, sort_order, created_at)
        VALUES (?, ?, ?, ?)
        """,
        ("default", "默认自选", 0, now),
    )


def get_watchlist_service() -> WatchlistService:
    global _svc
    if _svc is None:
        _svc = WatchlistService()
    return _svc
