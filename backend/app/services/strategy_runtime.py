"""Sandbox execution for user strategy packages."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from typing import Any

RUNNER_CODE = '''
import importlib.util
import json
import sys

def main():
    strategy_path = sys.argv[1]
    ctx = json.loads(sys.stdin.read())
    spec = importlib.util.spec_from_file_location("user_strategy", strategy_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "run"):
        print(json.dumps({"error": "strategy.py 须定义 run(ctx)"}))
        return
    result = mod.run(ctx)
    print(json.dumps({"result": result}, default=str))

if __name__ == "__main__":
    main()
'''


def resolve_strategy_dir(storage_path: str) -> str:
    """将 DB 中的 storage_path 规范为绝对目录（避免 cwd + 相对路径重复拼接）。"""
    path = os.path.normpath(storage_path)
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    return path


def run_strategy(strategy_path: str, context: dict[str, Any], timeout: int = 15) -> dict[str, Any]:
    strategy_dir = resolve_strategy_dir(strategy_path)
    strategy_py = os.path.join(strategy_dir, "strategy.py")
    if not os.path.isfile(strategy_py):
        return {"success": False, "error": f"未找到 strategy.py: {strategy_py}"}

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(RUNNER_CODE)
        runner_path = tf.name

    try:
        proc = subprocess.run(
            [sys.executable, runner_path, strategy_py],
            input=json.dumps(context),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=strategy_dir,
            env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
        if proc.returncode != 0:
            return {
                "success": False,
                "error": proc.stderr.strip() or "策略执行失败",
                "stdout": proc.stdout[:500],
            }
        out = json.loads(proc.stdout.strip() or "{}")
        if "error" in out:
            return {"success": False, "error": out["error"]}
        return {"success": True, "output": out.get("result")}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"策略执行超时（>{timeout}s）"}
    except json.JSONDecodeError:
        return {"success": False, "error": "策略返回非 JSON", "raw": proc.stdout[:500]}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        try:
            os.unlink(runner_path)
        except OSError:
            pass
