"""股票池数据目录：创建、解析路径、启动时权限检查。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# 文稿/AI/stock-pool（macOS Documents = 文稿）
DEFAULT_STOCK_POOL_DIR = Path.home() / "Documents" / "AI" / "stock-pool"

CACHE_SUBDIRS = ("checkpoints", "strategies", "klines")


def resolve_cache_dir(raw: str | None = None) -> str:
    """将配置路径展开为绝对路径；相对路径相对于 backend 根目录。"""
    value = raw or str(DEFAULT_STOCK_POOL_DIR)
    p = Path(value).expanduser()
    if not p.is_absolute():
        backend_root = Path(__file__).resolve().parents[2]
        p = backend_root / p
    return str(p.resolve())


def ensure_cache_layout(cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    for name in CACHE_SUBDIRS:
        os.makedirs(os.path.join(cache_dir, name), exist_ok=True)


def check_cache_access(cache_dir: str) -> dict[str, Any]:
    """检查目录是否存在及当前进程是否可读写。"""
    path = resolve_cache_dir(cache_dir)
    exists = os.path.isdir(path)
    readable = os.access(path, os.R_OK) if exists else False
    writable = os.access(path, os.W_OK) if exists else False
    return {
        "path": path,
        "exists": exists,
        "readable": readable,
        "writable": writable,
        "ok": exists and readable and writable,
    }


def bootstrap_cache(cache_dir: str) -> dict[str, Any]:
    """启动时创建目录结构并返回权限状态。"""
    path = resolve_cache_dir(cache_dir)
    try:
        ensure_cache_layout(path)
        status = check_cache_access(path)
        status["subdirs"] = list(CACHE_SUBDIRS)
        return status
    except OSError as e:
        return {
            "path": path,
            "exists": os.path.isdir(path),
            "readable": False,
            "writable": False,
            "ok": False,
            "error": str(e),
        }
