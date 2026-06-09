"""
策略闭环调度服务

负责每日自动执行完整的策略闭环：
1. 回填信号前向收益
2. 重新计算策略健康度
3. 运行活跃策略生成当日信号
4. 对衰减策略生成优化候选
"""
from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime
from typing import Any

from app.core.db import get_conn, init_db
from app.services.strategy_library import (
    list_strategies,
    get_strategy,
    update_signal_forward_returns,
)
from app.services.strategy_monitor import (
    run_strategy_signals,
    check_strategy_health,
    should_trigger_optimization,
)
from app.services.strategy_optimizer import optimize_strategy


def init_strategy_cycle_tables():
    """初始化策略闭环表"""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_cycle_runs (
                run_id TEXT PRIMARY KEY,
                trigger_type TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                total_strategies INTEGER DEFAULT 0,
                signal_runs INTEGER DEFAULT 0,
                health_checks INTEGER DEFAULT 0,
                optimization_jobs INTEGER DEFAULT 0,
                error TEXT,
                report_json TEXT
            )
        """
        )


class StrategyCycleService:
    """策略闭环调度服务"""

    def __init__(self):
        init_db()
        init_strategy_cycle_tables()
        self._current_run_id: str | None = None
        self._progress: dict[str, Any] = {}

    def get_latest_run(self) -> dict[str, Any] | None:
        """获取最近一次闭环执行记录"""
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT run_id, trigger_type, status, started_at, finished_at,
                       total_strategies, signal_runs, health_checks, optimization_jobs,
                       error, report_json
                FROM strategy_cycle_runs
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()

        if not row:
            return None

        result = dict(row)
        if result.get("report_json"):
            try:
                result["report"] = json.loads(result["report_json"])
            except json.JSONDecodeError:
                result["report"] = None
        return result

    def get_run_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """获取历史闭环执行记录"""
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT run_id, trigger_type, status, started_at, finished_at,
                       total_strategies, signal_runs, health_checks, optimization_jobs,
                       error
                FROM strategy_cycle_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()

        return [dict(row) for row in rows]

    def is_running(self) -> bool:
        """检查是否有闭环正在执行"""
        return self._current_run_id is not None

    def get_progress(self) -> dict[str, Any] | None:
        """获取当前执行进度"""
        if not self._current_run_id:
            return None
        return {
            "run_id": self._current_run_id,
            **self._progress
        }

    def run_cycle(self, trigger_type: str = "manual") -> dict[str, Any]:
        """
        执行完整策略闭环

        Args:
            trigger_type: 触发类型 (manual/scheduled/auto)

        Returns:
            执行结果摘要
        """
        if self._current_run_id:
            raise RuntimeError("已有闭环正在执行中，请稍后再试")

        run_id = str(uuid.uuid4())
        self._current_run_id = run_id
        started_at = datetime.now().isoformat()

        # 初始化执行记录
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO strategy_cycle_runs
                (run_id, trigger_type, status, started_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, trigger_type, "running", started_at)
            )

        try:
            # 执行闭环
            result = self._execute_cycle()

            # 更新为成功
            finished_at = datetime.now().isoformat()
            with get_conn() as conn:
                conn.execute(
                    """
                    UPDATE strategy_cycle_runs
                    SET status = ?,
                        finished_at = ?,
                        total_strategies = ?,
                        signal_runs = ?,
                        health_checks = ?,
                        optimization_jobs = ?,
                        report_json = ?
                    WHERE run_id = ?
                    """,
                    (
                        "completed",
                        finished_at,
                        result["total_strategies"],
                        result["signal_runs"],
                        result["health_checks"],
                        result["optimization_jobs"],
                        json.dumps(result.get("details", {}), ensure_ascii=False),
                        run_id
                    )
                )

            return {
                "run_id": run_id,
                "status": "completed",
                "started_at": started_at,
                "finished_at": finished_at,
                **result
            }

        except Exception as e:
            # 更新为失败
            error_msg = str(e)
            error_trace = traceback.format_exc()
            finished_at = datetime.now().isoformat()

            with get_conn() as conn:
                conn.execute(
                    """
                    UPDATE strategy_cycle_runs
                    SET status = ?,
                        finished_at = ?,
                        error = ?
                    WHERE run_id = ?
                    """,
                    ("failed", finished_at, error_trace, run_id)
                )

            return {
                "run_id": run_id,
                "status": "failed",
                "started_at": started_at,
                "finished_at": finished_at,
                "error": error_msg
            }
        finally:
            self._current_run_id = None
            self._progress = {}

    def _execute_cycle(self) -> dict[str, Any]:
        """执行闭环的核心逻辑"""
        # 获取所有活跃策略
        strategies = list_strategies(status="active")

        total_strategies = len(strategies)
        signal_runs = 0
        health_checks = 0
        optimization_jobs = 0

        details = {
            "strategies": []
        }

        self._progress = {
            "phase": "backfill",
            "message": "回填信号前向收益",
            "current": 0,
            "total": total_strategies
        }

        # 步骤1: 回填所有策略的前向收益
        for idx, strategy in enumerate(strategies):
            try:
                self._progress["current"] = idx + 1
                update_signal_forward_returns(strategy["id"])
            except Exception as e:
                print(f"回填策略 {strategy['id']} 收益失败: {e}")

        # 步骤2: 对每个策略执行完整流程
        for idx, strategy in enumerate(strategies):
            strategy_id = strategy["id"]
            strategy_name = strategy.get("name", strategy_id)

            self._progress = {
                "phase": "processing",
                "message": f"处理策略: {strategy_name}",
                "current": idx + 1,
                "total": total_strategies
            }

            strategy_detail = {
                "strategy_id": strategy_id,
                "strategy_name": strategy_name,
                "signal_run": None,
                "health_check": None,
                "optimization": None,
                "error": None
            }

            try:
                # 2.1 运行选股生成当日信号
                self._progress["sub_phase"] = "生成信号"
                signal_result = run_strategy_signals(strategy_id)
                signal_runs += 1
                strategy_detail["signal_run"] = {
                    "candidates_count": len(signal_result.get("candidates", [])),
                    "run_id": signal_result.get("run_id")
                }

                # 2.2 计算健康度
                self._progress["sub_phase"] = "检查健康度"
                health = check_strategy_health(strategy_id, persist=True)
                health_checks += 1
                strategy_detail["health_check"] = {
                    "health_score": health.health_score,
                    "status": health.status,
                    "confidence_level": health.confidence_level,
                    "sub_scores": health.sub_scores,
                    "degradation_signals": health.degradation_signals
                }

                # 2.3 如果策略衰减，触发优化
                if should_trigger_optimization(health):
                    self._progress["sub_phase"] = "生成优化候选"
                    try:
                        # 获取策略规格
                        strategy_data = get_strategy(strategy_id)
                        if strategy_data:
                            from app.services.strategy_optimizer import optimize_strategy, OptimizationConfig
                            from app.models.strategy_spec import StrategySpec
                            from app.services.strategy_library import save_optimization_result
                            import asyncio

                            spec = StrategySpec(**strategy_data['spec'])
                            config = OptimizationConfig(
                                objective="sharpe",
                                search_method="grid",
                                max_trials=30
                            )

                            # 由于 optimize_strategy 是 async 函数，需要在事件循环中运行
                            # 这里使用同步方式运行异步函数
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)

                            optimization_result = loop.run_until_complete(
                                optimize_strategy(spec, config)
                            )

                            # 保存优化结果到数据库
                            # candidate_spec 是 dict 类型，rejected 时为空字典 {}
                            candidate_spec = optimization_result.candidate_spec if optimization_result.candidate_spec else None

                            saved_optimization_id = save_optimization_result(
                                result=optimization_result,
                                candidate_spec=candidate_spec
                            )

                            optimization_jobs += 1
                            strategy_detail["optimization"] = {
                                "job_id": saved_optimization_id,
                                "optimization_id": optimization_result.optimization_id,
                                "status": optimization_result.decision,
                                "decision": optimization_result.decision,
                                "reason": optimization_result.decision_reason
                            }
                    except Exception as opt_err:
                        print(f"优化策略 {strategy_id} 失败: {opt_err}")
                        import traceback
                        traceback.print_exc()
                        strategy_detail["optimization"] = {
                            "error": str(opt_err)
                        }

            except Exception as e:
                error_msg = str(e)
                print(f"处理策略 {strategy_id} 失败: {error_msg}")
                strategy_detail["error"] = error_msg

            details["strategies"].append(strategy_detail)

        return {
            "total_strategies": total_strategies,
            "signal_runs": signal_runs,
            "health_checks": health_checks,
            "optimization_jobs": optimization_jobs,
            "details": details
        }


_service: StrategyCycleService | None = None


def get_strategy_cycle_service() -> StrategyCycleService:
    """获取策略闭环服务单例"""
    global _service
    if _service is None:
        _service = StrategyCycleService()
    return _service
