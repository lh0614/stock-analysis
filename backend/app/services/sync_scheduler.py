"""每日定时数据同步调度：配置持久化、并发锁、复用 universe.iter_sync_all。"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Any

from app.core.db import get_conn, init_db
from app.services.sync_run import (
    SyncRunLease,
    is_sync_running,
    release_sync_run,
    try_acquire_sync_run,
)
from app.services.universe import get_universe_service

CONFIG_KEY = "sync_scheduler_config"
RUN_STATE_KEY = "sync_scheduler_run_state"
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
DEFAULT_TIME_OF_DAY = "15:30"
DEFAULT_SYNC_MODE = "incremental"
LOOP_INTERVAL_SEC = 60


def _parse_time_of_day(value: str) -> tuple[int, int] | None:
    m = TIME_RE.match((value or "").strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def _normalize_sync_mode(mode: str | None) -> str:
    m = (mode or DEFAULT_SYNC_MODE).strip().lower()
    return m if m in ("incremental", "full") else DEFAULT_SYNC_MODE


class SyncSchedulerService:
    def __init__(self) -> None:
        init_db()
        self._last_scheduled_date: str | None = None
        self._progress: dict[str, Any] = {}

    def _load_json_pref(self, key: str) -> dict[str, Any]:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM user_preferences WHERE key = ?", (key,)
            ).fetchone()
        if not row:
            return {}
        try:
            data = json.loads(row["value"])
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _save_json_pref(self, key: str, data: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, json.dumps(data, ensure_ascii=False)),
            )

    def load_config(self) -> dict[str, Any]:
        raw = self._load_json_pref(CONFIG_KEY)
        parsed = _parse_time_of_day(raw.get("time_of_day", DEFAULT_TIME_OF_DAY))
        time_of_day = (
            f"{parsed[0]:02d}:{parsed[1]:02d}"
            if parsed
            else DEFAULT_TIME_OF_DAY
        )
        return {
            "enabled": bool(raw.get("enabled", False)),
            "time_of_day": time_of_day,
            "sync_mode": _normalize_sync_mode(raw.get("sync_mode")),
        }

    def save_config(
        self,
        *,
        enabled: bool | None = None,
        time_of_day: str | None = None,
        sync_mode: str | None = None,
    ) -> dict[str, Any]:
        current = self.load_config()
        if enabled is not None:
            current["enabled"] = bool(enabled)
        if time_of_day is not None:
            parsed = _parse_time_of_day(time_of_day)
            if not parsed:
                raise ValueError("time_of_day 格式应为 HH:MM，例如 15:30")
            current["time_of_day"] = f"{parsed[0]:02d}:{parsed[1]:02d}"
        if sync_mode is not None:
            current["sync_mode"] = _normalize_sync_mode(sync_mode)
        self._save_json_pref(CONFIG_KEY, current)
        return current

    def _load_run_state(self) -> dict[str, Any]:
        return self._load_json_pref(RUN_STATE_KEY)

    def _update_run_state(self, **fields: Any) -> dict[str, Any]:
        state = self._load_run_state()
        state.update(fields)
        self._save_json_pref(RUN_STATE_KEY, state)
        return state

    def _compute_next_run_at(self, config: dict[str, Any]) -> str | None:
        if not config.get("enabled"):
            return None
        parsed = _parse_time_of_day(config.get("time_of_day", DEFAULT_TIME_OF_DAY))
        if not parsed:
            return None
        hour, minute = parsed
        now = datetime.now()
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate.isoformat()

    def get_status(self) -> dict[str, Any]:
        config = self.load_config()
        run_state = self._load_run_state()
        running = is_sync_running()
        status = {
            **config,
            "running": running,
            "last_started_at": run_state.get("last_started_at"),
            "last_finished_at": run_state.get("last_finished_at"),
            "last_status": run_state.get("last_status"),
            "last_message": run_state.get("last_message"),
            "last_error": run_state.get("last_error"),
            "last_trigger": run_state.get("last_trigger"),
            "next_run_at": self._compute_next_run_at(config),
        }
        if running and self._progress:
            status["progress"] = dict(self._progress)
        return status

    def _begin_run(self, trigger: str) -> None:
        now = datetime.now().isoformat()
        self._progress = {"phase": "starting", "message": "同步启动中…"}
        self._update_run_state(
            last_started_at=now,
            last_finished_at=None,
            last_status="running",
            last_message="同步进行中",
            last_error=None,
            last_trigger=trigger,
        )

    def _end_run(
        self,
        *,
        status: str,
        message: str | None = None,
        error: str | None = None,
    ) -> None:
        now = datetime.now().isoformat()
        self._update_run_state(
            last_finished_at=now,
            last_status=status,
            last_message=message,
            last_error=error,
        )
        self._progress = {}

    def _execute_sync(self, sync_mode: str, run_lease: SyncRunLease) -> None:
        svc = get_universe_service()
        final_message: str | None = None
        for item in svc.iter_sync_all(sync_mode=sync_mode, run_lease=run_lease):
            if (
                item.get("event") == "error"
                and item.get("reason") == "already_running"
            ):
                self._end_run(
                    status="skipped",
                    message=item.get("message") or "已有同步任务正在运行，请稍后再试",
                    error=None,
                )
                return
            ev = item.get("event")
            if ev == "klines_scanning":
                self._progress = {
                    "phase": "klines",
                    "current": item.get("current"),
                    "total": item.get("total"),
                    "symbol": item.get("symbol"),
                    "message": (
                        f"K 线同步 {item.get('current')}/{item.get('total')} "
                        f"{item.get('symbol', '')}"
                    ),
                }
            elif ev == "list_complete":
                self._progress = {
                    "phase": "list",
                    "message": item.get("message") or "列表同步完成",
                }
            elif ev == "start":
                self._progress = {
                    "phase": item.get("phase") or "list",
                    "message": "同步已开始",
                }
            elif ev == "complete":
                final_message = item.get("message")
            elif ev == "error":
                raise RuntimeError(
                    item.get("error") or item.get("message") or "同步失败"
                )
        self._end_run(
            status="success",
            message=final_message or "同步完成",
            error=None,
        )

    def _worker_run(self, sync_mode: str, run_lease: SyncRunLease) -> None:
        try:
            self._execute_sync(sync_mode, run_lease)
        except Exception as e:
            self._end_run(status="failed", message=None, error=str(e))

    async def trigger_run(self, *, trigger: str = "manual") -> dict[str, Any]:
        run_lease = try_acquire_sync_run()
        if run_lease is None:
            msg = "已有同步任务正在运行，请稍后再试"
            if trigger == "scheduled":
                self._update_run_state(
                    last_status="skipped",
                    last_message="定时触发跳过：已有同步任务正在运行",
                    last_error=None,
                    last_trigger="scheduled",
                )
            return {
                "accepted": False,
                "reason": "already_running",
                "message": msg,
                **self.get_status(),
            }

        try:
            self._begin_run(trigger)
            accepted_status = self.get_status()
            accepted_status["running"] = True
            config = self.load_config()
            mode = config["sync_mode"]
            loop = asyncio.get_running_loop()
            fut = loop.run_in_executor(
                None, lambda: self._worker_run(mode, run_lease)
            )

            def _done_callback(task: asyncio.Future) -> None:
                try:
                    task.result()
                except Exception as e:
                    self._end_run(status="failed", message=None, error=str(e))

            fut.add_done_callback(_done_callback)
        except Exception as e:
            release_sync_run()
            self._end_run(
                status="failed",
                message=None,
                error=f"启动同步任务失败: {e}",
            )
            return {
                "accepted": False,
                "reason": "start_failed",
                "message": "同步任务启动失败",
                **self.get_status(),
            }

        return {
            "accepted": True,
            "reason": None,
            "message": "同步任务已启动",
            **accepted_status,
        }

    async def _check_scheduled_run(self) -> None:
        config = self.load_config()
        if not config.get("enabled"):
            return
        parsed = _parse_time_of_day(config.get("time_of_day", DEFAULT_TIME_OF_DAY))
        if not parsed:
            return
        hour, minute = parsed
        now = datetime.now()
        if now.hour != hour or now.minute != minute:
            return
        today = now.date().isoformat()
        if self._last_scheduled_date == today:
            return
        self._last_scheduled_date = today

        await self.trigger_run(trigger="scheduled")

    async def run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(LOOP_INTERVAL_SEC)
                await self._check_scheduled_run()
            except asyncio.CancelledError:
                break
            except Exception:
                pass


_svc: SyncSchedulerService | None = None


def get_sync_scheduler_service() -> SyncSchedulerService:
    global _svc
    if _svc is None:
        _svc = SyncSchedulerService()
    return _svc
