"""数据质量评估、跨源对账与报告。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from app.core.config import settings
from app.core.data_paths import quality_report_path, source_compare_report_path
from app.services.data_store import read_daily_bars, read_parquet, write_parquet

LEVEL_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4}
C_WARN = "数据存在单源或轻微异常，结论仅供参考"
D_BLOCK = "数据缺失或冲突严重，本次不生成方向结论"


def _worst_level(levels: list[str]) -> str:
    if not levels:
        return "D"
    return max(levels, key=lambda x: LEVEL_ORDER.get(x, 0))


def _grade_bar(row: pd.Series, *, stale_days: int = 0) -> tuple[str, list[str]]:
    issues: list[str] = []
    level = "A"
    o, h, l, c = row.get("open"), row.get("high"), row.get("low"), row.get("close")
    try:
        o, h, l, c = float(o), float(h), float(l), float(c)
    except (TypeError, ValueError):
        return "D", ["invalid_ohlc"]
    if h < max(o, c) or l > min(o, c):
        return "D", ["ohlc_invalid"]
    vol = float(row.get("volume") or 0)
    amt = float(row.get("amount") or 0)
    if vol < 0 or amt < 0:
        return "D", ["negative_volume"]
    src_count = int(row.get("source_count") or 1)
    if src_count < 2:
        level = "C"
        issues.append("single_source")
    if stale_days >= 3:
        level = "C" if level != "D" else level
        issues.append("stale_data")
    elif stale_days >= 1:
        if level == "A":
            level = "B"
        issues.append("data_lag")
    return level, issues


def _compare_pkl_vs_parquet(symbol: str) -> list[dict[str, Any]]:
    """简化跨源：pkl 末根 close 与 parquet 末根 close 对比。"""
    code = symbol.zfill(6)[:6]
    conflicts: list[dict[str, Any]] = []
    df = read_daily_bars(symbol=code)
    if df.empty:
        return conflicts
    pkl_path = os.path.join(settings.CACHE_DIR, "klines", f"{code}_full.pkl")
    if not os.path.isfile(pkl_path):
        return conflicts
    try:
        pkl_df = pd.read_pickle(pkl_path)
        if pkl_df is None or pkl_df.empty:
            return conflicts
        col = "close" if "close" in pkl_df.columns else None
        if not col:
            return conflicts
        pkl_close = float(pkl_df[col].iloc[-1])
        pq_close = float(df["close"].iloc[-1])
        if pkl_close <= 0:
            return conflicts
        diff_pct = abs(pkl_close - pq_close) / pkl_close
        level = "C"
        if diff_pct > 0.01:
            level = "D"
        elif diff_pct > 0.003:
            level = "C"
        else:
            return conflicts
        conflicts.append(
            {
                "symbol": code,
                "trade_date": str(df["trade_date"].iloc[-1]),
                "source_a": "pkl",
                "source_b": "parquet",
                "close_a": pkl_close,
                "close_b": pq_close,
                "diff_pct": round(diff_pct * 100, 4),
                "quality_level": level,
            }
        )
    except Exception:
        pass
    return conflicts


def build_source_compare_report(symbols: list[str] | None = None) -> dict[str, Any]:
    if symbols:
        sym_list = [s.zfill(6)[:6] for s in symbols]
    else:
        df = read_daily_bars()
        sym_list = sorted(df["symbol"].unique().tolist()) if not df.empty else []
    rows: list[dict] = []
    for sym in sym_list[:2000]:
        rows.extend(_compare_pkl_vs_parquet(sym))
    out_df = pd.DataFrame(rows)
    if not out_df.empty:
        write_parquet(out_df, source_compare_report_path())
    return {"conflict_count": len(rows), "path": source_compare_report_path()}


def assess_symbol(symbol: str) -> dict[str, Any]:
    code = symbol.zfill(6)[:6]
    df = read_daily_bars(symbol=code)
    if df.empty:
        return {
            "symbol": code,
            "quality_level": "D",
            "issues": ["no_data"],
            "bar_count": 0,
            "ui_hint": "数据缺失，系统将自动尝试从数据源拉取",
            "block_direction": True,
            "can_retry": True,
            "retry_action": "auto_fetch",
            "retry_hint": "点击「刷新」按钮重新拉取数据",
        }
    today = datetime.now().date()
    latest = str(df["trade_date"].iloc[-1])[:10]
    try:
        stale_days = (today - datetime.strptime(latest, "%Y-%m-%d").date()).days
    except ValueError:
        stale_days = 0
    levels: list[str] = []
    all_issues: list[str] = []
    for _, row in df.tail(60).iterrows():
        lv, iss = _grade_bar(row, stale_days=stale_days)
        levels.append(lv)
        all_issues.extend(iss)
    compare = _compare_pkl_vs_parquet(code)
    for c in compare:
        all_issues.append(f"cross_source_diff_{c.get('diff_pct')}%")
        levels.append(c.get("quality_level", "C"))
    worst = _worst_level(levels)
    block = worst == "D"
    ui_hint = None
    can_retry = False
    retry_action = None
    retry_hint = None

    if worst == "C":
        ui_hint = C_WARN
    elif worst == "D":
        ui_hint = D_BLOCK
        can_retry = True
        retry_action = "force_refetch"
        retry_hint = "数据质量严重异常，建议清除缓存并重新拉取"

    return {
        "symbol": code,
        "quality_level": worst,
        "issues": list(dict.fromkeys(all_issues)),
        "bar_count": len(df),
        "latest_trade_date": latest,
        "stale_days": stale_days,
        "block_direction": block,
        "ui_hint": ui_hint,
        "cross_source_conflicts": compare,
        "can_retry": can_retry,
        "retry_action": retry_action,
        "retry_hint": retry_hint,
    }


def build_quality_report(symbols: list[str] | None = None) -> dict[str, Any]:
    if symbols:
        sym_list = [s.zfill(6)[:6] for s in symbols]
    else:
        df = read_daily_bars()
        sym_list = sorted(df["symbol"].unique().tolist()) if not df.empty else []
    compare_meta = build_source_compare_report(sym_list)
    rows = []
    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for sym in sym_list:
        info = assess_symbol(sym)
        counts[info["quality_level"]] = counts.get(info["quality_level"], 0) + 1
        rows.append(
            {
                "symbol": info["symbol"],
                "trade_date": info.get("latest_trade_date") or datetime.now().strftime("%Y-%m-%d"),
                "quality_level": info["quality_level"],
                "issues": json.dumps(info.get("issues") or [], ensure_ascii=False),
                "bar_count": info.get("bar_count", 0),
                "stale_days": info.get("stale_days", 0),
                "updated_at": datetime.now().isoformat(),
            }
        )
    report_df = pd.DataFrame(rows)
    if not report_df.empty:
        write_parquet(report_df, quality_report_path())
    return {
        "symbol_count": len(sym_list),
        "counts": counts,
        "path": quality_report_path(),
        "compare": compare_meta,
        "generated_at": datetime.now().isoformat(),
    }


def get_summary() -> dict[str, Any]:
    path = quality_report_path()
    df = read_parquet(path)
    if df.empty:
        return {"total": 0, "counts": {"A": 0, "B": 0, "C": 0, "D": 0}, "conflicts": 0, "blocked": 0}
    counts = df["quality_level"].value_counts().to_dict()
    cmp_df = read_parquet(source_compare_report_path())
    return {
        "total": len(df),
        "counts": {k: int(v) for k, v in counts.items()},
        "conflicts": int(len(cmp_df)) if not cmp_df.empty else int((df["quality_level"] == "C").sum()),
        "blocked": int((df["quality_level"] == "D").sum()) if "quality_level" in df.columns else 0,
    }


def get_symbol_quality(symbol: str) -> dict[str, Any]:
    return assess_symbol(symbol)


def list_conflicts(limit: int = 100) -> list[dict[str, Any]]:
    cmp_df = read_parquet(source_compare_report_path())
    if not cmp_df.empty:
        return cmp_df.head(limit).to_dict("records")
    df = read_parquet(quality_report_path())
    if df.empty:
        return []
    sub = df[df["quality_level"].isin(["C", "D"])].head(limit)
    out = []
    for _, r in sub.iterrows():
        row = r.to_dict()
        try:
            row["issues"] = json.loads(row.get("issues") or "[]")
        except json.JSONDecodeError:
            row["issues"] = row.get("issues")
        out.append(row)
    return out


def list_missing_bars(limit: int = 100) -> list[dict[str, Any]]:
    df = read_parquet(quality_report_path())
    if df.empty:
        return []
    sub = df[(df["quality_level"] == "D") | (df.get("bar_count", 0) < 20)].head(limit)
    out = []
    for _, r in sub.iterrows():
        row = r.to_dict()
        try:
            row["issues"] = json.loads(row.get("issues") or "[]")
        except json.JSONDecodeError:
            pass
        out.append(row)
    return out


def get_quality_summary_for_symbols(symbols: list[str]) -> dict[str, Any]:
    """
    获取一组股票的数据质量摘要

    Args:
        symbols: 股票代码列表

    Returns:
        数据质量摘要，包含总数、各等级分布、最新行情日期等
    """
    if not symbols:
        return {
            "total_symbols": 0,
            "quality_distribution": {"A": 0, "B": 0, "C": 0, "D": 0},
            "has_factor_data": 0,
            "missing_factor_data": 0,
            "latest_trade_date": None,
            "average_stale_days": 0,
            "quality_grade": "D",
            "recommendation": "无股票数据"
        }

    quality_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    has_data_count = 0
    stale_days_sum = 0
    latest_dates = []

    for symbol in symbols:
        quality = assess_symbol(symbol)
        level = quality.get("quality_level", "D")
        quality_counts[level] = quality_counts.get(level, 0) + 1

        if quality.get("bar_count", 0) > 0:
            has_data_count += 1

        stale_days = quality.get("stale_days", 0)
        stale_days_sum += stale_days

        latest_date = quality.get("latest_trade_date")
        if latest_date:
            latest_dates.append(latest_date)

    total = len(symbols)
    missing_count = total - has_data_count
    avg_stale = stale_days_sum / total if total > 0 else 0

    # 计算整体质量等级
    d_pct = quality_counts["D"] / total if total > 0 else 0
    c_pct = quality_counts["C"] / total if total > 0 else 0

    if d_pct > 0.3:
        overall_grade = "D"
        recommendation = "数据质量严重不足，不建议依据该结果决策"
    elif d_pct > 0.1 or c_pct > 0.5:
        overall_grade = "C"
        recommendation = "数据质量一般，结论仅供参考"
    elif c_pct > 0.2:
        overall_grade = "B"
        recommendation = "数据质量较好，可作参考"
    else:
        overall_grade = "A"
        recommendation = "数据质量优秀"

    return {
        "total_symbols": total,
        "quality_distribution": quality_counts,
        "has_factor_data": has_data_count,
        "missing_factor_data": missing_count,
        "latest_trade_date": max(latest_dates) if latest_dates else None,
        "average_stale_days": round(avg_stale, 1),
        "quality_grade": overall_grade,
        "recommendation": recommendation
    }

