"""P2 factor adapter built on the existing local Parquet data store."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.services.data_store import read_daily_bars
from app.services.technical import compute_indicators


def _safe_return(close: pd.Series, idx: int, window: int) -> float:
    if idx - window < 0:
        return 0.0
    prev = float(close.iloc[idx - window])
    cur = float(close.iloc[idx])
    return cur / prev - 1 if prev else 0.0


def _build_feature_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    work = df.sort_values("trade_date").reset_index(drop=True).copy()
    close = work["close"].astype(float)
    high = work["high"].astype(float)
    low = work["low"].astype(float)
    volume = work["volume"].astype(float) if "volume" in work.columns else pd.Series([0.0] * len(work))
    returns = close.pct_change().fillna(0)

    records = [
        {
            "timestamps": str(row["trade_date"]),
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row.get("volume") or 0,
        }
        for _, row in work.iterrows()
    ]
    indicators = compute_indicators(records, ["ma", "macd", "rsi"])
    ma = indicators.get("ma") or {}
    macd = indicators.get("macd") or {}
    rsi = indicators.get("rsi") or {}

    rows: list[dict[str, Any]] = []
    for idx, row in work.iterrows():
        start20 = max(0, idx - 19)
        start60 = max(0, idx - 59)
        close20 = close.iloc[start20: idx + 1]
        close60 = close.iloc[start60: idx + 1]
        ret20 = returns.iloc[max(0, idx - 19): idx + 1]
        ret60 = returns.iloc[max(0, idx - 59): idx + 1]
        vol5 = float(volume.iloc[max(0, idx - 4): idx + 1].mean()) if idx >= 4 else 0.0
        vol20 = float(volume.iloc[max(0, idx - 19): idx + 1].mean()) if idx >= 19 else 0.0
        vol60 = float(volume.iloc[max(0, idx - 59): idx + 1].mean()) if idx >= 59 else 0.0
        price_pos = 0.5
        if len(close60) > 1:
            lo = float(close60.min())
            hi = float(close60.max())
            price_pos = (float(close.iloc[idx]) - lo) / (hi - lo + 1e-9)

        ma5 = ma.get("ma5") if idx == len(work) - 1 else float(close.iloc[max(0, idx - 4): idx + 1].mean())
        ma10 = ma.get("ma10") if idx == len(work) - 1 else float(close.iloc[max(0, idx - 9): idx + 1].mean())
        ma20 = ma.get("ma20") if idx == len(work) - 1 else float(close20.mean())
        ma60 = ma.get("ma60") if idx == len(work) - 1 and len(close) >= 60 else float(close60.mean())
        prior_high20 = float(high.iloc[max(0, idx - 20): idx].max()) if idx > 0 else float(high.iloc[idx])
        rows.append(
            {
                "symbol": str(row["symbol"]).zfill(6)[:6] if "symbol" in row else "",
                "trade_date": str(row["trade_date"])[:10],
                "close": float(close.iloc[idx]),
                "return_5d": _safe_return(close, idx, 5),
                "return_20d": _safe_return(close, idx, 20),
                "return_60d": _safe_return(close, idx, 60),
                "volatility_20d": float(ret20.std() * np.sqrt(252)) if len(ret20) >= 10 else 0.0,
                "volatility_60d": float(ret60.std() * np.sqrt(252)) if len(ret60) >= 20 else 0.0,
                "volume_ratio_5_20": vol5 / vol20 if vol20 else 1.0,
                "volume_ratio_20_60": vol20 / vol60 if vol60 else 1.0,
                "rsi6": float(rsi.get("rsi6", 50)) if idx == len(work) - 1 else 50,
                "rsi12": float(rsi.get("rsi12", 50)) if idx == len(work) - 1 else 50,
                "macd": float(macd.get("macd", 0)) if idx == len(work) - 1 else 0.0,
                "macd_signal": float(macd.get("dea", 0)) if idx == len(work) - 1 else 0.0,
                "ma5": float(ma5 or 0),
                "ma10": float(ma10 or 0),
                "ma20": float(ma20 or 0),
                "ma60": float(ma60 or 0),
                "ma_bullish_alignment": float(close.iloc[idx] > ma5 > ma10 > ma20 > ma60) if ma5 and ma10 and ma20 and ma60 else 0.0,
                "price_position_60d": float(price_pos),
                "high_52w_distance": float(close.iloc[idx] / max(float(high.iloc[max(0, idx - 251): idx + 1].max()), 1e-9) - 1),
                "breakout_20d_high": float(close.iloc[idx] > prior_high20),
                "pullback_to_ma20": float(bool(ma20 and close.iloc[idx] > ma20 and low.iloc[max(0, idx - 4): idx + 1].min() <= ma20 * 1.02)),
            }
        )
    return rows


def get_factor_data_for_symbol(
    symbol: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    lookback_start = start_date
    df = read_daily_bars(symbol=symbol, start_date=lookback_start, end_date=end_date)
    rows = _build_feature_rows(df)
    if start_date:
        rows = [row for row in rows if row["trade_date"] >= start_date]
    if end_date:
        rows = [row for row in rows if row["trade_date"] <= end_date]
    return rows
