"""智能选股引擎 - 基于 StrategySpec 的精准选股"""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

import pandas as pd

from app.models.strategy_spec import (
    CandidateStock,
    ConditionSpec,
    ScreenerResult,
    StrategySpec,
)
from app.services.data_quality import get_symbol_quality, get_quality_summary_for_symbols
from app.services.data_store import read_parquet
from app.services.universe import get_universe_service
from app.core.data_paths import factors_path


def _eval_condition(value: Any, condition: ConditionSpec) -> bool:
    """评估单个条件是否满足"""
    if value is None:
        return False

    op = condition.op
    target = condition.value

    if op == "gt":
        return float(value) > float(target)
    elif op == "lt":
        return float(value) < float(target)
    elif op == "gte":
        return float(value) >= float(target)
    elif op == "lte":
        return float(value) <= float(target)
    elif op == "eq":
        if isinstance(target, bool):
            return bool(value) == target
        return value == target
    elif op == "in":
        return value in target
    elif op == "not_in":
        return value not in target
    return False


def _load_factors(symbols: list[str] | None = None) -> pd.DataFrame:
    """加载因子数据"""
    try:
        df = read_parquet(factors_path())
        if df.empty:
            return pd.DataFrame()

        # 转换为宽表格式（每个 symbol 一行，每个 factor 一列）
        pivot = df.pivot_table(
            index=["symbol", "trade_date"],
            columns="factor_name",
            values="value",
            aggfunc="last"
        ).reset_index()

        # 只保留每个股票最新日期的数据
        latest = pivot.sort_values("trade_date").groupby("symbol").tail(1)

        if symbols:
            latest = latest[latest["symbol"].isin(symbols)]

        return latest
    except Exception as e:
        print(f"加载因子数据失败: {e}")
        return pd.DataFrame()


def _calculate_composite_score(
    factor_values: dict[str, Any],
    conditions: list[ConditionSpec],
    ranking: list[Any]
) -> float:
    """计算综合得分"""
    score = 0.0
    total_weight = 0.0

    # 1. 条件满足度得分
    for cond in conditions:
        factor_val = factor_values.get(cond.factor)
        if factor_val is not None and _eval_condition(factor_val, cond):
            score += cond.weight * 10  # 每个满足的条件贡献 10 * weight 分
            total_weight += cond.weight

    # 2. 排序因子得分（归一化到 0-100）
    for rank_spec in ranking:
        factor_val = factor_values.get(rank_spec.factor)
        if factor_val is not None:
            # 简单归一化（实际应该基于全市场分位数）
            normalized = min(100, max(0, float(factor_val) * 10))
            if rank_spec.direction == "desc":
                score += normalized * rank_spec.weight
            else:
                score += (100 - normalized) * rank_spec.weight
            total_weight += rank_spec.weight

    # 归一化到 0-100
    if total_weight > 0:
        score = (score / total_weight) * 10

    return min(100, max(0, score))


def run_intelligent_screening(spec: StrategySpec) -> ScreenerResult:
    """执行智能选股"""
    start_time = time.time()
    run_id = str(uuid.uuid4())

    # 1. 构建股票池
    universe_svc = get_universe_service()

    if spec.universe.use_watchlist:
        # 使用自选股
        from app.core.db import get_conn
        with get_conn() as conn:
            rows = conn.execute("SELECT DISTINCT symbol FROM watchlist_items").fetchall()
        symbols = [r["symbol"] for r in rows]
        universe = universe_svc.query(symbols=symbols) if symbols else []
    elif spec.universe.custom_symbols:
        # 使用自定义股票池
        universe = universe_svc.query(symbols=spec.universe.custom_symbols)
    else:
        # 使用板块过滤
        universe = universe_svc.query(
            include_chinext="chinext" in spec.universe.boards,
            include_star="star" in spec.universe.boards,
            include_bse="bse" in spec.universe.boards,
            exclude_st=spec.universe.exclude_st,
        )

    total_scanned = len(universe)
    print(f"股票池构建完成，共 {total_scanned} 只股票")

    # 2. 加载因子数据
    symbols_in_universe = [s["symbol"] for s in universe]
    factors_df = _load_factors(symbols_in_universe)

    if factors_df.empty:
        print("警告：因子数据为空，无法进行筛选")
        return ScreenerResult(
            run_id=run_id,
            strategy_spec=spec,
            candidates=[],
            total_scanned=total_scanned,
            total_matched=0,
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    # 3. 筛选候选股
    candidates = []

    for stock in universe:
        symbol = stock["symbol"]

        # 获取因子值
        factor_row = factors_df[factors_df["symbol"] == symbol]
        if factor_row.empty:
            continue

        factor_values = factor_row.iloc[0].to_dict()
        signal_trade_date = str(factor_values.get("trade_date", ""))[:10]
        factor_values.pop("symbol", None)
        factor_values.pop("trade_date", None)
        if signal_trade_date:
            factor_values["_trade_date"] = signal_trade_date

        # 评估入场条件
        matched_conditions = []
        all_conditions_met = True

        for cond in spec.entry_conditions:
            factor_val = factor_values.get(cond.factor)
            is_met = _eval_condition(factor_val, cond)

            if is_met:
                matched_conditions.append({
                    "factor": cond.factor,
                    "value": factor_val,
                    "condition": f"{cond.op} {cond.value}",
                    "met": True
                })
            else:
                all_conditions_met = False
                break

        if not all_conditions_met:
            continue

        # 数据质量过滤
        quality = get_symbol_quality(symbol)
        if quality["quality_level"] not in spec.risk_filters.quality_level:
            continue

        # 计算综合得分
        score = _calculate_composite_score(
            factor_values,
            spec.entry_conditions,
            spec.ranking
        )

        # 识别风险
        risks = []
        if quality["quality_level"] in ["C", "D"]:
            risks.append({
                "type": "data_quality",
                "message": f"数据质量为 {quality['quality_level']} 级"
            })

        candidates.append(CandidateStock(
            symbol=symbol,
            name=stock.get("name", symbol),
            score=score,
            rank=0,  # 稍后排序
            quality_level=quality["quality_level"],
            matched_conditions=matched_conditions,
            factor_values=factor_values,
            risks=risks,
            next_actions=["deep_analyze", "backtest", "create_plan"]
        ))

    # 4. 排序和排名
    candidates.sort(key=lambda x: x.score, reverse=True)
    for idx, candidate in enumerate(candidates, 1):
        candidate.rank = idx

    # 5. 限制返回数量
    max_return = spec.position.max_positions * 3  # 返回3倍持仓数量
    candidates = candidates[:max_return]

    # 6. 生成数据质量摘要
    candidate_symbols = [c.symbol for c in candidates]
    data_quality_summary = get_quality_summary_for_symbols(candidate_symbols)

    execution_time_ms = (time.time() - start_time) * 1000

    print(f"选股完成：扫描 {total_scanned} 只，命中 {len(candidates)} 只，耗时 {execution_time_ms:.0f}ms")
    print(f"数据质量：{data_quality_summary['quality_grade']} - {data_quality_summary['recommendation']}")

    return ScreenerResult(
        run_id=run_id,
        strategy_spec=spec,
        candidates=candidates,
        total_scanned=total_scanned,
        total_matched=len(candidates),
        execution_time_ms=execution_time_ms,
        data_quality_summary=data_quality_summary,
    )


def explain_symbol_against_strategy(symbol: str, spec: StrategySpec) -> dict[str, Any]:
    code = symbol.zfill(6)[:6]
    factors_df = _load_factors([code])
    if factors_df.empty:
        return {
            "symbol": code,
            "matched": False,
            "reason": "缺少因子数据",
            "failed_conditions": [],
            "matched_conditions": [],
            "factor_values": {},
        }
    factor_values = factors_df.iloc[0].to_dict()
    factor_values.pop("symbol", None)
    factor_values.pop("trade_date", None)
    matched_conditions = []
    failed_conditions = []
    for cond in spec.entry_conditions:
        value = factor_values.get(cond.factor)
        met = _eval_condition(value, cond)
        item = {
            "factor": cond.factor,
            "value": value,
            "op": cond.op,
            "target": cond.value,
            "met": met,
        }
        if met:
            matched_conditions.append(item)
        else:
            failed_conditions.append({**item, "reason": "因子不满足条件" if value is not None else "缺少该因子"})
    quality = get_symbol_quality(code)
    quality_met = quality["quality_level"] in spec.risk_filters.quality_level
    if not quality_met:
        failed_conditions.append(
            {
                "factor": "data_quality",
                "value": quality["quality_level"],
                "op": "in",
                "target": spec.risk_filters.quality_level,
                "met": False,
                "reason": "数据质量不在策略允许范围",
            }
        )
    return {
        "symbol": code,
        "matched": not failed_conditions,
        "matched_conditions": matched_conditions,
        "failed_conditions": failed_conditions,
        "factor_values": factor_values,
        "quality": quality,
    }
