"""Support / resistance and price structure."""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.services.technical import records_to_df, latest_ma


def compute_price_levels(records: list[dict]) -> dict[str, Any]:
    df = records_to_df(records)
    if df.empty or "close" not in df.columns:
        return {"levels": [], "position_pct": None, "labels": []}

    close = df["close"]
    latest = float(close.iloc[-1])
    high = df["high"] if "high" in df.columns else close
    low = df["low"] if "low" in df.columns else close

    lookback = min(60, len(df))
    recent = df.tail(lookback)

    resistance = float(recent["high"].max())
    support = float(recent["low"].min())

    mas = latest_ma(close)
    levels = [
        {"type": "resistance", "price": round(resistance, 2), "label": f"{lookback}日高点"},
        {"type": "support", "price": round(support, 2), "label": f"{lookback}日低点"},
    ]
    for key in ("ma20", "ma60"):
        if mas.get(key):
            levels.append(
                {
                    "type": "ma",
                    "price": mas[key],
                    "label": key.upper(),
                }
            )

    span = resistance - support
    position_pct = round((latest - support) / span * 100, 1) if span > 0 else 50.0

    labels: list[str] = []
    if latest >= resistance * 0.98:
        labels.append("接近压力位")
    if latest <= support * 1.02:
        labels.append("接近支撑位")
    vol = df["volume"] if "volume" in df.columns else None
    if vol is not None and len(vol) >= 5:
        avg_vol = vol.tail(20).mean()
        if vol.iloc[-1] > avg_vol * 1.5 and close.iloc[-1] > close.iloc[-2]:
            labels.append("放量上涨")
        elif vol.iloc[-1] < avg_vol * 0.7:
            labels.append("缩量整理")

    return {
        "latest_price": round(latest, 2),
        "levels": levels,
        "position_pct": position_pct,
        "labels": labels,
    }
