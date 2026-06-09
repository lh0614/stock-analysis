"""策略库数据库表定义和管理"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.core.db import get_conn


def init_strategy_library_tables():
    """初始化策略库相关表"""
    with get_conn() as conn:
        # 策略主表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_specs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                intent_text TEXT,
                spec_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'idea',
                active_version TEXT,
                rating TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
        )

        # 策略版本表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_versions (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                version TEXT NOT NULL,
                spec_json TEXT NOT NULL,
                change_note TEXT,
                generated_by TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategy_specs(id)
            )
        """
        )

        # 策略评估表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_evaluations (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                version_id TEXT,
                backtest_run_id TEXT,
                sample_type TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                rating TEXT,
                overfit_flag INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategy_specs(id),
                FOREIGN KEY (version_id) REFERENCES strategy_versions(id)
            )
        """
        )

        # 策略优化记录表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_optimizations (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                from_version_id TEXT,
                to_version_id TEXT,
                objective TEXT,
                changes_json TEXT,
                metrics_before_json TEXT,
                metrics_after_json TEXT,
                decision TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategy_specs(id)
            )
        """
        )
        _ensure_column(conn, "strategy_optimizations", "candidate_spec_json", "TEXT")
        _ensure_column(conn, "strategy_optimizations", "decision_reason", "TEXT")
        _ensure_column(conn, "strategy_optimizations", "status", "TEXT DEFAULT 'pending'")
        _ensure_column(conn, "strategy_optimizations", "promoted_strategy_id", "TEXT")

        # 智能选股运行记录表（不要复用旧选股器 screener_runs，字段不同）
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS intelligent_screener_runs (
                run_id TEXT PRIMARY KEY,
                strategy_id TEXT,
                intent_text TEXT,
                parsed_spec_json TEXT NOT NULL,
                candidates_json TEXT,
                total_scanned INTEGER,
                total_matched INTEGER,
                execution_time_ms REAL,
                created_at TEXT NOT NULL
            )
        """
        )

        # 策略信号表：记录策略每日真实选股结果，并在后续数据成熟后回填前向收益
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_signals (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                run_id TEXT,
                symbol TEXT NOT NULL,
                name TEXT,
                signal_date TEXT NOT NULL,
                score REAL,
                rank INTEGER,
                quality_level TEXT,
                factor_values_json TEXT,
                matched_conditions_json TEXT,
                forward_return_5d REAL,
                forward_return_20d REAL,
                evaluated_at TEXT,
                market_state TEXT,
                market_trend TEXT,
                market_volatility TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(strategy_id, symbol, signal_date),
                FOREIGN KEY (strategy_id) REFERENCES strategy_specs(id)
            )
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_strategy_signals_strategy_date
            ON strategy_signals(strategy_id, signal_date)
        """
        )

        # 策略健康检查历史表
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_health_checks (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                health_score REAL NOT NULL,
                status TEXT NOT NULL,
                recent_signals_count INTEGER,
                recent_win_rate REAL,
                recent_avg_return REAL,
                degradation_signals_json TEXT,
                recommendations_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategy_specs(id)
            )
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_strategy_health_checks_strategy_date
            ON strategy_health_checks(strategy_id, created_at)
        """
        )
        _ensure_column(conn, "strategy_health_checks", "sub_scores_json", "TEXT")
        _ensure_column(conn, "strategy_health_checks", "confidence_level", "TEXT")
        _ensure_column(conn, "strategy_health_checks", "data_quality_json", "TEXT")

        conn.commit()


def _json_default(value: Any) -> Any:
    """JSON fallback for numpy/pandas scalars and pydantic models."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _candidate_to_dict(candidate: Any) -> dict[str, Any]:
    if hasattr(candidate, "model_dump"):
        return candidate.model_dump(mode="json")
    if isinstance(candidate, dict):
        return candidate
    return dict(candidate)


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")]
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def save_strategy(spec_dict: dict[str, Any]) -> str:
    """保存策略到数据库"""
    init_strategy_library_tables()
    strategy_id = spec_dict.get("id") or f"strat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO strategy_specs
            (id, name, source, intent_text, spec_json, status, rating, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                strategy_id,
                spec_dict.get("name", "未命名策略"),
                spec_dict.get("source", "manual"),
                spec_dict.get("intent_text", ""),
                json.dumps(spec_dict, ensure_ascii=False),
                spec_dict.get("status", "idea"),
                spec_dict.get("rating"),
                spec_dict.get("created_at", datetime.now().isoformat()),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()

    return strategy_id


def get_strategy(strategy_id: str) -> dict[str, Any] | None:
    """获取策略详情"""
    init_strategy_library_tables()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM strategy_specs WHERE id = ?", (strategy_id,)
        ).fetchone()

        if not row:
            return None

        return {
            "id": row["id"],
            "name": row["name"],
            "source": row["source"],
            "intent_text": row["intent_text"],
            "spec": json.loads(row["spec_json"]),
            "status": row["status"],
            "rating": row["rating"],
            "active_version": row["active_version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def list_strategies(
    status: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """列出策略"""
    init_strategy_library_tables()
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT id, name, source, status, rating, created_at, updated_at
                FROM strategy_specs
                WHERE status = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """,
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, source, status, rating, created_at, updated_at
                FROM strategy_specs
                ORDER BY updated_at DESC
                LIMIT ?
            """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]


def update_strategy_status(strategy_id: str, status: str, rating: str | None = None):
    """更新策略状态"""
    init_strategy_library_tables()
    with get_conn() as conn:
        if rating:
            conn.execute(
                """
                UPDATE strategy_specs
                SET status = ?, rating = ?, updated_at = ?
                WHERE id = ?
            """,
                (status, rating, datetime.now().isoformat(), strategy_id),
            )
        else:
            conn.execute(
                """
                UPDATE strategy_specs
                SET status = ?, updated_at = ?
                WHERE id = ?
            """,
                (status, datetime.now().isoformat(), strategy_id),
            )
        conn.commit()


def update_strategy_spec(
    strategy_id: str,
    spec_dict: dict[str, Any],
    status: str | None = None,
    rating: str | None = None,
) -> None:
    """更新已有策略规格，保留策略主记录身份。"""
    init_strategy_library_tables()
    spec_dict["id"] = strategy_id
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status, rating FROM strategy_specs WHERE id = ?", (strategy_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"策略{strategy_id}不存在")
        conn.execute(
            """
            UPDATE strategy_specs
            SET name = ?,
                source = ?,
                intent_text = ?,
                spec_json = ?,
                status = ?,
                rating = ?,
                active_version = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                spec_dict.get("name", "未命名策略"),
                spec_dict.get("source", "optimized"),
                spec_dict.get("intent_text", ""),
                json.dumps(spec_dict, ensure_ascii=False, default=_json_default),
                status or spec_dict.get("status") or row["status"],
                rating if rating is not None else spec_dict.get("rating") or row["rating"],
                spec_dict.get("version"),
                datetime.now().isoformat(),
                strategy_id,
            ),
        )
        conn.commit()


def save_strategy_version(
    strategy_id: str,
    version: str,
    spec_dict: dict[str, Any],
    change_note: str | None = None,
    generated_by: str = "optimizer",
) -> str:
    """保存策略候选/晋级版本快照。"""
    init_strategy_library_tables()
    version_id = f"{strategy_id}_v_{version.replace('.', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO strategy_versions
            (id, strategy_id, version, spec_json, change_note, generated_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                strategy_id,
                version,
                json.dumps(spec_dict, ensure_ascii=False, default=_json_default),
                change_note,
                generated_by,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    return version_id


def list_strategy_versions(strategy_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """列出策略版本快照。"""
    init_strategy_library_tables()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, strategy_id, version, spec_json, change_note, generated_by, created_at
            FROM strategy_versions
            WHERE strategy_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (strategy_id, limit),
        ).fetchall()
    versions = []
    for row in rows:
        item = dict(row)
        item["spec"] = json.loads(item.pop("spec_json") or "{}")
        versions.append(item)
    return versions


def get_strategy_version(version_id: str) -> dict[str, Any] | None:
    """读取单个策略版本快照。"""
    init_strategy_library_tables()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, strategy_id, version, spec_json, change_note, generated_by, created_at
            FROM strategy_versions
            WHERE id = ?
            """,
            (version_id,),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["spec"] = json.loads(item.pop("spec_json") or "{}")
    return item


def save_evaluation(
    strategy_id: str,
    sample_type: str,
    metrics: dict[str, Any],
    rating: str | None = None,
    overfit_flag: bool = False,
) -> str:
    """保存评估结果"""
    init_strategy_library_tables()
    eval_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO strategy_evaluations
            (id, strategy_id, sample_type, metrics_json, rating, overfit_flag, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                eval_id,
                strategy_id,
                sample_type,
                json.dumps(metrics, ensure_ascii=False),
                rating,
                1 if overfit_flag else 0,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()

    return eval_id


def save_screener_run(run_data: dict[str, Any]) -> str:
    """保存选股运行记录"""
    init_strategy_library_tables()
    run_id = run_data.get("run_id") or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO intelligent_screener_runs
            (run_id, strategy_id, intent_text, parsed_spec_json, candidates_json,
             total_scanned, total_matched, execution_time_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                run_id,
                run_data.get("strategy_id"),
                run_data.get("intent_text", ""),
                json.dumps(run_data.get("strategy_spec", {}), ensure_ascii=False),
                json.dumps(run_data.get("candidates", []), ensure_ascii=False),
                run_data.get("total_scanned", 0),
                run_data.get("total_matched", 0),
                run_data.get("execution_time_ms", 0),
                run_data.get("created_at", datetime.now().isoformat()),
            ),
        )
        conn.commit()

    return run_id


def get_screener_run(run_id: str) -> dict[str, Any] | None:
    """读取智能选股运行记录。"""
    init_strategy_library_tables()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM intelligent_screener_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    if not row:
        return None
    return {
        "run_id": row["run_id"],
        "strategy_id": row["strategy_id"],
        "intent_text": row["intent_text"],
        "strategy_spec": json.loads(row["parsed_spec_json"] or "{}"),
        "candidates": json.loads(row["candidates_json"] or "[]"),
        "total_scanned": row["total_scanned"],
        "total_matched": row["total_matched"],
        "execution_time_ms": row["execution_time_ms"],
        "created_at": row["created_at"],
    }


def list_screener_runs(limit: int = 50) -> list[dict[str, Any]]:
    """列出智能选股运行记录。"""
    init_strategy_library_tables()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT run_id, strategy_id, intent_text, total_scanned, total_matched,
                   execution_time_ms, created_at
            FROM intelligent_screener_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_strategy_signals(
    strategy_id: str,
    run_id: str | None,
    candidates: list[Any],
    signal_date: str | None = None,
) -> int:
    """保存策略选股信号，按 strategy_id + symbol + signal_date 去重。"""
    init_strategy_library_tables()
    created_at = datetime.now().isoformat()
    saved = 0

    # 获取当前市场环境
    from app.services.strategy_environment import get_current_market_state
    try:
        market_state_data = get_current_market_state(signal_date)
        market_state = market_state_data.get("state")
        market_trend = market_state_data.get("trend")
        market_volatility = market_state_data.get("volatility_level")
    except Exception:
        market_state = None
        market_trend = None
        market_volatility = None

    with get_conn() as conn:
        for candidate in candidates:
            item = _candidate_to_dict(candidate)
            factor_values = item.get("factor_values") or {}
            matched_conditions = item.get("matched_conditions") or []
            item_signal_date = (
                signal_date
                or str(factor_values.get("_trade_date") or factor_values.get("trade_date") or "")[:10]
                or datetime.now().strftime("%Y-%m-%d")
            )
            symbol = str(item.get("symbol", "")).zfill(6)[:6]
            if not symbol:
                continue
            signal_id = f"{strategy_id}_{symbol}_{item_signal_date}"
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO strategy_signals
                (id, strategy_id, run_id, symbol, name, signal_date, score, rank,
                 quality_level, factor_values_json, matched_conditions_json,
                 market_state, market_trend, market_volatility, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal_id,
                    strategy_id,
                    run_id,
                    symbol,
                    item.get("name"),
                    item_signal_date,
                    item.get("score"),
                    item.get("rank"),
                    item.get("quality_level"),
                    json.dumps(factor_values, ensure_ascii=False, default=_json_default),
                    json.dumps(matched_conditions, ensure_ascii=False, default=_json_default),
                    market_state,
                    market_trend,
                    market_volatility,
                    created_at,
                ),
            )
            saved += cur.rowcount
        conn.commit()

    return saved


def list_strategy_signals(strategy_id: str, days: int = 60) -> list[dict[str, Any]]:
    """读取策略近期信号。"""
    init_strategy_library_tables()
    start_date = (datetime.now() - timedelta(days=max(1, days))).strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM strategy_signals
            WHERE strategy_id = ? AND signal_date >= ?
            ORDER BY signal_date DESC, rank ASC, score DESC
            """,
            (strategy_id, start_date),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                """
                SELECT *
                FROM strategy_signals
                WHERE strategy_id = ?
                ORDER BY signal_date DESC, rank ASC, score DESC
                LIMIT 200
                """,
                (strategy_id,),
            ).fetchall()

    signals: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["factor_values"] = json.loads(item.pop("factor_values_json") or "{}")
        item["matched_conditions"] = json.loads(item.pop("matched_conditions_json") or "[]")
        signals.append(item)
    return signals


def update_signal_forward_returns(strategy_id: str | None = None) -> dict[str, int]:
    """用本地日线数据回填策略信号的 5 日/20 日前向收益。"""
    init_strategy_library_tables()
    from app.services.data_store import read_daily_bars

    where = "WHERE forward_return_5d IS NULL OR forward_return_20d IS NULL"
    params: list[Any] = []
    if strategy_id:
        where = (
            "WHERE strategy_id = ? "
            "AND (forward_return_5d IS NULL OR forward_return_20d IS NULL)"
        )
        params.append(strategy_id)

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, strategy_id, symbol, signal_date, forward_return_5d, forward_return_20d
            FROM strategy_signals
            {where}
            ORDER BY signal_date ASC
            """,
            params,
        ).fetchall()

    checked = 0
    updated = 0
    for row in rows:
        checked += 1
        bars = read_daily_bars(symbol=row["symbol"], start_date=row["signal_date"])
        if bars.empty or "close" not in bars.columns:
            continue
        bars = bars.sort_values("trade_date").reset_index(drop=True)
        if bars.empty:
            continue

        entry_close = float(bars.iloc[0]["close"])
        if entry_close <= 0:
            continue

        ret_5d = None
        ret_20d = None
        if row["forward_return_5d"] is None and len(bars) > 5:
            ret_5d = float(bars.iloc[5]["close"]) / entry_close - 1
        if row["forward_return_20d"] is None and len(bars) > 20:
            ret_20d = float(bars.iloc[20]["close"]) / entry_close - 1

        if ret_5d is None and ret_20d is None:
            continue

        with get_conn() as conn:
            conn.execute(
                """
                UPDATE strategy_signals
                SET forward_return_5d = COALESCE(?, forward_return_5d),
                    forward_return_20d = COALESCE(?, forward_return_20d),
                    evaluated_at = ?
                WHERE id = ?
                """,
                (ret_5d, ret_20d, datetime.now().isoformat(), row["id"]),
            )
            conn.commit()
        updated += 1

    return {"checked": checked, "updated": updated}


def get_latest_strategy_baseline(strategy_id: str) -> dict[str, float]:
    """从最近一次策略评估提取健康度基准，缺失时返回保守默认值。"""
    init_strategy_library_tables()
    baseline = {
        "win_rate": 0.55,
        "avg_return": 0.02,
        "max_drawdown": 0.12,
    }
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT metrics_json
            FROM strategy_evaluations
            WHERE strategy_id = ?
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (strategy_id,),
        ).fetchall()

    for row in rows:
        try:
            metrics = json.loads(row["metrics_json"] or "{}")
        except json.JSONDecodeError:
            continue
        if "out_sample" in metrics and isinstance(metrics["out_sample"], dict):
            metrics = metrics["out_sample"].get("metrics") or metrics["out_sample"]
        baseline["win_rate"] = float(
            metrics.get("win_rate")
            or metrics.get("out_sample_win_rate")
            or baseline["win_rate"]
        )
        annual_return = float(
            metrics.get("annual_return")
            or metrics.get("out_sample_annual_return")
            or metrics.get("total_return")
            or 0
        )
        total_trades = max(1, int(metrics.get("total_trades") or 12))
        baseline["avg_return"] = float(metrics.get("avg_return") or annual_return / total_trades)
        baseline["max_drawdown"] = float(
            metrics.get("max_drawdown")
            or metrics.get("out_sample_max_drawdown")
            or baseline["max_drawdown"]
        )
        break

    return baseline


def save_optimization_result(
    result: Any,
    candidate_spec: dict[str, Any] | None = None,
) -> str:
    """保存策略优化任务结果。"""
    init_strategy_library_tables()
    from app.services.strategy_optimizer import flatten_evaluation_metrics

    result_dict = result.model_dump(mode="json") if hasattr(result, "model_dump") else dict(result)
    optimization_id = result_dict["optimization_id"]
    decision = result_dict.get("decision", "rejected")
    status = "rejected" if decision == "rejected" else "pending"

    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO strategy_optimizations
            (id, strategy_id, from_version_id, to_version_id, objective, changes_json,
             metrics_before_json, metrics_after_json, decision, candidate_spec_json,
             decision_reason, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                optimization_id,
                result_dict.get("strategy_id"),
                result_dict.get("from_version"),
                result_dict.get("to_version"),
                result_dict.get("objective"),
                json.dumps(result_dict.get("changes", []), ensure_ascii=False, default=_json_default),
                json.dumps(flatten_evaluation_metrics(result_dict.get("metrics_before", {})), ensure_ascii=False, default=_json_default),
                json.dumps(flatten_evaluation_metrics(result_dict.get("metrics_after", {})), ensure_ascii=False, default=_json_default),
                decision,
                json.dumps(candidate_spec or result_dict.get("candidate_spec") or {}, ensure_ascii=False, default=_json_default),
                result_dict.get("decision_reason", ""),
                status,
                result_dict.get("created_at", datetime.now().isoformat()),
            ),
        )
        conn.commit()

    return optimization_id


def get_optimization_result(job_id: str) -> dict[str, Any] | None:
    """读取优化任务详情。"""
    init_strategy_library_tables()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM strategy_optimizations WHERE id = ?", (job_id,)
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    return {
        "optimization_id": item["id"],
        "strategy_id": item["strategy_id"],
        "from_version": item["from_version_id"],
        "to_version": item["to_version_id"],
        "objective": item["objective"],
        "changes": json.loads(item["changes_json"] or "[]"),
        "metrics_before": json.loads(item["metrics_before_json"] or "{}"),
        "metrics_after": json.loads(item["metrics_after_json"] or "{}"),
        "decision": item["decision"],
        "decision_reason": item.get("decision_reason") or "",
        "candidate_spec": json.loads(item.get("candidate_spec_json") or "{}"),
        "status": item.get("status") or "pending",
        "promoted_strategy_id": item.get("promoted_strategy_id"),
        "created_at": item["created_at"],
    }


def list_optimization_results(
    strategy_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """列出优化任务。"""
    init_strategy_library_tables()
    with get_conn() as conn:
        if strategy_id:
            rows = conn.execute(
                """
                SELECT id
                FROM strategy_optimizations
                WHERE strategy_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (strategy_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id
                FROM strategy_optimizations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [item for row in rows if (item := get_optimization_result(row["id"]))]


def promote_optimization_result(job_id: str) -> dict[str, Any]:
    """将优化候选版本晋级为原策略当前规格。"""
    init_strategy_library_tables()
    job = get_optimization_result(job_id)
    if not job:
        raise ValueError(f"优化任务{job_id}不存在")
    if job["status"] == "promoted":
        return job
    if job["decision"] == "rejected":
        raise ValueError("已拒绝的优化结果不能晋级")
    candidate_spec = job.get("candidate_spec") or {}
    if not candidate_spec:
        raise ValueError("优化任务缺少候选策略规格")

    strategy_id = job["strategy_id"]
    candidate_spec["id"] = strategy_id
    candidate_spec["source"] = "optimized"
    candidate_spec["status"] = "validated"
    version_id = save_strategy_version(
        strategy_id=strategy_id,
        version=candidate_spec.get("version") or job.get("to_version") or "1.1.0",
        spec_dict=candidate_spec,
        change_note=f"promoted from optimization {job_id}",
        generated_by="optimizer",
    )
    update_strategy_spec(strategy_id, candidate_spec, status="validated")

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE strategy_optimizations
            SET status = 'promoted', promoted_strategy_id = ?
            WHERE id = ?
            """,
            (strategy_id, job_id),
        )
        conn.commit()

    updated = get_optimization_result(job_id) or job
    updated["version_id"] = version_id
    return updated


def reject_optimization_result(job_id: str) -> dict[str, Any]:
    """拒绝优化候选版本。"""
    init_strategy_library_tables()
    job = get_optimization_result(job_id)
    if not job:
        raise ValueError(f"优化任务{job_id}不存在")
    with get_conn() as conn:
        conn.execute(
            "UPDATE strategy_optimizations SET status = 'rejected' WHERE id = ?",
            (job_id,),
        )
        conn.commit()
    return get_optimization_result(job_id) or job


def save_strategy_health_check(
    strategy_id: str,
    health_score: float,
    status: str,
    recent_signals_count: int,
    recent_win_rate: float | None,
    recent_avg_return: float | None,
    degradation_signals: list[str],
    recommendations: list[str],
    sub_scores: dict[str, Any] | None = None,
    confidence_level: str | None = None,
    data_quality: dict[str, Any] | None = None,
) -> str:
    """保存策略健康度检查记录"""
    init_strategy_library_tables()
    check_id = f"check_{uuid.uuid4().hex}"
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO strategy_health_checks
            (id, strategy_id, health_score, status, recent_signals_count,
             recent_win_rate, recent_avg_return, degradation_signals_json,
             recommendations_json, sub_scores_json, confidence_level,
             data_quality_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                check_id,
                strategy_id,
                health_score,
                status,
                recent_signals_count,
                recent_win_rate,
                recent_avg_return,
                json.dumps(degradation_signals, ensure_ascii=False),
                json.dumps(recommendations, ensure_ascii=False),
                json.dumps(sub_scores or {}, ensure_ascii=False, default=_json_default),
                confidence_level,
                json.dumps(data_quality or {}, ensure_ascii=False, default=_json_default),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    return check_id


def get_strategy_health_checks(strategy_id: str, days: int = 30) -> list[dict[str, Any]]:
    """获取策略健康度历史记录"""
    init_strategy_library_tables()
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM strategy_health_checks
            WHERE strategy_id = ? AND created_at >= ?
            ORDER BY created_at ASC
        """,
            (strategy_id, cutoff_date),
        ).fetchall()

        return [
            {
                "id": row["id"],
                "strategy_id": row["strategy_id"],
                "health_score": row["health_score"],
                "status": row["status"],
                "recent_signals_count": row["recent_signals_count"],
                "recent_win_rate": row["recent_win_rate"],
                "recent_avg_return": row["recent_avg_return"],
                "degradation_signals": json.loads(row["degradation_signals_json"]) if row["degradation_signals_json"] else [],
                "recommendations": json.loads(row["recommendations_json"]) if row["recommendations_json"] else [],
                "sub_scores": json.loads(row["sub_scores_json"]) if "sub_scores_json" in row.keys() and row["sub_scores_json"] else {},
                "confidence_level": row["confidence_level"] if "confidence_level" in row.keys() else None,
                "data_quality": json.loads(row["data_quality_json"]) if "data_quality_json" in row.keys() and row["data_quality_json"] else {},
                "created_at": row["created_at"],
            }
            for row in rows
        ]
