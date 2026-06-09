"""策略自进化闭环 smoke 测试。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.core.db import get_conn
from app.services.strategy_library import (
    get_strategy,
    get_strategy_health_checks,
    list_strategy_versions,
    promote_optimization_result,
    save_optimization_result,
    save_strategy,
)
from app.services.strategy_monitor import check_strategy_health
from app.services.strategy_optimizer import OptimizationResult


def main() -> None:
    strategy_id = "smoke_evolution_strategy_tmp"
    job_id = "smoke_evolution_job_tmp"

    with get_conn() as conn:
        conn.execute("DELETE FROM strategy_optimizations WHERE id = ?", (job_id,))
        conn.execute("DELETE FROM strategy_versions WHERE strategy_id = ?", (strategy_id,))
        conn.execute("DELETE FROM strategy_health_checks WHERE strategy_id = ?", (strategy_id,))
        conn.execute("DELETE FROM strategy_specs WHERE id = ?", (strategy_id,))

    save_strategy(
        {
            "id": strategy_id,
            "name": "smoke evolution strategy",
            "source": "manual",
            "status": "active",
            "version": "1.0.0",
            "entry_conditions": [{"factor": "rsi6", "op": "lt", "value": 40, "weight": 1.0}],
            "ranking": [],
        }
    )

    before = len(get_strategy_health_checks(strategy_id, days=1))
    check_strategy_health(strategy_id, persist=False)
    after_read = len(get_strategy_health_checks(strategy_id, days=1))
    assert after_read == before, "只读健康查询不应写入历史"

    check_strategy_health(strategy_id, persist=True)
    after_check = len(get_strategy_health_checks(strategy_id, days=1))
    assert after_check == before + 1, "显式健康检查应写入历史"

    result = OptimizationResult(
        optimization_id=job_id,
        strategy_id=strategy_id,
        from_version="1.0.0",
        to_version="1.1.0",
        objective="sharpe",
        search_method="grid",
        trials_count=1,
        changes=[
            {
                "param_path": "entry_conditions.0.value",
                "param_name": "rsi6_threshold",
                "from_value": 40,
                "to_value": 35,
            }
        ],
        metrics_before={"out_sample_sharpe": 0.2, "out_sample_annual_return": 0.03},
        metrics_after={"out_sample_sharpe": 0.4, "out_sample_annual_return": 0.08},
        decision="candidate",
        decision_reason="smoke",
        candidate_spec={
            "id": strategy_id,
            "name": "smoke evolution strategy",
            "source": "optimized",
            "status": "validated",
            "version": "1.1.0",
            "entry_conditions": [{"factor": "rsi6", "op": "lt", "value": 35, "weight": 1.0}],
            "ranking": [],
        },
    )
    save_optimization_result(result, result.candidate_spec)
    promoted = promote_optimization_result(job_id)
    assert promoted["status"] == "promoted", "优化候选应可晋级"
    assert get_strategy(strategy_id)["spec"]["version"] == "1.1.0"
    assert list_strategy_versions(strategy_id), "晋级应写入版本快照"

    with get_conn() as conn:
        conn.execute("DELETE FROM strategy_optimizations WHERE id = ?", (job_id,))
        conn.execute("DELETE FROM strategy_versions WHERE strategy_id = ?", (strategy_id,))
        conn.execute("DELETE FROM strategy_health_checks WHERE strategy_id = ?", (strategy_id,))
        conn.execute("DELETE FROM strategy_specs WHERE id = ?", (strategy_id,))

    print("strategy_evolution_smoke_ok")


if __name__ == "__main__":
    main()
