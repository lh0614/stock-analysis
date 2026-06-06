"""pkl → raw → daily_bars.parquet 标准化管道。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import pandas as pd

from app.core.config import settings
from app.core.data_fetcher import StockDataFetcher
from app.core.data_paths import ensure_data_layout, raw_klines_dir
from app.services.data_store import upsert_daily_bars


def _pkl_path(symbol: str) -> str:
    code = symbol.zfill(6)[:6]
    return os.path.join(settings.CACHE_DIR, "klines", f"{code}_full.pkl")


def _df_to_bars(symbol: str, df: pd.DataFrame, source: str = "merged") -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    if "timestamps" in work.columns:
        work["trade_date"] = pd.to_datetime(work["timestamps"]).dt.strftime("%Y-%m-%d")
    elif isinstance(work.index, pd.DatetimeIndex):
        work["trade_date"] = work.index.strftime("%Y-%m-%d")
    else:
        return pd.DataFrame()
    code = symbol.zfill(6)[:6]
    now = datetime.now().isoformat()
    rows = []
    for _, r in work.iterrows():
        try:
            rows.append(
                {
                    "symbol": code,
                    "trade_date": str(r["trade_date"])[:10],
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r.get("volume") or 0),
                    "amount": float(r.get("amount") or 0),
                    "adjust": "qfq",
                    "source": source,
                    "source_count": 1,
                    "quality_level": "B",
                    "updated_at": now,
                }
            )
        except (TypeError, ValueError, KeyError):
            continue
    return pd.DataFrame(rows)


def save_raw_snapshot(symbol: str, source: str, records: list[dict]) -> str:
    ensure_data_layout()
    code = symbol.zfill(6)[:6]
    day = datetime.now().strftime("%Y%m%d")
    dest_dir = os.path.join(raw_klines_dir(source), code)
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, f"{day}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"symbol": code, "source": source, "rows": len(records), "saved_at": datetime.now().isoformat()}, f)
    return path


def ingest_symbol_from_pkl(symbol: str, source: str = "merged") -> dict[str, Any]:
    path = _pkl_path(symbol)
    if not os.path.isfile(path):
        return {"symbol": symbol, "status": "skipped", "reason": "no_pkl"}
    try:
        df = pd.read_pickle(path)
        fetcher = StockDataFetcher(cache_dir=settings.CACHE_DIR)
        df = fetcher.standardize_column_names(df)
        bars = _df_to_bars(symbol, df, source=source)
        if bars.empty:
            return {"symbol": symbol, "status": "failed", "reason": "empty_bars"}
        save_raw_snapshot(symbol, source, bars.to_dict("records"))
        n = upsert_daily_bars(bars)
        return {"symbol": symbol, "status": "ok", "bars": n}
    except Exception as e:
        return {"symbol": symbol, "status": "failed", "error": str(e)}


def ingest_symbols(symbols: list[str]) -> dict[str, Any]:
    ok = failed = skipped = 0
    for sym in symbols:
        r = ingest_symbol_from_pkl(sym)
        st = r.get("status")
        if st == "ok":
            ok += 1
        elif st == "skipped":
            skipped += 1
        else:
            failed += 1
    return {"ok": ok, "failed": failed, "skipped": skipped, "total": len(symbols)}
