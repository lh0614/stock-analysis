"""财务与估值同步（M12）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from app.core.data_paths import fundamentals_path, valuation_path
from app.services.data_store import read_daily_bars, read_parquet, write_parquet


def _code(symbol: str) -> str:
    return str(symbol).zfill(6)[:6]


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace("%", "").replace(",", ""))
    except Exception:
        return None


def _pick(row: pd.Series, names: list[str]) -> Any:
    for name in names:
        for col in row.index:
            if name in str(col):
                return row[col]
    return None


def _latest_row(df: pd.DataFrame) -> pd.Series | None:
    if df is None or df.empty:
        return None
    return df.iloc[0] if len(df) == 1 else df.iloc[-1]


def _fetch_financial_indicator(symbol: str) -> dict[str, Any]:
    try:
        import akshare as ak

        df = ak.stock_financial_analysis_indicator(symbol=_code(symbol), start_year="2019")
        row = _latest_row(df)
        if row is None:
            raise ValueError("empty financial indicator")
        return {
            "symbol": _code(symbol),
            "report_period": str(_pick(row, ["报告期", "日期"]) or datetime.now().strftime("%Y-%m-%d"))[:10],
            "revenue": _num(_pick(row, ["营业总收入", "主营业务收入", "营业收入"])),
            "net_profit": _num(_pick(row, ["净利润", "归母净利润"])),
            "roe": _num(_pick(row, ["净资产收益率", "ROE"])),
            "gross_margin": _num(_pick(row, ["销售毛利率", "毛利率"])),
            "debt_ratio": _num(_pick(row, ["资产负债率"])),
            "ocf": _num(_pick(row, ["经营现金流", "每股经营性现金流"])),
            "source": "akshare:sina_financial_indicator",
            "updated_at": datetime.now().isoformat(),
            "error": None,
        }
    except Exception as exc:
        return {
            "symbol": _code(symbol),
            "report_period": datetime.now().strftime("%Y-%m-%d"),
            "revenue": None,
            "net_profit": None,
            "roe": None,
            "gross_margin": None,
            "debt_ratio": None,
            "ocf": None,
            "source": "unavailable",
            "updated_at": datetime.now().isoformat(),
            "error": str(exc)[:200],
        }


def _latest_valuation_value(symbol: str, indicator: str) -> tuple[str | None, float | None, str | None]:
    try:
        import akshare as ak

        df = ak.stock_zh_valuation_baidu(symbol=_code(symbol), indicator=indicator, period="近一年")
        row = _latest_row(df)
        if row is None:
            raise ValueError("empty valuation")
        date_val = _pick(row, ["日期", "date", "trade"])
        value = _pick(row, ["值", "value", indicator])
        if value is None:
            numeric_cols = [c for c in row.index if _num(row[c]) is not None]
            value = row[numeric_cols[-1]] if numeric_cols else None
        return str(date_val)[:10] if date_val is not None else None, _num(value), None
    except Exception as exc:
        return None, None, str(exc)[:200]


def sync_fundamentals(symbols: list[str]) -> dict[str, Any]:
    rows = []
    for sym in symbols[:200]:
        rows.append(_fetch_financial_indicator(sym))
    if rows:
        write_parquet(pd.DataFrame(rows), fundamentals_path())
    available = sum(1 for r in rows if r.get("source") != "unavailable")
    return {"symbols": len(rows), "available": available, "path": fundamentals_path()}


def sync_valuation(symbols: list[str]) -> dict[str, Any]:
    rows = []
    for sym in symbols[:200]:
        code = _code(sym)
        trade_date = datetime.now().strftime("%Y-%m-%d")
        errors: dict[str, str] = {}
        pe_date, pe_ttm, pe_error = _latest_valuation_value(code, "市盈率(TTM)")
        pb_date, pb, pb_error = _latest_valuation_value(code, "市净率")
        cap_date, market_cap, cap_error = _latest_valuation_value(code, "总市值")
        for key, err in {"pe_ttm": pe_error, "pb": pb_error, "market_cap": cap_error}.items():
            if err:
                errors[key] = err
        bars = read_daily_bars(symbol=code)
        close = float(bars["close"].iloc[-1]) if not bars.empty else None
        rows.append(
            {
                "symbol": code,
                "trade_date": pe_date or pb_date or cap_date or trade_date,
                "close": close,
                "pe_ttm": pe_ttm,
                "pb": pb,
                "ps": None,
                "dividend_yield": None,
                "market_cap": market_cap,
                "source": "akshare:baidu_valuation" if not errors else "partial_or_unavailable",
                "error": "; ".join(f"{k}:{v}" for k, v in errors.items()) if errors else None,
                "updated_at": datetime.now().isoformat(),
            }
        )
    if rows:
        write_parquet(pd.DataFrame(rows), valuation_path())
    available = sum(1 for r in rows if r.get("pe_ttm") is not None or r.get("pb") is not None or r.get("market_cap") is not None)
    return {"symbols": len(rows), "available": available, "path": valuation_path()}


def get_fundamentals(symbol: str) -> dict[str, Any]:
    df = read_parquet(fundamentals_path())
    code = _code(symbol)
    if df.empty:
        return {"symbol": code, "data_available": False, "record": None, "missing_fields": ["fundamentals"]}
    sub = df[df["symbol"].astype(str).str.zfill(6).str[:6] == code]
    if sub.empty:
        return {"symbol": code, "data_available": False, "record": None, "missing_fields": ["fundamentals"]}
    row = sub.sort_values("report_period").iloc[-1].to_dict()
    missing = [k for k in ["revenue", "net_profit", "roe", "gross_margin", "debt_ratio", "ocf"] if row.get(k) is None or pd.isna(row.get(k))]
    return {"symbol": code, "data_available": len(missing) < 6, "record": row, "missing_fields": missing}


def get_valuation(symbol: str) -> dict[str, Any]:
    df = read_parquet(valuation_path())
    code = _code(symbol)
    if df.empty:
        return {"symbol": code, "data_available": False, "record": None, "missing_fields": ["valuation"]}
    sub = df[df["symbol"].astype(str).str.zfill(6).str[:6] == code]
    if sub.empty:
        return {"symbol": code, "data_available": False, "record": None, "missing_fields": ["valuation"]}
    row = sub.sort_values("trade_date").iloc[-1].to_dict()
    missing = [k for k in ["pe_ttm", "pb", "ps", "dividend_yield", "market_cap"] if row.get(k) is None or pd.isna(row.get(k))]
    return {"symbol": code, "data_available": len(missing) < 5, "record": row, "missing_fields": missing}


def get_fundamental_summary(symbol: str) -> dict[str, Any]:
    fundamentals = get_fundamentals(symbol)
    valuation = get_valuation(symbol)
    return {
        "symbol": _code(symbol),
        "fundamentals": fundamentals,
        "valuation": valuation,
        "data_available": fundamentals["data_available"] or valuation["data_available"],
        "updated_at": datetime.now().isoformat(),
    }
