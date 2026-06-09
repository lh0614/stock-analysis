"""策略闭环调度 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any
import threading

from app.services.strategy_cycle import get_strategy_cycle_service

router = APIRouter()


class TriggerCycleRequest(BaseModel):
    """触发闭环请求"""
    trigger_type: str = Field(default="manual", description="触发类型: manual/scheduled/auto")


class CycleStatusResponse(BaseModel):
    """闭环状态响应"""
    is_running: bool
    progress: dict[str, Any] | None = None
    latest_run: dict[str, Any] | None = None


@router.post("/trigger")
def trigger_cycle(request: TriggerCycleRequest) -> dict[str, Any]:
    """
    手动触发策略闭环

    执行完整闭环流程：
    1. 回填信号前向收益
    2. 运行活跃策略生成当日信号
    3. 计算策略健康度
    4. 对衰减策略生成优化候选
    """
    service = get_strategy_cycle_service()

    try:
        if service.is_running():
            raise RuntimeError("已有闭环正在执行中，请稍后再试")

        def _run_cycle() -> None:
            service.run_cycle(trigger_type=request.trigger_type)

        thread = threading.Thread(target=_run_cycle, daemon=True)
        thread.start()

        return {
            "accepted": True,
            "status": "running",
            "message": "策略闭环已在后台启动",
            "trigger_type": request.trigger_type,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行闭环失败: {str(e)}")


@router.get("/status")
def get_cycle_status() -> CycleStatusResponse:
    """
    获取策略闭环执行状态

    返回当前是否正在执行、执行进度以及最近一次执行结果
    """
    service = get_strategy_cycle_service()

    return CycleStatusResponse(
        is_running=service.is_running(),
        progress=service.get_progress(),
        latest_run=service.get_latest_run()
    )


@router.get("/history")
def get_cycle_history(limit: int = 20) -> dict[str, Any]:
    """
    获取策略闭环执行历史

    Args:
        limit: 返回记录数量，默认 20
    """
    service = get_strategy_cycle_service()

    history = service.get_run_history(limit=limit)

    return {
        "total": len(history),
        "runs": history
    }


@router.get("/runs/{run_id}")
def get_cycle_run_detail(run_id: str) -> dict[str, Any]:
    """
    获取指定闭环执行的详细信息

    Args:
        run_id: 闭环执行ID
    """
    from app.core.db import get_conn
    import json

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT run_id, trigger_type, status, started_at, finished_at,
                   total_strategies, signal_runs, health_checks, optimization_jobs,
                   error, report_json
            FROM strategy_cycle_runs
            WHERE run_id = ?
            """,
            (run_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"闭环执行记录不存在: {run_id}")

    result = dict(row)
    if result.get("report_json"):
        try:
            result["report"] = json.loads(result["report_json"])
            del result["report_json"]
        except json.JSONDecodeError:
            result["report"] = None

    return result
