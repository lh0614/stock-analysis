from fastapi import APIRouter

from app.services.events_sync import recent_events, sync_events

router = APIRouter()


@router.post('/sync')
async def sync_events_api(symbols: list[str]):
    return sync_events(symbols)


@router.get('/symbol/{symbol}')
async def symbol_events(symbol: str, limit: int = 10):
    return {'items': recent_events(symbol, limit)}
