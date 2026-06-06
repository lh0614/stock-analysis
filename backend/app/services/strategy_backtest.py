"""策略回测评估引擎 - 样本内外拆分"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from app.models.strategy_spec import ConditionSpec, RankingSpec, StrategySpec
from app.services.data_store import read_daily_bars

DEFAULT_COSTS = {
    "commission": 0.0003,
    "stamp_tax": 0.001,
    "slippage": 0.001,
}
LIMIT_UP_PCT = 0.095
LIMIT_DOWN_PCT = -0.095


class BacktestResult:
    """回测结果"""

    def __init__(self):
        self.trades = []
        self.equity_curve = []
        self.returns = []
        self.metrics = {}


def _calculate_metrics(
    returns: list[float],
    trades: list[dict],
    periods_per_year: int = 252,
) -> dict[str, Any]:
    """计算回测指标"""
    if not returns or not trades:
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "profit_loss_ratio": 0.0,
            "total_trades": 0,
        }

    returns_arr = np.array(returns)
    equity = np.cumprod(1 + returns_arr)

    # 总收益率
    total_return = equity[-1] - 1

    # 年化收益率（假设 252 个交易日）
    trading_days = len(returns)
    annual_return = (1 + total_return) ** (periods_per_year / trading_days) - 1 if trading_days > 0 else 0

    # 最大回撤
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    max_drawdown = abs(drawdown.min())

    # 夏普比率
    if returns_arr.std() > 0:
        sharpe_ratio = (returns_arr.mean() * periods_per_year) / (returns_arr.std() * np.sqrt(periods_per_year))
    else:
        sharpe_ratio = 0.0

    # 胜率和盈亏比
    winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
    losing_trades = [t for t in trades if t.get("pnl", 0) < 0]

    win_rate = len(winning_trades) / len(trades) if trades else 0

    avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0
    avg_loss = abs(np.mean([t["pnl"] for t in losing_trades])) if losing_trades else 0
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

    return {
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "max_drawdown": float(max_drawdown),
        "sharpe_ratio": float(sharpe_ratio),
        "win_rate": float(win_rate),
        "profit_loss_ratio": float(profit_loss_ratio),
        "total_trades": len(trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
    }


def _eval_condition(value: Any, condition: ConditionSpec) -> bool:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    if condition.op == "gt":
        return float(value) > float(condition.value)
    if condition.op == "lt":
        return float(value) < float(condition.value)
    if condition.op == "gte":
        return float(value) >= float(condition.value)
    if condition.op == "lte":
        return float(value) <= float(condition.value)
    if condition.op == "eq":
        if isinstance(condition.value, bool):
            return bool(value) == condition.value
        return value == condition.value
    if condition.op == "in":
        return value in condition.value
    if condition.op == "not_in":
        return value not in condition.value
    return False


def _rsi(close: pd.Series, period: int) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    val = 100 - (100 / (1 + rs))
    v = val.iloc[-1]
    return float(v) if pd.notna(v) else None


def _factor_snapshot(hist: pd.DataFrame) -> dict[str, Any]:
    """Calculate point-in-time factors using only history up to the rebalance date."""
    if hist.empty or len(hist) < 30:
        return {}
    work = hist.sort_values("trade_date").copy()
    close = work["close"].astype(float)
    high = work["high"].astype(float)
    low = work["low"].astype(float)
    volume = work["volume"].astype(float) if "volume" in work.columns else pd.Series([0] * len(work))
    ret = close.pct_change().dropna()

    def ma(n: int) -> float | None:
        if len(close) < n:
            return None
        return float(close.rolling(n).mean().iloc[-1])

    latest = float(close.iloc[-1])
    ma5, ma10, ma20, ma60 = ma(5), ma(10), ma(20), ma(60)
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=9, adjust=False).mean()
    macd_hist = float(2 * (dif.iloc[-1] - dea.iloc[-1])) if len(close) >= 35 else 0

    vol20 = float(volume.tail(20).mean()) if len(volume) >= 20 else 0
    vol5 = float(volume.tail(5).mean()) if len(volume) >= 5 else 0
    vol_ratio = vol5 / vol20 if vol20 > 0 else 1.0
    window60 = close.tail(60)
    price_position_60d = float((latest - window60.min()) / (window60.max() - window60.min() + 1e-9))
    high_20d = float(high.iloc[-21:-1].max()) if len(high) > 21 else float(high.iloc[-1])
    recent_lows = low.tail(5)
    pullback_to_ma20 = bool(
        ma20 and latest > ma20 and any(ma20 * 0.98 <= float(x) <= ma20 * 1.02 for x in recent_lows)
    )

    return {
        "close": latest,
        "ma5": ma5 or 0,
        "ma10": ma10 or 0,
        "ma20": ma20 or 0,
        "ma60": ma60 or 0,
        "close_above_ma20": bool(ma20 and latest > ma20),
        "ma_bullish_alignment": bool(
            ma5 and ma10 and ma20 and ma60 and latest > ma5 > ma10 > ma20 > ma60
        ),
        "macd_hist": macd_hist,
        "rsi6": _rsi(close, 6) or 0,
        "rsi12": _rsi(close, 12) or 0,
        "rsi24": _rsi(close, 24) or 0,
        "return_1d": float(close.iloc[-1] / close.iloc[-2] - 1) if len(close) > 1 else 0,
        "return_5d": float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) > 6 else 0,
        "return_20d": float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else 0,
        "return_60d": float(close.iloc[-1] / close.iloc[-61] - 1) if len(close) > 61 else 0,
        "volatility_20d": float(ret.tail(20).std() * np.sqrt(252)) if len(ret) >= 20 else 0,
        "volatility_60d": float(ret.tail(60).std() * np.sqrt(252)) if len(ret) >= 60 else 0,
        "volume_ratio_5_20": vol_ratio,
        "breakout_20d_high": bool(latest > high_20d),
        "pullback_to_ma20": pullback_to_ma20,
        "price_position_60d": price_position_60d,
    }


def _ranking_score(factors: dict[str, Any], ranking: list[RankingSpec]) -> float:
    if not ranking:
        return 0.0
    score = 0.0
    for r in ranking:
        val = factors.get(r.factor)
        if val is None:
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            fval = 1.0 if bool(val) else 0.0
        score += fval * r.weight * (1 if r.direction == "desc" else -1)
    return score


def _rebalance_step(freq: str) -> int:
    return {"daily": 1, "weekly": 5, "monthly": 20}.get(freq, 5)


def _is_limit_up(prev_close: float, close: float) -> bool:
    return prev_close > 0 and close / prev_close - 1 >= LIMIT_UP_PCT


def _is_limit_down(prev_close: float, close: float) -> bool:
    return prev_close > 0 and close / prev_close - 1 <= LIMIT_DOWN_PCT


def _row_close(df: pd.DataFrame, idx: int) -> float:
    return float(df.iloc[idx]["close"])


def _rolling_strategy_backtest(
    strategy_spec: StrategySpec,
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> BacktestResult:
    """Point-in-time rolling rebalance backtest.

    At each rebalance date, factors are recomputed from historical bars up to
    that date only. The selected portfolio is held to the next rebalance date.
    """
    result = BacktestResult()
    frames: dict[str, pd.DataFrame] = {}
    all_dates: set[str] = set()
    lookback_start = (pd.to_datetime(start_date) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    for symbol in symbols:
        df = read_daily_bars(symbol=symbol, start_date=lookback_start, end_date=end_date)
        if df.empty or len(df) < 35:
            continue
        df = df.sort_values("trade_date").reset_index(drop=True)
        frames[symbol] = df
        all_dates.update(str(x)[:10] for x in df["trade_date"].tolist() if str(x)[:10] >= start_date)

    dates = sorted(all_dates)
    step = _rebalance_step(strategy_spec.rebalance)
    periods_per_year = max(1, int(252 / step))
    rebalance_dates = dates[::step]
    max_positions = max(1, strategy_spec.position.max_positions)

    portfolio_returns: list[float] = []
    equity = 1.0
    skipped_trades: list[dict[str, Any]] = []
    turnover_events = 0
    for i, entry_date in enumerate(rebalance_dates[:-1]):
        exit_date = rebalance_dates[i + 1]
        selected: list[tuple[str, dict[str, Any], float]] = []

        for symbol, df in frames.items():
            hist = df[df["trade_date"].astype(str) <= entry_date]
            if len(hist) < 35:
                continue
            factors = _factor_snapshot(hist)
            if not factors:
                continue
            if not all(_eval_condition(factors.get(cond.factor), cond) for cond in strategy_spec.entry_conditions):
                continue
            score = _ranking_score(factors, strategy_spec.ranking)
            selected.append((symbol, factors, score))

        selected.sort(key=lambda x: x[2], reverse=True)
        selected = selected[:max_positions]
        if not selected:
            portfolio_returns.append(0.0)
            result.equity_curve.append({"date": entry_date, "equity": equity})
            continue

        trade_returns: list[float] = []
        for symbol, factors, score in selected:
            df = frames[symbol]
            entry_rows = df[df["trade_date"].astype(str) >= entry_date]
            exit_rows = df[df["trade_date"].astype(str) >= exit_date]
            if entry_rows.empty or exit_rows.empty:
                continue
            entry_idx = int(entry_rows.index[0])
            exit_idx = int(exit_rows.index[0])
            entry_row = df.iloc[entry_idx]
            exit_row = df.iloc[exit_idx]
            entry_close = float(entry_row["close"])
            exit_close = float(exit_row["close"])
            prev_entry_close = _row_close(df, max(0, entry_idx - 1))
            prev_exit_close = _row_close(df, max(0, exit_idx - 1))
            if _is_limit_up(prev_entry_close, entry_close):
                skipped_trades.append({"symbol": symbol, "date": str(entry_row["trade_date"])[:10], "reason": "limit_up_buy"})
                continue
            if _is_limit_down(prev_exit_close, exit_close):
                skipped_trades.append({"symbol": symbol, "date": str(exit_row["trade_date"])[:10], "reason": "limit_down_sell"})
                continue
            entry = entry_close * (1 + DEFAULT_COSTS["slippage"])
            exit_val = exit_close * (1 - DEFAULT_COSTS["slippage"])
            gross_return = (exit_val - entry) / entry if entry > 0 else 0
            pnl_pct = gross_return - DEFAULT_COSTS["commission"] * 2 - DEFAULT_COSTS["stamp_tax"]
            trade_returns.append(pnl_pct)
            turnover_events += 1
            result.trades.append(
                {
                    "symbol": symbol,
                    "entry_date": str(entry_row["trade_date"])[:10],
                    "exit_date": str(exit_row["trade_date"])[:10],
                    "entry_price": entry,
                    "exit_price": exit_val,
                    "gross_return": gross_return,
                    "pnl": pnl_pct,
                    "costs": DEFAULT_COSTS,
                    "score": score,
                    "factors": factors,
                }
            )

        period_return = float(np.mean(trade_returns)) if trade_returns else 0.0
        portfolio_returns.append(period_return)
        equity *= 1 + period_return
        result.equity_curve.append({"date": exit_date, "equity": equity})

    result.returns = portfolio_returns
    result.metrics = _calculate_metrics(portfolio_returns, result.trades, periods_per_year=periods_per_year)
    result.metrics["rebalance_count"] = len(rebalance_dates)
    result.metrics["symbols_considered"] = len(frames)
    result.metrics["skipped_trade_count"] = len(skipped_trades)
    result.metrics["turnover"] = float(turnover_events / max(1, len(rebalance_dates)))
    result.metrics["costs"] = DEFAULT_COSTS
    if dates and frames:
        benchmark_returns = []
        first_symbol = next(iter(frames))
        bench = frames[first_symbol]
        bench = bench[(bench["trade_date"].astype(str) >= start_date) & (bench["trade_date"].astype(str) <= end_date)]
        if len(bench) > 1:
            benchmark_returns.append(float(bench.iloc[-1]["close"]) / float(bench.iloc[0]["close"]) - 1)
        result.metrics["benchmark_return"] = float(np.mean(benchmark_returns)) if benchmark_returns else 0.0
    result.metrics["skipped_trades"] = skipped_trades[:100]

    return result


def run_strategy_backtest(
    strategy_spec: StrategySpec,
    candidates: list[dict[str, Any]],
    test_start_date: str | None = None,
    test_end_date: str | None = None,
) -> dict[str, Any]:
    """
    对策略进行回测

    Args:
        strategy_spec: 策略规格
        candidates: 候选股列表（来自选股结果）
        test_start_date: 测试开始日期（用于样本外测试）
        test_end_date: 测试结束日期
    """
    # 默认回测最近 1 年
    if not test_end_date:
        test_end_date = datetime.now().strftime("%Y-%m-%d")
    if not test_start_date:
        test_start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    # 提取 symbols，兼容字典和 Pydantic 对象
    symbols = []
    for c in candidates[:20]:
        if isinstance(c, dict):
            symbols.append(c.get("symbol"))
        else:
            symbols.append(getattr(c, "symbol", ""))
    symbols = [s for s in symbols if s]

    result = _rolling_strategy_backtest(
        strategy_spec=strategy_spec,
        symbols=symbols,
        start_date=test_start_date,
        end_date=test_end_date,
    )

    return {
        "backtest_id": str(uuid.uuid4()),
        "strategy_name": strategy_spec.name,
        "test_period": {"start": test_start_date, "end": test_end_date},
        "rebalance": strategy_spec.rebalance,
        "symbols_tested": len(symbols),
        "metrics": result.metrics,
        "trade_count": len(result.trades),
        "equity_curve": result.equity_curve,
        "trades": result.trades[:500],
        "created_at": datetime.now().isoformat(),
    }


def run_in_sample_out_sample_backtest(
    strategy_spec: StrategySpec,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    样本内/样本外拆分回测

    样本内（in-sample）：用于策略开发和参数优化
    样本外（out-of-sample）：用于验证策略泛化能力
    """
    end_date = datetime.now()
    total_days = 730  # 2 年

    # 样本内：前 70% 时间
    in_sample_start = (end_date - timedelta(days=total_days)).strftime("%Y-%m-%d")
    in_sample_end = (end_date - timedelta(days=int(total_days * 0.3))).strftime("%Y-%m-%d")

    # 样本外：后 30% 时间
    out_sample_start = (end_date - timedelta(days=int(total_days * 0.3))).strftime("%Y-%m-%d")
    out_sample_end = end_date.strftime("%Y-%m-%d")

    print(f"样本内回测: {in_sample_start} ~ {in_sample_end}")
    in_sample_result = run_strategy_backtest(
        strategy_spec, candidates, in_sample_start, in_sample_end
    )

    print(f"样本外回测: {out_sample_start} ~ {out_sample_end}")
    out_sample_result = run_strategy_backtest(
        strategy_spec, candidates, out_sample_start, out_sample_end
    )

    # 检测过拟合
    in_sample_return = in_sample_result["metrics"]["annual_return"]
    out_sample_return = out_sample_result["metrics"]["annual_return"]

    # 如果样本外收益显著低于样本内（差距超过 50%），标记为疑似过拟合
    overfit_flag = False
    if in_sample_return > 0.1:  # 样本内年化收益 > 10%
        degradation = (in_sample_return - out_sample_return) / in_sample_return
        if degradation > 0.5:  # 样本外收益下降超过 50%
            overfit_flag = True

    return {
        "evaluation_id": str(uuid.uuid4()),
        "strategy_name": strategy_spec.name,
        "in_sample": in_sample_result,
        "out_sample": out_sample_result,
        "overfit_flag": overfit_flag,
        "overfit_reason": (
            f"样本外收益显著低于样本内 (样本内:{in_sample_return:.2%}, 样本外:{out_sample_return:.2%})"
            if overfit_flag
            else None
        ),
        "created_at": datetime.now().isoformat(),
    }
