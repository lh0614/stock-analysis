"""
P2-1: 单股预测模型 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import Any, Literal

from app.services.stock_prediction import (
    StockPredictionModel,
    batch_predict,
    get_latest_model,
)

router = APIRouter()


class TrainModelRequest(BaseModel):
    """训练模型请求"""
    model_config = ConfigDict(protected_namespaces=())

    model_type: Literal["logistic", "random_forest", "lightgbm"] = "logistic"
    target_horizon: int = 20
    prediction_threshold: float = 0.05
    symbols: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None


class PredictRequest(BaseModel):
    """预测请求"""
    symbol: str
    trade_date: str | None = None


class BatchPredictRequest(BaseModel):
    """批量预测请求"""
    symbols: list[str]
    trade_date: str | None = None


@router.post("/train")
async def train_prediction_model(request: TrainModelRequest):
    """
    训练单股预测模型

    训练数据集包含：
    - 技术因子特征（趋势、波动、成交量、技术指标等）
    - 市场环境特征（市场趋势、波动率、成交量等）
    - 数据质量特征（完整度、时效性等）

    标签：
    - 未来 N 日收益
    - 是否上涨
    - 是否跑赢基准
    """
    try:
        model = StockPredictionModel(
            model_type=request.model_type,
            target_horizon=request.target_horizon,
            prediction_threshold=request.prediction_threshold,
        )

        result = model.train(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        # 保存模型
        filepath = model.save()

        return {
            "status": "success",
            "message": "模型训练完成",
            "model_path": filepath,
            **result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型训练失败: {str(e)}")


@router.post("/predict")
async def predict_stock(request: PredictRequest):
    """
    预测单只股票

    返回：
    - up_probability: 上涨概率
    - down_probability: 下跌概率
    - predicted_class: 预测类别（up/down）
    - confidence: 置信度
    - feature_importance: 主要贡献因子
    - warning: 预测警告（如有）
    """
    try:
        model = get_latest_model()
        if model is None:
            raise HTTPException(status_code=404, detail="没有可用的预测模型，请先训练")

        result = model.predict(
            symbol=request.symbol,
            trade_date=request.trade_date,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")


@router.post("/batch-predict")
async def batch_predict_stocks(request: BatchPredictRequest):
    """
    批量预测多只股票

    适用场景：
    - 对选股结果进行预测评分
    - 对持仓股票进行风险预警
    - 对候选池进行优先级排序
    """
    try:
        results = batch_predict(
            symbols=request.symbols,
            trade_date=request.trade_date,
        )

        # 按上涨概率排序
        def up_probability(item: dict[str, Any]) -> float:
            prediction = item.get("prediction")
            if isinstance(prediction, dict):
                return float(prediction.get("up_probability", 0) or 0)
            return 0.0

        sorted_results = sorted(
            [r for r in results if isinstance(r.get("prediction"), dict)],
            key=up_probability,
            reverse=True,
        )

        error_results = [r for r in results if not isinstance(r.get("prediction"), dict)]

        return {
            "status": "success",
            "total": len(request.symbols),
            "success": len(sorted_results),
            "failed": len(error_results),
            "predictions": sorted_results,
            "errors": error_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量预测失败: {str(e)}")


@router.get("/model-info")
async def get_model_info():
    """
    获取当前模型信息

    返回：
    - 模型类型
    - 预测周期
    - 训练指标
    - 模型版本
    """
    try:
        model = get_latest_model()
        if model is None:
            return {
                "status": "no_model",
                "message": "没有可用的模型",
            }

        return {
            "status": "available",
            "model_type": model.model_type,
            "target_horizon": model.target_horizon,
            "model_version": model.model_version,
            "training_metrics": model.training_metrics,
            "feature_count": len(model.feature_names),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型信息失败: {str(e)}")


@router.get("/model-metrics")
async def get_model_metrics():
    """
    获取模型评估指标

    返回：
    - 训练集指标（准确率、精确率、召回率、AUC）
    - 测试集指标
    - 样本分布
    - 适用范围说明
    """
    try:
        model = get_latest_model()
        if model is None:
            raise HTTPException(status_code=404, detail="没有可用的模型")

        metrics = model.training_metrics

        return {
            "status": "success",
            "model_version": model.model_version,
            "target_horizon": f"{model.target_horizon}天",
            "training_metrics": metrics.get("train", {}),
            "test_metrics": metrics.get("test", {}),
            "sample_info": {
                "train_samples": metrics.get("train_samples", 0),
                "test_samples": metrics.get("test_samples", 0),
                "positive_ratio_train": metrics.get("positive_ratio_train", 0),
                "positive_ratio_test": metrics.get("positive_ratio_test", 0),
            },
            "applicable_scope": "适用于 A 股市场中长线预测，数据质量 B 级以上",
            "limitations": [
                "模型基于历史数据，无法预测突发事件",
                "数据质量差时预测不可靠",
                "极端市场环境下预测准确率下降",
            ],
            "training_date": metrics.get("training_date"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型指标失败: {str(e)}")
