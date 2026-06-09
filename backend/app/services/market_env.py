"""市场环境：指数趋势与市场评级。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import akshare as ak

from app.services.data_store import read_daily_bars


def _index_metrics(code: str, name: str) -> dict[str, Any]:
    try:
        df = ak.stock_zh_index_daily(symbol=f"sh{code}" if code.startswith("0") else f"sz{code}")
        if df is None or df.empty:
            return {"name": name, "trend": "unknown"}
        df = df.tail(120)
        close = df["close"].astype(float)
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else ma20
        last = close.iloc[-1]
        chg = (last / close.iloc[-2] - 1) * 100 if len(close) > 1 else 0
        trend = "bullish" if last > ma20 > ma60 else "bearish" if last < ma20 else "neutral"
        return {
            "name": name,
            "close": round(float(last), 2),
            "ma20": round(float(ma20), 2),
            "ma60": round(float(ma60), 2),
            "change_pct": round(chg, 2),
            "trend": trend,
            "signal": "close > ma20" if last > ma20 else "close < ma20",
        }
    except Exception:
        return {"name": name, "trend": "unknown", "error": "fetch_failed"}


def get_indices() -> list[dict[str, Any]]:
    mapping = [
        ("000001", "上证指数"),
        ("399001", "深证成指"),
        ("399006", "创业板指"),
        ("000688", "科创50"),
        ("000300", "沪深300"),
        ("000905", "中证500"),
        ("000852", "中证1000"),
    ]
    return [_index_metrics(c, n) for c, n in mapping]


def compute_regime() -> dict[str, Any]:
    indices = get_indices()
    bearish = sum(1 for i in indices if i.get("trend") == "bearish")
    bullish = sum(1 for i in indices if i.get("trend") == "bullish")
    if bearish >= 4:
        regime = "risk"
        score = max(20, 50 - bearish * 8)
        summary = "多数指数处于弱势，建议降低候选股权重"
    elif bullish >= 4:
        regime = "strong"
        score = min(85, 50 + bullish * 8)
        summary = "指数趋势偏强，可适度提高进攻仓位"
    else:
        regime = "range"
        score = 50
        summary = "市场震荡，宜精选个股、控制仓位"
    evidence = [
        {"name": i["name"], "value": i.get("signal", i.get("trend"))}
        for i in indices[:5]
        if i.get("trend") != "unknown"
    ]
    return {
        "market_regime": regime,
        "score": score,
        "summary": summary,
        "evidence": evidence,
        "indices": indices,
        "updated_at": datetime.now().isoformat(),
    }


def get_breadth() -> dict[str, Any]:
    """市场宽度：上涨/下跌、涨停跌停、新高新低、MA20多头比例。"""
    from app.services.universe import get_universe_service

    symbols = [s["symbol"] for s in get_universe_service().query()][:500]
    up = down = limit_up = limit_down = new_high = new_low = ma_bull = 0
    for sym in symbols:
        df = read_daily_bars(symbol=sym)
        if len(df) < 25:
            continue
        c0 = float(df["close"].iloc[-2])
        c1 = float(df["close"].iloc[-1])
        if c1 > c0:
            up += 1
        elif c1 < c0:
            down += 1
        pct = (c1 / c0 - 1) if c0 else 0
        if pct >= 0.095:
            limit_up += 1
        if pct <= -0.095:
            limit_down += 1
        if c1 >= float(df["close"].tail(20).max()):
            new_high += 1
        if c1 <= float(df["close"].tail(20).min()):
            new_low += 1
        ma20 = float(df["close"].tail(20).mean())
        if c1 > ma20:
            ma_bull += 1
    total = up + down or 1
    return {
        "up_count": up,
        "down_count": down,
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "new_high_20d": new_high,
        "new_low_20d": new_low,
        "ma20_bull_ratio": round(ma_bull / max(1, total), 2),
        "down_ratio": round(down / total, 2),
        "sample_size": total,
    }


def get_sectors() -> list[dict[str, Any]]:
    """本地板块/行业强弱。

    当前股票池若无行业字段，则使用 board 作为可验证分组，避免返回固定假数据。
    """
    from app.services.universe import get_universe_service

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in get_universe_service().query()[:800]:
        name = item.get("industry") or item.get("sector") or item.get("board") or "未分组"
        groups.setdefault(str(name), []).append(item)

    rows: list[dict[str, Any]] = []
    for name, items in groups.items():
        returns_5d: list[float] = []
        returns_20d: list[float] = []
        ma20_bull = 0
        sampled = 0
        for item in items[:120]:
            df = read_daily_bars(symbol=item["symbol"])
            if len(df) < 22:
                continue
            close = df["close"].astype(float)
            last = float(close.iloc[-1])
            returns_5d.append(last / float(close.iloc[-6]) - 1 if len(close) > 6 else 0.0)
            returns_20d.append(last / float(close.iloc[-21]) - 1)
            if last > float(close.tail(20).mean()):
                ma20_bull += 1
            sampled += 1
        if sampled == 0:
            continue
        ret5 = sum(returns_5d) / len(returns_5d) if returns_5d else 0.0
        ret20 = sum(returns_20d) / len(returns_20d) if returns_20d else 0.0
        bull_ratio = ma20_bull / sampled
        if ret20 > 0.05 and bull_ratio >= 0.6:
            strength = "strong"
        elif ret20 < -0.05 or bull_ratio < 0.35:
            strength = "weak"
        else:
            strength = "neutral"
        rows.append(
            {
                "name": name,
                "return_5d": round(ret5, 4),
                "return_20d": round(ret20, 4),
                "ma20_bull_ratio": round(bull_ratio, 2),
                "sample_size": sampled,
                "strength": strength,
            }
        )
    rows.sort(key=lambda x: (x["return_20d"], x["ma20_bull_ratio"]), reverse=True)
    return rows[:30]
