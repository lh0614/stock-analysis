# 本地股票分析平台 — 后端服务

**产品代号**：Local Stock Analysis（LSA）  
**技术栈**：Python 3.11 · FastAPI · SQLite · AKShare / 东方财富 / Baostock

本目录提供 LSA 的 REST API：行情拉取、技术指标、七阶段分析流水线、工作流/策略管理、选股器、资讯、预警等。数据与计算优先落在本机（Local-First），**不提供任何实盘交易能力**。

---

## 快速开始

### 环境要求

- Python 3.11+
- 可访问公网（用于拉取行情与资讯）

### 本地开发

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python start_server.py
```

服务默认监听 **http://localhost:8000**。

| 地址 | 说明 |
|------|------|
| http://localhost:8000/docs | Swagger API 文档 |
| http://localhost:8000/redoc | ReDoc 文档 |
| http://localhost:8000/health | 健康检查 |
| http://localhost:8000/api/v1/health | 含数据源列表的健康检查 |

### Docker

在项目根目录执行：

```bash
docker compose up --build
```

后端镜像入口为 `uvicorn app.main:app`，数据目录挂载到卷 `lsa-data`（路径 `data/`）。

---

## 目录结构

```
backend/
├── app/
│   ├── main.py              # FastAPI 应用、路由注册、预警轮询
│   ├── api/                 # HTTP 路由层
│   │   ├── stock.py         # 行情、指标、摘要、OHLCV 导出
│   │   ├── analysis.py      # 流水线、方向、价位、预测、解读
│   │   ├── workflow.py      # 工作流模板 CRUD
│   │   ├── strategy.py      # 策略上传、版本、执行
│   │   ├── settings.py      # 用户偏好、缓存管理
│   │   ├── watchlist.py     # 自选股
│   │   ├── screener.py      # 选股器
│   │   ├── news.py          # 资讯时间线
│   │   └── alerts.py        # 预警规则与事件
│   ├── core/
│   │   ├── config.py        # 配置（CORS、数据源顺序等）
│   │   ├── db.py            # SQLite 初始化与访问
│   │   ├── data_fetcher.py  # 多源行情拉取与缓存
│   │   └── source_priority.py
│   └── services/            # 业务逻辑
│       ├── pipeline.py      # 七阶段分析流水线
│       ├── pipeline_checkpoint.py
│       ├── technical.py     # MA / MACD / RSI 等
│       ├── direction.py       # 方向研判
│       ├── price_levels.py    # 支撑压力
│       ├── interpretation.py  # 规则引擎解读
│       ├── workflow_memory.py
│       ├── strategy_store.py / strategy_runtime.py
│       ├── screener.py / watchlist.py / news.py / alerts.py
│       └── export_data.py / cache_admin.py
├── data/                    # 运行时数据（默认，可配置）
│   ├── lsa.db               # SQLite 主库
│   ├── checkpoints/         # 流水线断点
│   ├── strategies/          # 策略包（含内置 builtin_momentum）
│   └── stock_universe.json  # 选股器股票池
├── requirements.txt
├── start_server.py          # 开发启动（uvicorn --reload）
└── Dockerfile
```

---

## 配置

通过 `backend/.env`（可选）或环境变量覆盖 `app/core/config.py` 中的默认值：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `API_V1_STR` | `/api/v1` | API 前缀 |
| `CACHE_DIR` | `~/Documents/AI/stock-pool` | 股票池根目录（SQLite、klines、断点、策略） |
| `CACHE_EXPIRE_DAYS` | `1` | 行情缓存过期天数 |
| `DATA_SOURCES` | `eastmoney,akshare,baostock` | 数据源 failover 顺序 |
| `DEFAULT_DATA_SOURCE` | `eastmoney` | 首选数据源 |

CORS 默认允许 `http://localhost:5173`（Vite 开发服务器）。

---

## 数据源说明

- **日 K 线**，默认 **前复权（qfq）**
- 拉取失败时按配置顺序依次尝试：**东方财富 → AKShare → Baostock**
- 成功使用的数据源会写入响应 `metadata.data_source`
- 流水线、方向分析等默认历史窗口约 **365 个自然日**（可在工作流中配置 `chart_period`）

资讯接口独立走 AKShare 新闻相关 API，与 K 线数据源无关。

---

## 分析流水线

七阶段顺序（`STAGE_ORDER`）：

1. **ingest** — 拉取 OHLCV  
2. **validate** — 数据质检  
3. **feature** — 技术指标特征  
4. **strategy** — 执行策略包  
5. **predict** — 多周期概率/区间（情景预测，非喊单）  
6. **direction** — 偏多/偏空/震荡 + 置信度  
7. **present** — 汇总输出  

支持：

- `POST /api/v1/analysis/run` — 同步完整运行  
- `POST /api/v1/analysis/run/stream` — **SSE** 流式推送各阶段进度  
- `GET /api/v1/analysis/checkpoint?symbol=` — 查询可续跑断点  
- `POST /api/v1/analysis/resume` / `resume/stream` — 从断点续跑  

断点 JSON 保存在 `data/checkpoints/`。

---

## API 概览

所有业务接口前缀为 **`/api/v1`**。

### 健康与根

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 服务信息 |
| GET | `/health` | 健康检查 |
| GET | `/api/v1/health` | 健康检查 + 数据源列表 |

### 行情 ` /stocks`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/{symbol}` | OHLCV（支持 `period`、`adjust` 等查询参数） |
| GET | `/{symbol}/indicators` | 技术指标 |
| GET | `/{symbol}/summary` | 摘要信息 |
| GET | `/{symbol}/export` | 下载 CSV（OHLCV + 可选指标） |

### 分析 ` /analysis`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/checkpoint` | 断点元数据 |
| POST | `/run`、`/run/stream` | 启动流水线 |
| POST | `/resume`、`/resume/stream` | 续跑 |
| GET | `/runs`、`/runs/{run_id}` | 运行历史 |
| GET | `/{symbol}/direction` | 方向卡数据 |
| GET | `/{symbol}/price-levels` | 支撑/压力 |
| GET | `/{symbol}/forecast` | 短/中/长预测 |
| GET | `/{symbol}/interpretation` | 规则解读（受设置开关控制） |

### 工作流 ` /workflows`

列表、创建、更新、删除、设默认、导入/导出。内置模板：`builtin_short` / `builtin_medium` / `builtin_long`。

### 策略 ` /strategies`

列表、详情、版本历史、上传、修订、沙箱执行、删除。

### 设置 ` /settings`

用户偏好（如 `last_symbol`、数据源顺序、AI 解读开关）、缓存统计与清理。

### 自选股 ` /watchlist`

分组与标的 CRUD。

### 选股器 ` /screener`

预设条件、`POST /run` 与 `POST /run/stream` 并行扫描。

### 资讯 ` /news`

`GET /{symbol}/timeline` — 标的相关资讯时间线。

### 预警 ` /alerts`

规则 CRUD、事件列表、手动 `POST /evaluate`；应用启动后每 **300 秒** 后台轮询评估一次。

完整参数与响应模型见 **Swagger**：http://localhost:8000/docs

---

## 持久化

SQLite 文件：`{CACHE_DIR}/lsa.db`

主要表：

| 表名 | 用途 |
|------|------|
| `workflows` | 工作流模板 |
| `strategies` / `strategy_revisions` | 策略包与修订记录 |
| `pipeline_runs` | 流水线运行记录 |
| `user_preferences` | 键值偏好 |
| `watchlist_*` | 自选股分组与条目 |
| `alert_rules` / `alert_events` | 预警 |

Pickle 行情缓存与断点文件同在 `data/` 下，可通过设置 API 清理。

---

## 策略包约定

用户策略存放在 `data/strategies/{strategy_id}/`，需包含：

- `manifest.json` — 元数据（名称、版本、适用周期等）
- `strategy.py` — 实现 `run(context) -> dict` 入口

内置示例：`data/strategies/builtin_momentum/`。

---

## 依赖

见 `requirements.txt`，核心包括：

- **FastAPI** / **Uvicorn** — Web 服务  
- **pandas** / **numpy** — 数据处理  
- **akshare** / **baostock** — 行情与资讯  
- **pydantic-settings** — 配置  

---

## 与前端协作

- 开发时前端 Vite 将 `/api` 代理到 `http://localhost:8000`
- 生产 Docker 中前端 Nginx 反向代理同路径
- 前端仓库文档：`../frontend/README.md`
- 产品需求：`../prd.md`（v1.2）

---

## 免责声明

本服务输出均为**分析结论与概率研判**，不构成投资建议。用户须自行决策，系统不提供券商柜台或真实买卖能力。
