"""Cache directory stats and cleanup."""
from __future__ import annotations

import os
import shutil
from typing import Any

from app.core.config import settings


def cache_stats() -> dict[str, Any]:
    root = settings.CACHE_DIR
    total_bytes = 0
    file_count = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                total_bytes += os.path.getsize(path)
                file_count += 1
            except OSError:
                pass
    from app.core.cache_paths import check_cache_access

    access = check_cache_access(root)
    return {
        "cache_dir": access["path"],
        "file_count": file_count,
        "size_mb": round(total_bytes / (1024 * 1024), 2),
        "readable": access["readable"],
        "writable": access["writable"],
    }


def clear_pickles() -> dict[str, Any]:
    root = settings.CACHE_DIR
    removed = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".pkl") or name.endswith(".pickle"):
                try:
                    os.remove(os.path.join(dirpath, name))
                    removed += 1
                except OSError:
                    pass
    return {"removed_files": removed, **cache_stats()}


def clear_all_cache() -> dict[str, Any]:
    root = settings.CACHE_DIR
    os.makedirs(root, exist_ok=True)
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if name == "lsa.db":
            continue
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)
        except OSError:
            pass
    os.makedirs(root, exist_ok=True)
    return cache_stats()
