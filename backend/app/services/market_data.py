"""P2 market feature adapter using existing market environment services."""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.services.data_store import read_daily_bars


def get_market_indicators(trade_date: str | None = None) -> dict[str, Any]:
    df = read_daily_bars()
    if df.empty:
        return {
            "trade_date": trade_date,
            "trend_signal": 0,
            "volatility_percentile": 0.5,
            "volume_ratio": 1.0,
            "industry_momentum": 0.5,
            "market_regime": "unknown",
            "regime_score": 50,
            "breadth": {"sample_size": 0},
        }

    work = df.sort_values("trade_date")
    if trade_date:
        work = work[work["trade_date"].astype(str) <= trade_date]
    latest = work.groupby("symbol").tail(1).head(300)
    prev = work.groupby("symbol").tail(21)
    ret20_values = []
    ma20_bull = 0
    up = down = 0
    vol_values = []
    for symbol, part in prev.groupby("symbol"):
        if len(part) < 2:
            continue
        part = part.sort_values("trade_date")
        close = part["close"].astype(float)
        current = float(close.iloc[-1])
        prior = float(close.iloc[0])
        ret20 = current / prior - 1 if prior else 0.0
        ret20_values.append(ret20)
        if current > float(close.mean()):
            ma20_bull += 1
        if len(close) >= 2:
            if current > float(close.iloc[-2]):
                up += 1
            elif current < float(close.iloc[-2]):
                down += 1
            vol_values.append(float(close.pct_change().dropna().std() or 0))
    sample = max(1, len(ret20_values))
    avg_ret20 = sum(ret20_values) / sample if ret20_values else 0.0
    bull_ratio = ma20_bull / sample
    if avg_ret20 > 0.03 and bull_ratio >= 0.55:
        regime_name = "strong"
        trend_signal = 1
        score = 70
    elif avg_ret20 < -0.03 or bull_ratio <= 0.35:
        regime_name = "risk"
        trend_signal = -1
        score = 35
    else:
        regime_name = "range"
        trend_signal = 0
        score = 50
    volatility_percentile = min(1.0, max(0.0, float(pd.Series(vol_values).rank(pct=True).iloc[-1]) if vol_values else 0.5))
    breadth = {
        "up_count": up,
        "down_count": down,
        "down_ratio": round(down / max(1, up + down), 4),
        "ma20_bull_ratio": round(bull_ratio, 4),
        "sample_size": sample,
    }
    return {
        "trade_date": trade_date,
        "trend_signal": trend_signal,
        "volatility_percentile": volatility_percentile,
        "volume_ratio": 1.0,
        "industry_momentum": bull_ratio,
        "market_regime": regime_name,
        "regime_score": score,
        "breadth": breadth,
    }
