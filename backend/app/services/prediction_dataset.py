"""
P2-1: 单股预测模型 - 数据集构建和特征工程
"""
from __future__ import annotations

import pandas as pd
from datetime import datetime, timedelta
from typing import Any

from app.services.factor_engine import get_factor_data_for_symbol
from app.services.market_data import get_market_indicators
from app.services.stock_pool import get_all_symbols


def build_prediction_dataset(
    symbols: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    prediction_horizons: list[int] = [5, 10, 20],
) -> pd.DataFrame:
    """
    构建单股预测数据集

    Args:
        symbols: 股票代码列表，None 表示全市场
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        prediction_horizons: 预测周期（天数）

    Returns:
        DataFrame with columns:
        - symbol: 股票代码
        - trade_date: 交易日期
        - features: 特征字段（技术因子、市场环境等）
        - labels: 标签字段（未来收益、跑赢基准等）
    """
    if symbols is None:
        symbols = [s["symbol"] for s in get_all_symbols()]

    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    if start_date is None:
        # 默认 1 年数据
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")

    rows = []

    for symbol in symbols:
        try:
            # 获取因子数据
            factor_data = get_factor_data_for_symbol(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            if not factor_data or len(factor_data) < max(prediction_horizons) + 10:
                continue

            df = pd.DataFrame(factor_data)
            df = df.sort_values("trade_date")

            # 构建特征
            for idx in range(len(df) - max(prediction_horizons)):
                row_data = df.iloc[idx]
                trade_date = row_data["trade_date"]

                # 基础特征
                features = extract_technical_features(df.iloc[:idx+1])

                # 市场环境特征
                market_features = extract_market_features(trade_date)
                features.update(market_features)

                # 数据质量特征
                quality_features = extract_quality_features(symbol, trade_date)
                features.update(quality_features)

                # 构建标签
                labels = build_prediction_labels(
                    df=df,
                    current_idx=idx,
                    horizons=prediction_horizons
                )

                # 合并
                row = {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    **features,
                    **labels
                }
                rows.append(row)

        except Exception as e:
            # 跳过有问题的股票
            continue

    if not rows:
        return pd.DataFrame()

    dataset = pd.DataFrame(rows)
    return dataset


def extract_technical_features(df: pd.DataFrame) -> dict[str, Any]:
    """
    提取技术因子特征

    Args:
        df: 历史数据 DataFrame（按时间排序）

    Returns:
        特征字典
    """
    if len(df) == 0:
        return {}

    latest = df.iloc[-1]

    features = {
        # 趋势特征
        "return_5d": latest.get("return_5d", 0),
        "return_20d": latest.get("return_20d", 0),
        "return_60d": latest.get("return_60d", 0),

        # 波动特征
        "volatility_20d": latest.get("volatility_20d", 0),
        "volatility_60d": latest.get("volatility_60d", 0),

        # 成交量特征
        "volume_ratio_5_20": latest.get("volume_ratio_5_20", 1.0),
        "volume_ratio_20_60": latest.get("volume_ratio_20_60", 1.0),

        # 技术指标
        "rsi6": latest.get("rsi6", 50),
        "rsi12": latest.get("rsi12", 50),
        "macd": latest.get("macd", 0),
        "macd_signal": latest.get("macd_signal", 0),

        # 均线特征
        "ma5": latest.get("ma5", 0),
        "ma10": latest.get("ma10", 0),
        "ma20": latest.get("ma20", 0),
        "ma60": latest.get("ma60", 0),
        "ma_bullish_alignment": 1 if latest.get("ma_bullish_alignment") else 0,

        # 价格位置
        "price_position_60d": latest.get("price_position_60d", 0.5),
        "high_52w_distance": latest.get("high_52w_distance", 0),

        # 突破特征
        "breakout_20d_high": 1 if latest.get("breakout_20d_high") else 0,
        "pullback_to_ma20": 1 if latest.get("pullback_to_ma20") else 0,
    }

    return features


def extract_market_features(trade_date: str) -> dict[str, Any]:
    """
    提取市场环境特征

    Args:
        trade_date: 交易日期

    Returns:
        市场特征字典
    """
    try:
        market_data = get_market_indicators(trade_date)

        if not market_data:
            return {
                "market_trend": 0,
                "market_volatility": 0,
                "market_volume": 0,
                "industry_strength": 0,
            }

        features = {
            "market_trend": market_data.get("trend_signal", 0),  # -1/0/1
            "market_volatility": market_data.get("volatility_percentile", 0.5),
            "market_volume": market_data.get("volume_ratio", 1.0),
            "industry_strength": market_data.get("industry_momentum", 0),
        }

        return features

    except Exception:
        return {
            "market_trend": 0,
            "market_volatility": 0,
            "market_volume": 0,
            "industry_strength": 0,
        }


def extract_quality_features(symbol: str, trade_date: str) -> dict[str, Any]:
    """
    提取数据质量特征

    Args:
        symbol: 股票代码
        trade_date: 交易日期

    Returns:
        质量特征字典
    """
    from app.services.data_quality import assess_symbol

    try:
        quality = assess_symbol(symbol, reference_date=trade_date)

        quality_score = {
            "A": 1.0,
            "B": 0.8,
            "C": 0.5,
            "D": 0.2
        }.get(quality.get("quality_level", "B"), 0.8)

        features = {
            "data_quality_score": quality_score,
            "data_completeness": quality.get("completeness", 0.9),
            "data_stale_days": quality.get("stale_days", 0),
        }

        return features

    except Exception:
        return {
            "data_quality_score": 0.8,
            "data_completeness": 0.9,
            "data_stale_days": 0,
        }


def build_prediction_labels(
    df: pd.DataFrame,
    current_idx: int,
    horizons: list[int]
) -> dict[str, Any]:
    """
    构建预测标签

    Args:
        df: 数据 DataFrame
        current_idx: 当前索引
        horizons: 预测周期列表

    Returns:
        标签字典
    """
    labels = {}

    current_close = df.iloc[current_idx].get("close", 0)
    if current_close == 0:
        return labels

    for horizon in horizons:
        future_idx = current_idx + horizon

        if future_idx >= len(df):
            # 超出数据范围
            labels[f"return_{horizon}d"] = None
            labels[f"label_up_{horizon}d"] = None
            labels[f"label_beat_benchmark_{horizon}d"] = None
            labels[f"max_drawdown_{horizon}d"] = None
            continue

        # 未来收益
        future_close = df.iloc[future_idx].get("close", 0)
        future_return = (future_close - current_close) / current_close if current_close > 0 else 0
        labels[f"return_{horizon}d"] = future_return

        # 上涨标签（> 0）
        labels[f"label_up_{horizon}d"] = 1 if future_return > 0 else 0

        # 跑赢基准标签（> 5%）
        labels[f"label_beat_benchmark_{horizon}d"] = 1 if future_return > 0.05 else 0

        # 最大回撤
        period_data = df.iloc[current_idx:future_idx+1]
        if len(period_data) > 1:
            closes = period_data["close"].values
            cummax = pd.Series(closes).cummax()
            drawdowns = (closes - cummax) / cummax
            max_drawdown = drawdowns.min()
            labels[f"max_drawdown_{horizon}d"] = max_drawdown
        else:
            labels[f"max_drawdown_{horizon}d"] = 0

    return labels


def prepare_training_data(
    dataset: pd.DataFrame,
    target_horizon: int = 20,
    test_size: float = 0.2
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    准备训练数据

    Args:
        dataset: 原始数据集
        target_horizon: 目标预测周期
        test_size: 测试集比例

    Returns:
        (X_train, X_test, y_train, y_test)
    """
    # 移除缺失标签的样本
    target_col = f"return_{target_horizon}d"
    dataset = dataset[dataset[target_col].notna()].copy()

    if len(dataset) == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 特征列
    feature_cols = [
        "return_5d", "return_20d", "return_60d",
        "volatility_20d", "volatility_60d",
        "volume_ratio_5_20", "volume_ratio_20_60",
        "rsi6", "rsi12", "macd", "macd_signal",
        "ma5", "ma10", "ma20", "ma60", "ma_bullish_alignment",
        "price_position_60d", "high_52w_distance",
        "breakout_20d_high", "pullback_to_ma20",
        "market_trend", "market_volatility", "market_volume", "industry_strength",
        "data_quality_score", "data_completeness", "data_stale_days",
    ]

    # 过滤存在的列
    feature_cols = [col for col in feature_cols if col in dataset.columns]

    X = dataset[feature_cols]
    y = dataset[target_col]

    # 时间序列拆分（不打乱顺序）
    split_idx = int(len(dataset) * (1 - test_size))

    X_train = X.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_train = y.iloc[:split_idx]
    y_test = y.iloc[split_idx:]

    return X_train, X_test, y_train, y_test


def get_feature_names() -> list[str]:
    """获取特征名称列表"""
    return [
        "return_5d", "return_20d", "return_60d",
        "volatility_20d", "volatility_60d",
        "volume_ratio_5_20", "volume_ratio_20_60",
        "rsi6", "rsi12", "macd", "macd_signal",
        "ma5", "ma10", "ma20", "ma60", "ma_bullish_alignment",
        "price_position_60d", "high_52w_distance",
        "breakout_20d_high", "pullback_to_ma20",
        "market_trend", "market_volatility", "market_volume", "industry_strength",
        "data_quality_score", "data_completeness", "data_stale_days",
    ]
