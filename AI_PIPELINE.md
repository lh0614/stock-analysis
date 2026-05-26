# AI 流水线

本项目使用本地多 Agent 流水线。推荐在 **Cursor 终端**执行完整任务，让 Cursor 承担实时日志观察；Codex 只做任务规划、最终验收和扩散决策，默认不读取完整日志和全量 diff。

## 语言约定

- **思考、对话、`.ai/` 产物、任务单与摘要**：一律使用中文。
- **哨兵值** `NO_NEXT_TASK`、`NO_EXPANSION` 保持英文，便于脚本解析。
- 项目规则见 `.cursor/rules/chinese-language.mdc`（对已打开的 Cursor Agent 会话生效）。

## 推荐用法

在 Cursor 终端运行：

```bash
python3 scripts/ai_pipeline.py --deepseek-mode exec --max-iterations 3 "你的任务"
```

执行时你可以在 Cursor 终端看到完整实时日志（含 Codex / Cursor / DeepSeek 子进程输出；无输出时每 30s 有心跳）。

实时可观测文件：

| 文件 | 用途 |
|------|------|
| `.ai/PIPELINE_LIVE.log` | 全流水线追加日志（终端同步） |
| `.ai/PIPELINE_STATUS.json` | 当前步骤、阶段、命令 |
| `.ai/CHAT_SNAPSHOT.md` | 给 Cursor Agent 读的聊天快照（状态 + 最近 40 行输出） |
| `.ai/CODEX_PLAN.log` 等 | 各步骤完整日志 |

**Cursor Agent 监控（并同步到聊天）**：另开终端或让 Agent 轮询：

```bash
python3 scripts/pipeline_monitor.py --watch --interval 15
```

Agent 也可直接读取 `.ai/CHAT_SNAPSHOT.md`，把内容贴回对话。

各角色分步日志仍写入 `.ai/*.log`；Codex final check 默认只读取短摘要，以降低 Codex token 消耗。

## 角色分工

### Codex

- 生成任务单、验收标准、Cursor 交接任务和 DeepSeek 复核任务。
- 最终只读取摘要材料做验收决策。
- 决定是否继续必修修复。
- 当前任务接受后，判断是否有可选扩散功能，并写入 `.ai/EXPANSION_PROPOSAL.md`。
- 不实现应用代码。

### Cursor Agent

- 执行代码变更。
- 在 Cursor 终端输出完整实时日志。
- 将完整输出写入 `.ai/CURSOR.log`。
- 必须写中文短摘要：
  - `.ai/CURSOR_SUMMARY.md`
  - `.ai/CURSOR_CHANGED.md`
  - `.ai/CURSOR_VERIFY.md`

### DeepSeek

- 只做独立复核，不实现代码。
- 输入包含任务、工作树状态、Cursor 摘要和精简 diff。
- 必须写中文短摘要：
  - `.ai/DEEPSEEK_SUMMARY.md`

### Shell 验证

验证命令仍是事实来源。默认验证包括：

```bash
cd frontend && pnpm build
cd backend && venv/bin/python -c "from app.main import app; print('import ok')"
```

验证结果写入：

- `.ai/VERIFY.log`：完整验证日志。
- `.ai/VERIFY_SUMMARY.md`：短验证摘要。

## Codex 低 Token 模式

默认参数：

```bash
--codex-review-mode summary
```

该模式下 Codex final check 默认只读取：

- `.ai/TASK.md`
- `.ai/ACCEPTANCE.md`
- `.ai/PIPELINE_SUMMARY.md`
- `.ai/CURSOR_SUMMARY.md`
- `.ai/CURSOR_CHANGED.md`
- `.ai/CURSOR_VERIFY.md`
- `.ai/DEEPSEEK_SUMMARY.md`
- `.ai/VERIFY_SUMMARY.md`

除非摘要矛盾或存在高风险问题，Codex 不读取完整 `.ai/CURSOR.log`、`.ai/DEEPSEEK.log` 或 `.ai/DIFF.patch`。

如需要更详细但仍有限制的最终检查，可使用：

```bash
python3 scripts/ai_pipeline.py \
  --codex-review-mode bounded \
  --max-diff-lines 400 \
  --max-log-lines 160 \
  --deepseek-mode exec \
  --max-iterations 3 \
  "你的任务"
```

## 产物目录

```text
.ai/
  REQUIREMENT.md
  TASK.md
  ACCEPTANCE.md
  CURSOR_TASK.md
  DEEPSEEK_TASK.md
  CURSOR.log
  CURSOR_SUMMARY.md
  CURSOR_CHANGED.md
  CURSOR_VERIFY.md
  DEEPSEEK.log
  DEEPSEEK_SUMMARY.md
  VERIFY.log
  VERIFY_SUMMARY.md
  WORKTREE_STATUS.log
  DIFF.patch
  PIPELINE_SUMMARY.md
  REVIEW.md
  NEXT_TASK.md
  EXPANSION_PROPOSAL.md
  RESULT.md
```

## 循环规则

```text
1. 用户在 Cursor 终端执行流水线命令
2. Codex 生成任务交接文件
3. Cursor 执行并输出完整实时日志，同时写短摘要
4. DeepSeek 基于 Cursor 摘要和精简 diff 复核
5. Shell 执行验证命令
6. Codex 只读摘要做最终决策
7. 若存在必修问题，写入 NEXT_TASK.md 并进入下一轮
8. 若无必修问题，NEXT_TASK.md 写 NO_NEXT_TASK
9. 若有可选扩散功能，写入 EXPANSION_PROPOSAL.md，等待人工确认
```

`NEXT_TASK.md` 只放必修修复；扩散功能只能放入 `EXPANSION_PROPOSAL.md`，不会自动执行。

## 什么时候再找 Codex

完整流程在 Cursor 终端跑完后，再让 Codex 读取以下摘要文件即可：

```text
.ai/RESULT.md
.ai/NEXT_TASK.md
.ai/EXPANSION_PROPOSAL.md
.ai/VERIFY_SUMMARY.md
```

这样 Codex 只做验收和扩散决策，不再消耗大量 token 盯完整实时日志。
