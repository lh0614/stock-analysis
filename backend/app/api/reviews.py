from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.reviews import REVIEW_TAGS, create_review, get_stats, list_reviews

router = APIRouter()


class ReviewCreate(BaseModel):
    plan_id: str
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    tags: List[str] = []
    lesson: str = ""


@router.get("")
async def get_reviews():
    return {"reviews": list_reviews(), "tags": REVIEW_TAGS}


@router.post("")
async def post_review(body: ReviewCreate):
    return create_review(body.model_dump())


@router.get("/stats")
async def review_stats():
    return get_stats()
