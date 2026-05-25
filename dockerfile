# 使用官方 Python 3.11 镜像作为基础
FROM python:3.11-slim

# 设置环境变量，防止 Python 输出缓存到控制台
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 设置工作目录
WORKDIR /app

# 复制依赖清单
COPY requirements.txt .

# 使用 pip3 安装依赖（这是关键）
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# 复制当前目录下的所有文件到容器的 /app 目录
COPY . .

# 暴露端口（假设你的 FastAPI/Flask 跑在 8000 端口）
EXPOSE 8000

# 启动命令（根据你的项目调整，例如 uvicorn 或 flask run）
# 这里以 FastAPI 为例
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]