"""Intent parsing API: user requirement -> StrategySpec."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.strategy_spec import StrategySpec
from app.services.intent_parser import parse_intent_to_strategy_spec

router = APIRouter()


class ParseIntentRequest(BaseModel):
    text: str
    overrides: dict[str, Any] | None = None


class ParseIntentResponse(BaseModel):
    intent_text: str
    strategy_spec: StrategySpec
    warnings: list[str] = []


@router.post("/parse", response_model=ParseIntentResponse)
async def parse_intent(request: ParseIntentRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="请输入选股要求")
    spec = parse_intent_to_strategy_spec(request.text, request.overrides)
    warnings = []
    if spec.intent_text and len(spec.entry_conditions) <= 2:
        warnings.append("解析出的条件较少，建议检查或补充周期、股票池、风险偏好。")
    return ParseIntentResponse(
        intent_text=request.text,
        strategy_spec=spec,
        warnings=warnings,
    )


@router.post("/clarify")
async def clarify_intent(request: ParseIntentRequest):
    text = request.text.strip()
    questions = []
    if not any(x in text for x in ["短线", "中线", "长线", "短期", "长期"]):
        questions.append("需要按短线、中线还是长线筛选？")
    if not any(x in text for x in ["主板", "创业板", "科创板", "北交所", "自选"]):
        questions.append("股票池是否需要限制板块或使用自选股？")
    if not any(x in text for x in ["稳健", "进攻", "低波动", "回撤", "止损"]):
        questions.append("风险偏好是稳健、平衡还是进攻？")
    return {"questions": questions, "need_clarification": bool(questions)}
