"""Technical indicator calculations (pandas)."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def records_to_df(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    if "timestamps" in df.columns:
        df["timestamps"] = pd.to_datetime(df["timestamps"])
        df = df.sort_values("timestamps").reset_index(drop=True)
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def latest_ma(close: pd.Series, windows: tuple[int, ...] = (5, 10, 20, 60)) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for w in windows:
        if len(close) < w:
            out[f"ma{w}"] = None
        else:
            out[f"ma{w}"] = round(float(close.rolling(w).mean().iloc[-1]), 4)
    return out


def latest_rsi(close: pd.Series, period: int = 14) -> dict[str, float | None]:
    if len(close) < period + 1:
        return {"rsi6": None, "rsi12": None, "rsi24": None}

    def _rsi(p: int) -> float | None:
        if len(close) < p + 1:
            return None
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(p).mean()
        loss = (-delta.clip(upper=0)).rolling(p).mean()
        rs = gain / loss.replace(0, np.nan)
        val = 100 - (100 / (1 + rs))
        v = val.iloc[-1]
        return round(float(v), 2) if pd.notna(v) else None

    return {"rsi6": _rsi(6), "rsi12": _rsi(12), "rsi24": _rsi(24)}


def latest_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, float | None]:
    if len(close) < slow + signal:
        return {"dif": None, "dea": None, "macd": None}
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = 2 * (dif - dea)
    return {
        "dif": round(float(dif.iloc[-1]), 4),
        "dea": round(float(dea.iloc[-1]), 4),
        "macd": round(float(macd.iloc[-1]), 4),
    }


def compute_indicators(records: list[dict], indicator_list: list[str]) -> dict[str, Any]:
    df = records_to_df(records)
    if df.empty or "close" not in df.columns:
        return {}

    close = df["close"]
    result: dict[str, Any] = {}
    names = {x.strip().lower() for x in indicator_list}

    if "ma" in names:
        result["ma"] = latest_ma(close)
    if "rsi" in names:
        result["rsi"] = latest_rsi(close)
    if "macd" in names:
        result["macd"] = latest_macd(close)

    return result
