"""Baostock 单例会话：统一 login/logout，避免进程退出时 semaphore 泄漏告警。"""
from __future__ import annotations

import atexit
import threading

import baostock as bs

_lock = threading.RLock()
_logged_in = False


def ensure_login() -> bool:
    global _logged_in
    with _lock:
        if _logged_in:
            return True
        lg = bs.login()
        if getattr(lg, "error_code", "1") != "0":
            return False
        _logged_in = True
        return True


def logout() -> None:
    global _logged_in
    with _lock:
        if not _logged_in:
            return
        try:
            bs.logout()
        except Exception:
            pass
        finally:
            _logged_in = False


def is_logged_in() -> bool:
    return _logged_in


atexit.register(logout)
