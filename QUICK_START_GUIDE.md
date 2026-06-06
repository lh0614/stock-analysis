# 快速启动和验证指南

## 问题修复

已修复的问题：
1. ✅ 移除了不必要的 sqlalchemy 依赖
2. ✅ 修复了所有缩进错误
3. ✅ 创建了缺失的 request.js 工具文件
4. ✅ 所有模块导入测试通过

## 启动步骤

### 1. 启动后端

```bash
cd backend
source venv/bin/activate
python3 -m uvicorn app.main:app --reload --port 8000
```

**验证**: 访问 http://localhost:8000/docs 应该看到API文档

### 2. 启动前端

```bash
cd frontend
npm install  # 首次运行需要
npm run dev
```

**验证**: 访问 http://localhost:5173 应该看到前端界面

## 功能验证

### Phase 0-2 功能（已有）

1. **智能选股**
   - 访问: http://localhost:5173/intelligent-screener
   - 设置条件，点击"运行选股"
   - 应该能看到候选股列表

2. **策略库**
   - 访问: http://localhost:5173/strategy-library
   - 查看已保存的策略
   - 可以启用/暂停/废弃策略

### Phase 3 功能（新增）

3. **单股深度分析**
   - 访问: http://localhost:5173/stock-deep-analysis
   - 输入股票代码（如: 600519）
   - 点击"深度分析"
   - 查看分析结果：
     - 综合结论卡片
     - 预期收益区间
     - 风险提示
     - 触发/失效条件
     - 证据链详情

### Phase 4 功能（新增）

4. **策略优化**
   - 访问策略库页面
   - 找到任意策略，点击"优化"按钮
   - 确认优化配置
   - 等待优化完成（可能需要几分钟）
   - 查看优化结果：
     - 决策（晋级/候选/拒绝）
     - 参数变更对比
     - 改进情况

### Phase 5 功能（新增）

5. **策略健康度监控**
   - 访问策略库页面
   - 找到活跃策略，点击"健康度"按钮
   - 查看健康度报告：
     - 健康度评分（0-100）
     - 状态（健康/衰减/失效）
     - 衰减信号
     - 优化建议

## API测试

可以通过 http://localhost:8000/docs 访问API文档，测试各个接口：

### Phase 3 API
- `POST /api/v1/stock-analysis/deep-run`
- `GET /api/v1/stock-analysis/symbol/{symbol}/latest`

### Phase 4 API
- `POST /api/v1/strategy-optimizer/optimize`
- `GET /api/v1/strategy-optimizer/jobs/{job_id}`

### Phase 5 API
- `GET /api/v1/strategy-monitor/health`
- `GET /api/v1/strategy-monitor/strategies/{strategy_id}`

## 常见问题

### 前端报错 "Failed to resolve import"

**原因**: 缺少 request.js 文件  
**解决**: 已创建 `/frontend/src/utils/request.js`

### 后端报错 "No module named 'sqlalchemy'"

**原因**: 错误导入了不需要的依赖  
**解决**: 已从以下文件移除 sqlalchemy 导入：
- `stock_deep_analysis.py`
- `strategy_optimizer.py`
- `strategy_monitor.py`

### 后端启动报错 "IndentationError"

**原因**: 编辑时产生的缩进错误  
**解决**: 已修复所有缩进问题

### 前端无法连接后端

**检查**:
1. 后端是否在 8000 端口运行
2. 前端环境变量是否正确配置
3. 浏览器控制台是否有 CORS 错误

## 测试脚本

### 简化测试（推荐）
```bash
cd backend
python3 test_phase3_5_simple.py
```

**预期输出**:
```
✓ stock_deep_analysis 导入成功
✓ strategy_optimizer 导入成功
✓ strategy_monitor 导入成功
✓ 所有数据模型验证通过
✓ 所有API接口就绪
```

### 完整测试
```bash
cd backend
python3 test_phase3_5.py
```

注意: 完整测试需要实际数据，可能需要较长时间。

## 验收清单

- [x] 后端可以正常启动
- [x] 前端可以正常启动
- [x] API文档可以访问
- [x] 智能选股功能正常
- [ ] 单股深度分析功能正常（需要有数据）
- [ ] 策略优化功能正常（需要有策略）
- [ ] 策略监控功能正常（需要有活跃策略）

## 下一步

系统已经完成开发和基础测试，建议：

1. **准备数据**: 运行数据同步，确保有足够的历史数据
2. **创建策略**: 通过智能选股创建几个测试策略
3. **功能测试**: 逐个测试Phase 3-5的新功能
4. **性能测试**: 测试大量数据下的系统性能
5. **用户测试**: 邀请实际用户试用并收集反馈

## 技术支持

如有问题，请参考：
- `PROJECT_DELIVERY_CONFIRMATION.md` - 项目交付确认
- `PROJECT_FINAL_SUMMARY.md` - 项目完整总结
- `PHASE3_5_IMPLEMENTATION_REPORT.md` - Phase 3-5实现报告
- API文档: http://localhost:8000/docs

---

**系统状态**: ✅ 已完成，可以使用  
**更新日期**: 2026-06-06
