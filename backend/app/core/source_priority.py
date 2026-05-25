"""Resolve data source try-order from settings or defaults."""
from __future__ import annotations

from typing import Callable

from app.core.config import settings

SOURCE_FUNCS: dict[str, str] = {
    "eastmoney": "get_from_eastmoney",
    "akshare": "get_from_akshare",
    "baostock": "get_from_baostock",
}


def get_ordered_source_names() -> list[str]:
    try:
        from app.services.workflow_memory import get_workflow_service

        priority = get_workflow_service().get_preference("data_source_priority")
        if isinstance(priority, list) and priority:
            ordered = [s for s in priority if s in SOURCE_FUNCS]
            for name in settings.DATA_SOURCES:
                if name not in ordered:
                    ordered.append(name)
            return ordered
    except Exception:
        pass
    return list(settings.DATA_SOURCES)


def build_source_list(
    fetcher: object,
    explicit: str | None = None,
) -> list[tuple[str, Callable]]:
    """Return (name, callable) pairs in configured order."""
    mapping = {
        "eastmoney": fetcher.get_from_eastmoney,
        "akshare": fetcher.get_from_akshare,
        "baostock": fetcher.get_from_baostock,
    }
    if explicit and explicit in mapping:
        return [(explicit, mapping[explicit])]
    names = get_ordered_source_names()
    return [(n, mapping[n]) for n in names if n in mapping]
