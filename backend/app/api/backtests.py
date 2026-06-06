from datetime import datetime, timedelta
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.backtest import compare_runs, export_run, get_run, list_runs, run_backtest

router = APIRouter()


class BacktestRunRequest(BaseModel):
    name: str = "选股策略回测"
    symbols: List[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strategy: str = "portfolio_equal_weight"
    rebalance: str = "monthly"
    split_date: Optional[str] = None
    market_filter: bool = False
    costs: Optional[dict[str, float]] = None
    filters_json: Optional[dict[str, Any]] = None


@router.post("/run")
async def run_backtest_api(body: BacktestRunRequest):
    end = body.end_date or datetime.now().strftime("%Y-%m-%d")
    start = body.start_date or (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
    if not body.symbols:
        raise HTTPException(status_code=400, detail="请提供 symbols")
    return run_backtest(
        name=body.name,
        symbols=body.symbols,
        start_date=start,
        end_date=end,
        strategy=body.strategy,
        rebalance=body.rebalance,
        split_date=body.split_date,
        market_filter=body.market_filter,
        costs=body.costs,
        filters_json=body.filters_json,
    )


@router.get("/runs")
async def list_backtest_runs(limit: int = 50):
    return {"runs": list_runs(limit)}


@router.get("/runs/{run_id}")
async def get_backtest_run(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="回测不存在")
    return run


@router.get("/runs/{run_id}/trades")
async def get_backtest_trades(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="回测不存在")
    detail = run.get("detail") or {}
    return {"trades": detail.get("trades") or []}


@router.get("/runs/{run_id}/export")
async def export_backtest(run_id: str, fmt: str = "json"):
    try:
        return export_run(run_id, fmt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/compare")
async def compare_backtests(run_ids: List[str]):
    return {"items": compare_runs(run_ids)}
