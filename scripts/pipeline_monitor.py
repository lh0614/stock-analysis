#!/usr/bin/env python3
"""读取流水线实时状态，供终端或 Cursor Agent 同步到聊天（中文输出）。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

STEP_LABELS: dict[str, str] = {
    "pipeline": "流水线",
    "iteration": "迭代轮次",
    "git-status": "Git 状态",
    "codex-plan": "Codex 规划",
    "cursor": "Cursor 实施",
    "deepseek": "DeepSeek 复核",
    "verify": "验证",
    "verify-frontend": "前端构建验证",
    "verify-backend": "后端导入验证",
    "codex-review": "Codex 终审",
    "done": "完成",
    "idle": "空闲",
}

PHASE_LABELS: dict[str, str] = {
    "starting": "启动中",
    "running": "运行中",
    "done": "已完成",
    "failed": "失败",
    "skipped": "已跳过",
    "completed": "已全部完成",
    "unknown": "未知",
    "parse_error": "解析错误",
}


def step_label(step: str | None) -> str:
    if not step:
        return "未知步骤"
    return STEP_LABELS.get(step, step)


def phase_label(phase: str | None) -> str:
    if not phase:
        return "未知阶段"
    return PHASE_LABELS.get(phase, phase)


def read_status(ai_dir: Path) -> dict:
    path = ai_dir / "PIPELINE_STATUS.json"
    if not path.exists():
        return {"step": "idle", "phase": "unknown", "message": "未找到 PIPELINE_STATUS.json"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"step": "error", "phase": "parse_error", "message": str(exc)}


def tail_lines(path: Path, max_lines: int) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if max_lines <= 0:
        return lines
    return lines[-max_lines:]


def format_chat_snapshot(ai_dir: Path, *, tail: int = 40) -> str:
    status = read_status(ai_dir)
    step = str(status.get("step", "?"))
    phase = str(status.get("phase", "?"))
    iteration = status.get("iteration")
    command = status.get("command", "")
    updated = status.get("updated_at", "")
    message = status.get("message", "")

    header = [
        "## 流水线状态",
        f"- 步骤: **{step_label(step)}**（`{step}`）",
        f"- 阶段: **{phase_label(phase)}**（`{phase}`）",
    ]
    if iteration is not None:
        header.append(f"- 轮次: {iteration}")
    if updated:
        header.append(f"- 更新时间: {updated}")
    if command:
        header.append(f"- 命令: `{command[:200]}{'…' if len(command) > 200 else ''}`")
    if message:
        header.append(f"- 说明: {message}")

    live = tail_lines(ai_dir / "PIPELINE_LIVE.log", tail)
    body = ["", "## 最近输出", "```text"]
    body.extend(live if live else ["（暂无输出）"])
    body.append("```")
    return "\n".join(header + body)


def main() -> int:
    parser = argparse.ArgumentParser(description="监控 .ai 流水线实时日志（中文）")
    parser.add_argument("--project", default=".", help="项目根目录")
    parser.add_argument("--tail", type=int, default=40, help="PIPELINE_LIVE.log 包含的行数")
    parser.add_argument("--watch", action="store_true", help="轮询并打印聊天快照，直到流水线结束")
    parser.add_argument("--interval", type=float, default=15.0, help="watch 模式轮询间隔（秒）")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    ai_dir = project / ".ai"

    if not args.watch:
        print(format_chat_snapshot(ai_dir, tail=args.tail))
        return 0

    last_text = ""
    while True:
        status = read_status(ai_dir)
        text = format_chat_snapshot(ai_dir, tail=args.tail)
        if text != last_text:
            print("\n" + "=" * 60 + "\n")
            print(text, flush=True)
            last_text = text
        phase = str(status.get("phase", ""))
        step = str(status.get("step", ""))
        if phase in {"completed", "failed"} and step in {"done", "idle"}:
            break
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    sys.exit(main())
