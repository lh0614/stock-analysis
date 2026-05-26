# Local Stock Analysis — 运行手册

**产品代号**：Local Stock Analysis（LSA）  
本文件描述本仓库的日常搭建、构建验证与冒烟检查。产品需求见 `prd.md`；前后端细节见 `frontend/README.md` 与 `backend/README.md`。

---

## 仓库结构

```
local-stock-analysis/
├── backend/                 # FastAPI 后端（Python 3.11）
│   ├── app/
│   │   ├── main.py          # 应用入口、路由、健康检查
│   │   ├── api/             # HTTP 路由（stock、analysis、workflow 等）
│   │   ├── core/            # 配置、数据库、行情拉取
│   │   └── services/        # 流水线、选股器、策略等业务逻辑
│   ├── data/                # 本地运行时数据（见下方「忽略目录」）
│   ├── requirements.txt
│   ├── start_server.py      # 开发启动（uvicorn --reload）
│   ├── Dockerfile
│   └── README.md
├── frontend/                # Vue 3 + Vite 前端
│   ├── src/                 # 页面、组件、API 客户端、Pinia
│   ├── dist/                # 生产构建输出（见下方「忽略目录」）
│   ├── package.json
│   ├── vite.config.js       # 开发代理 /api → localhost:8000
│   ├── Dockerfile           # 多阶段构建 + Nginx
│   └── README.md
├── docker-compose.yml       # 同时启动 backend + frontend
├── dockerfile               # 根目录备用 Dockerfile（compose 使用子目录 Dockerfile）
├── prd.md                   # 产品需求文档
└── docs/PRD.md              # PRD 副本/归档
```

| 路径 | 作用 |
|------|------|
| `backend/app/api/` | REST 接口层，前缀 `/api/v1` |
| `backend/app/services/` | 分析流水线、选股器、策略、预警等 |
| `frontend/src/views/` | 驾驶舱、选股器、工作流、策略、预警、设置 |
| `frontend/src/api/` | Axios 封装，对接后端 API |

---

## 本地忽略的运行时目录

以下目录/文件由 `.gitignore` 排除，**不会提交到 Git**；克隆后需在本机重新生成或自行维护数据。

| 路径 | 说明 |
|------|------|
| `backend/data/` | 本地开发时的 SQLite、断点、策略包、股票池 JSON 等（若 `CACHE_DIR` 指向别处，数据可能在其他路径） |
| `backend/venv/`、`backend/.venv/` | Python 虚拟环境 |
| `frontend/node_modules/` | 前端依赖 |
| `frontend/dist/` | `pnpm build` 产物 |
| `backend/.env` | 本地环境变量（可参考 `backend/.env.example`） |

**说明**：默认 `CACHE_DIR` 为 `~/Documents/AI/stock-pool`（见 `backend/app/core/config.py`）。Docker Compose 将后端数据挂载到命名卷 `lsa-data`，容器内路径为 `data/`。

---

## 前端：安装与构建验证

### 环境要求

- Node.js **18+**
- **pnpm**（推荐；仓库含 `pnpm-lock.yaml`）或 npm

### 安装与开发

```bash
cd frontend
pnpm install          # 或: npm install
pnpm dev              # 或: npm run dev
```

浏览器访问 **http://localhost:5173**。开发模式下 Vite 将 `/api` 代理到 `http://localhost:8000`。

### 构建验证（无需启动后端）

推荐用 **`pnpm verify`** 做生产构建检查（内部执行 `pnpm build`，退出码为 `0` 即成功）。

```bash
cd frontend
pnpm install
pnpm verify           # 首选：等价于 pnpm build，输出到 frontend/dist/
pnpm preview        # 可选：本地预览 dist/
```

`pnpm verify` 委托给 `pnpm build`；构建成功且无报错即表示前端 toolchain 正常。

---

## 后端：安装与冒烟检查

### 环境要求

- Python **3.11+**
- 可访问公网（行情与资讯数据源）

### 安装与启动

```bash
cd backend
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 可选：复制并编辑环境变量
cp .env.example .env

python start_server.py
```

服务默认：**http://localhost:8000**

### 启动前快速检查（可选）

确认依赖与应用模块可加载：

```bash
cd backend
source venv/bin/activate
python -c "from app.main import app; print('import ok')"
```

### 冒烟检查（需服务已运行）

在**另一个终端**执行：

```bash
# 基础健康检查
curl -sf http://localhost:8000/health

# API 健康检查（含数据源与缓存目录状态）
curl -sf http://localhost:8000/api/v1/health

# 根路径
curl -sf http://localhost:8000/
```

预期：`/health` 返回 JSON 且 `status` 为 `healthy`；`/api/v1/health` 返回 `status` 为 `healthy` 或 `degraded`（缓存目录不可写时为 `degraded`）。

交互式验证：打开 **http://localhost:8000/docs**（Swagger）。

---

## Docker Compose：一键启动

在**仓库根目录**执行：

```bash
docker compose up --build
```

| 服务 | 宿主机端口 | 说明 |
|------|------------|------|
| backend | 8000 | 健康检查通过后 frontend 才启动 |
| frontend | 5173 → 容器 80 | Nginx 托管构建产物，`/api` 反代 backend |

冒烟（容器启动后）：

```bash
curl -sf http://localhost:8000/health
curl -sf http://localhost:5173/
```

停止：`docker compose down`（保留数据卷加 `-v` 会删除 `lsa-data`，慎用）。

---

## 端到端手动验证清单

按顺序勾选，用于发布前或环境变更后的最小验证。

### 环境准备

- [ ] `backend/venv` 已创建且 `pip install -r requirements.txt` 成功
- [ ] `frontend/node_modules` 已安装（`pnpm install`）
- [ ] （可选）`backend/.env` 中 `CACHE_DIR` 指向可读写目录

### 后端

- [ ] `python start_server.py` 启动无报错
- [ ] `curl http://localhost:8000/health` 返回 `healthy`
- [ ] `curl http://localhost:8000/api/v1/health` 有 JSON 响应
- [ ] 浏览器打开 http://localhost:8000/docs 可加载 Swagger

### 前端（本地开发）

- [ ] 后端已在 8000 端口运行
- [ ] `pnpm dev` 后打开 http://localhost:5173
- [ ] 侧栏各页面可切换（`/`、`/screener`、`/workflows` 等）
- [ ] 分析驾驶舱：搜索有效 A 股代码（如 `000001`），K 线或摘要有数据或明确错误提示
- [ ] 后端离线时：页面仍有内置工作流回退，无未捕获控制台错误

### 前端（构建）

- [ ] `pnpm verify` 成功，`frontend/dist/index.html` 存在

### Docker（可选）

- [ ] `docker compose up --build` 两服务均为 healthy / 可访问
- [ ] http://localhost:5173 页面加载，且 `/api/v1/health` 经 Nginx 可达

### 回归要点

- [ ] 选股器 `/screener` 可发起扫描或显示进度/结果
- [ ] 设置页 `/settings` 可打开；缓存相关操作不导致 500
- [ ] 流水线运行或 SSE 连接失败时，UI 有提示而非白屏

---

## 常用端口与文档

| 资源 | URL |
|------|-----|
| 前端（开发） | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

---

## 故障速查

| 现象 | 处理 |
|------|------|
| 前端 `timeout` / 工作流加载失败 | 确认后端 `python start_server.py` 或 Docker backend 健康 |
| `/api/v1/health` 为 `degraded` | 检查 `CACHE_DIR` 路径是否存在且可读写 |
| `pnpm: command not found` | 安装 pnpm 或改用 `npm install` / `npm run build` |
| Docker frontend 不启动 | 等待 backend healthcheck；查看 `docker compose logs backend` |

本仓库输出仅供分析参考，不构成投资建议；不提供实盘交易能力。
