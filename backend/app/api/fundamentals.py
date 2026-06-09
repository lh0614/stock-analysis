from fastapi import APIRouter

from app.services.fundamentals_sync import (
    get_fundamental_summary,
    get_fundamentals,
    get_valuation,
    sync_fundamentals,
    sync_valuation,
)

router = APIRouter()


@router.post('/sync')
async def sync_fundamentals_api(symbols: list[str]):
    f = sync_fundamentals(symbols)
    v = sync_valuation(symbols)
    return {'fundamentals': f, 'valuation': v}


@router.get('/{symbol}')
async def get_fundamental_summary_api(symbol: str):
    return get_fundamental_summary(symbol)


@router.get('/{symbol}/fundamentals')
async def get_fundamentals_api(symbol: str):
    return get_fundamentals(symbol)


@router.get('/{symbol}/valuation')
async def get_valuation_api(symbol: str):
    return get_valuation(symbol)
