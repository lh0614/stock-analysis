"""Analysis direction (bias + evidence) for short / medium / long horizons."""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.services.technical import records_to_df, compute_indicators, latest_ma


DISCLAIMER = "分析结论仅供参考，不构成投资建议"


def _bias_from_score(score: float) -> str:
    if score >= 0.25:
        return "bullish"
    if score <= -0.25:
        return "bearish"
    return "neutral"


def _confidence(score: float) -> int:
    return int(min(95, max(35, 50 + abs(score) * 80)))


def _horizon_direction(
    horizon: str,
    df: pd.DataFrame,
    indicators: dict[str, Any],
    price_info: dict[str, Any],
) -> dict[str, Any]:
    close = df["close"]
    latest = float(close.iloc[-1])
    evidence: list[dict[str, Any]] = []
    contradictions: list[str] = []
    score = 0.0

    ma = indicators.get("ma") or {}
    macd = indicators.get("macd") or {}
    rsi = indicators.get("rsi") or {}

    if horizon == "short":
        if macd.get("macd") is not None:
            if macd["macd"] > 0:
                score += 0.35
                evidence.append({"type": "indicator", "name": "MACD", "value": "柱状线为正值", "weight": 0.35})
            else:
                score -= 0.35
                evidence.append({"type": "indicator", "name": "MACD", "value": "柱状线为负值", "weight": 0.35})

        r12 = rsi.get("rsi12")
        if r12 is not None:
            if r12 > 70:
                contradictions.append(f"RSI12={r12} 处于超买区")
                score -= 0.15
            elif r12 < 30:
                evidence.append({"type": "indicator", "name": "RSI12", "value": f"{r12} 超卖反弹机会", "weight": 0.25})
                score += 0.25
            else:
                evidence.append({"type": "indicator", "name": "RSI12", "value": str(r12), "weight": 0.15})

        ma5 = ma.get("ma5")
        if ma5 is not None:
            if latest > ma5:
                score += 0.2
                evidence.append({"type": "price", "name": "MA5", "value": "价格在 MA5 上方", "weight": 0.2})
            else:
                score -= 0.2
                evidence.append({"type": "price", "name": "MA5", "value": "价格在 MA5 下方", "weight": 0.2})

        summary = "短线动能" + ("偏强" if score > 0.15 else "偏弱" if score < -0.15 else "震荡")

    elif horizon == "medium":
        ma20 = ma.get("ma20")
        if ma20 is not None:
            if latest > ma20:
                score += 0.35
                evidence.append({"type": "trend", "name": "MA20", "value": "中期趋势向上", "weight": 0.35})
            else:
                score -= 0.35
                evidence.append({"type": "trend", "name": "MA20", "value": "中期趋势向下", "weight": 0.35})

        if len(close) >= 30:
            ret30 = (latest - float(close.iloc[-30])) / float(close.iloc[-30])
            evidence.append(
                {
                    "type": "return",
                    "name": "30日涨跌",
                    "value": f"{ret30 * 100:.2f}%",
                    "weight": 0.25,
                }
            )
            score += max(-0.3, min(0.3, ret30 * 2))

        pos = price_info.get("position_pct")
        if pos is not None and pos > 80:
            contradictions.append("价格接近区间上沿，波段或遇阻")
        summary = "中线波段" + ("看多" if score > 0.15 else "看空" if score < -0.15 else "整理")

    else:  # long
        ma60 = ma.get("ma60")
        if ma60 is not None and len(close) >= 60:
            if latest > ma60:
                score += 0.3
                evidence.append({"type": "trend", "name": "MA60", "value": "长期均线之上", "weight": 0.3})
            else:
                score -= 0.3
                evidence.append({"type": "trend", "name": "MA60", "value": "长期均线之下", "weight": 0.3})

        if len(close) >= 120:
            ret120 = (latest - float(close.iloc[-120])) / float(close.iloc[-120])
            evidence.append(
                {
                    "type": "return",
                    "name": "半年涨跌",
                    "value": f"{ret120 * 100:.2f}%",
                    "weight": 0.25,
                }
            )
            score += max(-0.25, min(0.25, ret120))

        evidence.append(
            {
                "type": "note",
                "name": "长线维度",
                "value": "需结合基本面与估值（后续版本补全）",
                "weight": 0.1,
            }
        )
        summary = "长线趋势" + ("偏多" if score > 0.1 else "偏空" if score < -0.1 else "中性")

    bias = _bias_from_score(score)
    return {
        "horizon": horizon,
        "bias": bias,
        "bias_label": {"bullish": "偏多", "bearish": "偏空", "neutral": "震荡"}[bias],
        "confidence": _confidence(score),
        "summary": summary,
        "evidence": evidence[:5],
        "contradictions": contradictions,
        "disclaimer": DISCLAIMER,
    }


def build_directions(
    records: list[dict],
    indicators: dict[str, Any],
    price_info: dict[str, Any],
) -> dict[str, Any]:
    df = records_to_df(records)
    if df.empty:
        return {"short": None, "medium": None, "long": None}

    return {
        "short": _horizon_direction("short", df, indicators, price_info),
        "medium": _horizon_direction("medium", df, indicators, price_info),
        "long": _horizon_direction("long", df, indicators, price_info),
    }


def simple_forecast(records: list[dict], horizon: str) -> dict[str, Any]:
    """Probability band — not a guaranteed target price."""
    df = records_to_df(records)
    if df.empty or len(df) < 20:
        return {"horizon": horizon, "available": False}

    close = df["close"]
    latest = float(close.iloc[-1])
    vol = close.pct_change().dropna().tail(60).std()
    if pd.isna(vol) or vol == 0:
        vol = 0.02

    multipliers = {"short": 2.0, "medium": 4.0, "long": 8.0}
    m = multipliers.get(horizon, 3.0)
    band = latest * vol * m

    return {
        "horizon": horizon,
        "available": True,
        "current": round(latest, 2),
        "low": round(latest - band, 2),
        "high": round(latest + band, 2),
        "probability_note": "基于历史波动估算的参考区间，非预测承诺",
        "disclaimer": DISCLAIMER,
    }
