# 矿权日报 Agent — 快速启动指南

## 前置条件

- Python 3.11+
- OpenAI API Key（或 Anthropic API Key）

## 方式一：本地开发模式（推荐新手）

### 1. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 可选：安装 MinerU OCR（用于扫描件 PDF）
# pip install magic-pdf[full]
```

### 2. 配置环境变量

```bash
# 复制配置文件
cp .env.example .env

# 编辑 .env，填入你的 API Key
# 至少需要设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY
```

### 3. 运行 Agent

```bash
# 交互式运行
python -m code.agent.main

# 或指定查询
python -m code.agent.main "给我生成一份关于 Pilbara 锂矿的今日简报"

# 保存到指定文件
python -m code.agent.main "Pilbara 锂矿简报" -o report.md

# 查看帮助
python -m code.agent.main --help
```

### 4. 日志与调试

```bash
# 默认模式：显示进度和摘要
python -m code.agent.main "铜矿市场分析"

# 调试模式：显示详细日志（包括每次 MCP/LLM 调用）
python -m code.agent.main "铜矿市场分析" --log-level DEBUG

# 静默模式：只输出报告内容
python -m code.agent.main "铜矿市场分析" --quiet

# 指定日志文件
python -m code.agent.main "铜矿市场分析" --log-file my_agent.log
```

**日志输出位置：**
- 控制台：实时显示执行进度
- 文件：`logs/agent_YYYYMMDD.log`（默认，记录完整日志）

**执行摘要示例：**
```
╔══════════════════════════════════════════════════════════╗
║                      执行摘要                            ║
╠══════════════════════════════════════════════════════════╣
║  阶段执行情况:                                           ║
║    ✓ 提取目标            12.0s                        ║
║    ✓ 搜索新闻             7.4s                        ║
║    ✓ 提取PDF             1ms                        ║
║    ✓ 获取价格             3.9s                        ║
║    ✓ 生成报告            48.5s                        ║
╠══════════════════════════════════════════════════════════╣
║  新闻数据:   5 条                                        ║
║  PDF报告:   0/1   成功                                    ║
║  价格数据:   3 种                                        ║
║  LLM调用:    2 次                                       ║
║  MCP调用:   12 次                                       ║
║  总耗时:   72.3s                                       ║
╠══════════════════════════════════════════════════════════╣
║  报告已保存: reports/20260904_220156_铜矿市场分析.md        ║
╚══════════════════════════════════════════════════════════╝
```

## 方式二：Docker 模式（多镜像微服务）

适用于生产环境，每个服务独立部署和扩展。

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 2. 启动所有服务

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 3. 运行 Agent

```bash
# 在容器内运行
docker-compose exec agent python -m code.agent.main "Pilbara 锂矿简报"
```

## 方式三：Docker 模式（统一镜像）

适用于开发测试，简单易用，一个镜像包含所有服务。

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 2. 构建统一镜像

```bash
# 构建镜像
docker build -t kuangbao-agent .
```

### 3. 启动所有服务

```bash
# 使用简化版 compose 启动
docker-compose -f docker-compose.simple.yml up -d

# 查看日志
docker-compose -f docker-compose.simple.yml logs -f
```

### 4. 单独运行某个服务

```bash
# 运行新闻搜索服务
docker run -d --name news-mcp -p 8001:8001 -e SERVICE_TYPE=mining-news kuangbao-agent

# 运行 PDF 解析服务
docker run -d --name pdf-mcp -p 8002:8002 -e SERVICE_TYPE=mineral-pdf kuangbao-agent

# 运行价格查询服务
docker run -d --name price-mcp -p 8003:8003 -e SERVICE_TYPE=commodity-price kuangbao-agent

# 运行 Agent（交互式）
docker run -it --rm \
  -e SERVICE_TYPE=agent \
  -e MINING_NEWS_MCP_URL=http://host.docker.internal:8001 \
  -e MINERAL_PDF_MCP_URL=http://host.docker.internal:8002 \
  -e COMMODITY_PRICE_MCP_URL=http://host.docker.internal:8003 \
  --env-file .env \
  kuangbao-agent "Pilbara 锂矿简报"
```

### 5. 可用的 SERVICE_TYPE 值

| SERVICE_TYPE | 说明 | 端口 |
|--------------|------|------|
| `mining-news` | 新闻搜索 MCP 服务器 | 8001 |
| `mineral-pdf` | PDF 解析 MCP 服务器 | 8002 |
| `commodity-price` | 价格查询 MCP 服务器 | 8003 |
| `agent` | 主 Agent 客户端 | 8080 |

## 方式四：接入 Claude Desktop / Cursor

### 1. 复制配置文件

将 `mcp-config.json` 的内容复制到 Claude Desktop 配置目录：

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`

### 2. 重启 Claude Desktop

配置生效后，在 Claude Desktop 中直接使用：
- "搜索 Pilbara 锂矿的最新新闻"
- "帮我看看天齐锂业的股价走势"

## 测试 MCP Server

```bash
# 使用 MCP Inspector 测试
npx @modelcontextprotocol/inspector python -m code.servers.mining_news.server
npx @modelcontextprotocol/inspector python -m code.servers.commodity_price.server
npx @modelcontextprotocol/inspector python -m code.servers.mineral_pdf.server
```

## 常见问题

### Q: 首次运行很慢？
A: MinerU OCR 首次运行需要下载模型（约 1GB），请耐心等待。

### Q: 没有 GPU 可以用吗？
A: 可以。MinerU 会自动降级为 CPU 模式，只是 PDF 解析会较慢。

### Q: 如何切换 LLM 提供商？
A: 在 `.env` 中修改 `LLM_PROVIDER=openai` 或 `anthropic`。

### Q: 价格数据是真实的吗？
A: 当前使用模拟数据。接入真实 API 需要配置 `TRADING_ECONOMICS_API_KEY`。
