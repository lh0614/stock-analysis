"""DeepSeek-powered intent parser with deterministic fallback boundaries."""
from __future__ import annotations

import json
import re
from typing import Any

import requests

from app.core.config import settings
from app.models.strategy_spec import StrategySpec

ALLOWED_FACTORS = {
    "breakout_20d_high",
    "volume_ratio_5_20",
    "close_above_ma20",
    "pullback_to_ma20",
    "price_position_60d",
    "ma_bullish_alignment",
    "macd_hist",
    "rsi6",
    "rsi12",
    "rsi24",
    "return_1d",
    "return_5d",
    "return_20d",
    "return_60d",
    "volatility_20d",
    "volatility_60d",
    "ma5",
    "ma10",
    "ma20",
    "ma60",
    "close",
}
ALLOWED_BOARDS = {"main", "chinext", "star", "bse"}
ALLOWED_WEIGHTING = {"equal_weight", "score_weight", "volatility_inverse"}


class LLMIntentParserUnavailable(RuntimeError):
    """Raised when the LLM parser cannot be used."""


def is_llm_intent_parser_enabled() -> bool:
    return bool(settings.INTENT_LLM_ENABLED and settings.DEEPSEEK_API_KEY.strip())


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def _system_prompt() -> str:
    allowed_factors = ", ".join(sorted(ALLOWED_FACTORS))
    return f"""
你是 A 股本地股票分析系统的策略解析器。你的任务是把用户中文选股要求转换为严格 JSON。

只输出一个 JSON 对象，不要输出 markdown、解释或额外文本。

JSON 必须符合 StrategySpec 的核心字段：
{{
  "name": string,
  "description": string,
  "source": "generated",
  "intent_text": string,
  "horizon": "short" | "medium" | "long",
  "universe": {{
    "market": "A股",
    "exclude_st": boolean,
    "boards": ["main" | "chinext" | "star" | "bse"],
    "custom_symbols": null,
    "use_watchlist": boolean
  }},
  "entry_conditions": [
    {{"factor": string, "op": "gt"|"lt"|"eq"|"gte"|"lte"|"in"|"not_in", "value": any, "weight": number}}
  ],
  "ranking": [
    {{"factor": string, "direction": "asc"|"desc", "weight": number}}
  ],
  "exit_conditions": [
    {{"type": "stop_loss"|"stop_profit"|"trailing_stop"|"time_exit"|"signal_exit", "params": object}}
  ],
  "risk_filters": {{
    "quality_level": ["A","B","C"],
    "min_avg_amount_20d": number,
    "max_volatility_60d": number|null
  }},
  "position": {{
    "max_positions": integer,
    "weighting": "equal_weight"|"score_weight"|"volatility_inverse",
    "max_single_position": number
  }},
  "rebalance": "daily"|"weekly"|"monthly",
  "version": "1.0.0",
  "status": "generated",
  "tags": ["llm_intent_parsed"]
}}

允许使用的 factor 只能来自：
{allowed_factors}

解析要求：
1. 不确定时使用保守默认值，不要创造新 factor。
2. 短线 rebalance 用 daily，中线用 weekly，长线用 monthly。
3. 默认排除 ST。
4. 默认至少包含一个止损规则 stop_loss_pct。
5. 用户提到止盈、回撤、低波动、仓位、股票数量、板块时要映射到对应字段。
6. 如果用户要求无法完全表达，仍输出最接近的可执行 StrategySpec，并在 description 中说明保守假设。
""".strip()


def _sanitize_spec_dict(data: dict[str, Any], text: str) -> dict[str, Any]:
    data["source"] = "generated"
    data["intent_text"] = text
    data["status"] = "generated"
    data["version"] = data.get("version") or "1.0.0"
    data["tags"] = list(dict.fromkeys([*(data.get("tags") or []), "llm_intent_parsed"]))

    universe = data.setdefault("universe", {})
    universe["market"] = "A股"
    boards = [b for b in universe.get("boards", []) if b in ALLOWED_BOARDS]
    universe["boards"] = boards or ["main", "chinext", "star"]
    universe["exclude_st"] = bool(universe.get("exclude_st", True))
    universe["use_watchlist"] = bool(universe.get("use_watchlist", False))
    universe.setdefault("custom_symbols", None)

    data["entry_conditions"] = [
        cond
        for cond in data.get("entry_conditions", [])
        if isinstance(cond, dict) and cond.get("factor") in ALLOWED_FACTORS
    ]
    data["ranking"] = [
        rank
        for rank in data.get("ranking", [])
        if isinstance(rank, dict) and rank.get("factor") in ALLOWED_FACTORS
    ]
    if not data["ranking"]:
        data["ranking"] = [
            {"factor": "return_20d", "direction": "desc", "weight": 0.6},
            {"factor": "volume_ratio_5_20", "direction": "desc", "weight": 0.4},
        ]

    risk = data.setdefault("risk_filters", {})
    risk["quality_level"] = [x for x in risk.get("quality_level", ["A", "B", "C"]) if x in {"A", "B", "C", "D"}] or ["A", "B", "C"]
    risk["min_avg_amount_20d"] = float(risk.get("min_avg_amount_20d") or 1e8)

    position = data.setdefault("position", {})
    max_positions = int(position.get("max_positions") or 10)
    max_positions = max(1, min(100, max_positions))
    position["max_positions"] = max_positions
    if position.get("weighting") not in ALLOWED_WEIGHTING:
        position["weighting"] = "equal_weight"
    position["max_single_position"] = float(position.get("max_single_position") or min(0.2, 1 / max_positions))
    position["max_single_position"] = max(0.01, min(1.0, position["max_single_position"]))

    if not data.get("exit_conditions"):
        data["exit_conditions"] = [{"type": "stop_loss", "params": {"stop_loss_pct": 0.08}}]

    return data


def parse_intent_with_deepseek(text: str, overrides: dict[str, Any] | None = None) -> StrategySpec:
    if not is_llm_intent_parser_enabled():
        raise LLMIntentParserUnavailable("DeepSeek intent parser is not configured")

    url = settings.DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": text.strip()},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=settings.DEEPSEEK_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    spec_dict = _sanitize_spec_dict(_extract_json_object(content), text)
    if overrides:
        for key, value in overrides.items():
            if value is not None:
                spec_dict[key] = value
    return StrategySpec(**spec_dict)
