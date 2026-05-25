"""Rule-based analysis interpretation (no external LLM; optional via settings)."""
from __future__ import annotations

from typing import Any

DISCLAIMER = (
    "本解读由本地规则引擎根据指标与方向卡自动生成，非大模型输出，可能存在遗漏；"
    "不构成投资建议。"
)

BIAS_ZH = {"bullish": "偏多", "bearish": "偏空", "neutral": "震荡"}


def build_interpretation(
    symbol: str,
    directions: dict[str, Any] | None,
    indicators: dict[str, Any] | None,
    price_levels: dict[str, Any] | None,
    forecasts: dict[str, Any] | None,
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []

    macd = (indicators or {}).get("macd") or {}
    rsi = (indicators or {}).get("rsi") or {}
    ma = (indicators or {}).get("ma") or {}

    if macd.get("macd") is not None:
        citations.append(
            {"source": "MACD", "field": "macd", "value": macd.get("macd")}
        )
    if rsi.get("rsi12") is not None:
        citations.append({"source": "RSI", "field": "rsi12", "value": rsi.get("rsi12")})

    for horizon, label in [("short", "短线"), ("medium", "中线"), ("long", "长线")]:
        d = (directions or {}).get(horizon)
        if not d:
            continue
        bias = d.get("bias", "neutral")
        conf = d.get("confidence", 50)
        evidence = d.get("evidence") or []
        bullets = [e.get("value", "") for e in evidence[:3] if e.get("value")]
        fc = (forecasts or {}).get(horizon) or {}
        text = (
            f"{label}方向{BIAS_ZH.get(bias, bias)}（置信度约 {conf}%）。"
            + ("依据：" + "；".join(bullets) + "。" if bullets else "")
        )
        if fc.get("range_low") is not None and fc.get("range_high") is not None:
            text += f" 预测区间参考 {fc['range_low']}–{fc['range_high']}。"
        sections.append({"horizon": horizon, "label": label, "text": text, "bias": bias})

    pl = price_levels or {}
    levels = pl.get("levels") or []
    supports = [l["price"] for l in levels if l.get("type") == "support"]
    resistances = [l["price"] for l in levels if l.get("type") == "resistance"]
    structure = ""
    if supports or resistances:
        s_txt = f"支撑 {supports[0]}" if supports else ""
        r_txt = f"压力 {resistances[0]}" if resistances else ""
        structure = "价格结构：" + "，".join(filter(None, [s_txt, r_txt])) + "。"

    summary_parts = [s["text"][:40] for s in sections[:2]]
    summary = f"{symbol}：" + (" ".join(summary_parts) if summary_parts else "数据不足，暂无法生成摘要。")
    if structure:
        summary += " " + structure

    return {
        "symbol": symbol,
        "generated_by": "rule_engine",
        "disclaimer": DISCLAIMER,
        "summary": summary,
        "sections": sections,
        "citations": citations,
    }
