"""Intent parsing API: user requirement -> StrategySpec."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.strategy_spec import StrategySpec
from app.services.llm_intent_parser import (
    LLMIntentParserUnavailable,
    is_llm_intent_parser_enabled,
    parse_intent_with_deepseek,
)
from app.services.intent_parser import parse_intent_to_strategy_spec
from app.services.strategy_research import (
    clarify_strategy_goal,
    generate_candidate_strategies,
    validate_strategy_spec,
)

router = APIRouter()


class ParseIntentRequest(BaseModel):
    text: str
    overrides: dict[str, Any] | None = None
    use_llm: bool = True


class ParseIntentResponse(BaseModel):
    intent_text: str
    strategy_spec: StrategySpec
    warnings: list[str] = []
    parser: str = "rule"
    llm_enabled: bool = False
    fallback_used: bool = False


class GenerateStrategiesRequest(BaseModel):
    text: str
    count: int = 4
    use_llm: bool = True


class ValidateSpecRequest(BaseModel):
    strategy_spec: dict[str, Any]


@router.post("/parse", response_model=ParseIntentResponse)
async def parse_intent(request: ParseIntentRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="请输入选股要求")
    parser = "rule"
    fallback_used = False
    warnings: list[str] = []
    if request.use_llm and is_llm_intent_parser_enabled():
        try:
            spec = parse_intent_with_deepseek(request.text, request.overrides)
            parser = "deepseek"
        except (LLMIntentParserUnavailable, Exception) as exc:
            spec = parse_intent_to_strategy_spec(request.text, request.overrides)
            fallback_used = True
            warnings.append(f"DeepSeek 解析失败，已使用规则解析兜底：{str(exc)[:120]}")
    else:
        spec = parse_intent_to_strategy_spec(request.text, request.overrides)
    if spec.intent_text and len(spec.entry_conditions) <= 2:
        warnings.append("解析出的条件较少，建议检查或补充周期、股票池、风险偏好。")
    return ParseIntentResponse(
        intent_text=request.text,
        strategy_spec=spec,
        warnings=warnings,
        parser=parser,
        llm_enabled=is_llm_intent_parser_enabled(),
        fallback_used=fallback_used,
    )


@router.post("/clarify")
async def clarify_intent(request: ParseIntentRequest):
    return clarify_strategy_goal(request.text)


@router.post("/generate-strategies")
async def generate_strategies(request: GenerateStrategiesRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="请输入策略目标")
    try:
        return generate_candidate_strategies(
            goal=request.text,
            count=request.count,
            use_llm=request.use_llm,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成候选策略失败: {str(exc)}")


@router.post("/validate-spec")
async def validate_spec(request: ValidateSpecRequest):
    return validate_strategy_spec(request.strategy_spec)
