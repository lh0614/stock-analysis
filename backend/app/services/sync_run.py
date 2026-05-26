"""全量同步（列表 + K 线）共享运行锁，供 SSE、调度器、定时触发统一互斥。"""
from __future__ import annotations

import threading

_lock = threading.Lock()
_running = False


class SyncRunLease:
    """已占用共享同步运行权的凭证；由 iter_sync_all 或原获取方在结束时 release。"""

    __slots__ = ()


def is_sync_running() -> bool:
    return _running


def try_acquire_sync_run() -> SyncRunLease | None:
    """非阻塞获取；成功返回 lease，调用方须在 finally 中 release_sync_run。"""
    global _running
    if not _lock.acquire(blocking=False):
        return None
    if _running:
        _lock.release()
        return None
    _running = True
    return SyncRunLease()


def release_sync_run() -> None:
    global _running
    if _running:
        _running = False
        _lock.release()
