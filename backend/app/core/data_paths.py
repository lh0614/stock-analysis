"""PRD2 数据仓目录布局。"""
from __future__ import annotations

import os
from pathlib import Path

from app.core.config import settings

DATA_SUBDIRS = (
    "raw/eastmoney/klines",
    "raw/akshare/klines",
    "raw/baostock/klines",
    "curated",
    "quality",
    "backtests/runs",
    "exports",
)


def data_root() -> str:
    return os.path.join(settings.CACHE_DIR, "data")


def curated_dir() -> str:
    return os.path.join(data_root(), "curated")


def quality_dir() -> str:
    return os.path.join(data_root(), "quality")


def raw_klines_dir(source: str) -> str:
    return os.path.join(data_root(), "raw", source, "klines")


def daily_bars_path() -> str:
    return os.path.join(curated_dir(), "daily_bars.parquet")


def stock_universe_parquet_path() -> str:
    return os.path.join(curated_dir(), "stock_universe.parquet")


def factors_path() -> str:
    return os.path.join(curated_dir(), "factors.parquet")


def quality_report_path() -> str:
    return os.path.join(quality_dir(), "daily_quality_report.parquet")


def source_compare_report_path() -> str:
    return os.path.join(quality_dir(), "source_compare_report.parquet")


def trade_calendar_path() -> str:
    return os.path.join(curated_dir(), "trade_calendar.parquet")


def events_path() -> str:
    return os.path.join(curated_dir(), "events.parquet")


def fundamentals_path() -> str:
    return os.path.join(curated_dir(), "fundamentals.parquet")


def valuation_path() -> str:
    return os.path.join(curated_dir(), "valuation.parquet")


def backtest_runs_dir() -> str:
    return os.path.join(data_root(), "backtests", "runs")


def ensure_data_layout() -> None:
    root = data_root()
    os.makedirs(root, exist_ok=True)
    for sub in DATA_SUBDIRS:
        os.makedirs(os.path.join(root, sub), exist_ok=True)


def path_exists(path: str) -> bool:
    return os.path.isfile(path)
