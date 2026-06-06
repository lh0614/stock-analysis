# 数据质量优化报告

## 🎯 优化目标

解决用户反馈的问题：
1. **数据缺失严重** - 000001 等股票显示"数据缺失或冲突严重"
2. **体验断裂** - 发现问题后没有给用户补救机会
3. **自动化不足** - 需要手动操作才能解决数据问题

---

## ✅ 已完成的优化

### 1. 智能数据采集增强

**文件**: `backend/app/services/pipeline.py`

#### 优化前
```python
# 只检查缓存，缓存为空直接调用 fetcher
df = read_daily_bars(symbol=symbol)
if not df.empty:
    records = records_from_daily_bars(df)
    meta = {"data_source": "parquet", "cached": True}
else:
    result = self.fetcher.get_stock_data(symbol, start_date, end_date)
```

#### 优化后
```python
# 检查缓存质量，数据不足（<20条）自动重新拉取
df = read_daily_bars(symbol=symbol, start_date=start_date, end_date=end_date)
if not df.empty and len(df) >= 20:
    records = records_from_daily_bars(df)
    meta = {"data_source": "parquet_cache", "cached": True}
else:
    # 缓存为空或数据不足，尝试从数据源拉取
    result = self.fetcher.get_stock_data(symbol, start_date, end_date)
    
    # 成功拉取后自动保存到缓存
    if records and len(records) >= 20:
        save_daily_bars(pd.DataFrame(records))
        meta["saved_to_cache"] = True
```

**改进**：
- ✅ 增加数据量检查（<20 条视为不足）
- ✅ 自动保存新拉取的数据到缓存
- ✅ 失败时提供详细错误信息和建议操作

---

### 2. 数据质量弹窗提示

**文件**: `frontend/src/components/common/DataQualityDialog.vue`

#### 功能
- ✅ **质量等级可视化** - A/B/C/D 级用不同颜色标签
- ✅ **问题详情展示** - 中文翻译所有质量问题
  ```
  - no_data → "数据缺失：缓存中无此股票数据"
  - invalid_ohlc → "OHLC 数据异常"
  - single_source → "数据来源单一：仅有一个数据源"
  - cross_source_diff → "跨源冲突：收盘价偏差 X%"
  ```
- ✅ **操作建议** - 根据 `retry_action` 显示不同按钮
  - `auto_fetch` → "自动拉取数据"
  - `force_refetch` → "强制重新拉取"
- ✅ **数据统计** - 显示数据条数、时效（多少天前）

#### 触发时机
```javascript
// HomeView.vue - applyPipelineResult()
if (qualityInfo.value?.quality_level === 'D' && qualityInfo.value?.can_retry) {
  showQualityDialog.value = true
}
```

---

### 3. 质量评估增强

**文件**: `backend/app/services/data_quality.py`

#### 优化后返回结构
```json
{
  "symbol": "000001",
  "quality_level": "D",
  "issues": ["no_data"],
  "bar_count": 0,
  "ui_hint": "数据缺失，系统将自动尝试从数据源拉取",
  "block_direction": true,
  "can_retry": true,
  "retry_action": "auto_fetch",
  "retry_hint": "点击「刷新」按钮重新拉取数据"
}
```

**新增字段**：
- ✅ `can_retry` - 是否可重试
- ✅ `retry_action` - 重试动作类型
- ✅ `retry_hint` - 用户提示文案

---

### 4. 强制重新拉取 API

**文件**: `backend/app/api/analysis.py`

#### 新增端点
```python
@router.post("/refetch")
async def refetch_and_analyze(body: AnalysisRunRequest):
    """清除缓存并强制从数据源拉取，然后运行分析"""
    symbol = body.symbol.strip()
    
    # 1. 清除 parquet 和 pkl 缓存
    clear_symbol_cache(symbol)
    
    # 2. 重新运行流水线（会自动从数据源拉取）
    return get_pipeline().run(symbol, body.workflow_id, body.strategy_id)
```

#### 前端集成
```javascript
// frontend/src/api/analysis.js
async refetchAndAnalyze(symbol, workflowId, strategyId) {
  const { data } = await api.post('/refetch', {
    symbol, workflow_id: workflowId, strategy_id: strategyId
  })
  return data
}
```

---

### 5. 缓存管理工具

**文件**: `backend/app/services/data_store.py`

#### 新增方法

**save_daily_bars(df)**
```python
def save_daily_bars(df: pd.DataFrame) -> int:
    """保存日线数据到 parquet"""
    return upsert_daily_bars(df)
```

**clear_symbol_cache(symbol)**
```python
def clear_symbol_cache(symbol: str) -> bool:
    """清除指定股票的缓存数据"""
    # 1. 从 parquet 中删除该股票的记录
    df = pd.read_parquet(path)
    df = df[df["symbol"] != code]
    df.to_parquet(path)
    
    # 2. 删除 pkl 缓存文件
    os.remove(f"{code}_full.pkl")
    
    return True
```

---

## 🎬 完整用户流程

### 场景：分析 000001（数据缺失）

#### 优化前
```
1. 用户输入 000001 点击"分析"
2. 流水线运行 1.7 秒
3. 显示红色横幅："数据缺失或冲突严重，本次不生成方向结论"
4. 用户困惑：怎么办？❌
```

#### 优化后
```
1. 用户输入 000001 点击"分析"
2. 流水线发现缓存为空，自动尝试从数据源拉取
3. 如果拉取成功：
   ✅ 自动保存到缓存
   ✅ 继续分析，显示正常结果
4. 如果拉取失败（数据源无此股票）：
   ⚠️ 弹出质量问题对话框
   
   📋 对话框内容：
   - 标题："数据质量问题"
   - 质量等级：D 级（红色危险标签）
   - 问题详情：
     ✓ 数据缺失：缓存中无此股票数据
   - 数据统计：
     ✓ 数据条数：0 条
     ✓ 数据时效：0 天前
   - 操作建议："点击「刷新」按钮重新拉取数据"
   
   🔘 按钮选项：
   - [取消] - 关闭对话框
   - [自动拉取数据] - 清除缓存并强制重新拉取
   
5. 用户点击"自动拉取数据"：
   ✅ 调用 /api/v1/analysis/refetch
   ✅ 清除 parquet 和 pkl 缓存
   ✅ 重新从数据源拉取
   ✅ 如果成功，显示完整分析结果
   ✅ 如果仍失败，提示"数据源无此股票代码"
```

---

## 📊 优化效果对比

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| **数据缺失检测** | 只在质量阶段发现 | 采集阶段提前检测并尝试修复 |
| **自动化程度** | 需手动清除缓存 | 自动尝试拉取 + 一键强制刷新 |
| **用户提示** | 简单横幅警告 | 详细对话框 + 操作指引 |
| **错误恢复** | 无法恢复 | 提供重试机制 |
| **缓存管理** | 手动操作文件 | API 一键清除 |

---

## 🔧 技术细节

### 数据源优先级（已有）
```python
# backend/app/core/config.py
DATA_SOURCES = ["eastmoney", "akshare", "baostock"]
```

### 容灾机制（已有）
```python
# backend/app/core/data_fetcher.py
def get_stock_data(symbol, start_date, end_date):
    for source in DATA_SOURCES:
        try:
            data = fetch_from_source(source, symbol, start_date, end_date)
            if data: return data
        except:
            continue  # 自动切换下一个源
    return {"success": False, "error": "所有数据源均失败"}
```

### 缓存策略
- **Parquet** - 主缓存，支持 SQL 查询（DuckDB）
- **PKL** - 旧缓存格式，逐步迁移
- **TTL** - 日 K 线缓存 1 天，分钟线当日有效

---

## 🚀 使用建议

### 1. 首次使用新股票
- 系统会自动尝试拉取数据
- 如果数据源没有该股票，会弹窗提示
- 建议检查股票代码是否正确（如 `60019` 应为 `600019`）

### 2. 数据陈旧（超过 3 天）
- 系统标记为 C 级质量
- 不会自动弹窗，但会在横幅提示
- 点击"刷新"按钮即可更新

### 3. 数据冲突（跨源偏差 >1%）
- 系统标记为 C 级或 D 级
- 弹窗显示具体偏差百分比
- 建议点击"强制重新拉取"清除冲突

### 4. 完全无数据
- 系统自动尝试拉取
- 如果拉取失败，弹窗提示
- 可能原因：
  - 股票代码错误
  - 数据源未收录（如新上市股票）
  - 网络问题

---

## 📝 待进一步优化（Phase 2）

### P1 - 用户体验
1. **批量数据修复** - 自选股列表一键检查并修复所有数据质量问题
2. **后台自动更新** - 定时任务自动更新所有缓存数据（避免陈旧）
3. **数据源健康监控** - 实时监控各数据源可用性，智能切换

### P2 - 高级功能
4. **数据对账报告** - 定期生成跨源对账报告，列出所有冲突
5. **手动数据导入** - 允许用户上传自己的 CSV 数据
6. **数据质量历史** - 记录每次质量评估结果，趋势分析

### P3 - 性能优化
7. **增量更新** - 只拉取最新交易日数据，而非全量重拉
8. **并行拉取** - 批量分析时并行拉取多只股票数据
9. **CDN 加速** - 数据源接入 CDN 提升拉取速度

---

## 🎉 总结

通过本次优化，实现了：

✅ **智能感知** - 自动检测数据质量问题  
✅ **主动修复** - 缓存不足时自动拉取并保存  
✅ **用户友好** - 弹窗提示 + 一键操作  
✅ **闭环完整** - 发现问题 → 提示用户 → 提供解决方案 → 验证修复  

**现在用户遇到数据问题时，系统会：**
1. 自动尝试修复（采集阶段自动拉取）
2. 修复失败时弹窗提示（详细问题说明）
3. 提供一键解决方案（强制重新拉取）
4. 记录操作结果（成功/失败反馈）

**数据问题从"用户困惑"变成"系统引导用户解决"！** 🚀
