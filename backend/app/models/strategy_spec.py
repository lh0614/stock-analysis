"""策略规格定义（StrategySpec）- PRD 核心数据结构"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class UniverseSpec(BaseModel):
    """股票池规格"""
    market: str = "A股"
    exclude_st: bool = True
    boards: list[str] = Field(default_factory=lambda: ["main", "chinext", "star"])
    custom_symbols: list[str] | None = None
    use_watchlist: bool = False


class ConditionSpec(BaseModel):
    """条件规格"""
    factor: str
    op: Literal["gt", "lt", "eq", "gte", "lte", "in", "not_in"]
    value: Any
    weight: float = 1.0


class RankingSpec(BaseModel):
    """排序规格"""
    factor: str
    direction: Literal["asc", "desc"] = "desc"
    weight: float = 1.0


class PositionSpec(BaseModel):
    """仓位规则"""
    max_positions: int = 10
    weighting: Literal["equal_weight", "score_weight", "volatility_inverse"] = "equal_weight"
    max_single_position: float = 0.2  # 单股最大仓位比例


class ExitRule(BaseModel):
    """退出规则"""
    type: Literal["stop_loss", "stop_profit", "trailing_stop", "time_exit", "signal_exit"]
    params: dict[str, Any]


class RiskFilter(BaseModel):
    """风险过滤"""
    quality_level: list[str] = Field(default_factory=lambda: ["A", "B", "C"])
    min_avg_amount_20d: float = 1e8  # 最小20日均成交额
    max_volatility_60d: float | None = None


class StrategySpec(BaseModel):
    """策略完整规格 - PRD 定义的核心结构"""

    # 基本信息
    id: str | None = None
    name: str
    description: str = ""
    source: Literal["generated", "manual", "uploaded", "optimized"] = "manual"
    intent_text: str = ""  # 用户原始意图

    # 策略配置
    horizon: Literal["short", "medium", "long"] = "medium"
    universe: UniverseSpec = Field(default_factory=UniverseSpec)

    # 入场条件
    entry_conditions: list[ConditionSpec] = Field(default_factory=list)

    # 排序规则
    ranking: list[RankingSpec] = Field(default_factory=list)

    # 退出条件
    exit_conditions: list[ExitRule] = Field(default_factory=list)

    # 风险过滤
    risk_filters: RiskFilter = Field(default_factory=RiskFilter)

    # 仓位管理
    position: PositionSpec = Field(default_factory=PositionSpec)

    # 调仓周期
    rebalance: Literal["daily", "weekly", "monthly"] = "weekly"

    # 版本信息
    version: str = "1.0.0"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # 状态
    status: Literal["idea", "generated", "backtested", "validated", "active", "watch", "degraded", "retired"] = "idea"

    # 标签
    tags: list[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "放量突破回踩策略",
                "horizon": "medium",
                "intent_text": "找最近20个交易日放量突破、回踩MA20不破、行业强于大盘的股票",
                "entry_conditions": [
                    {"factor": "breakout_20d_high", "op": "eq", "value": True, "weight": 1.0},
                    {"factor": "volume_ratio_5_20", "op": "gt", "value": 1.5, "weight": 0.8},
                    {"factor": "close_above_ma20", "op": "eq", "value": True, "weight": 1.0}
                ],
                "ranking": [
                    {"factor": "volume_ratio_5_20", "direction": "desc", "weight": 0.6},
                    {"factor": "return_20d", "direction": "desc", "weight": 0.4}
                ]
            }
        }


class CandidateStock(BaseModel):
    """候选股票结果"""
    symbol: str
    name: str
    score: float
    rank: int
    quality_level: str
    matched_conditions: list[dict[str, Any]]
    factor_values: dict[str, Any]
    risks: list[dict[str, str]] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ScreenerResult(BaseModel):
    """选股结果"""
    run_id: str
    strategy_spec: StrategySpec
    candidates: list[CandidateStock]
    total_scanned: int
    total_matched: int
    execution_time_ms: float
    data_quality_summary: dict[str, Any] | None = None  # 数据质量摘要
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

