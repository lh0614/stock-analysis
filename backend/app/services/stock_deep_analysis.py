"""
单股深度分析预测引擎

对单只股票进行多维度分析，输出可解释、可验证、可行动的分析预测
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import numpy as np

from app.services.data_quality import get_symbol_quality
from app.services.factors import get_factors_for_symbol


class EvidenceItem(BaseModel):
    """证据项"""
    dimension: str = Field(..., description="维度：技术/资金/财务/事件等")
    factor: str = Field(..., description="因子名称")
    value: Any = Field(..., description="因子值")
    interpretation: str = Field(..., description="解读")
    weight: float = Field(default=1.0, description="权重")


class RiskItem(BaseModel):
    """风险项"""
    type: str = Field(..., description="风险类型")
    level: str = Field(..., description="风险等级: high/medium/low")
    message: str = Field(..., description="风险描述")


class TriggerCondition(BaseModel):
    """触发条件"""
    condition: str = Field(..., description="条件描述")
    current_status: str = Field(..., description="当前状态")
    is_met: bool = Field(..., description="是否已满足")


class InvalidCondition(BaseModel):
    """失效条件"""
    condition: str = Field(..., description="条件描述")
    threshold: str = Field(..., description="阈值")


class TargetZone(BaseModel):
    """目标区间"""
    level: str = Field(..., description="级别: conservative/base/aggressive")
    price: float = Field(..., description="目标价格")
    return_pct: float = Field(..., description="收益率")
    probability: float = Field(..., description="概率估计")


class SimilarCase(BaseModel):
    """相似案例"""
    date: str = Field(..., description="日期")
    symbol: str = Field(..., description="股票代码")
    similarity: float = Field(..., description="相似度")
    subsequent_return_5d: Optional[float] = Field(None, description="后续5日收益")
    subsequent_return_20d: Optional[float] = Field(None, description="后续20日收益")


class StockAnalysisResult(BaseModel):
    """单股分析结果"""
    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    analysis_date: str = Field(..., description="分析日期")

    # 核心结论
    verdict: str = Field(..., description="结论: actionable/watch/avoid/insufficient_data")
    horizon: str = Field(..., description="周期: short/medium/long")
    confidence: float = Field(..., description="置信度 0-1")

    # 预期收益和风险
    win_rate_estimate: Optional[float] = Field(None, description="胜率估计")
    expected_return_range: Dict[str, float] = Field(
        default_factory=dict,
        description="预期收益区间: {low, base, high}"
    )
    risk_reward_ratio: Optional[float] = Field(None, description="风险收益比")

    # 条件和目标
    trigger_conditions: List[TriggerCondition] = Field(default_factory=list)
    invalid_conditions: List[InvalidCondition] = Field(default_factory=list)
    target_zones: List[TargetZone] = Field(default_factory=list)

    # 证据链
    evidence: List[EvidenceItem] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list, description="矛盾点")

    # 数据质量
    data_quality: Dict[str, Any] = Field(default_factory=dict)

    # 相似案例
    similar_cases: List[SimilarCase] = Field(default_factory=list)

    # 风险
    risks: List[RiskItem] = Field(default_factory=list)

    # 策略匹配
    strategy_matches: List[str] = Field(default_factory=list, description="匹配的策略ID")

    # 市场环境
    market_environment: Optional[str] = Field(None, description="市场环境")
    sector_strength: Optional[str] = Field(None, description="行业强弱")


def analyze_technical_structure(factors: Dict[str, Any], current_price: float) -> List[EvidenceItem]:
    """分析技术结构"""
    evidence = []

    # 均线分析
    if factors.get('close_above_ma20'):
        evidence.append(EvidenceItem(
            dimension="技术结构",
            factor="close_above_ma20",
            value=True,
            interpretation="价格在MA20上方，短期趋势向上",
            weight=1.5
        ))

    if factors.get('ma_bullish_alignment'):
        evidence.append(EvidenceItem(
            dimension="技术结构",
            factor="ma_bullish_alignment",
            value=True,
            interpretation="均线多头排列，中期趋势健康",
            weight=2.0
        ))

    # 突破分析
    if factors.get('breakout_20d_high'):
        evidence.append(EvidenceItem(
            dimension="技术结构",
            factor="breakout_20d_high",
            value=True,
            interpretation="创20日新高，突破形态确立",
            weight=2.0
        ))

    # 回踩分析
    if factors.get('pullback_to_ma20'):
        evidence.append(EvidenceItem(
            dimension="技术结构",
            factor="pullback_to_ma20",
            value=True,
            interpretation="近期回踩MA20支撑，可能形成二次买点",
            weight=1.8
        ))

    # 价格位置
    price_position = factors.get('price_position_60d', 0.5)
    if price_position > 0.8:
        interpretation = "价格处于60日高位区域，追高风险较大"
        weight = -1.5
    elif price_position > 0.5:
        interpretation = "价格处于60日中高位，有一定上行空间"
        weight = 1.0
    else:
        interpretation = "价格处于60日低位，估值相对合理"
        weight = 1.5

    evidence.append(EvidenceItem(
        dimension="技术结构",
        factor="price_position_60d",
        value=round(price_position, 3),
        interpretation=interpretation,
        weight=weight
    ))

    # MACD分析
    macd_hist = factors.get('macd_hist', 0)
    if macd_hist > 0:
        evidence.append(EvidenceItem(
            dimension="技术结构",
            factor="macd_hist",
            value=round(macd_hist, 4),
            interpretation="MACD柱状线为正，动能偏多",
            weight=1.0
        ))

    return evidence


def analyze_momentum_and_volatility(factors: Dict[str, Any]) -> List[EvidenceItem]:
    """分析动量和波动率"""
    evidence = []

    # 短期收益
    return_5d = factors.get('return_5d', 0)
    if abs(return_5d) > 0.05:
        interpretation = f"近5日{'上涨' if return_5d > 0 else '下跌'}{abs(return_5d)*100:.1f}%，短期动能{'较强' if return_5d > 0 else '较弱'}"
        weight = 1.5 if return_5d > 0 else -1.5
        evidence.append(EvidenceItem(
            dimension="动量",
            factor="return_5d",
            value=round(return_5d, 4),
            interpretation=interpretation,
            weight=weight
        ))

    # 中期收益
    return_20d = factors.get('return_20d', 0)
    if abs(return_20d) > 0.1:
        interpretation = f"近20日{'上涨' if return_20d > 0 else '下跌'}{abs(return_20d)*100:.1f}%，中期趋势{'向上' if return_20d > 0 else '向下'}"
        weight = 1.8 if return_20d > 0 else -1.8
        evidence.append(EvidenceItem(
            dimension="动量",
            factor="return_20d",
            value=round(return_20d, 4),
            interpretation=interpretation,
            weight=weight
        ))

    # 波动率
    volatility_20d = factors.get('volatility_20d', 0)
    if volatility_20d > 0.03:
        evidence.append(EvidenceItem(
            dimension="风险",
            factor="volatility_20d",
            value=round(volatility_20d, 4),
            interpretation=f"20日波动率{volatility_20d*100:.1f}%，波动较大",
            weight=-1.0
        ))

    # RSI分析
    rsi12 = factors.get('rsi12')
    if rsi12 is not None:
        if rsi12 > 70:
            interpretation = f"RSI12={rsi12:.1f}，超买区域，短期回调风险"
            weight = -1.5
        elif rsi12 < 30:
            interpretation = f"RSI12={rsi12:.1f}，超卖区域，可能反弹"
            weight = 1.5
        else:
            interpretation = f"RSI12={rsi12:.1f}，处于正常区间"
            weight = 0.5

        evidence.append(EvidenceItem(
            dimension="动量",
            factor="rsi12",
            value=round(rsi12, 2),
            interpretation=interpretation,
            weight=weight
        ))

    return evidence


def analyze_volume_and_liquidity(factors: Dict[str, Any]) -> List[EvidenceItem]:
    """分析成交量和流动性"""
    evidence = []

    # 量比分析
    volume_ratio = factors.get('volume_ratio_5_20', 1.0)
    if volume_ratio > 1.5:
        evidence.append(EvidenceItem(
            dimension="资金",
            factor="volume_ratio_5_20",
            value=round(volume_ratio, 2),
            interpretation=f"近5日量比{volume_ratio:.2f}，明显放量",
            weight=1.8
        ))
    elif volume_ratio < 0.7:
        evidence.append(EvidenceItem(
            dimension="资金",
            factor="volume_ratio_5_20",
            value=round(volume_ratio, 2),
            interpretation=f"近5日量比{volume_ratio:.2f}，成交萎缩",
            weight=-1.0
        ))

    return evidence


def calculate_risk_reward_ratio(
    current_price: float,
    factors: Dict[str, Any],
    evidence: List[EvidenceItem]
) -> Optional[float]:
    """计算风险收益比"""
    # 基于技术位置估算目标和止损
    price_position = factors.get('price_position_60d', 0.5)
    volatility = factors.get('volatility_20d', 0.02)

    # 目标空间估算（简化版）
    if price_position < 0.3:
        # 低位，目标空间大
        target_return = 0.15
    elif price_position < 0.7:
        target_return = 0.10
    else:
        target_return = 0.05

    # 止损空间估算
    stop_loss = min(0.08, volatility * 3)

    if stop_loss > 0:
        return target_return / stop_loss
    return None


def generate_trigger_conditions(factors: Dict[str, Any], evidence: List[EvidenceItem]) -> List[TriggerCondition]:
    """生成触发条件"""
    conditions = []

    # 检查是否已突破
    if factors.get('breakout_20d_high'):
        conditions.append(TriggerCondition(
            condition="突破20日新高",
            current_status="已满足",
            is_met=True
        ))
    else:
        conditions.append(TriggerCondition(
            condition="突破20日新高",
            current_status="待确认",
            is_met=False
        ))

    # 检查均线支撑
    if factors.get('close_above_ma20'):
        conditions.append(TriggerCondition(
            condition="站稳MA20",
            current_status="已满足",
            is_met=True
        ))
    else:
        conditions.append(TriggerCondition(
            condition="站稳MA20",
            current_status="待确认",
            is_met=False
        ))

    # 检查放量
    volume_ratio = factors.get('volume_ratio_5_20', 1.0)
    if volume_ratio > 1.3:
        conditions.append(TriggerCondition(
            condition="放量突破（量比>1.3）",
            current_status="已满足",
            is_met=True
        ))
    else:
        conditions.append(TriggerCondition(
            condition="放量突破（量比>1.3）",
            current_status=f"当前量比{volume_ratio:.2f}",
            is_met=False
        ))

    return conditions


def generate_invalid_conditions(factors: Dict[str, Any]) -> List[InvalidCondition]:
    """生成失效条件"""
    conditions = []

    ma20 = factors.get('ma20')
    if ma20 and ma20 > 0:
        conditions.append(InvalidCondition(
            condition="跌破MA20支撑",
            threshold=f"收盘价<{ma20:.2f}"
        ))

    # 止损条件
    conditions.append(InvalidCondition(
        condition="触发止损",
        threshold="单日跌幅>5%或累计亏损>8%"
    ))

    # RSI超买后回落
    rsi12 = factors.get('rsi12')
    if rsi12 and rsi12 > 70:
        conditions.append(InvalidCondition(
            condition="RSI超买后回落",
            threshold="RSI12从超买区下穿70"
        ))

    return conditions


def generate_target_zones(current_price: float, factors: Dict[str, Any]) -> List[TargetZone]:
    """生成目标区间"""
    price_position = factors.get('price_position_60d', 0.5)
    volatility = factors.get('volatility_20d', 0.02)

    # 根据价格位置和波动率估算目标
    if price_position < 0.3:
        base_return = 0.12
    elif price_position < 0.7:
        base_return = 0.08
    else:
        base_return = 0.04

    zones = [
        TargetZone(
            level="conservative",
            price=round(current_price * (1 + base_return * 0.5), 2),
            return_pct=round(base_return * 0.5, 4),
            probability=0.65
        ),
        TargetZone(
            level="base",
            price=round(current_price * (1 + base_return), 2),
            return_pct=round(base_return, 4),
            probability=0.45
        ),
        TargetZone(
            level="aggressive",
            price=round(current_price * (1 + base_return * 1.5), 2),
            return_pct=round(base_return * 1.5, 4),
            probability=0.25
        )
    ]

    return zones


def identify_risks(factors: Dict[str, Any], evidence: List[EvidenceItem]) -> List[RiskItem]:
    """识别风险"""
    risks = []

    # 价格位置风险
    price_position = factors.get('price_position_60d', 0.5)
    if price_position > 0.85:
        risks.append(RiskItem(
            type="估值",
            level="high",
            message="价格处于60日高位区间（85%+），追高风险较大"
        ))

    # 波动率风险
    volatility = factors.get('volatility_20d', 0.02)
    if volatility > 0.04:
        risks.append(RiskItem(
            type="波动",
            level="medium",
            message=f"20日波动率{volatility*100:.1f}%，价格波动较大"
        ))

    # RSI超买风险
    rsi12 = factors.get('rsi12')
    if rsi12 and rsi12 > 75:
        risks.append(RiskItem(
            type="技术",
            level="high",
            message=f"RSI12={rsi12:.1f}，严重超买，短期回调风险"
        ))

    # 成交量萎缩风险
    volume_ratio = factors.get('volume_ratio_5_20', 1.0)
    if volume_ratio < 0.6:
        risks.append(RiskItem(
            type="资金",
            level="medium",
            message=f"量比{volume_ratio:.2f}，成交萎缩，市场关注度不足"
        ))

    return risks


def make_verdict(
    evidence: List[EvidenceItem],
    quality_level: str,
    risks: List[RiskItem],
    trigger_conditions: List[TriggerCondition]
) -> tuple[str, float, str]:
    """
    综合判断结论
    返回: (verdict, confidence, horizon)
    """
    # 数据质量不足则无法分析
    if quality_level == 'D':
        return "insufficient_data", 0.0, "unknown"

    # 计算综合得分
    total_score = sum(e.weight for e in evidence)
    positive_score = sum(e.weight for e in evidence if e.weight > 0)
    negative_score = abs(sum(e.weight for e in evidence if e.weight < 0))

    # 检查触发条件满足情况
    met_conditions = sum(1 for c in trigger_conditions if c.is_met)
    total_conditions = len(trigger_conditions)
    condition_ratio = met_conditions / total_conditions if total_conditions > 0 else 0

    # 检查高风险
    has_high_risk = any(r.level == "high" for r in risks)

    # 判断逻辑
    if quality_level == 'C' or has_high_risk:
        verdict = "avoid"
        confidence = 0.6
    elif total_score > 5 and condition_ratio >= 0.6 and positive_score > negative_score * 2:
        verdict = "actionable"
        confidence = min(0.85, 0.6 + condition_ratio * 0.25)
    elif total_score > 2:
        verdict = "watch"
        confidence = 0.5 + condition_ratio * 0.2
    elif total_score < -3:
        verdict = "avoid"
        confidence = 0.7
    else:
        verdict = "watch"
        confidence = 0.4

    # 判断周期
    if condition_ratio >= 0.6:
        horizon = "short"  # 短期：1-2周
    else:
        horizon = "medium"  # 中期：1-2月

    return verdict, confidence, horizon


async def run_deep_analysis(symbol: str, name: str = "") -> StockAnalysisResult:
    """
    执行单股深度分析

    Args:
        symbol: 股票代码
        name: 股票名称（可选）

    Returns:
        StockAnalysisResult: 分析结果
    """
    # 1. 数据质量检查
    quality_info = get_symbol_quality(symbol)
    quality_level = quality_info.get('quality_level', 'D')

    if quality_level == 'D':
        return StockAnalysisResult(
            symbol=symbol,
            name=name,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            verdict="insufficient_data",
            horizon="unknown",
            confidence=0.0,
            data_quality=quality_info,
            evidence=[],
            risks=[RiskItem(
                type="数据",
                level="high",
                message="数据质量不足，无法进行可靠分析"
            )]
        )

    # 2. 计算因子
    factors = get_factors_for_symbol(symbol)
    if not factors:
        return StockAnalysisResult(
            symbol=symbol,
            name=name,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            verdict="insufficient_data",
            horizon="unknown",
            confidence=0.0,
            data_quality=quality_info,
            evidence=[],
            risks=[RiskItem(
                type="数据",
                level="high",
                message="因子计算失败"
            )]
        )

    # 获取当前价格（从因子中推算，因为get_factors_for_symbol不返回close）
    # 可以从ma5或通过return_1d反推
    current_price = factors.get('close', 0)
    if current_price <= 0:
        # 尝试从ma5推算（ma5通常接近当前价）
        current_price = factors.get('ma5', 0)

    if current_price <= 0:
        return StockAnalysisResult(
            symbol=symbol,
            name=name,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            verdict="insufficient_data",
            horizon="unknown",
            confidence=0.0,
            data_quality=quality_info
        )

    # 3. 多维度分析
    evidence = []
    evidence.extend(analyze_technical_structure(factors, current_price))
    evidence.extend(analyze_momentum_and_volatility(factors))
    evidence.extend(analyze_volume_and_liquidity(factors))

    # 4. 风险识别
    risks = identify_risks(factors, evidence)

    # 5. 生成条件
    trigger_conditions = generate_trigger_conditions(factors, evidence)
    invalid_conditions = generate_invalid_conditions(factors)

    # 6. 综合判断
    verdict, confidence, horizon = make_verdict(
        evidence, quality_level, risks, trigger_conditions
    )

    # 7. 计算风险收益比
    risk_reward = calculate_risk_reward_ratio(current_price, factors, evidence)

    # 8. 生成目标区间
    target_zones = generate_target_zones(current_price, factors)

    # 9. 胜率估算（简化版，基于历史统计）
    win_rate = None
    if verdict == "actionable":
        # 满足条件越多，胜率越高
        met_ratio = sum(1 for c in trigger_conditions if c.is_met) / len(trigger_conditions)
        win_rate = 0.45 + met_ratio * 0.2  # 45%-65%

    # 10. 预期收益区间
    expected_return = {}
    if target_zones:
        expected_return = {
            "low": target_zones[0].return_pct if len(target_zones) > 0 else 0,
            "base": target_zones[1].return_pct if len(target_zones) > 1 else 0,
            "high": target_zones[2].return_pct if len(target_zones) > 2 else 0
        }

    # 11. 矛盾点识别
    contradictions = []
    if any(e.factor == "breakout_20d_high" and e.value for e in evidence):
        if any(e.factor == "price_position_60d" and e.value > 0.8 for e in evidence):
            contradictions.append("突破新高但价格位置已偏高，追高需谨慎")

    return StockAnalysisResult(
        symbol=symbol,
        name=name,
        analysis_date=datetime.now().strftime('%Y-%m-%d'),
        verdict=verdict,
        horizon=horizon,
        confidence=confidence,
        win_rate_estimate=win_rate,
        expected_return_range=expected_return,
        risk_reward_ratio=risk_reward,
        trigger_conditions=trigger_conditions,
        invalid_conditions=invalid_conditions,
        target_zones=target_zones,
        evidence=evidence,
        contradictions=contradictions,
        data_quality=quality_info,
        risks=risks,
        similar_cases=[],  # TODO: 实现相似案例匹配
        strategy_matches=[]  # TODO: 实现策略匹配
    )
