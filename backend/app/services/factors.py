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

    # 基础数据
    closes = df["close"].astype(float).values
    highs = df["high"].astype(float).values
    lows = df["low"].astype(float).values
    volumes = df["volume"].astype(float).values if "volume" in df.columns else np.zeros(len(closes))

    rets = np.diff(closes) / closes[:-1] if len(closes) > 1 else np.array([])
    rows = []
    last_date = str(df["trade_date"].iloc[-1])
    ma = ind.get("ma") or {}
    macd = ind.get("macd") or {}
    rsi = ind.get("rsi") or {}

    # === 量价因子 ===
    vol20 = float(volumes[-20:].mean()) if len(volumes) >= 20 else 0
    vol5 = float(volumes[-5:].mean()) if len(volumes) >= 5 else 0
    vol_ratio = vol5 / vol20 if vol20 > 0 else 1.0

    # === 收益率因子 ===
    ret_1 = (closes[-1] / closes[-2] - 1) if len(closes) > 1 else 0
    ret_5 = (closes[-1] / closes[-6] - 1) if len(closes) > 6 else 0
    ret_20 = (closes[-1] / closes[-21] - 1) if len(closes) > 21 else 0
    ret_60 = (closes[-1] / closes[-61] - 1) if len(closes) > 61 else 0

    # === 波动率因子 ===
    hv20 = float(np.std(rets[-20:]) * np.sqrt(252)) if len(rets) >= 20 else 0
    hv60 = float(np.std(rets[-60:]) * np.sqrt(252)) if len(rets) >= 60 else 0

    # === 价格位置因子 ===
    window_60 = closes[-60:] if len(closes) >= 60 else closes
    price_pos_60d = float((closes[-1] - window_60.min()) / (window_60.max() - window_60.min() + 1e-9))

    # === 突破因子 ===
    high_20d = float(highs[-21:-1].max()) if len(highs) > 21 else float(highs[-1])
    breakout_20d_high = float(closes[-1] > high_20d)

    # === 回踩因子 ===
    ma20_val = ma.get("ma20", 0) or 0
    # 回踩 MA20 不破：当前价格在 MA20 上方，且最近5日内曾接近或略低于 MA20
    pullback_to_ma20 = False
    if ma20_val > 0 and closes[-1] > ma20_val:
        recent_lows = lows[-5:] if len(lows) >= 5 else lows
        # 最近5日最低价在 MA20 的 0.98-1.02 倍之间，视为回踩不破
        pullback_to_ma20 = any(ma20_val * 0.98 <= low <= ma20_val * 1.02 for low in recent_lows)

    # === 均线多头排列 ===
    ma5_val = ma.get("ma5", 0) or 0
    ma10_val = ma.get("ma10", 0) or 0
    ma60_val = ma.get("ma60", 0) or 0
    ma_bullish_alignment = float(
        ma5_val > 0 and ma10_val > 0 and ma20_val > 0 and ma60_val > 0
        and closes[-1] > ma5_val > ma10_val > ma20_val > ma60_val
    )

    # === MACD 因子 ===
    macd_dif = macd.get("dif", 0) or 0
    macd_dea = macd.get("dea", 0) or 0
    macd_hist = macd.get("macd", 0) or 0

    # === RSI 因子 ===
    rsi6 = rsi.get("rsi6", 0) or 0
    rsi12_val = rsi.get("rsi12", 0) or 0
    rsi24 = rsi.get("rsi24", 0) or 0

    base = {
        "symbol": symbol.zfill(6)[:6],
        "trade_date": last_date,
        "updated_at": datetime.now().isoformat(),
    }

    factor_map = {
        # 均线
        "ma5": ma5_val,
        "ma10": ma10_val,
        "ma20": ma20_val,
        "ma60": ma60_val,
        "ma120": ma.get("ma120"),
        "ma250": ma.get("ma250"),

        # 均线相关
        "close_above_ma20": float(closes[-1] > ma20_val) if ma20_val > 0 else 0,
        "ma_bullish_alignment": ma_bullish_alignment,

        # MACD
        "macd_dif": macd_dif,
        "macd_dea": macd_dea,
        "macd_hist": macd_hist,

        # RSI
        "rsi6": rsi6,
        "rsi12": rsi12_val,
        "rsi24": rsi24,

        # 收益率
        "return_1d": ret_1,
        "return_5d": ret_5,
        "return_20d": ret_20,
        "return_60d": ret_60,

        # 波动率
        "volatility_20d": hv20,
        "volatility_60d": hv60,

        # 量比
        "volume_ratio_5_20": vol_ratio,

        # 突破
        "breakout_20d_high": breakout_20d_high,

        # 回踩
        "pullback_to_ma20": float(pullback_to_ma20),

        # 价格位置
        "price_position_60d": price_pos_60d,
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
    """返回因子目录 - PRD P0 技术与量价因子"""
    items = [
        # 均线因子
        {"name": "ma5", "description": "5 日均线", "category": "MA"},
        {"name": "ma10", "description": "10 日均线", "category": "MA"},
        {"name": "ma20", "description": "20 日均线", "category": "MA"},
        {"name": "ma60", "description": "60 日均线", "category": "MA"},
        {"name": "ma120", "description": "120 日均线", "category": "MA"},
        {"name": "ma250", "description": "250 日均线", "category": "MA"},

        # 均线相关因子
        {"name": "close_above_ma20", "description": "收盘价高于MA20", "category": "MA"},
        {"name": "ma_bullish_alignment", "description": "均线多头排列", "category": "MA"},

        # MACD 因子
        {"name": "macd_dif", "description": "MACD DIF", "category": "MACD"},
        {"name": "macd_dea", "description": "MACD DEA", "category": "MACD"},
        {"name": "macd_hist", "description": "MACD 柱状图", "category": "MACD"},

        # RSI 因子
        {"name": "rsi6", "description": "6 日 RSI", "category": "RSI"},
        {"name": "rsi12", "description": "12 日 RSI", "category": "RSI"},
        {"name": "rsi24", "description": "24 日 RSI", "category": "RSI"},

        # 收益率因子
        {"name": "return_1d", "description": "1 日收益率", "category": "Return"},
        {"name": "return_5d", "description": "5 日收益率", "category": "Return"},
        {"name": "return_20d", "description": "20 日收益率", "category": "Return"},
        {"name": "return_60d", "description": "60 日收益率", "category": "Return"},

        # 波动率因子
        {"name": "volatility_20d", "description": "20 日历史波动率", "category": "Volatility"},
        {"name": "volatility_60d", "description": "60 日历史波动率", "category": "Volatility"},

        # 量价因子
        {"name": "volume_ratio_5_20", "description": "5日/20日均量比", "category": "Volume"},

        # 突破因子
        {"name": "breakout_20d_high", "description": "突破20日新高", "category": "Breakout"},

        # 回踩因子
        {"name": "pullback_to_ma20", "description": "回踩MA20不破", "category": "Pullback"},

        # 价格位置因子
        {"name": "price_position_60d", "description": "60日价格分位", "category": "Position"},
    ]
    formulas = {
        "ma5": ("rolling_mean(close, 5)", "price"),
        "ma10": ("rolling_mean(close, 10)", "price"),
        "ma20": ("rolling_mean(close, 20)", "price"),
        "ma60": ("rolling_mean(close, 60)", "price"),
        "ma120": ("rolling_mean(close, 120)", "price"),
        "ma250": ("rolling_mean(close, 250)", "price"),
        "close_above_ma20": ("close > ma20 ? 1 : 0", "bool"),
        "ma_bullish_alignment": ("close > ma5 > ma10 > ma20 > ma60 ? 1 : 0", "bool"),
        "macd_dif": ("EMA(close,12) - EMA(close,26)", "value"),
        "macd_dea": ("EMA(macd_dif,9)", "value"),
        "macd_hist": ("2 * (macd_dif - macd_dea)", "value"),
        "rsi6": ("RSI(close, 6)", "0-100"),
        "rsi12": ("RSI(close, 12)", "0-100"),
        "rsi24": ("RSI(close, 24)", "0-100"),
        "return_1d": ("close / close[-1] - 1", "ratio"),
        "return_5d": ("close / close[-5] - 1", "ratio"),
        "return_20d": ("close / close[-20] - 1", "ratio"),
        "return_60d": ("close / close[-60] - 1", "ratio"),
        "volatility_20d": ("std(daily_return, 20) * sqrt(252)", "annualized_ratio"),
        "volatility_60d": ("std(daily_return, 60) * sqrt(252)", "annualized_ratio"),
        "volume_ratio_5_20": ("mean(volume,5) / mean(volume,20)", "ratio"),
        "breakout_20d_high": ("close > max(high[-20:-1]) ? 1 : 0", "bool"),
        "pullback_to_ma20": ("close > ma20 and recent_low near ma20", "bool"),
        "price_position_60d": ("(close - min(close,60)) / (max(close,60) - min(close,60))", "0-1"),
    }
    for item in items:
        formula, unit = formulas.get(item["name"], ("", ""))
        item["formula"] = formula
        item["unit"] = unit
    return items


def get_factors_for_symbol(symbol: str) -> dict[str, float]:
    df = read_parquet(factors_path())
    if df.empty:
        recompute([symbol])
        df = read_parquet(factors_path())
    if df.empty:
        return {}
    sub = df[df["symbol"] == symbol.zfill(6)[:6]]
    return {str(r["factor_name"]): float(r["value"]) for _, r in sub.iterrows()}


def evaluate_factor_effectiveness(
    factor_name: str,
    horizon: int = 20,
    min_samples: int = 20,
) -> dict[str, Any]:
    """Evaluate a factor by cross-sectional IC/RankIC against forward returns."""
    df = read_parquet(factors_path())
    if df.empty:
        return {"factor": factor_name, "status": "no_data", "samples": 0}
    sub = df[df["factor_name"] == factor_name].copy()
    if sub.empty:
        return {"factor": factor_name, "status": "missing_factor", "samples": 0}

    rows = []
    for _, item in sub.iterrows():
        symbol = str(item["symbol"]).zfill(6)[:6]
        trade_date = str(item["trade_date"])[:10]
        bars = read_daily_bars(symbol=symbol, start_date=trade_date)
        if len(bars) <= horizon:
            continue
        close = bars["close"].astype(float).reset_index(drop=True)
        entry = float(close.iloc[0])
        exit_price = float(close.iloc[horizon])
        if entry <= 0:
            continue
        rows.append(
            {
                "symbol": symbol,
                "trade_date": trade_date,
                "factor_value": float(item["value"]),
                "forward_return": exit_price / entry - 1,
            }
        )
    if len(rows) < min_samples:
        return {"factor": factor_name, "status": "insufficient_samples", "samples": len(rows)}

    out = pd.DataFrame(rows)
    ic = float(out["factor_value"].corr(out["forward_return"], method="pearson") or 0)
    rank_ic = float(out["factor_value"].corr(out["forward_return"], method="spearman") or 0)
    quantiles = []
    try:
        out["bucket"] = pd.qcut(out["factor_value"], q=min(5, len(out)), duplicates="drop")
        grouped = out.groupby("bucket", observed=True)["forward_return"].mean()
        quantiles = [
            {"bucket": str(bucket), "avg_forward_return": round(float(value), 4)}
            for bucket, value in grouped.items()
        ]
    except Exception:
        quantiles = []
    degraded = abs(rank_ic) < 0.02
    return {
        "factor": factor_name,
        "status": "degraded" if degraded else "effective",
        "samples": len(rows),
        "horizon": horizon,
        "ic": round(ic, 4),
        "rank_ic": round(rank_ic, 4),
        "degraded": degraded,
        "warning": "近期 RankIC 接近 0，因子可能衰减" if degraded else None,
        "quantiles": quantiles,
    }


def monitor_factor_decay(factors: list[str] | None = None, horizon: int = 20) -> dict[str, Any]:
    catalog = get_factor_catalog()
    factor_names = factors or [item["name"] for item in catalog if item.get("unit") in {"ratio", "0-1", "0-100", "value"}]
    results = [evaluate_factor_effectiveness(name, horizon=horizon) for name in factor_names[:30]]
    alerts = [item for item in results if item.get("degraded")]
    return {
        "horizon": horizon,
        "total": len(results),
        "alerts": alerts,
        "results": results,
    }
