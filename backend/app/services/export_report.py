"""分析/选股/回测导出。"""
from __future__ import annotations

import json
from typing import Any

from app.services.backtest import get_run as get_backtest_run
from app.services.pipeline import get_pipeline
from app.services.screener import get_screener_service
from app.services.daily_review_report import export_analysis_markdown, build_daily_review_report


def export_analysis_run(run_id: str, fmt: str = "json") -> dict[str, Any]:
    run = get_pipeline().get_run(run_id)
    if not run:
        raise ValueError("分析运行不存在")
    if fmt == "markdown":
        return {"format": "markdown", "content": export_analysis_markdown(run)}
    return {"format": "json", "data": run}


def export_screener_csv(run_id: str) -> dict[str, Any]:
    data = get_screener_service().get_run_results(run_id, 1, 5000)
    return {"format": "csv", "items": data.get("items") or []}


def export_daily_review() -> dict[str, Any]:
    return {"format": "json", "data": build_daily_review_report()}
