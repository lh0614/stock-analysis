from fastapi import APIRouter

from app.services.daily_review_report import build_daily_review_report
from app.services.export_report import export_daily_review

router = APIRouter()


@router.get('/daily-review')
async def daily_review():
    return build_daily_review_report()


@router.get('/daily-review/export')
async def daily_review_export():
    return export_daily_review()
