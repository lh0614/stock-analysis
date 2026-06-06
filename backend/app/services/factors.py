"""因子计算与 factors.parquet 写入。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from app.core.data_paths import factors_path
from app.services.data_store import read_daily_bars, read_parquet, write_parquet
from app.services.technical import compute_indicators


def _compute_symbol_factors(symbol: str) -> pd.DataFrame:
    df = read_daily_bars(symbol=symbol)
    if df.empty or len(df) < 30:
        return pd.DataFrame()
    records = [
        {
            "timestamps": str(r["trade_date"]),
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "volume": r.get("volume") or 0,
        }
        for _, r in df.iterrows()
    ]
    ind = compute_indicators(records, ["ma", "macd", "rsi"])
    closes = df["close"].astype(float).values
    rets = np.diff(closes) / closes[:-1] if len(closes) > 1 else np.array([])
    rows = []
    last_date = str(df["trade_date"].iloc[-1])
    ma = ind.get("ma") or {}
    macd = ind.get("macd") or {}
    rsi = ind.get("rsi") or {}
    vol20 = float(df["volume"].tail(20).mean()) if "volume" in df.columns else 0
    vol5 = float(df["volume"].tail(5).mean()) if "volume" in df.columns else 0
    vol_ratio = vol5 / vol20 if vol20 > 0 else 1.0
    ret_20 = (closes[-1] / closes[-21] - 1) if len(closes) > 21 else 0
    ret_60 = (closes[-1] / closes[-61] - 1) if len(closes) > 61 else 0
    hv20 = float(np.std(rets[-20:]) * np.sqrt(252)) if len(rets) >= 20 else 0
    window = closes[-120:] if len(closes) >= 120 else closes
    pct_rank = float((closes[-1] - window.min()) / (window.max() - window.min() + 1e-9))
    base = {
        "symbol": symbol.zfill(6)[:6],
        "trade_date": last_date,
        "updated_at": datetime.now().isoformat(),
    }
    factor_map = {
        "ma5": ma.get("ma5"),
        "ma20": ma.get("ma20"),
        "ma60": ma.get("ma60"),
        "macd": macd.get("macd"),
        "rsi12": rsi.get("rsi12"),
        "volume_ratio": vol_ratio,
        "return_20d": ret_20,
        "return_60d": ret_60,
        "volatility_20d": hv20,
        "price_percentile_120d": pct_rank,
        "close_above_ma20": float(closes[-1] > (ma.get("ma20") or closes[-1])),
    }
    for name, val in factor_map.items():
        if val is None:
            continue
        rows.append({**base, "factor_name": name, "value": float(val)})
    return pd.DataFrame(rows)


def recompute(symbols: list[str] | None = None) -> dict[str, Any]:
    if symbols:
        sym_list = [s.zfill(6)[:6] for s in symbols]
    else:
        df = read_daily_bars()
        sym_list = sorted(df["symbol"].unique().tolist()) if not df.empty else []
    frames = []
    for sym in sym_list:
        part = _compute_symbol_factors(sym)
        if not part.empty:
            frames.append(part)
    if not frames:
        return {"symbols": 0, "rows": 0}
    combined = pd.concat(frames, ignore_index=True)
    write_parquet(combined, factors_path())
    return {"symbols": len(sym_list), "rows": len(combined)}


def get_factor_catalog() -> list[dict[str, str]]:
    return [
        {"name": "ma5", "description": "5 日均线"},
        {"name": "ma20", "description": "20 日均线"},
        {"name": "rsi12", "description": "12 日 RSI"},
        {"name": "return_20d", "description": "20 日收益率"},
        {"name": "volume_ratio", "description": "5 日/20 日均量比"},
        {"name": "volatility_20d", "description": "20 日历史波动率"},
        {"name": "price_percentile_120d", "description": "120 日价格分位"},
    ]


def get_factors_for_symbol(symbol: str) -> dict[str, float]:
    df = read_parquet(factors_path())
    if df.empty:
        recompute([symbol])
        df = read_parquet(factors_path())
    if df.empty:
        return {}
    sub = df[df["symbol"] == symbol.zfill(6)[:6]]
    return {str(r["factor_name"]): float(r["value"]) for _, r in sub.iterrows()}
