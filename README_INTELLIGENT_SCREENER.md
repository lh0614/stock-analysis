# 智能选股与策略自进化系统

基于 PRD 实现的智能股票分析系统，支持自动选股、策略回测、自动评级和策略库管理。

## ✨ 核心功能

- 🎯 **智能选股** - 基于25个技术指标的多条件精准筛选
- 📊 **样本内外回测** - 自动验证策略有效性，防止过拟合
- 🏆 **自动评级** - A/B/C/D 四级评级系统
- 📚 **策略库** - 版本管理、状态跟踪、生命周期监控
- 💡 **一键回测** - 选股即回测，自动保存优质策略

## 🚀 快速开始

### 方式一：使用启动脚本（推荐）

```bash
./start.sh
```

选择选项 1 启动完整系统。

### 方式二：手动启动

```bash
# 启动后端
cd backend
python3 -m uvicorn app.main:app --reload

# 启动前端（新终端）
cd frontend
npm run dev
```

### 访问系统

- 前端：http://localhost:5173
- 智能选股：http://localhost:5173/intelligent-screener
- 策略库：http://localhost:5173/strategy-library
- API 文档：http://localhost:8000/docs

## 📖 使用示例

### 1. 创建选股策略

1. 访问智能选股页面
2. 输入策略名称："放量突破策略"
3. 添加条件：
   - 突破20日新高 = true
   - 量比 > 1.5
   - 收盘价 > MA20
4. 添加排序：按20日收益率降序
5. 点击"选股并回测"

### 2. 查看回测结果

系统自动显示：
- 样本内表现（前70%时间）
- 样本外表现（后30%时间）
- 策略评级（A/B/C/D）
- 评级原因和建议

### 3. 管理策略库

访问策略库页面：
- 查看所有已保存策略
- 按状态筛选（已回测/已验证/启用中等）
- 启用/暂停/废弃策略
- 查看策略详情和配置

## 🧪 运行测试

```bash
cd backend
python3 test_e2e.py
```

测试覆盖完整流程：选股 → 回测 → 评级 → 保存。

## 📊 支持的因子（25个）

### 均线因子
- ma5, ma10, ma20, ma60, ma120, ma250
- close_above_ma20, ma_bullish_alignment

### 技术指标
- macd_dif, macd_dea, macd_hist
- rsi6, rsi12, rsi24

### 收益率
- return_1d, return_5d, return_20d, return_60d

### 波动率
- volatility_20d, volatility_60d

### 量价形态
- volume_ratio_5_20
- breakout_20d_high
- pullback_to_ma20
- price_position_60d

## 🎯 策略评级标准

| 评级 | 标准 | 建议 |
|-----|------|------|
| A | 样本外年化>15%，回撤<15%，夏普>1 | 启用 |
| B | 样本外年化>8%，回撤<25% | 谨慎启用 |
| C | 样本外表现一般或疑似过拟合 | 观察或优化 |
| D | 样本外收益为负或回撤>30% | 废弃 |

## 📁 项目结构

```
.
├── backend/                # 后端服务
│   ├── app/
│   │   ├── models/        # 数据模型（StrategySpec）
│   │   ├── services/      # 业务逻辑
│   │   │   ├── intelligent_screener.py   # 选股引擎
│   │   │   ├── strategy_backtest.py      # 回测引擎
│   │   │   ├── strategy_rating.py        # 评级系统
│   │   │   ├── strategy_library.py       # 策略库
│   │   │   └── factors.py                # 因子计算
│   │   └── api/           # API 接口
│   ├── test_e2e.py        # 端到端测试
│   └── test_screener.py   # 选股测试
├── frontend/              # 前端界面
│   └── src/
│       └── views/
│           ├── IntelligentScreenerView.vue  # 智能选股页面
│           └── StrategyLibraryView.vue      # 策略库页面
├── start.sh               # 快速启动脚本
└── IMPLEMENTATION_REPORT.md  # 实现报告
```

## 🛠️ 技术栈

### 后端
- FastAPI - 高性能 Web 框架
- Pydantic - 数据验证
- Pandas/NumPy - 数据处理
- SQLite - 策略库存储

### 前端
- Vue 3 - 渐进式框架
- Element Plus - UI 组件
- Axios - HTTP 客户端

## 📈 系统流程

```
用户配置策略
    ↓
智能选股引擎（25因子筛选）
    ↓
候选股列表（得分+命中原因）
    ↓
样本内外拆分回测
    ↓
自动评级（A/B/C/D）
    ↓
保存到策略库（评级≥B）
```

## 📝 PRD 完成度

- ✅ Phase 0: 数据和因子底座（100%）
- ✅ Phase 1: 智能选股（100%）
- ✅ Phase 2: 策略生成和回测（80%）
- ⏳ Phase 3: 单股分析（0%）
- ⏳ Phase 4: 策略优化（0%）
- ⏳ Phase 5: 自进化监控（0%）

**MVP 完成度：100%**（8/8 项全部完成）

## 📄 许可证

本项目基于 PRD 文档开发，仅供学习和研究使用。

## 🔗 相关文档

- [完整实现报告](./IMPLEMENTATION_REPORT.md)
- [PRD 文档](./智能选股与策略自进化系统%20PRD.md)

---

**注意事项**
- 本系统不提供投资建议
- 回测结果不代表未来收益
- 请在充分理解的基础上使用
