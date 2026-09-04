FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（PyMuPDF 需要）
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装依赖
COPY code/servers/mineral_pdf/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 可选：安装 MinerU
# RUN pip install --no-cache-dir magic-pdf[full]

# 复制代码
COPY code/servers/mineral_pdf ./code/servers/mineral_pdf

# 设置环境变量
ENV MCP_TRANSPORT=sse
ENV MCP_PORT=8002
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 8002

# 运行服务
CMD ["python", "-m", "code.servers.mineral_pdf.server"]
