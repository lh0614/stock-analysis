"""Rule-based intent parser: user text -> StrategySpec.

This is deliberately deterministic. It gives the product a usable no-LLM
baseline, and any future LLM parser should still output the same StrategySpec.
"""
from __future__ import annotations

import re
from typing import Any

from app.models.strategy_spec import (
    ConditionSpec,
    ExitRule,
    RankingSpec,
    RiskFilter,
    StrategySpec,
    UniverseSpec,
)


def _has_any(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def _number_after(text: str, patterns: list[str], default: float) -> float:
    for p in patterns:
        m = re.search(p, text)
        if m:
            try:
                return float(m.group(1))
            except (TypeError, ValueError):
                continue
    return default


def _infer_horizon(text: str) -> str:
    if _has_any(text, ["短线", "短期", "1-5", "1到5", "次日", "几天"]):
        return "short"
    if _has_any(text, ["长线", "长期", "价值", "财务", "估值", "分红"]):
        return "long"
    return "medium"


def _infer_name(text: str, horizon: str) -> str:
    if _has_any(text, ["突破", "新高"]):
        return "智能生成-放量突破策略"
    if _has_any(text, ["回踩", "低吸"]):
        return "智能生成-回踩低吸策略"
    if _has_any(text, ["超跌", "反弹"]):
        return "智能生成-超跌反弹策略"
    if horizon == "long":
        return "智能生成-长线筛选策略"
    return "智能生成-条件选股策略"


def _parse_boards(text: str) -> list[str]:
    boards = []
    if _has_any(text, ["主板"]):
        boards.append("main")
    if _has_any(text, ["创业板"]):
        boards.append("chinext")
    if _has_any(text, ["科创板"]):
        boards.append("star")
    if _has_any(text, ["北交所", "北证"]):
        boards.append("bse")
    return boards or ["main", "chinext", "star"]


def _parse_max_positions(text: str) -> int:
    m = re.search(r"(前|top|Top|TOP)\s*(\d+)", text)
    if m:
        return max(1, min(100, int(m.group(2))))
    m = re.search(r"(\d+)\s*只", text)
    if m:
        return max(1, min(100, int(m.group(1))))
    return 10


def parse_intent_to_strategy_spec(text: str, overrides: dict[str, Any] | None = None) -> StrategySpec:
    """Parse a Chinese stock-screening request into a StrategySpec.

    Supported baseline intents include trend breakout, MA pullback, oversold
    rebound, momentum ranking, and quality/data-risk filters.
    """
    raw = (text or "").strip()
    normalized = raw.lower()
    horizon = _infer_horizon(raw)
    conditions: list[ConditionSpec] = []
    ranking: list[RankingSpec] = []
    exit_rules: list[ExitRule] = []

    if _has_any(raw, ["突破", "新高"]):
        if _has_any(raw, ["20日", "二十日", "20 日"]):
            conditions.append(ConditionSpec(factor="breakout_20d_high", op="eq", value=True, weight=1.0))
        else:
            conditions.append(ConditionSpec(factor="breakout_20d_high", op="eq", value=True, weight=0.8))

    if _has_any(raw, ["放量", "量比", "成交量放大"]):
        threshold = _number_after(raw, [r"量比[^\d]*(\d+(?:\.\d+)?)", r"放量[^\d]*(\d+(?:\.\d+)?)"], 1.5)
        conditions.append(ConditionSpec(factor="volume_ratio_5_20", op="gt", value=threshold, weight=0.8))
        ranking.append(RankingSpec(factor="volume_ratio_5_20", direction="desc", weight=0.4))

    if _has_any(raw, ["回踩", "低吸"]):
        if _has_any(raw, ["ma20", "MA20", "20日线", "20 日线"]):
            conditions.append(ConditionSpec(factor="pullback_to_ma20", op="eq", value=True, weight=1.0))
            conditions.append(ConditionSpec(factor="close_above_ma20", op="eq", value=True, weight=0.8))
        else:
            conditions.append(ConditionSpec(factor="price_position_60d", op="lt", value=0.65, weight=0.8))

    if _has_any(raw, ["站上ma20", "站上MA20", "高于ma20", "高于MA20", "ma20上方", "MA20上方"]):
        conditions.append(ConditionSpec(factor="close_above_ma20", op="eq", value=True, weight=1.0))

    if _has_any(raw, ["均线多头", "多头排列"]):
        conditions.append(ConditionSpec(factor="ma_bullish_alignment", op="eq", value=True, weight=1.0))

    if _has_any(raw, ["超跌", "反弹"]):
        rsi_threshold = _number_after(raw, [r"rsi[^\d]*(\d+(?:\.\d+)?)", r"RSI[^\d]*(\d+(?:\.\d+)?)"], 35)
        conditions.append(ConditionSpec(factor="rsi12", op="lt", value=rsi_threshold, weight=1.0))
        conditions.append(ConditionSpec(factor="price_position_60d", op="lt", value=0.35, weight=0.7))

    if _has_any(raw, ["不超买", "避免超买", "不要超买"]):
        conditions.append(ConditionSpec(factor="rsi12", op="lt", value=70, weight=0.6))

    if _has_any(raw, ["强势", "动量", "涨幅", "相对强"]):
        ranking.append(RankingSpec(factor="return_20d", direction="desc", weight=0.8))

    if _has_any(raw, ["低波动", "稳健", "回撤小"]):
        conditions.append(ConditionSpec(factor="volatility_20d", op="lt", value=0.45, weight=0.5))
        ranking.append(RankingSpec(factor="volatility_20d", direction="asc", weight=0.4))

    if not conditions:
        # Conservative default: trend up but not overbought.
        conditions = [
            ConditionSpec(factor="close_above_ma20", op="eq", value=True, weight=1.0),
            ConditionSpec(factor="rsi12", op="lt", value=70, weight=0.6),
        ]

    if not ranking:
        ranking = [
            RankingSpec(factor="return_20d", direction="desc", weight=0.6),
            RankingSpec(factor="volume_ratio_5_20", direction="desc", weight=0.4),
        ]

    if _has_any(raw, ["止损"]):
        stop_loss = _number_after(raw, [r"止损[^\d]*(\d+(?:\.\d+)?)\s*%?"], 8)
        if stop_loss > 1:
            stop_loss = stop_loss / 100
        exit_rules.append(ExitRule(type="stop_loss", params={"stop_loss_pct": stop_loss}))
    else:
        exit_rules.append(ExitRule(type="stop_loss", params={"stop_loss_pct": 0.08}))

    if _has_any(raw, ["止盈", "目标"]):
        take_profit = _number_after(raw, [r"(?:止盈|目标)[^\d]*(\d+(?:\.\d+)?)\s*%?"], 15)
        if take_profit > 1:
            take_profit = take_profit / 100
        exit_rules.append(ExitRule(type="stop_profit", params={"take_profit_pct": take_profit}))

    max_positions = _parse_max_positions(normalized)
    exclude_st = not _has_any(raw, ["包含ST", "包含 st", "允许ST", "允许 st"])

    spec = StrategySpec(
        name=_infer_name(raw, horizon),
        description="由规则解析器根据用户要求生成，可继续手工调整。",
        source="generated",
        intent_text=raw,
        horizon=horizon,  # type: ignore[arg-type]
        universe=UniverseSpec(
            market="A股",
            exclude_st=exclude_st,
            boards=_parse_boards(raw),
        ),
        entry_conditions=conditions,
        ranking=ranking,
        exit_conditions=exit_rules,
        risk_filters=RiskFilter(
            quality_level=["A", "B", "C"],
            min_avg_amount_20d=1e8,
        ),
        position={
            "max_positions": max_positions,
            "weighting": "equal_weight",
            "max_single_position": min(0.2, 1 / max_positions if max_positions else 0.2),
        },
        rebalance="weekly" if horizon != "short" else "daily",
        status="generated",
        tags=["intent_parsed"],
    )

    if overrides:
        data = spec.model_dump()
        for key, value in overrides.items():
            if value is not None:
                data[key] = value
        spec = StrategySpec(**data)

    return spec
