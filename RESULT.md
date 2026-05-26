# 交付汇报 — 数据同步定时器

## 变更文件列表

### 后端（新增）
- `backend/app/services/sync_scheduler.py` — 定时调度服务（配置持久化、并发锁、每日触发）
- `backend/app/api/sync_scheduler.py` — REST API

### 后端（修改）
- `backend/app/main.py` — 注册路由；lifespan 启动/取消调度循环

### 前端（新增）
- `frontend/src/api/syncScheduler.js`
- `frontend/src/views/SyncSchedulerView.vue`

### 前端（修改）
- `frontend/src/router/index.js` — 路由 `/sync-scheduler`
- `frontend/src/config/menu.js` — 系统管理 → 数据同步

## 变更后的行为说明

- **API**
  - `GET /api/v1/sync-scheduler/status` — 配置 + 运行状态（含 `next_run_at`、进度）
  - `PUT /api/v1/sync-scheduler/config` — 保存 `enabled`、`time_of_day`（HH:MM）、`sync_mode`（incremental/full）
  - `POST /api/v1/sync-scheduler/run` — 后台立即同步；运行中返回 `accepted: false`
- **调度**：服务启动后每 60 秒检查一次；启用且到达每日固定时间时调用 `universe.iter_sync_all`；到点若已在跑则记录 `skipped`。
- **持久化**：`user_preferences` 键 `sync_scheduler_config`、`sync_scheduler_run_state`。
- **前端**：独立「数据同步」页，可配置/保存/立即同步；运行中每 2 秒轮询状态；选股器原有同步按钮未改动。

## 验证命令及结果

| 命令 | 结果 |
|------|------|
| `cd backend && python -m compileall app` | 通过（exit 0） |
| `cd frontend && pnpm build` | 通过（exit 0） |

## 未完成项或风险

- 定时精度为分钟级轮询（60s 间隔），非秒级 cron；服务在触发时刻未运行则可能错过当日一次。
- 长时间同步占用线程池 worker，与选股器 SSE 同步并行时仍可能争抢资源（universe 层无全局锁，仅调度器自身有锁）。
- 未做端到端联调（需启动后端 + 真实行情源）。

## 新增依赖

无。调度使用现有 `asyncio` + `run_in_executor`，配置复用 SQLite `user_preferences`。
