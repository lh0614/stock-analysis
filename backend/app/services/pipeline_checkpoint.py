"""Persist partial pipeline state for resume after failure."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.services.workflow_memory import get_workflow_service

CHECKPOINT_DIR = os.path.join(settings.CACHE_DIR, "checkpoints")


def _ensure_dir() -> None:
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)


def save_checkpoint(payload: dict[str, Any]) -> str:
    _ensure_dir()
    run_id = payload["run_id"]
    symbol = payload["symbol"]
    path = os.path.join(CHECKPOINT_DIR, f"{run_id}.json")
    payload["saved_at"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, default=str)
    get_workflow_service().set_preference(
        f"checkpoint_{symbol}",
        {"run_id": run_id, "path": path, "next_stage": payload.get("next_stage")},
    )
    return path


def load_checkpoint(run_id: str) -> dict[str, Any] | None:
    path = os.path.join(CHECKPOINT_DIR, f"{run_id}.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_resumable(symbol: str) -> dict[str, Any] | None:
    meta = get_workflow_service().get_preference(f"checkpoint_{symbol}")
    if not meta or not isinstance(meta, dict):
        return None
    run_id = meta.get("run_id")
    if not run_id:
        return None
    cp = load_checkpoint(run_id)
    if not cp or not cp.get("records"):
        return None
    return cp


def clear_checkpoint(symbol: str, run_id: str | None = None) -> None:
    get_workflow_service().set_preference(f"checkpoint_{symbol}", None)
    if run_id:
        path = os.path.join(CHECKPOINT_DIR, f"{run_id}.json")
        if os.path.isfile(path):
            os.remove(path)
