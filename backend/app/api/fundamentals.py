from fastapi import APIRouter

from app.services.fundamentals_sync import sync_fundamentals, sync_valuation

router = APIRouter()


@router.post('/sync')
async def sync_fundamentals_api(symbols: list[str]):
    f = sync_fundamentals(symbols)
    v = sync_valuation(symbols)
    return {'fundamentals': f, 'valuation': v}
