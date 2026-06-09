"""
P2-1: 单股预测模型 - 模型训练和预测服务
"""
from __future__ import annotations

import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from app.services.prediction_dataset import (
    build_prediction_dataset,
    get_feature_names,
    prepare_training_data,
)

# 尝试导入机器学习库
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import (
        accuracy_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False


MODEL_DIR = Path("models/prediction")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def _classification_metrics(y_true: pd.Series, y_pred: np.ndarray, y_proba: np.ndarray) -> dict[str, float]:
    if ML_AVAILABLE:
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision_score(y_true, y_pred, zero_division=0)),
            "recall": float(recall_score(y_true, y_pred, zero_division=0)),
            "auc": float(roc_auc_score(y_true, y_proba)) if len(np.unique(y_true)) > 1 else 0.0,
        }
    true = np.array(y_true).astype(int)
    pred = np.array(y_pred).astype(int)
    accuracy = float((true == pred).mean()) if len(true) else 0.0
    tp = float(((true == 1) & (pred == 1)).sum())
    fp = float(((true == 0) & (pred == 1)).sum())
    fn = float(((true == 1) & (pred == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"accuracy": accuracy, "precision": precision, "recall": recall, "auc": 0.0}


class SimpleProbabilityModel:
    """Small local fallback classifier when scikit-learn is unavailable."""

    def __init__(self) -> None:
        self.feature_names: list[str] = []
        self.weights: np.ndarray | None = None
        self.bias: float = 0.0
        self.coef_: np.ndarray | None = None
        self.means: pd.Series | None = None
        self.stds: pd.Series | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        self.feature_names = list(X.columns)
        Xn = X.fillna(0).astype(float)
        self.means = Xn.mean()
        self.stds = Xn.std().replace(0, 1).fillna(1)
        target = y.astype(float).values
        weights = []
        for col in self.feature_names:
            series = Xn[col].values
            if np.std(series) == 0 or np.std(target) == 0:
                weights.append(0.0)
            else:
                corr = float(np.corrcoef(series, target)[0, 1])
                weights.append(0.0 if np.isnan(corr) else corr)
        self.weights = np.array(weights, dtype=float)
        norm = np.linalg.norm(self.weights)
        if norm > 0:
            self.weights = self.weights / norm
        self.coef_ = np.array([self.weights])
        positive_rate = float(target.mean()) if len(target) else 0.5
        self.bias = np.log((positive_rate + 1e-6) / (1 - positive_rate + 1e-6))

    def _score(self, X: pd.DataFrame) -> np.ndarray:
        if self.weights is None:
            raise RuntimeError("模型未训练")
        Xn = X.fillna(0).astype(float).reindex(columns=self.feature_names, fill_value=0)
        standardized = (Xn - self.means) / self.stds if self.means is not None and self.stds is not None else Xn
        standardized = standardized.replace([np.inf, -np.inf], 0).fillna(0)
        return standardized.values @ self.weights + self.bias

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        score = self._score(X)
        up = 1 / (1 + np.exp(-score))
        return np.vstack([1 - up, up]).T

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


class StockPredictionModel:
    """单股预测模型"""

    def __init__(
        self,
        model_type: Literal["logistic", "random_forest", "lightgbm"] = "logistic",
        target_horizon: int = 20,
        prediction_threshold: float = 0.05,
    ):
        self.model_type = model_type
        self.target_horizon = target_horizon
        self.prediction_threshold = prediction_threshold
        self.model = None
        self.feature_names = get_feature_names()
        self.training_metrics = {}
        self.model_version = datetime.now().strftime("%Y%m%d_%H%M%S")

    def train(
        self,
        symbols: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        训练模型

        Args:
            symbols: 训练股票列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            训练结果和评估指标
        """
        if not ML_AVAILABLE and self.model_type != "logistic":
            raise RuntimeError("机器学习库未安装，仅支持 logistic 轻量兜底模型")

        # 1. 构建数据集
        dataset = build_prediction_dataset(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            prediction_horizons=[self.target_horizon],
        )

        if len(dataset) == 0:
            raise ValueError("数据集为空，无法训练")

        # 2. 准备训练数据
        X_train, X_test, y_train_raw, y_test_raw = prepare_training_data(
            dataset=dataset,
            target_horizon=self.target_horizon,
            test_size=0.2,
        )
        if X_train.empty or X_test.empty:
            raise ValueError("训练样本不足，无法完成时间序列切分")

        # 转换为分类标签（涨/跌）
        y_train = (y_train_raw > self.prediction_threshold).astype(int)
        y_test = (y_test_raw > self.prediction_threshold).astype(int)

        # 3. 训练模型
        if self.model_type == "logistic":
            self.model = LogisticRegression(max_iter=1000, random_state=42) if ML_AVAILABLE else SimpleProbabilityModel()
        elif self.model_type == "random_forest":
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
            )
        elif self.model_type == "lightgbm":
            if not LIGHTGBM_AVAILABLE:
                raise RuntimeError("LightGBM 未安装")
            self.model = lgb.LGBMClassifier(
                n_estimators=100,
                max_depth=10,
                learning_rate=0.05,
                random_state=42,
            )
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

        self.model.fit(X_train, y_train)

        # 4. 评估
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)

        y_train_proba = self.model.predict_proba(X_train)[:, 1]
        y_test_proba = self.model.predict_proba(X_test)[:, 1]

        train_metrics = _classification_metrics(y_train, y_train_pred, y_train_proba)
        test_metrics = _classification_metrics(y_test, y_test_pred, y_test_proba)

        self.training_metrics = {
            "train": train_metrics,
            "test": test_metrics,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "positive_ratio_train": y_train.mean(),
            "positive_ratio_test": y_test.mean(),
            "training_date": datetime.now().isoformat(),
        }

        return {
            "status": "success",
            "model_type": self.model_type,
            "target_horizon": self.target_horizon,
            "model_version": self.model_version,
            "metrics": self.training_metrics,
        }

    def predict(
        self,
        symbol: str,
        trade_date: str | None = None,
    ) -> dict[str, Any]:
        """
        预测单只股票

        Args:
            symbol: 股票代码
            trade_date: 预测日期（默认最新）

        Returns:
            预测结果
        """
        if self.model is None:
            raise RuntimeError("模型未训练，请先调用 train()")

        if trade_date is None:
            trade_date = datetime.now().strftime("%Y-%m-%d")

        # 构建特征
        from app.services.prediction_dataset import (
            extract_technical_features,
            extract_market_features,
            extract_quality_features,
        )
        from app.services.factor_engine import get_factor_data_for_symbol
        from datetime import timedelta

        # 获取历史数据
        start_date = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=120)).strftime("%Y-%m-%d")
        factor_data = get_factor_data_for_symbol(
            symbol=symbol,
            start_date=start_date,
            end_date=trade_date,
        )

        if not factor_data or len(factor_data) < 20:
            return {
                "symbol": symbol,
                "trade_date": trade_date,
                "prediction": "insufficient_data",
                "confidence": 0,
                "error": "历史数据不足"
            }

        df = pd.DataFrame(factor_data).sort_values("trade_date")

        # 提取特征
        tech_features = extract_technical_features(df)
        market_features = extract_market_features(trade_date)
        quality_features = extract_quality_features(symbol, trade_date)

        features = {**tech_features, **market_features, **quality_features}

        # 构建特征向量
        X = pd.DataFrame([features])[self.feature_names]

        # 填充缺失值
        X = X.fillna(0)

        # 预测
        prediction_proba = self.model.predict_proba(X)[0]
        prediction_class = self.model.predict(X)[0]

        # 获取特征重要性（如果支持）
        feature_importance = []
        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            top_indices = np.argsort(importances)[-5:][::-1]
            feature_importance = [
                {
                    "feature": self.feature_names[idx],
                    "importance": float(importances[idx])
                }
                for idx in top_indices
            ]
        elif hasattr(self.model, "coef_"):
            coefs = np.abs(getattr(self.model, "coef_")[0])
            top_indices = np.argsort(coefs)[-5:][::-1]
            feature_importance = [
                {
                    "feature": self.feature_names[idx],
                    "importance": float(coefs[idx] / (coefs.sum() or 1.0)),
                }
                for idx in top_indices
            ]

        result = {
            "symbol": symbol,
            "trade_date": trade_date,
            "model_version": self.model_version,
            "target_horizon": self.target_horizon,
            "prediction": {
                "up_probability": float(prediction_proba[1]),
                "down_probability": float(prediction_proba[0]),
                "predicted_class": "up" if prediction_class == 1 else "down",
                "confidence": float(max(prediction_proba)),
            },
            "feature_importance": feature_importance,
            "data_quality": quality_features.get("data_quality_score", 0.8),
            "warning": self._get_prediction_warning(prediction_proba, quality_features),
        }

        return result

    def _get_prediction_warning(
        self,
        prediction_proba: np.ndarray,
        quality_features: dict[str, Any]
    ) -> str | None:
        """生成预测警告"""
        confidence = max(prediction_proba)
        quality_score = quality_features.get("data_quality_score", 0.8)

        if quality_score < 0.5:
            return "数据质量差，预测结果不可靠"
        elif confidence < 0.6:
            return "预测置信度低，建议谨慎参考"
        elif quality_score < 0.7:
            return "数据质量一般，结论仅供参考"
        else:
            return None

    def save(self, filepath: str | None = None) -> str:
        """保存模型"""
        if self.model is None:
            raise RuntimeError("模型未训练，无法保存")

        if filepath is None:
            filepath = str(MODEL_DIR / f"model_{self.model_version}.pkl")

        model_data = {
            "model": self.model,
            "model_type": self.model_type,
            "target_horizon": self.target_horizon,
            "prediction_threshold": self.prediction_threshold,
            "feature_names": self.feature_names,
            "training_metrics": self.training_metrics,
            "model_version": self.model_version,
        }

        with open(filepath, "wb") as f:
            pickle.dump(model_data, f)

        # 保存元数据
        meta_filepath = filepath.replace(".pkl", "_meta.json")
        with open(meta_filepath, "w") as f:
            json.dump({
                "model_type": self.model_type,
                "target_horizon": self.target_horizon,
                "model_version": self.model_version,
                "training_metrics": self.training_metrics,
            }, f, indent=2)

        return filepath

    @classmethod
    def load(cls, filepath: str) -> "StockPredictionModel":
        """加载模型"""
        with open(filepath, "rb") as f:
            model_data = pickle.load(f)

        instance = cls(
            model_type=model_data["model_type"],
            target_horizon=model_data["target_horizon"],
            prediction_threshold=model_data["prediction_threshold"],
        )

        instance.model = model_data["model"]
        instance.feature_names = model_data["feature_names"]
        instance.training_metrics = model_data["training_metrics"]
        instance.model_version = model_data["model_version"]

        return instance


def get_latest_model(model_type: str = "logistic") -> StockPredictionModel | None:
    """获取最新训练的模型"""
    model_files = list(MODEL_DIR.glob(f"model_*.pkl"))

    if not model_files:
        return None

    # 按修改时间排序
    latest_file = max(model_files, key=lambda p: p.stat().st_mtime)

    try:
        return StockPredictionModel.load(str(latest_file))
    except Exception:
        return None


def batch_predict(
    symbols: list[str],
    trade_date: str | None = None,
    model: StockPredictionModel | None = None,
) -> list[dict[str, Any]]:
    """
    批量预测

    Args:
        symbols: 股票代码列表
        trade_date: 预测日期
        model: 预测模型（None 表示使用最新模型）

    Returns:
        预测结果列表
    """
    if model is None:
        model = get_latest_model()
        if model is None:
            raise RuntimeError("没有可用的预测模型，请先训练")

    results = []
    for symbol in symbols:
        try:
            result = model.predict(symbol=symbol, trade_date=trade_date)
            results.append(result)
        except Exception as e:
            results.append({
                "symbol": symbol,
                "trade_date": trade_date,
                "prediction": "error",
                "error": str(e)
            })

    return results
