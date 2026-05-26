"""Local stock universe: read from local files; write only via sync_from_remote."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Generator

if TYPE_CHECKING:
    from app.services.sync_run import SyncRunLease

import akshare as ak

from app.core.board import (
    BOARD_BSE,
    BOARD_CHINEXT,
    BOARD_MAIN,
    BOARD_STAR,
    classify_board,
    is_main_board,
    is_st_stock,
)
from app.core.config import settings
from app.core.db import get_conn, init_db

UNIVERSE_JSON = os.path.join(settings.CACHE_DIR, "stock_universe.json")
KLINES_DIR = os.path.join(settings.CACHE_DIR, "klines")
CUSTOM_POOL_KEY = "screener_custom_symbols"
UNIVERSE_LAST_SYNC_KEY = "universe_last_sync"
UNIVERSE_LAST_DELTA_KEY = "universe_last_sync_delta"
UNIVERSE_LAST_KLINES_KEY = "universe_last_klines_sync"
MIN_UNIVERSE_SIZE = 4000
_SYMBOL_RE = re.compile(r"^\d{6}$")


def _full_klines_symbols() -> set[str]:
    if not os.path.isdir(KLINES_DIR):
        return set()
    out: set[str] = set()
    for fn in os.listdir(KLINES_DIR):
        if fn.endswith("_full.pkl"):
            code = fn[: -len("_full.pkl")].strip()
            if code.isdigit():
                out.add(code.zfill(6))
    return out


def _klines_symbols() -> set[str]:
    full = _full_klines_symbols()
    if full:
        return full
    if not os.path.isdir(KLINES_DIR):
        return set()
    out: set[str] = set()
    for fn in os.listdir(KLINES_DIR):
        if fn.endswith(".pkl"):
            code = fn.split("_", 1)[0].strip()
            if code.isdigit():
                out.add(code.zfill(6))
    return out


def _stock_signature(stock: dict[str, Any]) -> tuple:
    return (
        stock.get("name", ""),
        stock.get("board", ""),
        int(stock.get("is_st", 0)),
        int(stock.get("is_main_board", 0)),
    )


def _read_json_file(path: str) -> dict | list | None:
    if not os.path.isfile(path):
        return None
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            with open(path, encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError, OSError):
            continue
    return None


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "symbol": row["symbol"],
        "name": row["name"] or "",
        "board": row["board"],
        "is_st": bool(row["is_st"]),
        "is_main_board": bool(row["is_main_board"]),
        "updated_at": row["updated_at"],
    }


def _parse_sync_meta(last_sync: str | None) -> dict[str, Any]:
    if not last_sync:
        return {
            "last_sync": None,
            "last_sync_display": None,
            "synced_today": False,
            "stale_sync": True,
            "sync_reminder": "尚未同步股票列表，请点击「同步列表」从本地/远端更新数据。",
        }
    try:
        dt = datetime.fromisoformat(last_sync.replace("Z", "+00:00")[:26])
    except ValueError:
        dt = None
    if not dt:
        return {
            "last_sync": last_sync,
            "last_sync_display": last_sync,
            "synced_today": False,
            "stale_sync": True,
            "sync_reminder": "同步时间格式异常，建议重新点击「同步列表」。",
        }
    today = datetime.now().date()
    synced_today = dt.date() == today
    display = dt.strftime("%Y-%m-%d %H:%M")
    stale = not synced_today
    reminder = None
    if stale:
        reminder = (
            f"上次同步为 {display}，今日尚未更新。"
            "建议点击「同步列表」以保持列表准确。"
        )
    return {
        "last_sync": last_sync,
        "last_sync_display": display,
        "synced_today": synced_today,
        "stale_sync": stale,
        "sync_reminder": reminder,
    }


class UniverseService:
    def __init__(self) -> None:
        init_db()
        os.makedirs(settings.CACHE_DIR, exist_ok=True)

    def _enrich(self, symbol: str, name: str) -> dict[str, Any]:
        board = classify_board(symbol)
        return {
            "symbol": str(symbol).zfill(6),
            "name": str(name).strip(),
            "board": board,
            "is_st": 1 if is_st_stock(symbol, name) else 0,
            "is_main_board": 1 if is_main_board(symbol) else 0,
            "updated_at": datetime.now().isoformat(),
        }

    def _load_json_map(self) -> dict[str, dict[str, Any]]:
        data = _read_json_file(UNIVERSE_JSON)
        if not isinstance(data, dict) or not data.get("stocks"):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for item in data["stocks"]:
            sym = str(item.get("symbol", "")).zfill(6)
            if _SYMBOL_RE.match(sym):
                out[sym] = self._enrich(sym, item.get("name", ""))
        return out

    def _load_db_map(self) -> dict[str, dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM stock_universe").fetchall()
        return {r["symbol"]: _row_to_dict(r) for r in rows} if rows else {}

    def load_local_map(self) -> dict[str, dict[str, Any]]:
        """只读：优先 SQLite，否则 stock_universe.json（不写库）。"""
        db_map = self._load_db_map()
        if db_map:
            return db_map
        return self._load_json_map()

    def _normalize_remote_rows(self, rows: list[tuple[str, str]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for code, name in rows:
            sym = str(code).strip().zfill(6)
            if not _SYMBOL_RE.match(sym) or sym in seen:
                continue
            seen.add(sym)
            out.append(self._enrich(sym, name))
        return out

    @staticmethod
    def _validate_remote_list(stocks: list[dict[str, Any]]) -> bool:
        if len(stocks) < MIN_UNIVERSE_SIZE:
            return False
        symbols = {s["symbol"] for s in stocks}
        return len(symbols) >= MIN_UNIVERSE_SIZE

    def _try_fetch(
        self, label: str, fn: Callable[[], list[tuple[str, str]]]
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        try:
            raw = fn()
            stocks = self._normalize_remote_rows(raw)
            if self._validate_remote_list(stocks):
                return stocks, label, None
            return [], None, f"{label}: 数量不足({len(stocks)})"
        except Exception as e:
            return [], None, f"{label}: {e}"

    def _fetch_remote_stocks(self) -> tuple[list[dict[str, Any]], str | None, list[str]]:
        warnings: list[str] = []
        fetchers: list[tuple[str, Callable[[], list[tuple[str, str]]]]] = [
            (
                "akshare_code_name",
                lambda: [
                    (str(r["code"]), str(r["name"]))
                    for _, r in ak.stock_info_a_code_name().iterrows()
                ],
            ),
            (
                "akshare_spot",
                lambda: [
                    (str(r["代码"]), str(r["名称"]))
                    for _, r in ak.stock_zh_a_spot_em().iterrows()
                ],
            ),
        ]
        for label, fn in fetchers:
            stocks, source, err = self._try_fetch(label, fn)
            if stocks:
                return stocks, source, warnings
            if err:
                warnings.append(err)
        return [], None, warnings

    @staticmethod
    def _diff_universe(
        local: dict[str, dict[str, Any]],
        remote: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        local_keys = set(local)
        remote_keys = set(remote)
        added_keys = remote_keys - local_keys
        removed_keys = local_keys - remote_keys
        common = local_keys & remote_keys

        added = [remote[k] for k in sorted(added_keys)]
        removed = [local[k] for k in sorted(removed_keys)]
        updated: list[dict[str, Any]] = []
        unchanged = 0
        for k in common:
            if _stock_signature(local[k]) != _stock_signature(remote[k]):
                updated.append(remote[k])
            else:
                unchanged += 1

        return {
            "added": added,
            "updated": updated,
            "removed": removed,
            "unchanged": unchanged,
        }

    def _apply_incremental(
        self, remote: dict[str, dict[str, Any]], delta: dict[str, Any], now: str
    ) -> None:
        with get_conn() as conn:
            if delta["added"]:
                conn.executemany(
                    """
                    INSERT INTO stock_universe
                    (symbol, name, board, is_st, is_main_board, updated_at)
                    VALUES (:symbol, :name, :board, :is_st, :is_main_board, :updated_at)
                    """,
                    delta["added"],
                )
            if delta["updated"]:
                conn.executemany(
                    """
                    UPDATE stock_universe SET
                        name = :name, board = :board, is_st = :is_st,
                        is_main_board = :is_main_board, updated_at = :updated_at
                    WHERE symbol = :symbol
                    """,
                    delta["updated"],
                )
            if delta["removed"]:
                placeholders = ",".join("?" * len(delta["removed"]))
                symbols = [s["symbol"] for s in delta["removed"]]
                conn.execute(
                    f"DELETE FROM stock_universe WHERE symbol IN ({placeholders})",
                    symbols,
                )

            summary = {
                "added": len(delta["added"]),
                "updated": len(delta["updated"]),
                "removed": len(delta["removed"]),
                "unchanged": delta["unchanged"],
                "total_after": len(remote),
                "local_before": delta["local_before"],
            }
            conn.execute(
                """
                INSERT INTO user_preferences (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (UNIVERSE_LAST_SYNC_KEY, now),
            )
            conn.execute(
                """
                INSERT INTO user_preferences (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (UNIVERSE_LAST_DELTA_KEY, json.dumps(summary, ensure_ascii=False)),
            )

    def _write_json_snapshot(
        self,
        remote_list: list[dict[str, Any]],
        now: str,
        delta: dict[str, int],
    ) -> None:
        payload = {
            "saved_at": now,
            "sync_mode": "incremental",
            "count": len(remote_list),
            "delta": delta,
            "stocks": [
                {"symbol": s["symbol"], "name": s["name"]} for s in remote_list
            ],
        }
        tmp = UNIVERSE_JSON + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, UNIVERSE_JSON)

    def _bootstrap_db_from_map(self, stock_map: dict[str, dict[str, Any]], now: str) -> None:
        """仅在 sync 入口：将本地 JSON 快照首次导入 SQLite。"""
        if not stock_map:
            return
        stocks = list(stock_map.values())
        with get_conn() as conn:
            conn.execute("DELETE FROM stock_universe")
            conn.executemany(
                """
                INSERT INTO stock_universe
                (symbol, name, board, is_st, is_main_board, updated_at)
                VALUES (:symbol, :name, :board, :is_st, :is_main_board, :updated_at)
                """,
                stocks,
            )
            conn.execute(
                """
                INSERT INTO user_preferences (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (UNIVERSE_LAST_SYNC_KEY, now),
            )

    def _sync_list_phase(self) -> dict[str, Any]:
        """阶段一：股票列表增量同步。"""
        now = datetime.now().isoformat()
        local_map = self.load_local_map()
        remote_list, remote_source, warnings = self._fetch_remote_stocks()
        updated = False
        delta_out = {
            "added": 0,
            "updated": 0,
            "removed": 0,
            "unchanged": 0,
            "local_before": len(local_map),
        }
        message = ""

        if remote_list:
            remote_map = {s["symbol"]: s for s in remote_list}
            delta = self._diff_universe(local_map, remote_map)
            delta["local_before"] = len(local_map)
            self._apply_incremental(remote_map, delta, now)
            delta_out = {
                "added": len(delta["added"]),
                "updated": len(delta["updated"]),
                "removed": len(delta["removed"]),
                "unchanged": delta["unchanged"],
                "local_before": delta["local_before"],
            }
            self._write_json_snapshot(remote_list, now, delta_out)
            local_map = remote_map
            updated = True
            message = f"已从 {remote_source} 增量更新列表"
        elif local_map:
            db_map = self._load_db_map()
            if not db_map:
                self._bootstrap_db_from_map(local_map, now)
            message = "远端暂不可用，已继续使用本地列表（未改动数据）"
            warnings.append("远端获取失败，未修改本地数据")
        else:
            json_map = self._load_json_map()
            if json_map and self._validate_remote_list(list(json_map.values())):
                self._bootstrap_db_from_map(json_map, now)
                self._write_json_snapshot(
                    list(json_map.values()),
                    now,
                    {**delta_out, "unchanged": len(json_map)},
                )
                local_map = json_map
                updated = True
                message = "已从本地 JSON 文件恢复股票列表"
            else:
                message = "暂无本地列表，将仅尝试同步已有代码的全量K线"

        return {
            "success": True,
            "updated": updated,
            "message": message,
            "remote_source": remote_source,
            "warnings": warnings,
            "delta": delta_out,
            "local_map": local_map,
            "count": len(local_map),
        }

    def _record_klines_sync(self, summary: dict[str, Any]) -> None:
        now = datetime.now().isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (UNIVERSE_LAST_KLINES_KEY, now),
            )
            conn.execute(
                """
                INSERT INTO user_preferences (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (UNIVERSE_LAST_SYNC_KEY, now),
            )
            conn.execute(
                """
                INSERT INTO user_preferences (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (
                    "universe_last_klines_summary",
                    json.dumps({**summary, "finished_at": now}, ensure_ascii=False),
                ),
            )

    def iter_sync_all(
        self,
        *,
        sync_mode: str = "full",
        run_lease: SyncRunLease | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """sync_mode: full=断点续传+增量；incremental=仅补已有全量的落后日 K。

        run_lease: 调用方已 try_acquire_sync_run 时传入，跳过二次获取，结束时仍由此处释放。
        """
        from app.services.sync_run import (
            SyncRunLease,
            release_sync_run,
            try_acquire_sync_run,
        )

        if run_lease is None:
            run_lease = try_acquire_sync_run()
            if run_lease is None:
                yield {
                    "event": "error",
                    "success": False,
                    "reason": "already_running",
                    "message": "已有同步任务正在运行，请稍后再试",
                }
                return
        try:
            try:
                yield from self._iter_sync_all_impl(sync_mode=sync_mode)
            except Exception as e:
                yield {
                    "event": "error",
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
        finally:
            release_sync_run()

    def _iter_sync_all_impl(
        self, *, sync_mode: str = "full"
    ) -> Generator[dict[str, Any], None, None]:
        from app.services.klines_sync import get_klines_sync_service

        yield {"event": "start", "phase": "list", "sync_mode": sync_mode}
        list_result = self._sync_list_phase()
        yield {
            "event": "list_complete",
            "success": True,
            "message": list_result["message"],
            "count": list_result["count"],
            "delta": list_result["delta"],
            "warnings": list_result["warnings"],
        }

        local_map = list_result["local_map"]
        symbols = sorted(local_map.keys())
        if not symbols:
            stats = self.get_stats()
            yield {
                "event": "complete",
                "success": True,
                "message": "无股票代码可同步K线",
                "stats": stats,
            }
            return

        klines_svc = get_klines_sync_service()
        klines_summary: dict[str, Any] = {}
        paused = False
        try:
            for item in klines_svc.iter_sync_full(symbols, mode=sync_mode):
                yield item
                if item.get("event") == "klines_complete":
                    klines_summary = item
                if item.get("event") == "klines_paused":
                    paused = True
                    klines_summary = item
        except GeneratorExit:
            paused = True
            klines_summary = klines_svc.get_last_summary()

        if not klines_summary:
            klines_summary = klines_svc.get_last_summary()
        if klines_summary and klines_summary.get("ok") is not None:
            self._record_klines_sync(klines_summary)

        stats = self.get_stats()
        reg = stats.get("klines_registry") or {}
        if paused:
            msg = (
                f"同步已暂停（进度已保存）：本轮 K 线 ok {klines_summary.get('ok', 0)}、"
                f"跳过 {klines_summary.get('skipped', 0)}、失败 {klines_summary.get('failed', 0)}；"
                f"已完成全量 {reg.get('klines_complete', 0)} 只，待续传 {reg.get('klines_pending', 0)} 只"
            )
        else:
            msg = (
                f"同步结束：列表 {list_result['count']} 只；"
                f"本轮 K 线 ok {klines_summary.get('ok', 0)}、"
                f"跳过 {klines_summary.get('skipped', 0)}、失败 {klines_summary.get('failed', 0)}；"
                f"累计全量完成 {reg.get('klines_complete', 0)} 只"
            )
        yield {
            "event": "complete",
            "success": True,
            "paused": paused,
            "resumable": reg.get("klines_pending", 0) > 0,
            "message": msg,
            "list": list_result,
            "klines": klines_summary,
            "stats": stats,
            "folder": self._folder_snapshot(local_map),
        }

    def sync_from_remote(self) -> dict[str, Any]:
        """兼容旧接口：仅同步列表；完整同步请用 /sync/stream。"""
        list_result = self._sync_list_phase()
        stats = self.get_stats()
        return {
            "success": True,
            "updated": list_result["updated"],
            "mode": "list_only",
            "synced_at": stats.get("last_sync"),
            "count": list_result["count"],
            "delta": list_result["delta"],
            "message": list_result["message"] + "（全量K线请使用流式同步）",
            "remote_source": list_result["remote_source"],
            "folder": self._folder_snapshot(list_result["local_map"]),
            "stats": stats,
            "warnings": list_result["warnings"],
        }

    def _folder_snapshot(self, local: dict[str, dict[str, Any]]) -> dict[str, Any]:
        klines = _klines_symbols()
        local_keys = set(local)
        json_exists = os.path.isfile(UNIVERSE_JSON)
        json_mtime = None
        if json_exists:
            json_mtime = datetime.fromtimestamp(
                os.path.getmtime(UNIVERSE_JSON)
            ).isoformat()
        full_klines = _full_klines_symbols()
        return {
            "cache_dir": settings.CACHE_DIR,
            "db_count": len(self._load_db_map()),
            "json_exists": json_exists,
            "json_mtime": json_mtime,
            "klines_cached": len(klines),
            "klines_full": len(full_klines),
            "klines_not_in_list": len(klines - local_keys),
            "list_not_in_klines": len(local_keys - klines),
            "history_range": "1990-01-01 ~ 今日",
        }

    def get_stats(self) -> dict[str, Any]:
        local_map = self.load_local_map()
        total = len(local_map)
        boards: dict[str, int] = {}
        st = 0
        for s in local_map.values():
            boards[s["board"]] = boards.get(s["board"], 0) + 1
            if s.get("is_st"):
                st += 1

        last_sync = None
        with get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM user_preferences WHERE key = ?",
                (UNIVERSE_LAST_SYNC_KEY,),
            ).fetchone()
            if row:
                last_sync = row["value"]
            if not last_sync and os.path.isfile(UNIVERSE_JSON):
                data = _read_json_file(UNIVERSE_JSON)
                if isinstance(data, dict):
                    last_sync = data.get("saved_at")

        klines_last = None
        with get_conn() as conn:
            row_k = conn.execute(
                "SELECT value FROM user_preferences WHERE key = ?",
                (UNIVERSE_LAST_KLINES_KEY,),
            ).fetchone()
            if row_k:
                klines_last = row_k["value"]

        from app.services.klines_registry import get_klines_registry

        meta = _parse_sync_meta(last_sync)
        full_n = len(_full_klines_symbols())
        reg = get_klines_registry()
        reg_sum = reg.get_summary()
        keys = list(local_map.keys())
        plan_full = (
            reg.build_queue(keys, mode="full")
            if keys
            else {"complete": 0, "pending": 0, "pending_full": 0, "total_list": 0}
        )
        plan_inc = (
            reg.build_queue(keys, mode="incremental")
            if keys
            else {"complete": 0, "pending": 0, "skipped_no_file": 0, "total_list": 0}
        )
        return {
            "total": total,
            "boards": boards,
            "st": st,
            "last_sync": meta["last_sync"],
            "last_sync_display": meta["last_sync_display"],
            "synced_today": meta["synced_today"],
            "stale_sync": meta["stale_sync"],
            "sync_reminder": meta["sync_reminder"],
            "klines_full": full_n,
            "klines_complete": plan_full.get("complete", 0),
            "klines_pending": plan_full.get("pending", 0),
            "klines_pending_incremental": plan_inc.get("pending", 0),
            "klines_pending_full": plan_full.get("pending_full", 0),
            "klines_last_sync": klines_last,
            "klines_registry": {
                **reg_sum,
                "klines_complete": plan_full.get("complete", 0),
                "klines_pending_incremental": plan_inc.get("pending", 0),
                "klines_pending_full": plan_full.get("pending_full", 0),
            },
            "data_source": "local",
            "history_range": "1990-01-01 ~ 今日",
        }

    def query(
        self,
        *,
        include_chinext: bool = True,
        include_star: bool = True,
        include_bse: bool = True,
        exclude_st: bool = True,
        main_board_only: bool = False,
        symbols: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """只读本地 SQLite / JSON，不写入。"""
        local_map = self.load_local_map()

        if symbols:
            out = []
            for sym in {str(s).zfill(6) for s in symbols if s}:
                if sym in local_map:
                    out.append(local_map[sym])
                else:
                    out.append(
                        {
                            "symbol": sym,
                            "name": "",
                            "board": classify_board(sym),
                            "is_st": is_st_stock(sym),
                            "is_main_board": is_main_board(sym),
                            "updated_at": "",
                        }
                    )
            return out[:limit] if limit else out

        out = []
        for s in local_map.values():
            board = s["board"]
            if board == BOARD_CHINEXT and not include_chinext:
                continue
            if board == BOARD_STAR and not include_star:
                continue
            if board == BOARD_BSE and not include_bse:
                continue
            if exclude_st and s.get("is_st"):
                continue
            if main_board_only and not s.get("is_main_board"):
                continue
            out.append(s)
        out.sort(key=lambda x: x["symbol"])
        if limit:
            out = out[: int(limit)]
        return out

    def get_custom_pool(self) -> list[str]:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM user_preferences WHERE key = ?", (CUSTOM_POOL_KEY,)
            ).fetchone()
        if not row:
            return []
        try:
            data = json.loads(row["value"])
            return [str(s).zfill(6) for s in data if s]
        except json.JSONDecodeError:
            return []

    def set_custom_pool(self, symbols: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for s in symbols:
            sym = str(s).strip().zfill(6)
            if sym and sym not in seen:
                seen.add(sym)
                cleaned.append(sym)
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (CUSTOM_POOL_KEY, json.dumps(cleaned, ensure_ascii=False)),
            )
        return cleaned


_svc: UniverseService | None = None


def get_universe_service() -> UniverseService:
    global _svc
    if _svc is None:
        _svc = UniverseService()
    return _svc
