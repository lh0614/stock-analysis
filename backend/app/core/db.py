"""SQLite persistence for workflows, strategies, and pipeline runs."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

from app.core.config import settings


def _db_path() -> str:
    os.makedirs(settings.CACHE_DIR, exist_ok=True)
    return os.path.join(settings.CACHE_DIR, "lsa.db")


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(_db_path(), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                workflow_type TEXT NOT NULL DEFAULT 'custom',
                horizon TEXT NOT NULL DEFAULT 'short',
                indicators TEXT NOT NULL DEFAULT '["ma","macd","rsi"]',
                chart_period TEXT NOT NULL DEFAULT '1y',
                is_default INTEGER NOT NULL DEFAULT 0,
                config_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS strategies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                horizons TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                is_builtin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS strategy_revisions (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                version TEXT NOT NULL,
                params_json TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            );

            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                workflow_id TEXT,
                success INTEGER NOT NULL,
                result_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS watchlist_groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS watchlist_items (
                id TEXT PRIMARY KEY,
                group_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                note TEXT,
                added_at TEXT NOT NULL,
                UNIQUE(group_id, symbol),
                FOREIGN KEY (group_id) REFERENCES watchlist_groups(id)
            );

            CREATE TABLE IF NOT EXISTS screener_runs (
                run_id TEXT PRIMARY KEY,
                preset_id TEXT,
                filters_json TEXT,
                result_count INTEGER,
                result_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                rule_type TEXT NOT NULL,
                threshold REAL NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                cooldown_minutes INTEGER NOT NULL DEFAULT 60,
                last_triggered_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alert_events (
                id TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                message TEXT NOT NULL,
                payload_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (alert_id) REFERENCES alerts(id)
            );

            CREATE TABLE IF NOT EXISTS stock_universe (
                symbol TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                board TEXT NOT NULL,
                is_st INTEGER NOT NULL DEFAULT 0,
                is_main_board INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_stock_universe_board ON stock_universe(board);
            CREATE INDEX IF NOT EXISTS idx_stock_universe_st ON stock_universe(is_st);

            CREATE TABLE IF NOT EXISTS klines_sync_records (
                symbol TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                bars INTEGER NOT NULL DEFAULT 0,
                first_date TEXT,
                last_date TEXT,
                error TEXT,
                cache_file TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_klines_sync_status ON klines_sync_records(status);

            CREATE TABLE IF NOT EXISTS klines_sync_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                total INTEGER NOT NULL DEFAULT 0,
                done_ok INTEGER NOT NULL DEFAULT 0,
                done_skipped INTEGER NOT NULL DEFAULT 0,
                done_failed INTEGER NOT NULL DEFAULT 0,
                queue_pending INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS backtest_runs (
                run_id TEXT PRIMARY KEY,
                name TEXT,
                strategy_id TEXT,
                filters_json TEXT,
                config_json TEXT,
                metrics_json TEXT,
                result_path TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trade_plans (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                horizon TEXT NOT NULL,
                trigger_price REAL,
                invalid_price REAL,
                target_price_1 REAL,
                target_price_2 REAL,
                max_position_pct REAL,
                rationale_json TEXT,
                risks_json TEXT,
                status TEXT NOT NULL,
                source_run_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS simulated_trades (
                id TEXT PRIMARY KEY,
                plan_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                fee REAL DEFAULT 0,
                traded_at TEXT NOT NULL,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                pnl REAL,
                pnl_pct REAL,
                tags_json TEXT,
                lesson TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS strategy_backtest_refs (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                revision_id TEXT,
                backtest_run_id TEXT NOT NULL,
                metrics_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS screener_strategies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                filters_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        _ensure_column(conn, "strategies", "enabled", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "trade_plans", "risk_reward_ratio", "REAL")
        _seed_workflows(conn)
        _seed_watchlist(conn)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _seed_watchlist(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM watchlist_groups").fetchone()[0]
    if count > 0:
        return
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT INTO watchlist_groups (id, name, sort_order, created_at)
        VALUES (?, ?, ?, ?)
        """,
        ("default", "默认自选", 0, now),
    )


def _seed_workflows(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
    if count > 0:
        return
    now = datetime.now().isoformat()
    builtins = [
        ("builtin_short", "短线攻坚", "builtin", "short", '["ma","macd","rsi"]', "3m", 1),
        ("builtin_medium", "中线波段", "builtin", "medium", '["ma","macd","rsi"]', "1y", 0),
        ("builtin_long", "长线价值", "builtin", "long", '["ma","rsi"]', "1y", 0),
    ]
    for row in builtins:
        conn.execute(
            """
            INSERT INTO workflows (id, name, workflow_type, horizon, indicators, chart_period, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*row, now, now),
        )


def row_to_workflow(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "workflow_type": row["workflow_type"],
        "horizon": row["horizon"],
        "indicators": json.loads(row["indicators"]),
        "chart_period": row["chart_period"],
        "is_default": bool(row["is_default"]),
        "config": json.loads(row["config_json"]) if row["config_json"] else {},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
