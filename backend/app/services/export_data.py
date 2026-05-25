"""Export OHLCV + indicators as CSV or JSON."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from app.core.data_fetcher import StockDataFetcher
from app.core.config import settings
from app.services.technical import records_to_df


def build_export_payload(
    fetcher: StockDataFetcher,
    symbol: str,
    start_date: str | None,
    end_date: str | None,
    include_indicators: bool = True,
) -> dict[str, Any]:
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    result = fetcher.get_stock_data(symbol, start_date, end_date)
    if not result.get("success"):
        raise ValueError(result.get("error", "无数据"))

    records = result["data"]
    df = records_to_df(records)
    if include_indicators and not df.empty and "close" in df.columns:
        close = df["close"]
        df["ma5"] = close.rolling(5).mean()
        df["ma20"] = close.rolling(20).mean()
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=9, adjust=False).mean()
        df["macd"] = 2 * (dif - dea)
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(12).mean()
        loss = (-delta.clip(upper=0)).rolling(12).mean()
        rs = gain / loss.replace(0, pd.NA)
        df["rsi12"] = 100 - (100 / (1 + rs))

    rows = df.to_dict(orient="records")
    for row in rows:
        for k, v in list(row.items()):
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()[:10]
            elif pd.isna(v):
                row[k] = None
            elif isinstance(v, float):
                row[k] = round(v, 4)

    return {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "rows": rows,
        "metadata": result.get("metadata", {}),
    }


def payload_to_csv(payload: dict[str, Any]) -> str:
    rows = payload.get("rows") or []
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def payload_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
