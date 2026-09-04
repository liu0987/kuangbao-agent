FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制全部代码
COPY code/ ./code/

# 设置环境变量
ENV PYTHONPATH=/app
ENV MCP_TRANSPORT=sse

# 默认运行 Agent（可通过环境变量覆盖）
ENV SERVICE_TYPE=agent

# 暴露端口
EXPOSE 8001 8002 8003 8080

# 健康检查脚本
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:${MCP_PORT:-8080}/health').raise_for_status()" || exit 1

# 启动脚本
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
