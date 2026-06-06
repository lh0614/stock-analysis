#!/bin/bash

# 智能选股与策略自进化系统 - 快速启动脚本

echo "=================================="
echo "智能选股与策略自进化系统"
echo "=================================="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装"
    exit 1
fi

echo "✓ Python3: $(python3 --version)"

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ 未找到 Node.js，请先安装"
    exit 1
fi

echo "✓ Node.js: $(node --version)"
echo ""

# 选择操作
echo "请选择操作:"
echo "1. 启动完整系统（后端 + 前端）"
echo "2. 仅启动后端"
echo "3. 仅启动前端"
echo "4. 运行端到端测试"
echo "5. 重新计算因子数据"
echo ""
read -p "请输入选项 (1-5): " choice

case $choice in
    1)
        echo ""
        echo "启动后端服务..."
        cd backend
        python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
        BACKEND_PID=$!

        echo "等待后端启动..."
        sleep 3

        echo ""
        echo "启动前端服务..."
        cd ../frontend
        npm run dev &
        FRONTEND_PID=$!

        echo ""
        echo "=================================="
        echo "✓ 系统启动成功！"
        echo "=================================="
        echo ""
        echo "访问地址："
        echo "  - 前端: http://localhost:5173"
        echo "  - 后端: http://localhost:8000"
        echo "  - API文档: http://localhost:8000/docs"
        echo ""
        echo "功能页面："
        echo "  - 智能选股: http://localhost:5173/intelligent-screener"
        echo "  - 策略库: http://localhost:5173/strategy-library"
        echo ""
        echo "按 Ctrl+C 停止服务"
        echo ""

        # 等待用户中断
        wait $BACKEND_PID $FRONTEND_PID
        ;;

    2)
        echo ""
        echo "启动后端服务..."
        cd backend
        python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
        ;;

    3)
        echo ""
        echo "启动前端服务..."
        cd frontend
        npm run dev
        ;;

    4)
        echo ""
        echo "运行端到端测试..."
        cd backend
        python3 test_e2e.py
        ;;

    5)
        echo ""
        echo "重新计算因子数据..."
        cd backend
        python3 -c "
from app.services.factors import recompute
print('开始计算因子...')
result = recompute()
print(f'✓ 因子计算完成')
print(f'  - 股票数: {result[\"symbols\"]}')
print(f'  - 因子行数: {result[\"rows\"]}')
"
        ;;

    *)
        echo "无效选项"
        exit 1
        ;;
esac
