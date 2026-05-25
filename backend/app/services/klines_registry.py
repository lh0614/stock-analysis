"""全量 K 线同步登记：完成记录、断点续传队列。"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.data_fetcher import StockDataFetcher
from app.core.db import get_conn, init_db

KLINES_DIR = os.path.join(settings.CACHE_DIR, "klines")
MIN_BARS = 30


class KlinesRegistry:
    def __init__(self) -> None:
        init_db()
        self.fetcher = StockDataFetcher(cache_dir=settings.CACHE_DIR)

    @staticmethod
    def _full_path(symbol: str) -> str:
        code = str(symbol).strip().zfill(6)
        return os.path.join(KLINES_DIR, f"{code}_full.pkl")

    def inspect_file(self, symbol: str) -> dict[str, Any] | None:
        path = self._full_path(symbol)
        if not os.path.isfile(path):
            return None
        try:
            import pandas as pd

            df = pd.read_pickle(path)
            if df is None or len(df) < MIN_BARS:
                return None
            first = self.fetcher._first_trade_date(df)
            last = self.fetcher._last_trade_date(df)
            if not last:
                return None
            today = datetime.now().strftime("%Y-%m-%d")
            fresh = last[:10] >= today
            last_dt = datetime.strptime(last[:10], "%Y-%m-%d").date()
            end_dt = datetime.strptime(today, "%Y-%m-%d").date()
            gap_days = max(0, (end_dt - last_dt).days)
            return {
                "symbol": str(symbol).zfill(6),
                "bars": len(df),
                "first_date": first,
                "last_date": last,
                "fresh": fresh,
                "gap_days": gap_days,
                "cache_file": os.path.basename(path),
            }
        except Exception:
            return None

    def get_record(self, symbol: str) -> dict[str, Any] | None:
        code = str(symbol).zfill(6)
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM klines_sync_records WHERE symbol = ?", (code,)
            ).fetchone()
        return dict(row) if row else None

    def is_fully_synced(self, symbol: str) -> bool:
        """已完成全量：有登记且文件有效、行情够新。"""
        code = str(symbol).zfill(6)
        info = self.inspect_file(code)
        if not info or not info.get("fresh"):
            return False
        rec = self.get_record(code)
        if rec and rec["status"] in ("ok", "skipped"):
            return True
        if info and info.get("bars", 0) >= MIN_BARS:
            self.upsert_from_result(
                {
                    "status": "ok",
                    "symbol": code,
                    "bars": info["bars"],
                    "first_date": info.get("first_date"),
                    "last_date": info.get("last_date"),
                    "cache_file": info.get("cache_file"),
                }
            )
            return True
        return False

    def upsert_from_result(self, result: dict[str, Any]) -> None:
        code = str(result.get("symbol", "")).zfill(6)
        if not code:
            return
        now = datetime.now().isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO klines_sync_records
                (symbol, status, bars, first_date, last_date, error, cache_file, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    status = excluded.status,
                    bars = excluded.bars,
                    first_date = excluded.first_date,
                    last_date = excluded.last_date,
                    error = excluded.error,
                    cache_file = excluded.cache_file,
                    updated_at = excluded.updated_at
                """,
                (
                    code,
                    result.get("status", "failed"),
                    int(result.get("bars") or 0),
                    result.get("first_date"),
                    result.get("last_date"),
                    result.get("error"),
                    result.get("cache_file"),
                    now,
                ),
            )

    def build_queue(
        self, symbols: list[str], *, mode: str = "full"
    ) -> dict[str, Any]:
        """
        full: 失败 + 未首次全量 + 需增量（断点续传）
        incremental: 仅已有 _full.pkl 且末根早于今日（不续传未完成全量）
        """
        failed: list[str] = []
        pending: list[str] = []
        stale: list[str] = []
        skipped_no_file = 0
        complete = 0
        incremental_only = mode == "incremental"

        for sym in symbols:
            code = str(sym).zfill(6)
            rec = self.get_record(code)
            if self.is_fully_synced(code):
                complete += 1
                continue

            finfo = self.inspect_file(code)

            if incremental_only:
                if finfo and not finfo.get("fresh"):
                    stale.append(code)
                else:
                    skipped_no_file += 1
                continue

            if rec and rec["status"] == "failed":
                failed.append(code)
                continue
            if finfo and not finfo.get("fresh"):
                stale.append(code)
            else:
                pending.append(code)

        queue = stale if incremental_only else (failed + pending + stale)
        return {
            "queue": queue,
            "mode": mode,
            "complete": complete,
            "pending": len(queue),
            "failed": len(failed),
            "stale": len(stale),
            "pending_full": len(pending),
            "skipped_no_file": skipped_no_file,
            "total_list": len(symbols),
        }

    def get_summary(self) -> dict[str, Any]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS c FROM klines_sync_records GROUP BY status
                """
            ).fetchall()
            job = conn.execute(
                """
                SELECT * FROM klines_sync_jobs ORDER BY updated_at DESC LIMIT 1
                """
            ).fetchone()
        by_status = {r["status"]: r["c"] for r in rows}
        ok = by_status.get("ok", 0) + by_status.get("skipped", 0)
        return {
            "records_ok": by_status.get("ok", 0),
            "records_skipped": by_status.get("skipped", 0),
            "records_failed": by_status.get("failed", 0),
            "records_total": sum(by_status.values()),
            "klines_complete": ok,
            "last_job": dict(job) if job else None,
        }

    def start_job(self, job_id: str, queue_len: int, complete: int) -> None:
        now = datetime.now().isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO klines_sync_jobs
                (job_id, status, total, queue_pending, started_at, updated_at)
                VALUES (?, 'running', ?, ?, ?, ?)
                """,
                (job_id, queue_len, queue_len, now, now),
            )

    def update_job(self, job_id: str, ok: int, skipped: int, failed: int, pending: int) -> None:
        now = datetime.now().isoformat()
        status = "completed" if pending <= 0 else "running"
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE klines_sync_jobs SET
                    status = ?, done_ok = ?, done_skipped = ?, done_failed = ?,
                    queue_pending = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, ok, skipped, failed, pending, now, job_id),
            )


_registry: KlinesRegistry | None = None


def get_klines_registry() -> KlinesRegistry:
    global _registry
    if _registry is None:
        _registry = KlinesRegistry()
    return _registry
