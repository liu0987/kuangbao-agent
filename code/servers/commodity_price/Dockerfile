FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY code/servers/commodity_price/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY code/servers/commodity_price ./code/servers/commodity_price

# 设置环境变量
ENV MCP_TRANSPORT=sse
ENV MCP_PORT=8003
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 8003

# 运行服务
CMD ["python", "-m", "code.servers.commodity_price.server"]
