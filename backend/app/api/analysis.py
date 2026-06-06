# backend/app/api/analysis.py
import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.services.pipeline import get_pipeline
from app.core.data_fetcher import StockDataFetcher
from app.core.config import settings
from app.services.technical import compute_indicators
from app.services.price_levels import compute_price_levels
from app.services.direction import build_directions, simple_forecast
from app.services.interpretation import build_interpretation
from app.services.workflow_memory import get_workflow_service
from datetime import datetime, timedelta

router = APIRouter()
_fetcher = StockDataFetcher(cache_dir=settings.CACHE_DIR)


class AnalysisRunRequest(BaseModel):
    symbol: str
    workflow_id: Optional[str] = None
    strategy_id: Optional[str] = None
    auto: bool = True


class ResumeRequest(BaseModel):
    run_id: str


@router.get("/checkpoint")
async def get_checkpoint(symbol: str = Query(..., min_length=1)):
    """Return resumable checkpoint metadata for a symbol."""
    info = get_pipeline().get_resumable(symbol.strip())
    if not info:
        return {"resumable": False}
    return {"resumable": True, **info}


@router.post("/resume")
async def resume_analysis(body: ResumeRequest):
    return get_pipeline().run_resume(body.run_id.strip())


@router.post("/resume/stream")
async def resume_analysis_stream(body: ResumeRequest):
    run_id = body.run_id.strip()
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id 不能为空")

    def event_stream():
        pipeline = get_pipeline()
        try:
            for item in pipeline.iter_resume(run_id):
                yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            err = {"event": "error", "result": {"success": False, "error": str(e)}}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/run")
async def run_analysis(body: AnalysisRunRequest):
    """Run full analysis pipeline for a symbol."""
    symbol = body.symbol.strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol 不能为空")
    return get_pipeline().run(symbol, body.workflow_id, body.strategy_id)


@router.post("/refetch")
async def refetch_and_analyze(body: AnalysisRunRequest):
    """Clear cache and force refetch data, then run analysis."""
    symbol = body.symbol.strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol 不能为空")

    # 清除缓存
    from app.services.data_store import clear_symbol_cache
    try:
        clear_symbol_cache(symbol)
    except Exception as e:
        # 即使清除失败也继续
        pass

    return get_pipeline().run(symbol, body.workflow_id, body.strategy_id)


@router.post("/run/stream")
async def run_analysis_stream(body: AnalysisRunRequest):
    """SSE stream of pipeline stage updates."""
    symbol = body.symbol.strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol 不能为空")

    def event_stream():
        pipeline = get_pipeline()
        try:
            for item in pipeline.iter_run(symbol, body.workflow_id, body.strategy_id):
                yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            err = {"event": "error", "result": {"success": False, "error": str(e)}}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs")
async def list_analysis_runs(
    symbol: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    return {"runs": get_pipeline().list_runs(symbol, limit)}


@router.get("/runs/{run_id}")
async def get_analysis_run(run_id: str):
    run = get_pipeline().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return run


@router.get("/runs/{run_id}/lineage")
async def get_analysis_lineage(run_id: str):
    run = get_pipeline().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return {
        "run_id": run_id,
        "lineage": run.get("lineage") or {},
        "stages": run.get("stages") or [],
    }


@router.post("/runs/{run_id}/plan")
async def create_plan_from_run(run_id: str):
    from app.services.trade_plans import build_plan_draft, create_plan

    run = get_pipeline().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    draft = run.get("plan_draft") or build_plan_draft(
        run["symbol"],
        run.get("directions"),
        run.get("price_levels"),
    )
    draft["source_run_id"] = run_id
    return create_plan(draft)


def _load_year_data(symbol: str):
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    result = _fetcher.get_stock_data(symbol, start_date, end_date)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "无数据"))
    return result["data"], result.get("metadata", {})


@router.get("/runs/{run_id}/export")
async def export_analysis(run_id: str, fmt: str = "json"):
    from app.services.export_report import export_analysis_run

    try:
        return export_analysis_run(run_id, fmt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{symbol}/interpretation")
async def get_interpretation(symbol: str):
    """Rule-based interpretation card (respects ai_interpretation_enabled setting)."""
    if not get_workflow_service().get_preference("ai_interpretation_enabled"):
        return {
            "symbol": symbol,
            "enabled": False,
            "message": "请在设置中开启「智能解读」",
        }
    records, meta = _load_year_data(symbol)
    indicators = compute_indicators(records, ["ma", "macd", "rsi"])
    price_levels = compute_price_levels(records)
    directions = build_directions(records, indicators, price_levels)
    forecasts = {
        "short": simple_forecast(records, "short"),
        "medium": simple_forecast(records, "medium"),
        "long": simple_forecast(records, "long"),
    }
    return {
        "symbol": symbol,
        "enabled": True,
        "interpretation": build_interpretation(
            symbol, directions, indicators, price_levels, forecasts
        ),
        "metadata": meta,
    }


@router.get("/{symbol}/direction")
async def get_direction(symbol: str):
    """Short / medium / long direction cards."""
    records, meta = _load_year_data(symbol)
    indicators = compute_indicators(records, ["ma", "macd", "rsi"])
    price_levels = compute_price_levels(records)
    directions = build_directions(records, indicators, price_levels)
    return {
        "symbol": symbol,
        "directions": directions,
        "metadata": meta,
    }


@router.get("/{symbol}/price-levels")
async def get_price_levels(symbol: str):
    records, meta = _load_year_data(symbol)
    return {"symbol": symbol, "data": compute_price_levels(records), "metadata": meta}


@router.get("/{symbol}/forecast")
async def get_forecast(symbol: str, horizon: str = "short"):
    if horizon not in ("short", "medium", "long"):
        raise HTTPException(status_code=400, detail="horizon 须为 short|medium|long")
    records, meta = _load_year_data(symbol)
    return {
        "symbol": symbol,
        "forecast": simple_forecast(records, horizon),
        "metadata": meta,
    }
