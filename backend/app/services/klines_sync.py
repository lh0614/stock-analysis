"""全量日 K 同步：断点续传、优先未完成、逐条落库。"""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Generator

from app.core.config import settings
from app.core.data_fetcher import StockDataFetcher
from app.services.klines_registry import get_klines_registry

KLINES_SYNC_DELAY_SEC = 0.12
HEARTBEAT_EVERY = 5


class KlinesSyncService:
    def __init__(self) -> None:
        self.fetcher = StockDataFetcher(cache_dir=settings.CACHE_DIR)
        self.registry = get_klines_registry()
        self._last_summary: dict[str, Any] = {}

    def get_last_summary(self) -> dict[str, Any]:
        return self._last_summary

    def iter_sync_full(
        self,
        symbols: list[str],
        *,
        job_id: str | None = None,
        mode: str = "full",
    ) -> Generator[dict[str, Any], None, None]:
        job_id = job_id or str(uuid.uuid4())
        plan = self.registry.build_queue(symbols, mode=mode)
        queue = plan["queue"]
        total = len(queue)
        ok = skipped = failed = 0
        already = plan["complete"]

        self.registry.start_job(job_id, total, already)
        self._last_summary = {
            "job_id": job_id,
            "total": total,
            "already_complete": already,
            "total_list": plan["total_list"],
        }

        inc = mode == "incremental"
        yield {
            "event": "klines_start",
            "job_id": job_id,
            "mode": mode,
            "total": total,
            "already_complete": already,
            "total_list": plan["total_list"],
            "skipped_no_file": plan.get("skipped_no_file", 0),
            "pending_full": plan.get("pending_full", 0),
            "resume": not inc and total < plan["total_list"],
            "range": "增量(末根+1~今日)" if inc else f"{StockDataFetcher.FULL_HISTORY_START} ~ 今日",
            "message": (
                f"增量更新 {total} 只（已有全量、末根非今日），已完成 {already} 只；"
                f"跳过无全量文件 {plan.get('skipped_no_file', 0)} 只"
                if inc and total
                else (
                    f"待同步 {total} 只，已完成 {already} 只（含断点续传）"
                    if total
                    else (
                        f"增量无需更新（{already} 只已至今日）"
                        if inc
                        else f"全量 K 线均已就绪（{already} 只）"
                    )
                )
            ),
        }

        if total == 0:
            self._last_summary.update(
                {"ok": 0, "skipped": 0, "failed": 0, "finished_at": datetime.now().isoformat()}
            )
            yield {
                "event": "klines_complete",
                "job_id": job_id,
                "total": 0,
                "ok": 0,
                "skipped": 0,
                "failed": 0,
                "already_complete": already,
                "finished_at": datetime.now().isoformat(),
            }
            self.registry.update_job(job_id, 0, 0, 0, 0)
            return

        try:
            for idx, code in enumerate(queue, start=1):
                yield {
                    "event": "klines_scanning",
                    "job_id": job_id,
                    "current": idx,
                    "total": total,
                    "symbol": code,
                }

                if self.registry.is_fully_synced(code):
                    result = {
                        "status": "skipped",
                        "symbol": code,
                        "bars": self.registry.inspect_file(code).get("bars", 0),
                        "message": "已完成全量",
                    }
                else:
                    result = self.fetcher.sync_full_history(code, quiet=True)

                self.registry.upsert_from_result(result)
                result["event"] = "klines_item"
                result["current"] = idx
                result["total"] = total
                result["job_id"] = job_id
                yield result

                st = result.get("status")
                if st == "ok":
                    ok += 1
                elif st == "skipped":
                    skipped += 1
                else:
                    failed += 1

                pending_left = total - idx
                self.registry.update_job(job_id, ok, skipped, failed, pending_left)

                if idx % HEARTBEAT_EVERY == 0:
                    yield {
                        "event": "heartbeat",
                        "job_id": job_id,
                        "current": idx,
                        "total": total,
                        "ok": ok,
                        "skipped": skipped,
                        "failed": failed,
                    }

                if idx < total:
                    time.sleep(KLINES_SYNC_DELAY_SEC)

        except GeneratorExit:
            self.registry.update_job(job_id, ok, skipped, failed, max(0, total - ok - skipped - failed))
            yield {
                "event": "klines_paused",
                "job_id": job_id,
                "ok": ok,
                "skipped": skipped,
                "failed": failed,
                "message": "连接中断，进度已保存，下次同步将续传",
            }
            raise

        self._last_summary = {
            "job_id": job_id,
            "total": total,
            "ok": ok,
            "skipped": skipped,
            "failed": failed,
            "already_complete": already,
            "finished_at": datetime.now().isoformat(),
        }
        self.registry.update_job(job_id, ok, skipped, failed, 0)
        yield {
            "event": "klines_complete",
            "job_id": job_id,
            "total": total,
            "ok": ok,
            "skipped": skipped,
            "failed": failed,
            "already_complete": already,
            "finished_at": datetime.now().isoformat(),
        }


_svc: KlinesSyncService | None = None


def get_klines_sync_service() -> KlinesSyncService:
    global _svc
    if _svc is None:
        _svc = KlinesSyncService()
    return _svc
