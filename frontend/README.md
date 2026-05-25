# 本地股票分析平台 — 前端应用

**产品代号**：Local Stock Analysis（LSA）  
**技术栈**：Vue 3 · Vite 5 · Pinia · Vue Router · Element Plus · ECharts · Axios

本目录为 LSA 的 Web 界面：分析驾驶舱、选股器、工作流记忆、策略工坊、预警中心与系统设置。UI 布局遵循**红熊设计规范**（侧栏 + 面包屑 + 主题变量）。

---

## 快速开始

### 环境要求

- Node.js 18+
- **pnpm**（推荐）或 npm
- 后端 API 已启动（默认 http://localhost:8000）

### 安装与运行

```bash
cd frontend
pnpm install
pnpm dev
```

浏览器访问 **http://localhost:5173**。

开发模式下，Vite 将 `/api` 代理到后端：

```js
// vite.config.js
proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } }
```

### 生产构建

```bash
pnpm build      # 输出到 dist/
pnpm preview    # 本地预览构建结果
```

### Docker

根目录 `docker compose up` 会构建前端镜像（Nginx 托管 `dist`，端口映射 **5173→80**），并等待后端健康检查通过后启动。

---

## 目录结构

```
frontend/
├── src/
│   ├── main.js                 # 应用入口、Element Plus 中文、全局样式
│   ├── App.vue
│   ├── router/index.js         # 路由（嵌套在 AppLayout 下）
│   ├── layouts/
│   │   └── AppLayout.vue       # 190px 侧栏 + 58px 面包屑 + 主内容区
│   ├── views/
│   │   ├── HomeView.vue        # 分析驾驶舱（核心页）
│   │   ├── ScreenerView.vue    # 选股器
│   │   ├── WorkflowsView.vue   # 工作流记忆
│   │   ├── StrategiesView.vue  # 策略工坊
│   │   ├── AlertsView.vue      # 预警中心
│   │   └── SettingsView.vue    # 系统设置
│   ├── components/
│   │   ├── layout/             # AppSidebar、AppBreadcrumb
│   │   ├── analysis/           # 流水线、方向卡、预测、解读等
│   │   ├── StockChart.vue      # ECharts K 线 + 成交量
│   │   ├── StockSearch.vue / StockSummary.vue / ...
│   │   └── WatchlistPanel.vue
│   ├── api/                    # Axios 封装（按领域分文件）
│   ├── stores/
│   │   └── workflow.js         # 工作流/策略选择 + 离线回退
│   ├── constants/
│   │   └── fallbackWorkflows.js  # 后端不可用时的内置模板
│   ├── config/
│   │   └── menu.js             # 侧栏菜单与面包屑元数据
│   └── styles/
│       ├── redbear-theme.css   # 设计令牌（色、圆角、阴影）
│       ├── redbear-layout.css
│       └── home.css            # 驾驶舱页局部样式
├── vite.config.js
├── package.json
├── Dockerfile                  # 多阶段构建 + Nginx
└── nginx.conf                  # /api 反代后端
```

---

## 页面与路由

| 路径 | 页面 | 功能概要 |
|------|------|----------|
| `/` | 分析驾驶舱 | 搜股、自选、七阶段流水线（SSE）、方向卡、K 线、资讯、解读、导出 |
| `/screener` | 选股器 | 预设条件、并行扫描、流式进度 |
| `/workflows` | 工作流记忆 | 短/中/长线模板 CRUD、默认工作流、导入导出 |
| `/strategies` | 策略工坊 | 策略列表、上传、版本与修订 |
| `/alerts` | 预警中心 | 规则管理、触发事件 |
| `/settings` | 系统设置 | 数据源顺序、AI 解读开关、缓存清理、最近标的 |

菜单与面包屑配置见 `src/config/menu.js`。

---

## API 客户端

所有请求默认前缀 **`/api/v1`**（可通过环境变量 `VITE_API_BASE` 覆盖，需含 `/api/v1` 部分时按各文件 `baseURL` 拼接方式使用）。

| 文件 | 职责 |
|------|------|
| `api/stock.js` | 行情、指标、摘要、CSV 导出 URL |
| `api/analysis.js` | 流水线 run/stream、断点、方向、预测、解读 |
| `api/workflow.js` | 工作流 CRUD（超时 30s） |
| `api/strategy.js` | 策略列表与上传 |
| `api/watchlist.js` | 自选股 |
| `api/screener.js` | 选股器 |
| `api/news.js` | 资讯时间线 |
| `api/alerts.js` | 预警 |
| `api/settings.js` | 偏好与健康相关设置 |

示例（分析流水线 SSE）：

```js
import analysisApi from '@/api/analysis.js'

const es = analysisApi.runStream({ symbol: '000001', workflow_id, strategy_id })
es.onmessage = (e) => {
  const payload = JSON.parse(e.data)
  // payload.event: stage | complete | error
}
```

---

## 状态与离线行为

### Pinia：`stores/workflow.js`

- 持久化当前选中的 **工作流 ID**、**策略 ID**（`localStorage`）
- `fetchWorkflows()`：成功后同步服务端模板；失败时使用 `constants/fallbackWorkflows.js` 中的内置三条，**不向页面抛出未捕获异常**

### 驾驶舱挂载顺序（`HomeView.vue`）

1. 先 `syncBackendStatus()`（调用 `/api/v1/health` 或等价检查）  
2. 后端在线：并行拉取工作流与策略（`Promise.allSettled`）  
3. 后端离线：应用本地默认工作流 + 提示启动 API  
4. 在线时加载 `last_symbol` 与 K 线数据；离线时仅尝试读取断点元数据  

后端健康检查**不做定时轮询**；布局层仅在挂载时检查一次。

---

## 分析驾驶舱模块

| 组件 | 说明 |
|------|------|
| `AnalysisToolbar` | 工作流/策略选择、运行流水线 |
| `AnalysisPipeline` | 七阶段进度展示（对接 SSE） |
| `DirectionCards` | 偏多/偏空/震荡与依据 |
| `ForecastTabs` | 短/中/长预测区间 |
| `PriceLevelsPanel` | 支撑与压力 |
| `InterpretationCard` | 规则引擎解读（受设置页开关控制） |
| `StockChart` | ECharts：K 线 + 均线 + MACD 副图 + 成交量柱 |
| `NewsTimeline` | 标的资讯 |
| `WatchlistPanel` | 自选股快捷切换 |
| `RunHistory` | 历史运行记录 |

K 线周期可选 1m / 3m / 6m / 1y；与后端 `period` 参数对应。图表使用 `setOption(..., { notMerge: true })` 避免系列残留。

---

## 样式与布局（红熊规范）

- **侧栏宽度**：190px，分组菜单可展开  
- **顶栏面包屑**：58px 高度  
- **主题变量**：`styles/redbear-theme.css`（主色、背景、边框、字号阶梯）  
- **布局工具类**：`styles/redbear-layout.css`  

Element Plus 在 `main.js` 中配置为**中文 locale**。

---

## 环境变量

| 变量 | 说明 |
|------|------|
| `VITE_API_BASE` | 可选；未设置时开发环境走 Vite 代理 `/api/v1` |

生产构建若需直连绝对地址，在 `.env.production` 中设置，并确保后端 CORS 已包含前端域名。

---

## 脚本

```bash
pnpm dev       # 开发服务器 :5173
pnpm build     # 生产构建 → dist/
pnpm preview   # 预览 dist/
```

---

## 与后端协作

| 场景 | 行为 |
|------|------|
| 开发 | Vite proxy `/api` → `localhost:8000` |
| Docker | Nginx `location /api` → `backend:8000` |
| 超时 | 工作流列表 30s；其他接口多为 15s，失败应有 UI 提示或静默回退 |

后端文档：`../backend/README.md`  
产品需求：`../prd.md`

---

## 常见问题

**控制台 `timeout of 15000ms exceeded`（workflow）**  
→ 多为后端未启动。先运行 `cd backend && python start_server.py`，或确认 8000 端口可达。前端已做离线回退，不应再出现未捕获的 Promise 错误。

**K 线空白或 ECharts 报错**  
→ 确认标的代码有效、后端返回 OHLCV；查看 `StockChart` 是否收到 `dates` / `ohlc` 数组。

**流水线卡在某一阶段**  
→ 打开网络面板查看 `analysis/run/stream` SSE；可在设置页清理缓存后重试，或使用断点续跑。

---

## 免责声明

界面展示的分析方向、预测区间与解读均为**辅助信息**，不构成投资建议。产品**不提供实盘交易**，模拟与回测结果须标注为非实盘。
