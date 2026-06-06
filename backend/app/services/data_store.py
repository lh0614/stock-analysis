"""Parquet 读写与 DuckDB 查询封装（duckdb 缺失时自动降级到 pandas）。"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd

from app.core.data_paths import daily_bars_path, ensure_data_layout, factors_path, quality_report_path

try:
    import duckdb  # type: ignore
except Exception:  # pragma: no cover
    duckdb = None


def _conn():
    ensure_data_layout()
    if duckdb is None:
        return None
    return duckdb.connect(database=":memory:")


def read_parquet(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        return pd.DataFrame()
    return pd.read_parquet(path)


def write_parquet(df: pd.DataFrame, path: str) -> None:
    if df is None or df.empty:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.isfile(path):
        existing = read_parquet(path)
        if not existing.empty:
            keys = _merge_keys(df, existing)
            if keys:
                combined = pd.concat([existing, df], ignore_index=True)
                combined = combined.drop_duplicates(subset=keys, keep="last")
                df = combined
    df.to_parquet(path, index=False)


def _merge_keys(new_df: pd.DataFrame, old_df: pd.DataFrame) -> list[str] | None:
    if "factor_name" in new_df.columns and "factor_name" in old_df.columns:
        return ["symbol", "trade_date", "factor_name"]
    if "adjust" in new_df.columns:
        return ["symbol", "trade_date", "adjust"]
    if "trade_date" in new_df.columns and "symbol" in new_df.columns:
        return ["symbol", "trade_date"]
    return None


def upsert_daily_bars(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    path = daily_bars_path()
    write_parquet(df, path)
    return len(df)


def read_daily_bars(
    symbol: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "qfq",
) -> pd.DataFrame:
    path = daily_bars_path()
    if not os.path.isfile(path):
        return pd.DataFrame()
    con = _conn()
    if con is not None:
        clauses = ["1=1"]
        params: list[Any] = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol.zfill(6)[:6])
        if start_date:
            clauses.append("trade_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("trade_date <= ?")
            params.append(end_date)
        # 只有在文件包含 adjust 列时才添加过滤条件
        try:
            test_df = con.execute(f"SELECT * FROM read_parquet('{path}') LIMIT 1").df()
            if adjust and "adjust" in test_df.columns:
                clauses.append("adjust = ?")
                params.append(adjust)
        except Exception:
            pass  # 如果检查失败，跳过 adjust 过滤

        sql = f"SELECT * FROM read_parquet('{path}') WHERE {' AND '.join(clauses)} ORDER BY trade_date"
        try:
            return con.execute(sql, params).df()
        finally:
            con.close()

    # fallback: pandas 过滤
    df = pd.read_parquet(path)
    if symbol:
        df = df[df["symbol"] == symbol.zfill(6)[:6]]
    if start_date:
        df = df[df["trade_date"] >= start_date]
    if end_date:
        df = df[df["trade_date"] <= end_date]
    if adjust and "adjust" in df.columns:
        df = df[df["adjust"] == adjust]
    return df.sort_values("trade_date")


def query_sql(sql: str, params: list[Any] | None = None) -> pd.DataFrame:
    con = _conn()
    if con is None:
        raise RuntimeError("duckdb 未安装，query_sql 不可用")
    try:
        if params:
            return con.execute(sql, params).df()
        return con.execute(sql).df()
    finally:
        con.close()


def get_data_status() -> dict[str, Any]:
    ensure_data_layout()
    bars_path = daily_bars_path()
    factors_p = factors_path()
    quality_p = quality_report_path()
    status: dict[str, Any] = {
        "daily_bars_exists": os.path.isfile(bars_path),
        "factors_exists": os.path.isfile(factors_p),
        "quality_report_exists": os.path.isfile(quality_p),
        "symbol_count": 0,
        "bar_count": 0,
        "latest_trade_date": None,
    }
    if status["daily_bars_exists"]:
        con = _conn()
        if con is not None:
            try:
                row = con.execute(
                    f"""
                    SELECT COUNT(*) AS cnt,
                           COUNT(DISTINCT symbol) AS sym,
                           MAX(trade_date) AS latest
                    FROM read_parquet('{bars_path}')
                    """
                ).fetchone()
                if row:
                    status["bar_count"] = int(row[0] or 0)
                    status["symbol_count"] = int(row[1] or 0)
                    status["latest_trade_date"] = str(row[2]) if row[2] else None
            finally:
                con.close()
        else:
            df = pd.read_parquet(bars_path)
            status["bar_count"] = int(len(df))
            status["symbol_count"] = int(df["symbol"].nunique()) if "symbol" in df.columns else 0
            status["latest_trade_date"] = str(df["trade_date"].max()) if "trade_date" in df.columns and len(df) else None
    return status


def records_from_daily_bars(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    out: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        out.append(
            {
                "timestamps": str(row.get("trade_date", "")),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume") or 0),
                "amount": float(row.get("amount") or 0),
            }
        )
    return out


def save_daily_bars(df: pd.DataFrame) -> int:
    """保存日线数据到 parquet，与 upsert_daily_bars 相同"""
    return upsert_daily_bars(df)


def clear_symbol_cache(symbol: str) -> bool:
    """清除指定股票的缓存数据（从 parquet 和 pkl 中删除）"""
    code = symbol.zfill(6)[:6]
    cleared = False

    # 1. 清除 parquet 缓存
    path = daily_bars_path()
    if os.path.isfile(path):
        try:
            df = pd.read_parquet(path)
            if not df.empty and "symbol" in df.columns:
                before_count = len(df)
                df = df[df["symbol"] != code]
                after_count = len(df)
                if after_count < before_count:
                    df.to_parquet(path, index=False)
                    cleared = True
        except Exception:
            pass

    # 2. 清除 pkl 缓存
    from app.core.config import settings
    pkl_path = os.path.join(settings.CACHE_DIR, "klines", f"{code}_full.pkl")
    if os.path.isfile(pkl_path):
        try:
            os.remove(pkl_path)
            cleared = True
        except Exception:
            pass

    return cleared
