"""财务与估值同步（M12）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from app.core.data_paths import fundamentals_path, valuation_path
from app.services.data_store import write_parquet


def sync_fundamentals(symbols: list[str]) -> dict[str, Any]:
    rows = []
    for sym in symbols[:200]:
        code = sym.zfill(6)[:6]
        rows.append(
            {
                "symbol": code,
                "report_period": datetime.now().strftime("%Y-%m-%d"),
                "revenue": None,
                "net_profit": None,
                "roe": None,
                "gross_margin": None,
                "debt_ratio": None,
                "ocf": None,
                "source": "placeholder",
                "updated_at": datetime.now().isoformat(),
            }
        )
    if rows:
        write_parquet(pd.DataFrame(rows), fundamentals_path())
    return {"symbols": len(rows), "path": fundamentals_path()}


def sync_valuation(symbols: list[str]) -> dict[str, Any]:
    rows = []
    for sym in symbols[:200]:
        code = sym.zfill(6)[:6]
        rows.append(
            {
                "symbol": code,
                "trade_date": datetime.now().strftime("%Y-%m-%d"),
                "pe_ttm": None,
                "pb": None,
                "ps": None,
                "dividend_yield": None,
                "updated_at": datetime.now().isoformat(),
            }
        )
    if rows:
        write_parquet(pd.DataFrame(rows), valuation_path())
    return {"symbols": len(rows), "path": valuation_path()}
