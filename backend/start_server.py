# backend/start_server.py
import subprocess
import sys
import warnings

# uvicorn --reload 热重载退出时，Baostock/子进程偶发 semaphore 泄漏提示，可忽略
warnings.filterwarnings(
    "ignore",
    message="resource_tracker: There appear to be",
    category=UserWarning,
    module="multiprocessing.resource_tracker",
)


def start_server():
    print("🚀 启动股票分析系统后端服务...")
    print("服务地址: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    
    # 使用子进程启动uvicorn
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000"
    ])

if __name__ == "__main__":
    start_server()