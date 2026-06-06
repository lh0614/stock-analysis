# backend/app/api/strategy.py
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Any, Optional

from app.services.strategy_store import get_strategy_store
from app.services.strategy_runtime import run_strategy
from app.core.data_fetcher import StockDataFetcher
from app.core.config import settings
from app.services.technical import compute_indicators
from datetime import datetime, timedelta

router = APIRouter()
_fetcher = StockDataFetcher(cache_dir=settings.CACHE_DIR)


class ReviseRequest(BaseModel):
    params: dict[str, Any] = {}
    note: str = ""


class EnableRequest(BaseModel):
    enabled: bool


@router.get("")
async def list_strategies():
    store = get_strategy_store()
    items = store.list_strategies()
    for item in items:
        item["horizons"] = __import__("json").loads(item["horizons"])
    return {"strategies": items}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    s = get_strategy_store().get(strategy_id)
    if not s:
        raise HTTPException(status_code=404, detail="策略不存在")
    import json
    s["horizons"] = json.loads(s["horizons"])
    return s


@router.get("/{strategy_id}/versions")
async def list_versions(strategy_id: str):
    revs = get_strategy_store().list_revisions(strategy_id)
    import json
    for r in revs:
        r["params"] = json.loads(r["params_json"] or "{}")
    return {"revisions": revs}


@router.post("/upload")
async def upload_strategy(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件不能超过 2MB")
    try:
        s = get_strategy_store().upload(file.filename or "strategy.py", content)
        import json
        s["horizons"] = json.loads(s["horizons"])
        return s
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{strategy_id}/revise")
async def revise_strategy(strategy_id: str, body: ReviseRequest):
    try:
        revised = get_strategy_store().revise(strategy_id, body.params, body.note)
        revised["backtest_compare_required"] = True
        return revised
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))




@router.patch("/{strategy_id}/enabled")
async def set_strategy_enabled(strategy_id: str, body: EnableRequest):
    item = get_strategy_store().set_enabled(strategy_id, body.enabled)
    if not item:
        raise HTTPException(status_code=404, detail="策略不存在")
    return item


@router.get("/{strategy_id}/backtest-refs")
async def strategy_backtest_refs(strategy_id: str, limit: int = 20):
    return {"items": get_strategy_store().list_backtest_refs(strategy_id, limit)}


@router.post("/{strategy_id}/run")
async def run_strategy_api(strategy_id: str, symbol: str):
    store = get_strategy_store()
    s = store.get(strategy_id)
    if not s:
        raise HTTPException(status_code=404, detail="策略不存在")
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
    result = _fetcher.get_stock_data(symbol, start, end)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    records = result["data"]
    indicators = compute_indicators(records, ["ma", "macd", "rsi"])
    params = store.get_latest_params(strategy_id)
    ctx = {
        "symbol": symbol,
        "ohlcv": records[-30:],
        "indicators": indicators,
        "params": params,
    }
    out = run_strategy(s["storage_path"], ctx)
    return {"symbol": symbol, "strategy_id": strategy_id, **out}


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str):
    if not get_strategy_store().delete(strategy_id):
        raise HTTPException(status_code=400, detail="无法删除")
    return {"ok": True}
