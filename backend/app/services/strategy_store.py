"""Strategy package storage and versioning."""
from __future__ import annotations

import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.db import get_conn, init_db


MANIFEST_NAME = "manifest.json"


class StrategyStore:
    def __init__(self) -> None:
        init_db()
        self.root = os.path.abspath(os.path.join(settings.CACHE_DIR, "strategies"))
        os.makedirs(self.root, exist_ok=True)
        self._ensure_builtin()
        self._migrate_storage_paths()

    @staticmethod
    def _abs_storage(path: str) -> str:
        return os.path.abspath(os.path.normpath(path))

    def _migrate_storage_paths(self) -> None:
        with get_conn() as conn:
            rows = conn.execute("SELECT id, storage_path FROM strategies").fetchall()
            for row in rows:
                abs_path = self._abs_storage(row["storage_path"])
                if abs_path != row["storage_path"]:
                    conn.execute(
                        "UPDATE strategies SET storage_path = ? WHERE id = ?",
                        (abs_path, row["id"]),
                    )

    def _ensure_builtin(self) -> None:
        builtin_id = "builtin_momentum"
        path = self._abs_storage(os.path.join(self.root, builtin_id))
        if os.path.isdir(path):
            self._upgrade_builtin_strategy_file()
            self._ensure_builtin_default_params(builtin_id)
            return
        os.makedirs(path, exist_ok=True)
        manifest = {
            "name": "builtin_momentum",
            "version": "1.0.0",
            "horizons": ["short", "medium"],
            "inputs": ["ohlcv", "indicators"],
            "outputs": ["score", "notes"],
        }
        with open(os.path.join(path, MANIFEST_NAME), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        self._write_builtin_strategy_file(path)
        now = datetime.now().isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO strategies (id, name, version, horizons, storage_path, is_builtin, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    builtin_id,
                    "内置动量策略",
                    "1.0.0",
                    json.dumps(["short", "medium"]),
                    path,
                    now,
                ),
            )
            # 默认参数修订
            exists = conn.execute(
                "SELECT 1 FROM strategy_revisions WHERE strategy_id = ?", (builtin_id,)
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO strategy_revisions (id, strategy_id, version, params_json, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        builtin_id,
                        "1.0.0",
                        json.dumps({"rsi_high": 70, "macd_weight": 0.4, "rsi_low": 30}),
                        "默认参数",
                        now,
                    ),
                )
        self._upgrade_builtin_strategy_file()

    def _write_builtin_strategy_file(self, path: str) -> None:
        strategy_py = '''
def run(ctx):
    """Built-in: MACD + RSI momentum; respects ctx['params']."""
    params = ctx.get("params") or {}
    rsi_high = float(params.get("rsi_high", 70))
    rsi_low = float(params.get("rsi_low", 30))
    macd_weight = float(params.get("macd_weight", 0.4))
    ind = ctx.get("indicators") or {}
    macd = ind.get("macd") or {}
    rsi = ind.get("rsi") or {}
    score = 0.0
    notes = []
    m = macd.get("macd")
    if m is not None:
        score += macd_weight if m > 0 else -macd_weight
        notes.append(f"MACD柱={m}(权重{macd_weight})")
    r = rsi.get("rsi12")
    if r is not None:
        if r > rsi_high:
            score -= 0.2
            notes.append(f"RSI超买(>{rsi_high})")
        elif r < rsi_low:
            score += 0.2
            notes.append(f"RSI超卖(<{rsi_low})")
        else:
            notes.append(f"RSI12={r}")
    return {"score": round(max(-1, min(1, score)), 3), "notes": notes, "params_used": params}
'''
        with open(os.path.join(path, "strategy.py"), "w", encoding="utf-8") as f:
            f.write(strategy_py.strip())

    def _upgrade_builtin_strategy_file(self) -> None:
        path = os.path.join(self.root, "builtin_momentum")
        if os.path.isdir(path):
            self._write_builtin_strategy_file(path)

    def _ensure_builtin_default_params(self, builtin_id: str) -> None:
        with get_conn() as conn:
            exists = conn.execute(
                "SELECT 1 FROM strategy_revisions WHERE strategy_id = ?", (builtin_id,)
            ).fetchone()
            if exists:
                return
            conn.execute(
                """
                INSERT INTO strategy_revisions (id, strategy_id, version, params_json, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    builtin_id,
                    "1.0.0",
                    json.dumps({"rsi_high": 70, "macd_weight": 0.4, "rsi_low": 30}),
                    "默认参数",
                    datetime.now().isoformat(),
                ),
            )

    def get_latest_params(self, strategy_id: str) -> dict[str, Any]:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT params_json FROM strategy_revisions
                WHERE strategy_id = ? ORDER BY created_at DESC LIMIT 1
                """,
                (strategy_id,),
            ).fetchone()
        if row and row["params_json"]:
            return json.loads(row["params_json"])
        return {}

    def list_strategies(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM strategies ORDER BY is_builtin DESC, created_at DESC"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["enabled"] = bool(d.get("enabled", 1))
            out.append(d)
        return out

    def get(self, strategy_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM strategies WHERE id = ?", (strategy_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["enabled"] = bool(d.get("enabled", 1))
        return d

    def get_path(self, strategy_id: str) -> str | None:
        s = self.get(strategy_id)
        if not s:
            return None
        return self._abs_storage(s["storage_path"])

    def _read_manifest(self, folder: str) -> dict[str, Any]:
        path = os.path.join(folder, MANIFEST_NAME)
        if not os.path.isfile(path):
            raise ValueError(f"缺少 {MANIFEST_NAME}")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for key in ("name", "version", "horizons", "inputs", "outputs"):
            if key not in data:
                raise ValueError(f"manifest 缺少字段: {key}")
        return data

    def upload(self, filename: str, content: bytes) -> dict[str, Any]:
        strategy_id = str(uuid.uuid4())[:12]
        dest = self._abs_storage(os.path.join(self.root, strategy_id))
        os.makedirs(dest, exist_ok=True)

        lower = filename.lower()
        if lower.endswith(".zip"):
            tmp = dest + "_tmp.zip"
            with open(tmp, "wb") as f:
                f.write(content)
            with zipfile.ZipFile(tmp, "r") as zf:
                for member in zf.namelist():
                    target_path = self._abs_storage(os.path.join(dest, member))
                    if not target_path.startswith(dest):
                        raise ValueError("zip 包含非法路径")
                zf.extractall(dest)
            os.remove(tmp)
        elif lower.endswith(".py"):
            with open(os.path.join(dest, "strategy.py"), "wb") as f:
                f.write(content)
            # minimal manifest
            manifest = {
                "name": os.path.splitext(os.path.basename(filename))[0],
                "version": "1.0.0",
                "horizons": ["short"],
                "inputs": ["ohlcv"],
                "outputs": ["score"],
            }
            with open(os.path.join(dest, MANIFEST_NAME), "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        else:
            shutil.rmtree(dest, ignore_errors=True)
            raise ValueError("仅支持 .py 或 .zip")

        manifest = self._read_manifest(dest)
        now = datetime.now().isoformat()
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO strategies (id, name, version, horizons, storage_path, is_builtin, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    strategy_id,
                    manifest["name"],
                    manifest["version"],
                    json.dumps(manifest["horizons"]),
                    dest,
                    now,
                ),
            )
            rev_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO strategy_revisions (id, strategy_id, version, params_json, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rev_id, strategy_id, manifest["version"], "{}", "初始上传", now),
            )
        return self.get(strategy_id)  # type: ignore

    def revise(self, strategy_id: str, params: dict[str, Any], note: str = "") -> dict[str, Any]:
        s = self.get(strategy_id)
        if not s:
            raise ValueError("策略不存在")
        if s.get("is_builtin"):
            return self._save_params_revision(
                strategy_id, s["version"], params, note or "内置策略参数修正"
            )

        parts = s["version"].split(".")
        try:
            patch = int(parts[-1]) + 1
            new_version = ".".join(parts[:-1] + [str(patch)])
        except (ValueError, IndexError):
            new_version = s["version"] + ".1"

        now = datetime.now().isoformat()
        rev_id = str(uuid.uuid4())
        with get_conn() as conn:
            conn.execute(
                "UPDATE strategies SET version = ? WHERE id = ?",
                (new_version, strategy_id),
            )
            conn.execute(
                """
                INSERT INTO strategy_revisions (id, strategy_id, version, params_json, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rev_id, strategy_id, new_version, json.dumps(params), note or "用户修正", now),
            )
        return {"strategy_id": strategy_id, "version": new_version, "revision_id": rev_id, "params": params}

    def _save_params_revision(
        self, strategy_id: str, version: str, params: dict[str, Any], note: str
    ) -> dict[str, Any]:
        now = datetime.now().isoformat()
        rev_id = str(uuid.uuid4())
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO strategy_revisions (id, strategy_id, version, params_json, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rev_id, strategy_id, version, json.dumps(params), note, now),
            )
        return {"strategy_id": strategy_id, "version": version, "revision_id": rev_id, "params": params}

    def list_revisions(self, strategy_id: str) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM strategy_revisions WHERE strategy_id = ?
                ORDER BY created_at DESC LIMIT 20
                """,
                (strategy_id,),
            ).fetchall()
        return [dict(r) for r in rows]


    def set_enabled(self, strategy_id: str, enabled: bool) -> dict[str, Any] | None:
        s = self.get(strategy_id)
        if not s:
            return None
        with get_conn() as conn:
            conn.execute("UPDATE strategies SET enabled = ? WHERE id = ?", (1 if enabled else 0, strategy_id))
        return self.get(strategy_id)

    def list_backtest_refs(self, strategy_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM strategy_backtest_refs WHERE strategy_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (strategy_id, limit),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("metrics_json"):
                d["metrics"] = json.loads(d["metrics_json"])
            out.append(d)
        return out

    def delete(self, strategy_id: str) -> bool:
        s = self.get(strategy_id)
        if not s or s.get("is_builtin"):
            return False
        path = s["storage_path"]
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        with get_conn() as conn:
            conn.execute("DELETE FROM strategy_revisions WHERE strategy_id = ?", (strategy_id,))
            conn.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
        return True


_store: StrategyStore | None = None


def get_strategy_store() -> StrategyStore:
    global _store
    if _store is None:
        _store = StrategyStore()
    return _store
