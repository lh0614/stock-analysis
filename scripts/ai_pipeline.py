#!/usr/bin/env python3
"""Local multi-agent orchestration scaffold.

This script intentionally keeps the workflow file-based and observable. It does
not hide agent output or auto-commit changes.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import shlex
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path


NO_NEXT_TASK = "NO_NEXT_TASK"
NO_EXPANSION = "NO_EXPANSION"
DEFAULT_MAX_DIFF_LINES = 400
DEFAULT_MAX_LOG_LINES = 160
DEFAULT_HEARTBEAT_SEC = 30
CHAT_SNAPSHOT_TAIL = 40

# 步骤/阶段的中文显示名（写入 CHAT_SNAPSHOT 与 PIPELINE_STATUS）
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
}


def step_label(step: str | None) -> str:
    if not step:
        return "未知步骤"
    return STEP_LABELS.get(step, step)


def phase_label(phase: str | None) -> str:
    if not phase:
        return "未知阶段"
    return PHASE_LABELS.get(phase, phase)


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append_live(ai_dir: Path, text: str) -> None:
    path = ai_dir / "PIPELINE_LIVE.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()


def log_event(message: str, *, ai_dir: Path | None = None, step: str | None = None) -> None:
    prefix = f"[{_ts()}]"
    if step:
        prefix += f" [{step}]"
    line = f"{prefix} {message}\n"
    print(line, end="", flush=True)
    if ai_dir:
        append_live(ai_dir, line)


def write_status(ai_dir: Path, **fields: object) -> None:
    path = ai_dir / "PIPELINE_STATUS.json"
    data: dict[str, object] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data.update(fields)
    if "step" in fields:
        data["step_label"] = step_label(str(fields["step"]))
    if "phase" in fields:
        data["phase_label"] = phase_label(str(fields["phase"]))
    data["updated_at"] = _ts()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_chat_snapshot(ai_dir, data)


def _write_chat_snapshot(ai_dir: Path, status: dict[str, object]) -> None:
    step = str(status.get("step", "?"))
    phase = str(status.get("phase", "?"))
    iteration = status.get("iteration")
    command = status.get("command", "")
    message = status.get("message", "")
    updated = status.get("updated_at", "")

    lines = [
        "# 流水线聊天快照",
        "",
        f"- 步骤: {step_label(step)}（{step}）",
        f"- 阶段: {phase_label(phase)}（{phase}）",
    ]
    if iteration is not None:
        lines.append(f"- 轮次: {iteration}")
    if updated:
        lines.append(f"- 更新时间: {updated}")
    if command:
        lines.append(f"- 命令: {command}")
    if message:
        lines.append(f"- 说明: {message}")
    lines.extend(["", "## 最近输出", "", "```text"])
    live = ai_dir / "PIPELINE_LIVE.log"
    if live.exists():
        tail = live.read_text(encoding="utf-8", errors="replace").splitlines()[-CHAT_SNAPSHOT_TAIL:]
        lines.extend(tail if tail else ["(暂无输出)"])
    else:
        lines.append("(暂无输出)")
    lines.extend(["", "```", ""])
    (ai_dir / "CHAT_SNAPSHOT.md").write_text("\n".join(lines), encoding="utf-8")


def run(
    cmd: list[str],
    cwd: Path,
    log_path: Path | None = None,
    check: bool = False,
    *,
    ai_dir: Path | None = None,
    step: str | None = None,
    heartbeat_sec: int = DEFAULT_HEARTBEAT_SEC,
    use_pty: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    printable = " ".join(shlex.quote(part) for part in cmd)
    label = step or "run"
    log_event(f"开始: {printable}", ai_dir=ai_dir, step=label)
    if ai_dir:
        write_status(
            ai_dir,
            step=label,
            phase="running",
            command=printable,
            message=f"{label} 执行中",
        )

    run_env = os.environ.copy() if env is None else env.copy()
    run_env["PYTHONUNBUFFERED"] = "1"

    log_handle = None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")
        log_handle = log_path.open("a", encoding="utf-8")

    chunks: list[str] = []
    start = time.monotonic()
    last_output = start
    stop_heartbeat = threading.Event()

    def emit_chunk(text: str) -> None:
        nonlocal last_output
        print(text, end="", flush=True)
        chunks.append(text)
        if log_handle:
            log_handle.write(text)
            log_handle.flush()
        if ai_dir:
            append_live(ai_dir, text)
        last_output = time.monotonic()

    def heartbeat_loop() -> None:
        while not stop_heartbeat.wait(heartbeat_sec):
            silent = int(time.monotonic() - last_output)
            elapsed = int(time.monotonic() - start)
            if silent < heartbeat_sec:
                continue
            msg = f"仍在运行… 总耗时 {elapsed}s，距上次输出 {silent}s"
            log_event(msg, ai_dir=ai_dir, step=label)
            if ai_dir:
                write_status(ai_dir, step=label, phase="running", message=msg)

    heartbeat = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat.start()

    returncode = 1
    try:
        if use_pty and hasattr(os, "openpty"):
            returncode = _run_pty(cmd, cwd=cwd, env=run_env, emit_chunk=emit_chunk)
        else:
            returncode = _run_pipe(cmd, cwd=cwd, env=run_env, emit_chunk=emit_chunk)
    finally:
        stop_heartbeat.set()
        heartbeat.join(timeout=1.0)
        if log_handle:
            log_handle.close()

    output = "".join(chunks)
    elapsed = int(time.monotonic() - start)
    if returncode == 0:
        log_event(f"结束 exit=0 耗时 {elapsed}s", ai_dir=ai_dir, step=label)
        if ai_dir:
            write_status(ai_dir, step=label, phase="done", exit_code=0, message=f"{label} 完成")
    else:
        log_event(f"失败 exit={returncode} 耗时 {elapsed}s", ai_dir=ai_dir, step=label)
        if ai_dir:
            write_status(
                ai_dir,
                step=label,
                phase="failed",
                exit_code=returncode,
                message=f"{label} 失败 (exit {returncode})",
            )
        if check:
            raise RuntimeError(f"命令执行失败 (exit {returncode}): {printable}")

    return subprocess.CompletedProcess(cmd, returncode, output, "")


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_PAGER"] = "cat"
    env["PAGER"] = "cat"
    return env


def _run_pipe(cmd: list[str], *, cwd: Path, env: dict[str, str], emit_chunk) -> int:
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        emit_chunk(line)
    return process.wait()


def _run_pty(cmd: list[str], *, cwd: Path, env: dict[str, str], emit_chunk) -> int:
    import pty

    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
        close_fds=True,
    )
    os.close(slave_fd)
    try:
        while True:
            ready, _, _ = select.select([master_fd], [], [], 1.0)
            if ready:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                emit_chunk(data.decode("utf-8", errors="replace"))
                continue
            if process.poll() is not None:
                while True:
                    ready, _, _ = select.select([master_fd], [], [], 0)
                    if not ready:
                        break
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    emit_chunk(data.decode("utf-8", errors="replace"))
                break
    finally:
        os.close(master_fd)
    return process.wait()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def trim_text(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if max_lines <= 0 or len(lines) <= max_lines:
        return text
    omitted = len(lines) - max_lines
    return "\n".join(lines[:max_lines]) + f"\n\n... 已截断 {omitted} 行，完整内容见磁盘日志。"


def read_trimmed(path: Path, max_lines: int, fallback: str) -> str:
    if not path.exists():
        return fallback
    return trim_text(path.read_text(encoding="utf-8"), max_lines)


def write_pipeline_summary(ai_dir: Path, *, verification_ok: bool | None = None) -> None:
    cursor_summary = read_trimmed(
        ai_dir / "CURSOR_SUMMARY.md",
        DEFAULT_MAX_LOG_LINES,
        read_trimmed(ai_dir / "CURSOR.log", DEFAULT_MAX_LOG_LINES, "未找到 Cursor 输出。"),
    )
    deepseek_summary = read_trimmed(
        ai_dir / "DEEPSEEK_SUMMARY.md",
        DEFAULT_MAX_LOG_LINES,
        read_trimmed(ai_dir / "DEEPSEEK.log", DEFAULT_MAX_LOG_LINES, "未找到 DeepSeek 输出。"),
    )
    verify_summary = read_trimmed(
        ai_dir / "VERIFY_SUMMARY.md",
        DEFAULT_MAX_LOG_LINES,
        read_trimmed(ai_dir / "VERIFY.log", DEFAULT_MAX_LOG_LINES, "未找到验证输出。"),
    )
    status = read_trimmed(ai_dir / "WORKTREE_STATUS.log", DEFAULT_MAX_LOG_LINES, "未找到工作树状态。")
    result_line = "未执行验证" if verification_ok is None else ("通过" if verification_ok else "不通过")
    write(ai_dir / "PIPELINE_SUMMARY.md", f"""
# 流水线摘要

## 验证结论

{result_line}

## 工作树状态

```text
{status}
```

## Cursor 摘要

{cursor_summary}

## DeepSeek 摘要

{deepseek_summary}

## 验证摘要

```text
{verify_summary}
```
""")


def codex_plan(
    project: Path,
    ai_dir: Path,
    requirement: str,
    iteration: int,
    previous_result: str | None,
    *,
    heartbeat_sec: int = DEFAULT_HEARTBEAT_SEC,
) -> None:
    log_event("[1/5] Codex 规划：写入 .ai 任务产物", ai_dir=ai_dir, step="codex-plan")
    write_status(ai_dir, iteration=iteration, step="codex-plan", phase="starting")
    previous_context = previous_result or "本次运行尚无上一轮结果。"
    prompt = f"""
你是本地多 Agent 开发流水线的规划负责人。请全程使用中文思考和撰写产物。

项目路径: {project}
当前轮次: {iteration}

用户需求:
{requirement}

上一轮上下文:
{previous_context}

请阅读仓库后编写范围明确的交接文件（全部使用中文 Markdown）:

- .ai/TASK.md
- .ai/ACCEPTANCE.md
- .ai/CURSOR_TASK.md
- .ai/DEEPSEEK_TASK.md

规则:
- Codex 只写规划、边界、验收标准和角色交接；不得修改应用代码。
- 只有 Cursor Agent 可以改代码/文件。
- DeepSeek 只做独立复核，不得实现代码。
- .ai 下所有 Markdown 必须使用中文（哨兵值 NO_NEXT_TASK、NO_EXPANSION 除外）。
- 每轮改动保持小而可审查；不要 commit 或 push。
- 若是跟进轮次，范围应缩小到满足验收所需的最小任务。
- .ai/CURSOR_TASK.md 必须要求 Cursor 汇报改动文件与行为，并写入中文摘要:
  - .ai/CURSOR_SUMMARY.md
  - .ai/CURSOR_CHANGED.md
  - .ai/CURSOR_VERIFY.md
- .ai/DEEPSEEK_TASK.md 必须要求 DeepSeek 复核实际改动文件，并写入 .ai/DEEPSEEK_SUMMARY.md（中文）。
"""
    run(
        [
            "codex",
            "exec",
            "--cd",
            str(project),
            "--sandbox",
            "danger-full-access",
            prompt,
        ],
        cwd=project,
        log_path=ai_dir / "CODEX_PLAN.log",
        check=True,
        ai_dir=ai_dir,
        step="codex-plan",
        heartbeat_sec=heartbeat_sec,
    )


def fallback_artifacts(ai_dir: Path, requirement: str) -> None:
    write(ai_dir / "TASK.md", f"""
# 任务

## 目标
{requirement}

## 范围
保持改动小且易审查。

## 不做事项
不要提交或推送。
不要重写无关模块。

## 完成条件
验证命令通过，且 diff 可审查。
""")
    write(ai_dir / "ACCEPTANCE.md", """
# 验收标准

- 已实现请求的行为。
- 保留既有行为。
- 验证命令通过；若命令不可用，需要记录具体原因。
""")
    write(ai_dir / "CURSOR_TASK.md", """
阅读 `.ai/TASK.md` 和 `.ai/ACCEPTANCE.md`。
实现最小合理改动。
不要提交或推送。
完成后用中文总结已改动文件、已改动行为和建议验证命令。
同时写入：
- `.ai/CURSOR_SUMMARY.md`：200-500 字摘要。
- `.ai/CURSOR_CHANGED.md`：文件列表和每个文件一句话说明。
- `.ai/CURSOR_VERIFY.md`：验证命令和结果。
""")
    write(ai_dir / "DEEPSEEK_TASK.md", """
根据 `.ai/TASK.md` 和 `.ai/ACCEPTANCE.md` 复核当前项目状态。
检查可能的 bug、缺失测试和范围膨胀。
用中文返回 PASS/FAIL、已检查的改动文件、认可的改动和必须修复项。
同时写入 `.ai/DEEPSEEK_SUMMARY.md`，只保留结论、阻塞问题、建议和验证评价。
不要修改文件。
""")


def run_cursor(project: Path, ai_dir: Path, *, heartbeat_sec: int = DEFAULT_HEARTBEAT_SEC) -> None:
    log_event("[2/5] Cursor 实施", ai_dir=ai_dir, step="cursor")
    write_status(ai_dir, step="cursor", phase="starting")
    task = read(ai_dir / "CURSOR_TASK.md")
    run(
        ["agent", "-p", "--force", "--trust", "--workspace", str(project), task],
        cwd=project,
        log_path=ai_dir / "CURSOR.log",
        check=True,
        ai_dir=ai_dir,
        step="cursor",
        heartbeat_sec=heartbeat_sec,
    )


def run_deepseek(
    project: Path,
    ai_dir: Path,
    mode: str,
    *,
    max_diff_lines: int,
    max_log_lines: int,
    heartbeat_sec: int = DEFAULT_HEARTBEAT_SEC,
) -> None:
    log_event("[3/5] DeepSeek 复核", ai_dir=ai_dir, step="deepseek")
    write_status(ai_dir, step="deepseek", phase="starting")
    task = read(ai_dir / "DEEPSEEK_TASK.md")
    refresh_diff_artifacts(project, ai_dir)
    cursor_log = read_trimmed(
        ai_dir / "CURSOR_SUMMARY.md",
        max_log_lines,
        read_trimmed(ai_dir / "CURSOR.log", max_log_lines, "未找到 Cursor 汇报。"),
    )
    cursor_changed = read_trimmed(ai_dir / "CURSOR_CHANGED.md", max_log_lines, "未找到 Cursor 文件变更摘要。")
    cursor_verify = read_trimmed(ai_dir / "CURSOR_VERIFY.md", max_log_lines, "未找到 Cursor 验证摘要。")
    diff = read_trimmed(ai_dir / "DIFF.patch", max_diff_lines, "未找到实际 diff。")
    status = read_trimmed(ai_dir / "WORKTREE_STATUS.log", max_log_lines, "未找到工作树状态。")
    review_context = f"""
{task}

## 实际工作树状态

```text
{status}
```

## Cursor 实施汇报

```text
{cursor_log}
```

## Cursor 文件变更摘要

```text
{cursor_changed}
```

## Cursor 验证摘要

```text
{cursor_verify}
```

## 精简 Diff

```diff
{diff}
```

请将复核摘要写入 `.ai/DEEPSEEK_SUMMARY.md`，只包含结论、必须修复项、建议和验证评价。
"""
    if mode == "skip":
        write(ai_dir / "DEEPSEEK.log", "已跳过 DeepSeek 复核。\n")
        write_status(ai_dir, step="deepseek", phase="skipped", message="已跳过 DeepSeek")
        return
    if mode == "exec":
        run(
            ["deepseek", "exec", review_context],
            cwd=project,
            log_path=ai_dir / "DEEPSEEK.log",
            ai_dir=ai_dir,
            step="deepseek",
            heartbeat_sec=heartbeat_sec,
        )
        return
    if mode == "tui":
        write(ai_dir / "DEEPSEEK_CONTEXT.md", review_context)
        log_event(
            "打开 DeepSeek TUI；若未自动带入上下文，请手动粘贴 .ai/DEEPSEEK_CONTEXT.md",
            ai_dir=ai_dir,
            step="deepseek",
        )
        run(
            ["deepseek"],
            cwd=project,
            log_path=ai_dir / "DEEPSEEK.log",
            ai_dir=ai_dir,
            step="deepseek",
            heartbeat_sec=heartbeat_sec,
            use_pty=True,
        )
        return
    raise ValueError(f"未知的 DeepSeek 模式: {mode}")


def refresh_diff_artifacts(project: Path, ai_dir: Path) -> None:
    genv = git_env()
    status = run(
        ["git", "--no-pager", "status", "--short"],
        cwd=project,
        env=genv,
        use_pty=False,
    ).stdout
    diff = run(
        ["git", "--no-pager", "diff", "--", "."],
        cwd=project,
        env=genv,
        use_pty=False,
    ).stdout
    base_status_path = ai_dir / "BASE_STATUS.log"
    base_untracked = set()
    if base_status_path.exists():
        for line in base_status_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("?? "):
                base_untracked.add(line[3:].strip())
    untracked = run(
        ["git", "--no-pager", "ls-files", "--others", "--exclude-standard"],
        cwd=project,
        env=genv,
        use_pty=False,
    ).stdout
    for rel_path in [line.strip() for line in untracked.splitlines() if line.strip()]:
        if rel_path.startswith(".ai/") or rel_path in base_untracked:
            continue
        path = project / rel_path
        if not path.is_file():
            continue
        file_diff = run(
            ["git", "--no-pager", "diff", "--no-index", "--", "/dev/null", rel_path],
            cwd=project,
            env=genv,
            use_pty=False,
        ).stdout
        file_diff = file_diff.replace(f"diff --git a/dev/null b/{rel_path}", f"diff --git a/{rel_path} b/{rel_path}")
        file_diff = file_diff.replace("--- a/dev/null", "--- /dev/null")
        diff += ("\n" if diff and not diff.endswith("\n") else "") + file_diff
    write(ai_dir / "WORKTREE_STATUS.log", status)
    write(ai_dir / "DIFF.patch", diff)


def verify(project: Path, ai_dir: Path, *, heartbeat_sec: int = DEFAULT_HEARTBEAT_SEC) -> bool:
    log_event("[4/5] 验证", ai_dir=ai_dir, step="verify")
    write_status(ai_dir, step="verify", phase="starting")
    commands = [
        (["pnpm", "build"], project / "frontend", "verify-frontend"),
        (
            ["venv/bin/python", "-c", "from app.main import app; print('import ok')"],
            project / "backend",
            "verify-backend",
        ),
    ]
    ok = True
    logs: list[str] = []
    for cmd, cwd, step in commands:
        result = run(
            cmd,
            cwd=cwd,
            ai_dir=ai_dir,
            step=step,
            heartbeat_sec=heartbeat_sec,
            use_pty=False,
        )
        logs.append(f"$ {' '.join(shlex.quote(part) for part in cmd)}\n{result.stdout}{result.stderr}")
        ok = ok and result.returncode == 0
    write(ai_dir / "VERIFY.log", "\n\n".join(logs))
    write(ai_dir / "VERIFY_SUMMARY.md", f"""
# 验证摘要

- 前端构建：{"通过" if "✓ built" in logs[0] and "ERR!" not in logs[0] else "请查看 VERIFY.log"}
- 后端导入：{"通过" if "import ok" in logs[1] else "请查看 VERIFY.log"}
- 总体结论：{"通过" if ok else "不通过"}
""")
    return ok


def codex_review(
    project: Path,
    ai_dir: Path,
    verification_ok: bool,
    iteration: int,
    max_iterations: int,
    *,
    review_mode: str,
    max_diff_lines: int,
    max_log_lines: int,
    heartbeat_sec: int = DEFAULT_HEARTBEAT_SEC,
) -> None:
    log_event("[5/5] Codex 终审：写入 review/result 产物", ai_dir=ai_dir, step="codex-review")
    write_status(ai_dir, step="codex-review", phase="starting", iteration=iteration)
    refresh_diff_artifacts(project, ai_dir)
    write_pipeline_summary(ai_dir, verification_ok=verification_ok)
    if review_mode == "summary":
        prompt = f"""
你是本地多 Agent 流水线的最终决策者。请全程使用中文思考和撰写产物。

验证是否通过: {verification_ok}
当前轮次: {iteration}
最大轮次: {max_iterations}

默认只阅读精简决策材料:
- .ai/TASK.md
- .ai/ACCEPTANCE.md
- .ai/PIPELINE_SUMMARY.md
- .ai/CURSOR_SUMMARY.md（若存在）
- .ai/CURSOR_CHANGED.md（若存在）
- .ai/CURSOR_VERIFY.md（若存在）
- .ai/DEEPSEEK_SUMMARY.md（若存在）
- .ai/VERIFY_SUMMARY.md（若存在）
- .ai/NEXT_TASK.md（若存在）

除非摘要矛盾或高风险决策信息不足，否则不要读取完整日志或 .ai/DIFF.patch。

请写入（全部中文 Markdown）:
- .ai/REVIEW.md：发现、风险、本轮是否可接受。
- .ai/NEXT_TASK.md：仅当不可接受时写入有界必修任务；否则写 exactly NO_NEXT_TASK。
- .ai/EXPANSION_PROPOSAL.md：可接受且有有价值的相邻功能时写可选扩散；否则写 exactly NO_EXPANSION。
- .ai/RESULT.md：面向用户的简洁摘要（改动文件与行为）。

规则:
- 不得修改应用代码；Cursor 是实施者，DeepSeek 是独立复核者。
- .ai 下 Markdown 必须中文（哨兵值 NO_NEXT_TASK、NO_EXPANSION 除外）。
- 验证失败时 NEXT_TASK.md 必须基于验证摘要给出有界修复任务。
- DeepSeek 或你发现必修问题时，NEXT_TASK.md 写最小必修修复/优化。
- 验收满足时 NEXT_TASK.md 写 exactly NO_NEXT_TASK；可选扩散只放 EXPANSION_PROPOSAL.md。
- 已达最大轮次仍有阻塞时，NEXT_TASK.md 保留阻塞任务并在 REVIEW.md 说明。
- 保持简洁；不要 commit 或 push。
"""
    else:
        diff_excerpt = read_trimmed(ai_dir / "DIFF.patch", max_diff_lines, "未找到 diff。")
        cursor_log = read_trimmed(ai_dir / "CURSOR.log", max_log_lines, "未找到 Cursor 日志。")
        deepseek_log = read_trimmed(ai_dir / "DEEPSEEK.log", max_log_lines, "未找到 DeepSeek 日志。")
        verify_log = read_trimmed(ai_dir / "VERIFY.log", max_log_lines, "未找到验证日志。")
        write(ai_dir / "CODEX_REVIEW_CONTEXT.md", f"""
# Codex 终审上下文

## 验证

```text
{verify_log}
```

## Cursor

```text
{cursor_log}
```

## DeepSeek

```text
{deepseek_log}
```

## Diff 摘录

```diff
{diff_excerpt}
```
""")
        prompt = f"""
你是本地多 Agent 流水线的最终检查者。请全程使用中文思考和撰写产物。

验证是否通过: {verification_ok}
当前轮次: {iteration}
最大轮次: {max_iterations}

请阅读:
- .ai/TASK.md
- .ai/ACCEPTANCE.md
- .ai/PIPELINE_SUMMARY.md
- .ai/CODEX_REVIEW_CONTEXT.md

请写入（全部中文 Markdown）:
- .ai/REVIEW.md
- .ai/NEXT_TASK.md（不可接受时有界任务，否则 exactly NO_NEXT_TASK）
- .ai/EXPANSION_PROPOSAL.md（可选扩散，否则 exactly NO_EXPANSION）
- .ai/RESULT.md

规则: 不得改应用代码；哨兵值 NO_NEXT_TASK、NO_EXPANSION 保持英文；不要 commit 或 push。
"""
    run(
        [
            "codex",
            "exec",
            "--cd",
            str(project),
            "--sandbox",
            "danger-full-access",
            prompt,
        ],
        cwd=project,
        log_path=ai_dir / "CODEX_REVIEW.log",
        check=True,
        ai_dir=ai_dir,
        step="codex-review",
        heartbeat_sec=heartbeat_sec,
    )


def archive_iteration(ai_dir: Path, iteration: int) -> None:
    archive_dir = ai_dir / "iterations" / f"{iteration:03d}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "REQUIREMENT.md",
        "TASK.md",
        "ACCEPTANCE.md",
        "CURSOR_TASK.md",
        "DEEPSEEK_TASK.md",
        "CURSOR.log",
        "DEEPSEEK.log",
        "VERIFY.log",
        "DIFF.patch",
        "REVIEW.md",
        "NEXT_TASK.md",
        "RESULT.md",
        "CODEX_PLAN.log",
        "CODEX_REVIEW.log",
        "WORKTREE_STATUS.log",
        "EXPANSION_PROPOSAL.md",
        "BASE_STATUS.log",
        "PIPELINE_LIVE.log",
        "PIPELINE_STATUS.json",
        "CHAT_SNAPSHOT.md",
    ]:
        source = ai_dir / name
        if source.exists():
            (archive_dir / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def read_next_task(ai_dir: Path) -> str:
    path = ai_dir / "NEXT_TASK.md"
    if not path.exists():
        return NO_NEXT_TASK
    return path.read_text(encoding="utf-8").strip()


def read_expansion_proposal(ai_dir: Path) -> str:
    path = ai_dir / "EXPANSION_PROPOSAL.md"
    if not path.exists():
        return NO_EXPANSION
    return path.read_text(encoding="utf-8").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="本地多 Agent 流水线（产物与日志默认中文）")
    parser.add_argument("requirement", help="本轮用户需求（中文）")
    parser.add_argument("--project", default=os.getcwd(), help="项目根目录")
    parser.add_argument("--deepseek-mode", choices=["exec", "tui", "skip"], default="exec", help="DeepSeek 模式")
    parser.add_argument("--skip-codex-plan", action="store_true", help="跳过 Codex 规划")
    parser.add_argument("--skip-cursor", action="store_true", help="跳过 Cursor 实施")
    parser.add_argument("--skip-deepseek", action="store_true", help="跳过 DeepSeek 复核")
    parser.add_argument("--max-iterations", type=int, default=3, help="最大迭代轮次")
    parser.add_argument(
        "--codex-review-mode",
        choices=["summary", "bounded"],
        default="summary",
        help="summary=仅读摘要；bounded=额外读截断日志与 diff",
    )
    parser.add_argument("--max-diff-lines", type=int, default=DEFAULT_MAX_DIFF_LINES, help="bounded 模式 diff 最大行数")
    parser.add_argument("--max-log-lines", type=int, default=DEFAULT_MAX_LOG_LINES, help="bounded 模式日志最大行数")
    parser.add_argument(
        "--heartbeat-sec",
        type=int,
        default=DEFAULT_HEARTBEAT_SEC,
        help="无子进程输出时，向终端/.ai 写入心跳的间隔（秒）",
    )
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    ai_dir = project / ".ai"
    ai_dir.mkdir(parents=True, exist_ok=True)
    live_log = ai_dir / "PIPELINE_LIVE.log"
    live_log.write_text(f"[{_ts()}] 流水线启动\n", encoding="utf-8")

    log_event(f"项目路径: {project}", ai_dir=ai_dir, step="pipeline")
    log_event(f"产物目录: {ai_dir}", ai_dir=ai_dir, step="pipeline")
    log_event(f"最大轮次: {args.max_iterations}", ai_dir=ai_dir, step="pipeline")
    log_event(
        "实时日志: 终端 + .ai/PIPELINE_LIVE.log；聊天快照: .ai/CHAT_SNAPSHOT.md",
        ai_dir=ai_dir,
        step="pipeline",
    )
    log_event(
        "监控命令: python3 scripts/pipeline_monitor.py --watch",
        ai_dir=ai_dir,
        step="pipeline",
    )
    log_event(f"Codex 终审模式: {args.codex_review_mode}", ai_dir=ai_dir, step="pipeline")
    write_status(
        ai_dir,
        step="pipeline",
        phase="starting",
        requirement=args.requirement[:500],
        message="流水线已启动",
    )

    if args.max_iterations < 1:
        raise ValueError("--max-iterations 至少为 1")

    base_status = run(
        ["git", "--no-pager", "status", "--short"],
        cwd=project,
        ai_dir=ai_dir,
        step="git-status",
        use_pty=False,
        env=git_env(),
    ).stdout
    write(ai_dir / "BASE_STATUS.log", base_status)

    requirement = args.requirement
    previous_result: str | None = None
    verification_ok = False

    for iteration in range(1, args.max_iterations + 1):
        log_event(f"=== 第 {iteration}/{args.max_iterations} 轮 ===", ai_dir=ai_dir, step="pipeline")
        write(ai_dir / "REQUIREMENT.md", requirement)

        write_status(ai_dir, iteration=iteration, step="iteration", phase="running")

        if args.skip_codex_plan:
            required = ["TASK.md", "ACCEPTANCE.md", "CURSOR_TASK.md", "DEEPSEEK_TASK.md"]
            if all((ai_dir / name).exists() for name in required):
                log_event("[1/5] 跳过 Codex 规划（沿用已有 .ai 产物）", ai_dir=ai_dir, step="codex-plan")
            else:
                log_event("[1/5] 跳过 Codex 规划，补写 fallback 产物", ai_dir=ai_dir, step="codex-plan")
                fallback_artifacts(ai_dir, requirement)
        else:
            codex_plan(
                project,
                ai_dir,
                requirement,
                iteration,
                previous_result,
                heartbeat_sec=args.heartbeat_sec,
            )
            required = ["TASK.md", "ACCEPTANCE.md", "CURSOR_TASK.md", "DEEPSEEK_TASK.md"]
            if not all((ai_dir / name).exists() for name in required):
                log_event("Codex 未生成全部产物，写入 fallback", ai_dir=ai_dir, step="codex-plan")
                fallback_artifacts(ai_dir, requirement)

        if not args.skip_cursor:
            run_cursor(project, ai_dir, heartbeat_sec=args.heartbeat_sec)
        else:
            log_event("[2/5] 跳过 Cursor 实施", ai_dir=ai_dir, step="cursor")

        if not args.skip_deepseek:
            run_deepseek(
                project,
                ai_dir,
                args.deepseek_mode,
                max_diff_lines=args.max_diff_lines,
                max_log_lines=args.max_log_lines,
                heartbeat_sec=args.heartbeat_sec,
            )
        else:
            log_event("[3/5] 跳过 DeepSeek 复核", ai_dir=ai_dir, step="deepseek")

        verification_ok = verify(project, ai_dir, heartbeat_sec=args.heartbeat_sec)
        codex_review(
            project,
            ai_dir,
            verification_ok,
            iteration,
            args.max_iterations,
            review_mode=args.codex_review_mode,
            max_diff_lines=args.max_diff_lines,
            max_log_lines=args.max_log_lines,
            heartbeat_sec=args.heartbeat_sec,
        )

        next_task = read_next_task(ai_dir)
        result_path = ai_dir / "RESULT.md"
        previous_result = result_path.read_text(encoding="utf-8") if result_path.exists() else None
        archive_iteration(ai_dir, iteration)

        if next_task == NO_NEXT_TASK:
            expansion = read_expansion_proposal(ai_dir)
            write_status(
                ai_dir,
                step="done",
                phase="completed",
                message="流水线完成",
                verification_ok=verification_ok,
            )
            if expansion and expansion != NO_EXPANSION:
                log_event(
                    f"流水线完成；可选扩散见 {ai_dir / 'EXPANSION_PROPOSAL.md'}，需人工确认后再跑",
                    ai_dir=ai_dir,
                    step="pipeline",
                )
            else:
                log_event("流水线完成，无 NEXT_TASK", ai_dir=ai_dir, step="pipeline")
            return 0 if verification_ok else 1

        if iteration == args.max_iterations:
            write_status(
                ai_dir,
                step="done",
                phase="failed",
                message="已达最大迭代次数，请人工查看 NEXT_TASK.md",
            )
            log_event("已达最大迭代次数，停止", ai_dir=ai_dir, step="pipeline")
            return 1

        log_event("Codex 要求继续下一轮", ai_dir=ai_dir, step="pipeline")
        requirement = next_task

    write_status(ai_dir, step="done", phase="completed", message="流水线结束")
    return 0 if verification_ok else 1


if __name__ == "__main__":
    sys.exit(main())
