"""P1 strategy research helpers: generation, batch backtest, version diff."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta
from typing import Any

from app.models.strategy_spec import ConditionSpec, RankingSpec, StrategySpec
from app.services.intent_parser import parse_intent_to_strategy_spec
from app.services.intelligent_screener import run_intelligent_screening
from app.services.llm_intent_parser import (
    ALLOWED_FACTORS,
    LLMIntentParserUnavailable,
    is_llm_intent_parser_enabled,
    parse_intent_with_deepseek,
)
from app.services.strategy_backtest import run_in_sample_out_sample_backtest, run_strategy_backtest
from app.services.strategy_library import save_evaluation, save_strategy
from app.services.strategy_rating import rate_strategy


QUALITY_SCORE = {"A": 100, "B": 80, "C": 50, "D": 20}


def clarify_strategy_goal(text: str) -> dict[str, Any]:
    """Return missing pieces before generating multiple strategies."""
    normalized = text.strip()
    questions: list[str] = []
    missing: list[str] = []
    if not any(x in normalized for x in ["短线", "中线", "长线", "短期", "长期", "波段"]):
        missing.append("horizon")
        questions.append("策略主要服务短线、中线还是长线？")
    if not any(x in normalized for x in ["主板", "创业板", "科创板", "北交所", "全市场", "自选"]):
        missing.append("universe")
        questions.append("股票池使用全市场、指定板块还是自选股？")
    if not any(x in normalized for x in ["稳健", "进攻", "激进", "低回撤", "低波动", "止损", "回撤"]):
        missing.append("risk_preference")
        questions.append("风险偏好是稳健低回撤、平衡还是进攻型？")
    return {
        "need_clarification": bool(questions),
        "missing_fields": missing,
        "questions": questions,
    }


def validate_strategy_spec(spec: StrategySpec | dict[str, Any]) -> dict[str, Any]:
    """Validate StrategySpec against executable local factor boundaries."""
    try:
        parsed = spec if isinstance(spec, StrategySpec) else StrategySpec(**spec)
    except Exception as exc:
        return {"valid": False, "errors": [str(exc)], "warnings": [], "unsupported_factors": []}

    errors: list[str] = []
    warnings: list[str] = []
    factors = [c.factor for c in parsed.entry_conditions] + [r.factor for r in parsed.ranking]
    unsupported = sorted({factor for factor in factors if factor not in ALLOWED_FACTORS})
    if unsupported:
        errors.append(f"存在系统不支持的因子: {', '.join(unsupported)}")
    if not parsed.entry_conditions:
        errors.append("至少需要一个入场条件")
    if not parsed.ranking:
        warnings.append("缺少排序规则，系统会默认按20日收益和量比排序")
    if parsed.position.max_positions <= 0:
        errors.append("最大持仓数必须大于0")
    if parsed.risk_filters.quality_level and "D" in parsed.risk_filters.quality_level:
        warnings.append("策略允许D级数据，可能影响回测和选股可信度")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "unsupported_factors": unsupported,
        "normalized_spec": parsed.model_dump(mode="json"),
    }


def _apply_variant(base: StrategySpec, idx: int, goal: str) -> StrategySpec:
    spec = copy.deepcopy(base)
    variants = [
        ("趋势突破", "breakout_20d_high", "eq", True, "return_20d", "desc", "daily"),
        ("回踩确认", "pullback_to_ma20", "eq", True, "volume_ratio_5_20", "desc", "weekly"),
        ("低波动动量", "volatility_20d", "lt", 0.08, "return_60d", "desc", "weekly"),
        ("均线多头", "ma_bullish_alignment", "eq", True, "price_position_60d", "desc", "weekly"),
        ("RSI修复", "rsi6", "lt", 45, "return_5d", "desc", "daily"),
    ]
    label, factor, op, value, rank_factor, direction, rebalance = variants[idx % len(variants)]
    spec.name = f"{goal[:18] or '策略目标'}-{label}"
    spec.description = f"候选策略：{label}；只使用系统已有因子，可直接回测。"
    spec.source = "generated"
    spec.status = "generated"
    spec.tags = list(dict.fromkeys([*spec.tags, "p1_candidate", label]))
    if not any(c.factor == factor for c in spec.entry_conditions):
        spec.entry_conditions.append(ConditionSpec(factor=factor, op=op, value=value, weight=1.0))
    spec.ranking = [
        RankingSpec(factor=rank_factor, direction=direction, weight=0.6),
        RankingSpec(factor="volume_ratio_5_20", direction="desc", weight=0.4),
    ]
    spec.rebalance = rebalance
    spec.version = "1.0.0"
    return spec


def generate_candidate_strategies(
    goal: str,
    count: int = 4,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Generate 3-5 executable candidate strategies for one research goal."""
    text = goal.strip()
    count = max(3, min(5, count))
    clarify = clarify_strategy_goal(text)
    strategies: list[dict[str, Any]] = []
    warnings: list[str] = []
    parser = "rule"

    styles = ["趋势突破", "回踩确认", "低波动动量", "均线多头", "RSI修复"]
    for idx in range(count):
        prompt = f"{text}，生成一个{styles[idx]}候选策略，只使用系统已有因子"
        try:
            if use_llm and is_llm_intent_parser_enabled():
                spec = parse_intent_with_deepseek(prompt)
                parser = "deepseek"
            else:
                raise LLMIntentParserUnavailable("DeepSeek not configured")
        except Exception as exc:
            if use_llm and is_llm_intent_parser_enabled():
                warnings.append(f"候选{idx + 1} DeepSeek生成失败，已使用规则候选：{str(exc)[:100]}")
            base = parse_intent_to_strategy_spec(text)
            spec = _apply_variant(base, idx, text)

        validation = validate_strategy_spec(spec)
        if validation["valid"]:
            item = validation["normalized_spec"]
            item["research_hypothesis"] = spec.description or f"{styles[idx]}候选策略"
            strategies.append(item)
        else:
            warnings.extend(validation["errors"])

    return {
        "goal": text,
        "parser": parser,
        "clarification": clarify,
        "strategies": strategies,
        "total": len(strategies),
        "warnings": list(dict.fromkeys(warnings)),
    }


def _flatten_metrics(backtest: dict[str, Any]) -> dict[str, Any]:
    in_metrics = backtest.get("in_sample", {}).get("metrics", {})
    out_metrics = backtest.get("out_sample", {}).get("metrics", {})
    return {
        "in_sample": in_metrics,
        "out_sample": out_metrics,
        "out_sample_annual_return": out_metrics.get("annual_return", 0),
        "out_sample_max_drawdown": out_metrics.get("max_drawdown", 0),
        "out_sample_sharpe": out_metrics.get("sharpe_ratio", 0),
        "out_sample_win_rate": out_metrics.get("win_rate", 0),
        "out_sample_trades": out_metrics.get("total_trades", 0),
    }


def _research_score(metrics: dict[str, Any], data_quality: dict[str, Any], overfit: bool) -> float:
    annual_return = float(metrics.get("out_sample_annual_return") or 0)
    max_drawdown = abs(float(metrics.get("out_sample_max_drawdown") or 0))
    sharpe = float(metrics.get("out_sample_sharpe") or 0)
    win_rate = float(metrics.get("out_sample_win_rate") or 0)
    trades = min(float(metrics.get("out_sample_trades") or 0), 30) / 30
    quality = QUALITY_SCORE.get(data_quality.get("quality_grade"), 50) / 100
    score = annual_return * 100 + sharpe * 12 + win_rate * 20 + trades * 10 + quality * 10 - max_drawdown * 80
    if overfit:
        score -= 40
    return round(score, 2)


def batch_backtest_strategies(
    specs: list[StrategySpec | dict[str, Any]],
    objective: str = "out_sample_sharpe",
    save_recommended: bool = False,
    top_n: int = 2,
) -> dict[str, Any]:
    """Backtest many candidate specs and return a ranked shortlist."""
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(specs):
        validation = validate_strategy_spec(raw)
        if not validation["valid"]:
            rows.append({
                "index": index,
                "status": "invalid",
                "errors": validation["errors"],
                "score": -999,
            })
            continue
        spec = StrategySpec(**validation["normalized_spec"])
        try:
            screening = run_intelligent_screening(spec)
            candidates = [item.model_dump(mode="json") for item in screening.candidates]
            if not candidates:
                rows.append({
                    "index": index,
                    "name": spec.name,
                    "status": "rejected",
                    "reason": "选股结果为空",
                    "score": -100,
                    "strategy_spec": spec.model_dump(mode="json"),
                })
                continue
            backtest = run_in_sample_out_sample_backtest(spec, candidates)
            metrics = _flatten_metrics(backtest)
            rating = rate_strategy(
                backtest["in_sample"]["metrics"],
                backtest["out_sample"]["metrics"],
                backtest["overfit_flag"],
            )
            data_quality = backtest["out_sample"].get("data_quality_summary") or screening.data_quality_summary or {}
            score = _research_score(metrics, data_quality, backtest["overfit_flag"])
            qualified = (
                not backtest["overfit_flag"]
                and float(metrics.get("out_sample_annual_return") or 0) > 0
                and float(metrics.get("out_sample_sharpe") or 0) > 0
                and rating.get("rating") in {"A", "B", "C"}
            )
            rows.append({
                "index": index,
                "name": spec.name,
                "status": "qualified" if qualified else "filtered",
                "reason": rating.get("reason") or ("通过" if qualified else "不满足观察条件"),
                "score": score,
                "rating": rating,
                "metrics": metrics,
                "data_quality": data_quality,
                "overfit_flag": backtest["overfit_flag"],
                "overfit_reason": backtest.get("overfit_reason"),
                "signal_count": len(candidates),
                "strategy_spec": spec.model_dump(mode="json"),
                "backtest_result": backtest,
            })
        except Exception as exc:
            rows.append({
                "index": index,
                "name": getattr(raw, "name", None) or (raw.get("name") if isinstance(raw, dict) else f"candidate-{index}"),
                "status": "error",
                "reason": str(exc),
                "score": -999,
            })

    rows.sort(key=lambda item: item.get("score", -999), reverse=True)
    recommended = [row for row in rows if row.get("status") == "qualified"][: max(1, top_n)]
    saved_ids: list[str] = []
    if save_recommended:
        for row in recommended:
            spec_dict = row["strategy_spec"]
            spec_dict["status"] = "backtested"
            spec_dict["rating"] = row.get("rating", {}).get("rating")
            strategy_id = save_strategy(spec_dict)
            save_evaluation(
                strategy_id=strategy_id,
                sample_type="batch_research",
                metrics=row["metrics"],
                rating=spec_dict.get("rating"),
                overfit_flag=bool(row.get("overfit_flag")),
            )
            row["saved_strategy_id"] = strategy_id
            saved_ids.append(strategy_id)

    return {
        "objective": objective,
        "total": len(specs),
        "ranked": rows,
        "recommended": recommended,
        "saved_strategy_ids": saved_ids,
    }


def _screen_candidates(spec: StrategySpec) -> list[dict[str, Any]]:
    screening = run_intelligent_screening(spec)
    return [item.model_dump(mode="json") for item in screening.candidates]


def rolling_backtest_analysis(
    spec: StrategySpec | dict[str, Any],
    window_days: int = 365,
    step_days: int = 180,
) -> dict[str, Any]:
    validation = validate_strategy_spec(spec)
    if not validation["valid"]:
        return {"valid": False, "errors": validation["errors"], "windows": []}
    parsed = StrategySpec(**validation["normalized_spec"])
    candidates = _screen_candidates(parsed)
    end = datetime.now()
    start = end - timedelta(days=max(window_days * 2, 730))
    windows = []
    cursor = start
    while cursor + timedelta(days=window_days) <= end:
        w_start = cursor.strftime("%Y-%m-%d")
        w_end = (cursor + timedelta(days=window_days)).strftime("%Y-%m-%d")
        result = run_strategy_backtest(parsed, candidates, w_start, w_end)
        metrics = result.get("metrics") or {}
        windows.append(
            {
                "start": w_start,
                "end": w_end,
                "annual_return": metrics.get("annual_return", 0),
                "max_drawdown": metrics.get("max_drawdown", 0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                "win_rate": metrics.get("win_rate", 0),
                "trade_count": metrics.get("total_trades", 0),
                "data_quality_summary": result.get("data_quality_summary") or {},
            }
        )
        cursor += timedelta(days=step_days)
    positive = len([w for w in windows if float(w.get("annual_return") or 0) > 0])
    return {
        "valid": True,
        "strategy_name": parsed.name,
        "window_days": window_days,
        "step_days": step_days,
        "windows": windows,
        "stability": {
            "positive_window_ratio": round(positive / len(windows), 4) if windows else 0,
            "window_count": len(windows),
        },
    }


def parameter_sensitivity_analysis(
    spec: StrategySpec | dict[str, Any],
    factor: str | None = None,
    multipliers: list[float] | None = None,
) -> dict[str, Any]:
    validation = validate_strategy_spec(spec)
    if not validation["valid"]:
        return {"valid": False, "errors": validation["errors"], "rows": []}
    parsed = StrategySpec(**validation["normalized_spec"])
    multipliers = multipliers or [0.8, 0.9, 1.0, 1.1, 1.2]
    numeric_conditions = [
        cond for cond in parsed.entry_conditions
        if isinstance(cond.value, (int, float)) and (factor is None or cond.factor == factor)
    ]
    if not numeric_conditions:
        return {"valid": True, "strategy_name": parsed.name, "rows": [], "message": "没有可做敏感性分析的数值型入场条件"}

    rows = []
    for cond in numeric_conditions[:3]:
        for mul in multipliers:
            candidate = copy.deepcopy(parsed)
            for item in candidate.entry_conditions:
                if item.factor == cond.factor and item.op == cond.op and item.value == cond.value:
                    item.value = round(float(cond.value) * float(mul), 6)
                    break
            candidates = _screen_candidates(candidate)
            result = run_in_sample_out_sample_backtest(candidate, candidates) if candidates else {}
            metrics = _flatten_metrics(result) if result else {}
            rows.append(
                {
                    "factor": cond.factor,
                    "op": cond.op,
                    "base_value": cond.value,
                    "multiplier": mul,
                    "test_value": round(float(cond.value) * float(mul), 6),
                    "signal_count": len(candidates),
                    "out_sample_annual_return": metrics.get("out_sample_annual_return", 0),
                    "out_sample_sharpe": metrics.get("out_sample_sharpe", 0),
                    "out_sample_max_drawdown": metrics.get("out_sample_max_drawdown", 0),
                    "overfit_flag": bool(result.get("overfit_flag")) if result else False,
                }
            )
    return {"valid": True, "strategy_name": parsed.name, "rows": rows}


def market_state_backtest_analysis(spec: StrategySpec | dict[str, Any]) -> dict[str, Any]:
    validation = validate_strategy_spec(spec)
    if not validation["valid"]:
        return {"valid": False, "errors": validation["errors"], "states": []}
    parsed = StrategySpec(**validation["normalized_spec"])
    candidates = _screen_candidates(parsed)
    end = datetime.now()
    periods = [
        ("long_history", end - timedelta(days=730), end - timedelta(days=365)),
        ("recent", end - timedelta(days=365), end),
    ]
    states = []
    for label, start, stop in periods:
        result = run_strategy_backtest(parsed, candidates, start.strftime("%Y-%m-%d"), stop.strftime("%Y-%m-%d"))
        metrics = result.get("metrics") or {}
        states.append(
            {
                "state": label,
                "start": start.strftime("%Y-%m-%d"),
                "end": stop.strftime("%Y-%m-%d"),
                "annual_return": metrics.get("annual_return", 0),
                "max_drawdown": metrics.get("max_drawdown", 0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                "win_rate": metrics.get("win_rate", 0),
                "trade_count": metrics.get("total_trades", 0),
            }
        )
    return {"valid": True, "strategy_name": parsed.name, "states": states}


def _normalize_conditions(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {f"{item.get('factor')}:{idx}": item for idx, item in enumerate(items or [])}


def compare_strategy_specs(current: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Compare two StrategySpec dictionaries by decision-relevant fields."""
    entry_current = _normalize_conditions(current.get("entry_conditions", []))
    entry_candidate = _normalize_conditions(candidate.get("entry_conditions", []))
    current_keys = set(entry_current)
    candidate_keys = set(entry_candidate)
    changed_entries = []
    for key in sorted(current_keys & candidate_keys):
        before = entry_current[key]
        after = entry_candidate[key]
        if before != after:
            changed_entries.append({"field": key, "before": before, "after": after})

    return {
        "summary": {
            "name": {"before": current.get("name"), "after": candidate.get("name")},
            "version": {"before": current.get("version"), "after": candidate.get("version")},
            "horizon": {"before": current.get("horizon"), "after": candidate.get("horizon")},
            "rebalance": {"before": current.get("rebalance"), "after": candidate.get("rebalance")},
        },
        "entry_conditions": {
            "added": [entry_candidate[k] for k in sorted(candidate_keys - current_keys)],
            "removed": [entry_current[k] for k in sorted(current_keys - candidate_keys)],
            "changed": changed_entries,
        },
        "ranking": {
            "before": current.get("ranking", []),
            "after": candidate.get("ranking", []),
            "changed": current.get("ranking", []) != candidate.get("ranking", []),
        },
        "position": {
            "before": current.get("position", {}),
            "after": candidate.get("position", {}),
            "changed": current.get("position", {}) != candidate.get("position", {}),
        },
        "exit_conditions": {
            "before": current.get("exit_conditions", []),
            "after": candidate.get("exit_conditions", []),
            "changed": current.get("exit_conditions", []) != candidate.get("exit_conditions", []),
        },
        "risk_filters": {
            "before": current.get("risk_filters", {}),
            "after": candidate.get("risk_filters", {}),
            "changed": current.get("risk_filters", {}) != candidate.get("risk_filters", {}),
        },
    }
