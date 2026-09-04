FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码（从项目根目录复制，需要在docker-compose中设置正确的context）
COPY code/servers/mining_news ./code/servers/mining_news

# 设置环境变量
ENV MCP_TRANSPORT=sse
ENV MCP_PORT=8001
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 8001

# 运行服务
CMD ["python", "-m", "code.servers.mining_news.server"]
