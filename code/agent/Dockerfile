FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY code/agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY code/agent ./code/agent

# 设置环境变量
ENV PYTHONPATH=/app

# 暴露端口（如果需要 HTTP 接口）
EXPOSE 8080

# 运行 Agent
CMD ["python", "-m", "code.agent.main"]
