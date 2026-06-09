#!/usr/bin/env python3
"""P2 verification: prediction, market fit, portfolio risk, factor decay."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.main import app
from app.models.strategy_spec import ConditionSpec, RankingSpec, StrategySpec
from app.services.factor_engine import get_factor_data_for_symbol
from app.services.factors import monitor_factor_decay
from app.services.market_data import get_market_indicators
from app.services.portfolio_risk import analyze_portfolio_risk, calculate_portfolio_metrics
from app.services.prediction_dataset import build_prediction_dataset
from app.services.stock_pool import get_stock_info
from app.services.stock_prediction import ML_AVAILABLE
from app.services.strategy_environment import classify_strategy_environment, check_strategy_market_fit, get_current_market_state


def check(condition: bool, label: str) -> bool:
    print(("✅" if condition else "❌"), label)
    return condition


def main() -> int:
    results: list[bool] = []
    paths = {getattr(route, "path", "") for route in app.routes}
    for path in [
        "/api/v1/prediction/train",
        "/api/v1/prediction/predict",
        "/api/v1/prediction/model-metrics",
        "/api/v1/strategy-environment/market-state",
        "/api/v1/portfolio-risk/generate-report",
        "/api/v1/factors/monitor/decay",
    ]:
        results.append(check(path in paths, f"API 已挂载: {path}"))

    results.append(check(ML_AVAILABLE, "scikit-learn 机器学习依赖可用"))

    factors = get_factor_data_for_symbol("000001")
    results.append(check(isinstance(factors, list), "因子适配层可返回序列"))

    market = get_market_indicators()
    results.append(check("trend_signal" in market, "市场数据适配层可返回指标"))

    info = get_stock_info("000001")
    results.append(check(bool(info and info.get("symbol") == "000001"), "股票池适配层可返回个股信息"))

    spec = StrategySpec(
        name="P2验收策略",
        entry_conditions=[ConditionSpec(factor="return_20d", op="gt", value=-1, weight=1.0)],
        ranking=[RankingSpec(factor="return_20d", direction="desc", weight=1.0)],
    )
    labels = classify_strategy_environment(spec)
    current = get_current_market_state()
    fit = check_strategy_market_fit(labels, current)
    results.append(check("market_states" in labels and "fit_status" in fit, "市场环境适配链路可运行"))

    risk = analyze_portfolio_risk([
        {"symbol": "000001", "total_score": 80, "signal_count": 2, "confidence": "medium"},
        {"symbol": "600000", "total_score": 70, "signal_count": 1, "confidence": "low"},
    ])
    metrics = calculate_portfolio_metrics([
        {"symbol": "000001", "total_score": 80, "signal_count": 2, "confidence": "medium"},
    ])
    results.append(check("concentration_risk" in risk and "diversity_score" in metrics, "组合风控链路可运行"))

    dataset = build_prediction_dataset(symbols=["000001"], prediction_horizons=[5])
    results.append(check(hasattr(dataset, "columns"), "预测数据集构建函数可运行"))

    decay = monitor_factor_decay(factors=["return_20d"], horizon=5)
    results.append(check("results" in decay and "alerts" in decay, "因子失效监控可运行"))

    passed = sum(results)
    total = len(results)
    print(f"\nP2 验证: {passed}/{total} ({passed / total * 100:.1f}%)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
