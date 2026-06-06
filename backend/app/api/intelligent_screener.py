# backend/app/api/intelligent_screener.py
"""智能选股 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.strategy_spec import StrategySpec, ScreenerResult
from app.services.intelligent_screener import run_intelligent_screening
from app.services.strategy_backtest import run_in_sample_out_sample_backtest
from app.services.strategy_rating import rate_strategy
from app.services.strategy_library import (
    get_screener_run as load_screener_run,
    save_strategy,
    save_screener_run,
    save_evaluation,
    update_strategy_status,
)

router = APIRouter()


class RunScreenerRequest(BaseModel):
    strategy_spec: StrategySpec


class BacktestRequest(BaseModel):
    save_as_strategy: bool = False


@router.post("/run", response_model=ScreenerResult)
async def run_screener(request: RunScreenerRequest):
    """
    执行智能选股

    根据 StrategySpec 进行精准选股，返回候选股列表及命中原因。
    """
    try:
        result = run_intelligent_screening(request.strategy_spec)

        # 保存选股记录
        save_screener_run({
            "run_id": result.run_id,
            "intent_text": request.strategy_spec.intent_text,
            "strategy_spec": request.strategy_spec.dict(),
            "candidates": [c.dict() for c in result.candidates],
            "total_scanned": result.total_scanned,
            "total_matched": result.total_matched,
            "execution_time_ms": result.execution_time_ms,
        })

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"选股执行失败: {str(e)}")


@router.post("/runs/{run_id}/backtest")
async def backtest_screener_result(run_id: str, request: BacktestRequest):
    """
    对选股结果进行回测

    执行样本内外拆分回测，评估策略有效性，并给出 A/B/C/D 评级。
    """
    try:
        saved_run = load_screener_run(run_id)
        if not saved_run:
            raise HTTPException(status_code=404, detail="选股运行记录不存在")

        strategy_spec = StrategySpec(**saved_run["strategy_spec"])
        candidates = saved_run.get("candidates") or []
        if not candidates:
            return {
                "backtest_result": None,
                "rating": None,
                "message": "该次选股无候选股，无法回测",
            }

        backtest_result = run_in_sample_out_sample_backtest(strategy_spec, candidates)
        rating_result = rate_strategy(
            backtest_result["in_sample"]["metrics"],
            backtest_result["out_sample"]["metrics"],
            backtest_result["overfit_flag"],
        )

        strategy_id = None
        if request.save_as_strategy:
            spec_dict = strategy_spec.dict()
            spec_dict["status"] = "backtested"
            spec_dict["rating"] = rating_result["rating"]
            strategy_id = save_strategy(spec_dict)
            save_evaluation(
                strategy_id,
                "in_out_sample",
                {
                    "in_sample": backtest_result["in_sample"]["metrics"],
                    "out_sample": backtest_result["out_sample"]["metrics"],
                },
                rating_result["rating"],
                backtest_result["overfit_flag"],
            )
            if rating_result["rating"] == "A":
                update_strategy_status(strategy_id, "validated", "A")

        return {
            "backtest_result": backtest_result,
            "rating": rating_result,
            "strategy_id": strategy_id,
            "message": "回测完成" + (f"，策略已保存 (ID: {strategy_id})" if strategy_id else ""),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测执行失败: {str(e)}")


@router.post("/run-and-backtest")
async def run_and_backtest(request: RunScreenerRequest):
    """
    执行选股并立即回测

    一站式完成选股、回测、评级的完整流程。
    """
    try:
        # 1. 执行选股
        print(f"执行选股: {request.strategy_spec.name}")
        screener_result = run_intelligent_screening(request.strategy_spec)

        if screener_result.total_matched == 0:
            return {
                "screener_result": screener_result.dict(),
                "backtest_result": None,
                "rating": None,
                "message": "未找到符合条件的候选股，无法进行回测"
            }

        # 2. 执行样本内外回测
        print(f"执行回测: 候选股数 {screener_result.total_matched}")
        candidates_dict = [c.dict() for c in screener_result.candidates]
        backtest_result = run_in_sample_out_sample_backtest(
            request.strategy_spec,
            candidates_dict
        )

        # 3. 策略评级
        rating_result = rate_strategy(
            backtest_result["in_sample"]["metrics"],
            backtest_result["out_sample"]["metrics"],
            backtest_result["overfit_flag"]
        )

        # 4. 保存策略到库（如果评级 >= B）
        strategy_id = None
        if rating_result["rating"] in ["A", "B"]:
            strategy_dict = request.strategy_spec.dict()
            strategy_dict["status"] = "backtested"
            strategy_dict["rating"] = rating_result["rating"]
            strategy_id = save_strategy(strategy_dict)

            # 保存评估结果
            save_evaluation(
                strategy_id,
                "in_out_sample",
                {
                    "in_sample": backtest_result["in_sample"]["metrics"],
                    "out_sample": backtest_result["out_sample"]["metrics"],
                },
                rating_result["rating"],
                backtest_result["overfit_flag"]
            )

            # 如果是 A 级，自动设为 validated 状态
            if rating_result["rating"] == "A":
                update_strategy_status(strategy_id, "validated", "A")

        return {
            "screener_result": screener_result.dict(),
            "backtest_result": backtest_result,
            "rating": rating_result,
            "strategy_id": strategy_id,
            "message": "选股和回测完成" + (f"，策略已保存 (ID: {strategy_id})" if strategy_id else "")
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.get("/runs/{run_id}", response_model=ScreenerResult)
async def get_screener_run(run_id: str):
    """
    获取选股运行结果
    """
    saved_run = load_screener_run(run_id)
    if not saved_run:
        raise HTTPException(status_code=404, detail="选股运行记录不存在")
    return ScreenerResult(
        run_id=saved_run["run_id"],
        strategy_spec=StrategySpec(**saved_run["strategy_spec"]),
        candidates=saved_run["candidates"],
        total_scanned=saved_run["total_scanned"] or 0,
        total_matched=saved_run["total_matched"] or 0,
        execution_time_ms=saved_run["execution_time_ms"] or 0,
        created_at=saved_run["created_at"],
    )


@router.post("/runs/{run_id}/save-strategy")
async def save_as_strategy(run_id: str):
    """
    将选股结果保存为策略
    """
    saved_run = load_screener_run(run_id)
    if not saved_run:
        raise HTTPException(status_code=404, detail="选股运行记录不存在")
    spec_dict = saved_run["strategy_spec"]
    spec_dict["status"] = "generated"
    strategy_id = save_strategy(spec_dict)
    return {"strategy_id": strategy_id, "message": "策略已保存"}
