# 矿权日报 Agent — 完整可执行方案

## Context

基于 MCP (Model Context Protocol) 协议搭建一个"矿权日报 Agent"，包含 3 个 MCP Server + 1 个 LangGraph Agent Client，能够输入一句话（如"给我生成一份关于 Pilbara 锂矿的今日简报"）输出完整的 Markdown 简报(新闻摘要 + 储量数据 + 价格走势 + 风险提示) + 引用源链接。

**核心价值**：通过 MCP 协议实现工具标准化，可直接接入 Claude Desktop / Cursor 验证使用。

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Client (LangGraph)              │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐               │
│  │ Node:   │   │ Node:   │   │ Node:   │   Node:       │
│  │ Search  │──▶│ Extract │──▶│ Parse   │──▶ Generate    │
│  │ News    │   │ PDF URLs│   │ PDF     │   Report      │
│  └─────────┘   └─────────┘   └─────────┘               │
│       │                                                 │
│       ▼ (并行)                                          │
│  ┌─────────┐                                           │
│  │ Node:   │                                           │
│  │ Get     │                                           │
│  │ Price   │                                           │
│  └─────────┘                                           │
└──────┬──────────────┬──────────────┬────────────────────┘
       │ MCP 协议      │              │
       ▼              ▼              ▼
┌──────────┐  ┌──────────────┐  ┌─────────────────┐
│ mining-  │  │ mineral-pdf- │  │ commodity-      │
│ news-mcp │  │ mcp          │  │ price-mcp       │
│          │  │              │  │                 │
│ search() │  │ extract_     │  │ get_price()     │
│ article()│  │   resources()│  │ get_trend()     │
└──────────┘  └──────────────┘  └─────────────────┘
     │              │                    │
     ▼              ▼                    ▼
 Google News     PyMuPDF +          LME (Trading
 RSS + GDELT     MinerU OCR        Economics API)
 + 垂直RSS                          + SMM 上海有色网
```

---

## 二、目录结构

```
kuangbao-agent/
├── .venv/                       # Python 虚拟环境（本地开发用，不入 git）
├── .gitignore                   # 忽略 .venv/、__pycache__/ 等
├── docker-compose.yml
├── mcp-config.json              # Claude Desktop / Cursor 配置
├── RUN.md                       # 5 分钟快速启动指南
├── requirements.txt             # 全部依赖
  ├── .env.example
│
└── code/                        # 全部代码
    ├── servers/                 # 3 个 MCP Server
    │   ├── mining_news/
    │   │   ├── __init__.py
    │   │   ├── server.py            # MCP server 主入口
    │   │   ├── sources/
    │   │   │   ├── __init__.py
    │   │   │   ├── google_news.py   # Google News RSS
    │   │   │   ├── gdelt.py         # GDELT 2.0 DOC API
    │   │   │   └── rss_feeds.py     # 垂直媒体 RSS
    │   │   ├── parsers.py           # 文章全文提取
    │   │   └── Dockerfile
    │   │
    │   ├── mineral_pdf/
    │   │   ├── __init__.py
    │   │   ├── server.py            # MCP server 主入口（含 SSRF 防护）
    │   │   ├── pdf_parser.py        # PyMuPDF 解析
    │   │   ├── ocr_engine.py        # MinerU OCR
    │   │   ├── resource_extractor.py # 储量数据提取
    │   │   └── Dockerfile
    │   │
    │   └── commodity_price/
    │       ├── __init__.py
    │       ├── server.py            # MCP server 主入口
    │       ├── sources/
    │       │   ├── __init__.py
    │       │   ├── lme.py           # LME 基础金属价格
    │       │   └── smm.py           # SMM 锂盐价格
    │       └── Dockerfile
    │
    ├── agent/                   # LangGraph Agent Client
    │   ├── __init__.py
    │   ├── main.py              # 入口，接收用户输入
    │   ├── graph.py             # LangGraph 图定义
    │   ├── llm.py               # LLM 懒加载配置（@lru_cache）
    │   ├── nodes/
    │   │   ├── __init__.py
    │   │   ├── search_news.py       # 新闻搜索节点（并行抓取）
    │   │   ├── extract_pdfs.py      # PDF 链接提取节点
    │   │   ├── parse_pdfs.py        # PDF 解析节点
    │   │   ├── get_prices.py        # 价格查询节点
    │   │   └── generate_report.py   # 简报生成节点（含上下文截断）
    │   ├── state.py             # Agent 状态定义
    │   ├── prompts.py           # LLM 提示词
    │   └── mcp_client.py        # MCP 客户端封装（双传输 + 重试）
    │
    └── tests/
        ├── test_news_server.py
        ├── test_pdf_server.py
        └── test_price_server.py
```

---

## 三、接口定义（3 个 MCP Server）

### 3.1 mining-news-mcp

```python
# code/servers/mining_news/server.py
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("mining-news-mcp")

@server.tool()
async def search(query: str, max_results: int = 10) -> list[dict]:
    """
    搜索矿业新闻，返回标题+摘要+URL+来源+发布时间

    数据源优先级：
    1. 垂直媒体 RSS（Mining.com, Kitco, Mining Weekly, Northern Miner, SMM, 中国矿业报）
    2. GDELT 2.0 DOC API（entity/topic 过滤 mining/mineral）
    3. Google News RSS

    Returns:
        [{
            "title": "Pilbara Minerals Reports Updated Resource Estimate",
            "url": "https://...",
            "source": "Mining.com",
            "published": "2026-09-03",
            "snippet": "Pilbara Minerals announced...",
            "has_pdf_link": true  # 页面是否包含 PDF 链接
        }]
    """
    ...

@server.tool()
async def article(url: str) -> dict:
    """
    提取文章全文，同时提取页面中的 PDF 链接

    Returns:
        {
            "title": "...",
            "content": "全文文本...",
            "published": "2026-09-03",
            "author": "...",
            "pdf_links": [
                {"url": "https://...report.pdf", "text": "NI 43-101 Technical Report"}
            ]
        }
    """
    ...
```

### 3.2 mineral-pdf-mcp

```python
# code/servers/mineral_pdf/server.py
import ipaddress
from urllib.parse import urlparse
import httpx

server = Server("mineral-pdf-mcp")

# ── SSRF 防护 ─────────────────────────────────────────────
# 禁止访问的内网 IP 段
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # 云元数据服务
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

# 允许的 PDF 来源域名白名单（可选，为空则不限制）
ALLOWED_DOMAINS: list[str] = []

# PDF 下载大小限制（50MB）
MAX_PDF_SIZE = 50 * 1024 * 1024


def _validate_pdf_url(url: str) -> None:
    """校验 PDF URL，防止 SSRF 攻击"""
    parsed = urlparse(url)

    # 1. 只允许 http/https
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"不支持的 URL 协议: {parsed.scheme}")

    # 2. 域名白名单（如果配置了）
    if ALLOWED_DOMAINS and parsed.hostname not in ALLOWED_DOMAINS:
        raise ValueError(f"域名不在白名单中: {parsed.hostname}")

    # 3. 禁止内网 IP
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        for network in BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError(f"禁止访问内网地址: {ip}")
    except ValueError:
        # hostname 不是 IP，是域名，跳过 IP 检查
        pass

    # 4. 禁止常见云元数据域名
    blocked_hosts = ["169.254.169.254", "metadata.google.internal"]
    if parsed.hostname in blocked_hosts:
        raise ValueError(f"禁止访问云元数据服务: {parsed.hostname}")


@server.tool()
async def extract_resources(pdf_url: str) -> dict:
    """
    下载并解析 NI 43-101 / JORC 矿产资源报告 PDF

    安全限制：
    - 仅允许 http/https 协议
    - 禁止内网 IP 地址（10.x, 172.16-31.x, 192.168.x, 127.x, 169.254.x）
    - PDF 大小限制 50MB
    - 可配置域名白名单

    解析策略：
    1. PyMuPDF 提取文本 → 判断是否为扫描件
    2. 文本 PDF → 直接提取表格 + 正文
    3. 扫描件 → MinerU OCR → 结构化提取

    Returns:
        {
            "report_title": "Pilgangoora Lithium-Tantalum Project NI 43-101",
            "report_date": "2026-06-15",
            "qualified_person": "John Smith, P.Geo.",
            "mineral_resources": {
                "measured": {
                    "tonnes_mt": 68.3,
                    "grade_l2o_pct": 1.26,
                    "contained_l2o_kt": 860
                },
                "indicated": {
                    "tonnes_mt": 214.7,
                    "grade_l2o_pct": 1.14,
                    "contained_l2o_kt": 2447
                },
                "inferred": {
                    "tonnes_mt": 106.2,
                    "grade_l2o_pct": 1.02,
                    "contained_l2o_kt": 1083
                }
            },
            "cut_off_grade": "0.2% Li2O",
            "effective_date": "2026-06-15",
            "source_pages": [23, 24, 25],
            "parse_confidence": 0.85,  # 解析置信度
            "raw_text_snippet": "..."  # 原始文本片段供验证
        }
    """
    ...
```

### 3.3 commodity-price-mcp

```python
# code/servers/commodity_price/server.py
server = Server("commodity-price-mcp")

@server.tool()
async def get_price(commodity: str, date: str = "latest", source: str = "auto") -> dict:
    """
    获取商品价格

    commodity: "lithium_carbonate" | "lithium_hydroxide" | "copper" | "nickel" | ...
    date: "latest" | "2026-09-03"
    source: "lme" | "smm" | "auto"（根据 commodity 自动选源）

    Returns:
        {
            "commodity": "lithium_carbonate",
            "price": 98500,
            "currency": "CNY",
            "unit": "元/吨",
            "date": "2026-09-03",
            "source": "SMM",
            "change_pct": -1.2
        }
    """
    ...

@server.tool()
async def get_trend(commodity: str, days: int = 30, source: str = "auto") -> dict:
    """
    获取商品价格趋势

    Returns:
        {
            "commodity": "lithium_carbonate",
            "currency": "CNY",
            "unit": "元/吨",
            "source": "SMM",
            "period": "30d",
            "current": 98500,
            "high": 102000,
            "low": 95800,
            "avg": 98900,
            "change_pct": -2.1,
            "data_points": [
                {"date": "2026-08-05", "price": 100600},
                {"date": "2026-08-06", "price": 100200},
                ...
            ]
        }
    """
    ...
```

---

## 四、LangGraph Agent 编排

### 4.1 State 定义

```python
# code/agent/state.py
from typing import TypedDict, Optional
from dataclasses import dataclass

@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    snippet: str
    pdf_links: list[dict]

@dataclass
class MineralResource:
    report_title: str
    indicated: dict
    inferred: dict
    measured: dict
    parse_confidence: float

@dataclass
class PriceData:
    commodity: str
    price: float
    currency: str
    unit: str
    change_pct: float
    trend: dict

class AgentState(TypedDict):
    # 输入
    query: str                    # 用户查询
    target: str                   # 目标矿区/公司

    # 中间数据
    news: list[NewsItem]          # 新闻列表
    pdf_results: list[MineralResource]  # PDF 解析结果
    prices: list[PriceData]       # 价格数据

    # 输出
    report: str                   # 最终 Markdown 简报
    sources: list[str]            # 引用源列表
    warnings: list[str]           # ⚠️ 警告/缺失数据提示

    # 控制
    errors: list[str]             # 错误记录
```

### 4.2 Graph 定义

```python
# code/agent/graph.py
from langgraph.graph import StateGraph, END, START
from .state import AgentState
from .nodes.search_news import search_news_node
from .nodes.extract_pdfs import extract_pdfs_node
from .nodes.parse_pdfs import parse_pdfs_node
from .nodes.get_prices import get_prices_node
from .nodes.generate_report import generate_report_node

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("search_news", search_news_node)
    graph.add_node("extract_pdfs", extract_pdfs_node)
    graph.add_node("parse_pdfs", parse_pdfs_node)
    graph.add_node("get_prices", get_prices_node)
    graph.add_node("generate_report", generate_report_node)

    # 入口 → 搜索新闻
    graph.add_edge(START, "search_news")

    # search_news 完成后，fan-out 到两条并行路径：
    #   路径 A: extract_pdfs → parse_pdfs → generate_report
    #   路径 B: get_prices → generate_report
    # 使用 conditional_edges 返回目标节点列表实现并行
    graph.add_conditional_edges(
        "search_news",
        lambda state: ["extract_pdfs", "get_prices"],  # fan-out: 并行执行
    )

    # 路径 A: PDF 提取链
    graph.add_edge("extract_pdfs", "parse_pdfs")

    # 两条路径汇入 generate_report（LangGraph 自动等待 fan-in）
    graph.add_edge("parse_pdfs", "generate_report")
    graph.add_edge("get_prices", "generate_report")

    # 终点
    graph.add_edge("generate_report", END)

    return graph.compile()
```

**LangGraph fan-out/fan-in 说明**：
- `add_conditional_edges` 的路由函数返回 `list[str]`（节点名列表），LangGraph 自动并行执行这些节点
- 不需要显式使用 `Send` 类型——直接返回节点名称字符串列表即可
- `generate_report` 节点会自动等待 `parse_pdfs` 和 `get_prices` 都完成后才执行（fan-in）

### 4.3 MCP 客户端封装（双传输模式 + 重试）

```python
# code/agent/mcp_client.py
"""
MCP 客户端封装，支持两种传输模式：
- stdio：本地开发 / Claude Desktop，以子进程方式启动 server
- SSE：Docker 跨容器通信，通过 HTTP 调用 server

内置指数退避重试机制，处理网络抖动等瞬时故障
"""
import os
import asyncio
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)

# ── 重试配置 ──────────────────────────────────────────────
MAX_RETRIES = 3          # 最大重试次数
RETRY_BASE_DELAY = 1.0   # 基础延迟（秒）
RETRY_MAX_DELAY = 10.0   # 最大延迟（秒）
CALL_TIMEOUT = 60        # 单次调用超时（秒）


# ── 服务器配置 ────────────────────────────────────────────
MCP_SERVERS = {
    "mining-news-mcp": {
        "stdio": {"command": "python", "args": ["-m", "code.servers.mining_news.server"]},
        "sse_url": os.getenv("MINING_NEWS_MCP_URL", "http://localhost:8001"),
    },
    "mineral-pdf-mcp": {
        "stdio": {"command": "python", "args": ["-m", "code.servers.mineral_pdf.server"]},
        "sse_url": os.getenv("MINERAL_PDF_MCP_URL", "http://localhost:8002"),
    },
    "commodity-price-mcp": {
        "stdio": {"command": "python", "args": ["-m", "code.servers.commodity_price.server"]},
        "sse_url": os.getenv("COMMODITY_PRICE_MCP_URL", "http://localhost:8003"),
    },
}

# 传输模式：auto（自动检测）| stdio | sse
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "auto")


def _detect_transport() -> str:
    """自动检测传输模式：Docker 环境用 SSE，本地用 stdio"""
    if MCP_TRANSPORT != "auto":
        return MCP_TRANSPORT
    # 如果设置了 SSE URL 环境变量，说明在 Docker 环境
    if os.getenv("MINING_NEWS_MCP_URL"):
        return "sse"
    return "stdio"


async def call(server_name: str, tool_name: str, arguments: dict) -> dict:
    """
    调用 MCP server 的指定工具（带重试）

    重试策略：指数退避，最多重试 MAX_RETRIES 次
    可重试异常：网络超时、连接错误、服务暂时不可用
    不可重试：参数错误、资源不存在
    """
    last_exception = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            return await asyncio.wait_for(
                _call_once(server_name, tool_name, arguments),
                timeout=CALL_TIMEOUT,
            )
        except (TimeoutError, ConnectionError, OSError) as e:
            # 可重试的瞬时错误
            last_exception = e
            if attempt < MAX_RETRIES:
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                logger.warning(
                    f"MCP 调用失败 [{server_name}.{tool_name}] "
                    f"第 {attempt + 1}/{MAX_RETRIES} 次重试，等待 {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"MCP 调用最终失败 [{server_name}.{tool_name}] "
                    f"已重试 {MAX_RETRIES} 次: {e}"
                )
        except Exception as e:
            # 不可重试的错误（参数错误等），直接抛出
            raise

    raise last_exception


async def _call_once(server_name: str, tool_name: str, arguments: dict) -> dict:
    """单次 MCP 调用（无重试）"""
    config = MCP_SERVERS[server_name]
    transport = _detect_transport()

    if transport == "sse":
        # SSE 模式：通过 HTTP 调用远程 server
        async with sse_client(config["sse_url"]) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return _parse_result(result)
    else:
        # stdio 模式：以子进程方式启动 server
        params = StdioServerParameters(
            command=config["stdio"]["command"],
            args=config["stdio"]["args"],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return _parse_result(result)


def _parse_result(result) -> dict:
    """解析 MCP 工具调用结果"""
    if result.content and len(result.content) > 0:
        return result.content[0].text  # JSON string → dict 由调用方处理
    return {}
```

**传输模式说明**：
| 场景 | 传输模式 | 原因 |
|------|----------|------|
| Claude Desktop / Cursor | stdio | 客户端以子进程启动 server，同进程通信 |
| Docker 跨容器 | SSE | 不同容器间必须走网络 |
| 本地调试 Agent | stdio | Agent 和 server 在同一台机器，子进程启动 |

### 4.4 各节点实现要点

```python
# code/agent/nodes/search_news.py
import asyncio

async def search_news_node(state: AgentState) -> dict:
    """调用 mining-news-mcp 的 search + article 工具"""
    results = await mcp_client.call("mining-news-mcp", "search", {
        "query": state["target"] + " mining mineral resource",
        "max_results": 10
    })

    top_items = results[:5]

    # 并行抓取文章详情（原来是串行，5 篇需要 10-15 秒；并行后约 2-3 秒）
    async def fetch_article(item: dict) -> NewsItem:
        article = await mcp_client.call("mining-news-mcp", "article", {
            "url": item["url"]
        })
        return NewsItem(
            title=item["title"],
            url=item["url"],
            source=item["source"],
            snippet=item["snippet"],
            pdf_links=article.get("pdf_links", [])
        )

    # return_exceptions=True 单个失败不影响其他
    results = await asyncio.gather(
        *[fetch_article(item) for item in top_items],
        return_exceptions=True
    )

    news_items = []
    warnings = list(state.get("warnings", []))
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            warnings.append(f"⚠️ 文章抓取失败: {top_items[i]['url']} - {str(result)}")
        else:
            news_items.append(result)

    return {"news": news_items, "warnings": warnings}
```

```python
# code/agent/nodes/extract_pdfs.py
async def extract_pdfs_node(state: AgentState) -> dict:
    """从新闻中筛选含 PDF 链接的条目，调用 PDF 解析"""
    pdf_results = []
    warnings = list(state.get("warnings", []))  # 复制已有警告，避免覆盖

    for item in state["news"]:
        for pdf_link in item["pdf_links"]:
            if "43-101" in pdf_link.get("text", "").upper() or \
               "jorc" in pdf_link.get("text", "").upper() or \
               "resource" in pdf_link.get("text", "").upper():
                try:
                    result = await mcp_client.call(
                        "mineral-pdf-mcp", "extract_resources",
                        {"pdf_url": pdf_link["url"]}
                    )
                    if result["parse_confidence"] < 0.6:
                        warnings.append(
                            f"⚠️ {result['report_title']} 解析置信度低({result['parse_confidence']:.0%})，请核实原始报告"
                        )
                    pdf_results.append(result)
                except Exception as e:
                    warnings.append(f"⚠️ PDF 解析失败: {pdf_link['url']} - {str(e)}")

    if not pdf_results:
        warnings.append("⚠️ 未找到可解析的 NI 43-101 / JORC 技术报告")

    return {"pdf_results": pdf_results, "warnings": warnings}
```

```python
# code/agent/nodes/get_prices.py
async def get_prices_node(state: AgentState) -> dict:
    """查询相关商品价格和趋势（不修改 state，只返回 partial update）"""
    commodities = infer_commodities(state["target"])

    prices = []
    warnings = list(state.get("warnings", []))  # 复制已有警告

    for comm in commodities:
        try:
            price = await mcp_client.call(
                "commodity-price-mcp", "get_price",
                {"commodity": comm}
            )
            trend = await mcp_client.call(
                "commodity-price-mcp", "get_trend",
                {"commodity": comm, "days": 30}
            )
            prices.append(PriceData(
                commodity=comm,
                price=price["price"],
                currency=price["currency"],
                unit=price["unit"],
                change_pct=price["change_pct"],
                trend=trend
            ))
        except Exception as e:
            # ✅ 不修改 state，追加到本地列表，最后一起返回
            warnings.append(f"⚠️ {comm} 价格数据暂不可用: {str(e)}")

    return {"prices": prices, "warnings": warnings}
```

**LangGraph 状态更新规则**：
- ❌ 禁止：`state["key"] = value` 或 `state.setdefault(...).append(...)`
- ✅ 正确：`return {"key": new_value}` — 返回 partial dict，LangGraph 自动合并到 state
- 对于 list 类型字段，需先复制已有值再追加，避免丢失其他节点写入的数据

```python
# code/agent/nodes/generate_report.py
from ..llm import get_llm
from ..prompts import REPORT_PROMPT

# ── 上下文长度限制 ────────────────────────────────────────
MAX_NEWS_CONTENT_LEN = 2000    # 每篇新闻最大字符数
MAX_PDF_SNIPPET_LEN = 3000     # 每份 PDF 报告最大字符数
MAX_CONTEXT_CHARS = 30000      # 总上下文最大字符数（约 8K tokens）


def _truncate(text: str, max_len: int) -> str:
    """截断文本，保留首尾"""
    if len(text) <= max_len:
        return text
    half = max_len // 2
    return text[:half] + f"\n\n... [已截断，共 {len(text)} 字符] ...\n\n" + text[-half:]


def build_context(state: AgentState) -> str:
    """构建 LLM 上下文，控制总长度"""
    parts = []

    # 1. 新闻摘要（截断每篇）
    if state.get("news"):
        parts.append("## 新闻数据\n")
        for i, item in enumerate(state["news"], 1):
            content = _truncate(item.snippet, MAX_NEWS_CONTENT_LEN)
            parts.append(f"### [{i}] {item.title}\n来源: {item.source}\n{content}\n")

    # 2. PDF 解析结果（截断每份）
    if state.get("pdf_results"):
        parts.append("## 矿产资源报告\n")
        for i, pdf in enumerate(state["pdf_results"], 1):
            snippet = _truncate(pdf.get("raw_text_snippet", ""), MAX_PDF_SNIPPET_LEN)
            parts.append(f"### [{i}] {pdf['report_title']}\n{snippet}\n")

    # 3. 价格数据（通常较短，不截断）
    if state.get("prices"):
        parts.append("## 价格数据\n")
        for p in state["prices"]:
            parts.append(f"- {p.commodity}: {p.price} {p.currency}/{p.unit} ({p.change_pct:+.1f}%)\n")

    # 4. 已有警告
    if state.get("warnings"):
        parts.append("## 数据警告\n")
        for w in state["warnings"]:
            parts.append(f"- {w}\n")

    context = "\n".join(parts)

    # 总长度兜底截断
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + f"\n\n... [总上下文已截断，共 {len(context)} 字符] ..."

    return context


async def generate_report_node(state: AgentState) -> dict:
    """LLM 生成最终简报（带上下文长度控制）"""
    context = build_context(state)
    llm = get_llm()

    report = await llm.ainvoke([
        SystemMessage(content=REPORT_PROMPT),
        HumanMessage(content=context)
    ])

    sources = collect_sources(state)

    return {"report": report.content, "sources": sources}
```

### 4.4 LLM 配置模块

```python
# code/agent/llm.py
"""
LLM 配置与实例化模块（懒加载）
支持 OpenAI / Anthropic / 其他兼容 API，通过环境变量切换

使用懒加载避免 import 时因环境变量未配置而报错
"""
import os
from functools import lru_cache
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic


@lru_cache(maxsize=1)
def get_llm():
    """
    懒加载 LLM 实例（首次调用时创建，之后复用缓存）
    使用 @lru_cache 确保全局单例，且线程安全
    """
    provider = os.getenv("LLM_PROVIDER", "openai")
    model = os.getenv("LLM_MODEL")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    if provider == "anthropic":
        return ChatAnthropic(
            model=model or "claude-sonnet-4-20250514",
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:  # openai (默认)
        return ChatOpenAI(
            model=model or "gpt-4o",
            temperature=temperature,
            max_tokens=max_tokens,
        )


# 向后兼容的属性式访问（from ..llm import llm）
class _LLMProxy:
    """代理对象，延迟初始化实际 LLM"""
    def __getattr__(self, name: str):
        return getattr(get_llm(), name)

llm = _LLMProxy()
```

**使用方式**：
```bash
# .env 中配置
LLM_PROVIDER=openai        # 或 anthropic
LLM_MODEL=gpt-4o           # 或 claude-sonnet-4-20250514
LLM_TEMPERATURE=0
LLM_MAX_TOKENS=4096
```

```python
# 任意节点中导入（两种方式均可）
from ..llm import llm           # 属性式访问（向后兼容）
from ..llm import get_llm       # 直接获取实例
```

---

## 五、简报模板与提示词

```python
# code/agent/prompts.py
REPORT_PROMPT = """你是一位矿业分析师，负责撰写矿权日报简报。

请根据以下数据生成一份结构化的 Markdown 简报，格式如下：

# {矿区/公司} 矿权日报 — {日期}

## 📰 新闻摘要
- 每条新闻一行摘要（2-3 句话）
- 标注来源和时间
- 最多 5 条

## ⛏️ 资源储量数据
- 表格形式展示 Measured / Indicated / Inferred
- 标注报告来源、生效日期、合格人员
- 如果解析置信度 < 80%，加 ⚠️ 警告

## 📈 价格走势
- 当前价格 + 30 日涨跌幅
- 价格趋势描述（上涨/下跌/震荡）
- 数据来源

## ⚠️ 风险提示
- 基于以上数据，列出 2-3 个关键风险点
- 如有数据缺失，明确标注

## 📋 引用源
- 按 [序号] 格式列出所有引用的新闻链接、报告名称、数据源

重要规则：
1. 所有数据必须来自提供的上下文，不得编造
2. 如果某板块无数据，写"⚠️ 未找到相关数据"并说明原因
3. 数字必须与原始数据一致，不得四舍五入或估算
"""
```

---

## 六、技术选型确认

| 组件 | 选型 | 理由 |
|------|------|------|
| MCP SDK | `mcp` (Python) | 官方 Python SDK，stdio 模式兼容 Claude Desktop |
| Agent 框架 | LangGraph | 状态图 + 并行节点 + 条件路由 |
| LLM | OpenAI GPT-4o / Claude | 简报生成，通过 `code/agent/llm.py` 统一配置，环境变量切换 |
| PDF 解析 | PyMuPDF (fitz) | 轻量、快速、支持文本 PDF |
| OCR | MinerU | 中文友好、表格识别强、开源 |
| 新闻爬取 | `feedparser` + `httpx` | RSS 解析 + 异步 HTTP |
| 价格数据 | Trading Economics + SMM | LME 金属 + 锂盐 |
| 部署 | Docker Compose | 一键启动所有服务 |

---

## 七、Fallback 策略（绝不编造数据）

```
场景                          处理方式
─────────────────────────────────────────────────
新闻搜索无结果               → 简报标注 "⚠️ 未找到相关新闻"
PDF 链接不存在               → 跳过，标注 "⚠️ 未找到技术报告"
PDF 解析失败                 → 标注 "⚠️ PDF 无法解析" + 附原始链接
PDF 解析置信度 < 80%         → 标注 ⚠️ 警告 + 建议用户核实
价格 API 超时/报错           → 标注 "⚠️ 价格数据暂不可用"
所有数据源都挂了             → 生成最小简报 + 说明原因 + 建议稍后重试
```

---

## 八、Docker Compose

```yaml
# docker-compose.yml
version: "3.8"

services:
  # ── MCP Servers（SSE 模式，跨容器通信）──────────────────
  mining-news-mcp:
    build: ./code/servers/mining_news
    ports:
      - "8001:8001"
    restart: unless-stopped
    environment:
      - MCP_TRANSPORT=sse
      - MCP_PORT=8001

  mineral-pdf-mcp:
    build: ./code/servers/mineral_pdf
    ports:
      - "8002:8002"
    volumes:
      - mineru_models:/root/.cache/mineru
    environment:
      - MCP_TRANSPORT=sse
      - MCP_PORT=8002
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]  # 可选，无 GPU 自动降级为 CPU

  commodity-price-mcp:
    build: ./code/servers/commodity_price
    ports:
      - "8003:8003"
    restart: unless-stopped
    environment:
      - MCP_TRANSPORT=sse
      - MCP_PORT=8003

  # ── Agent Client ──────────────────────────────────────
  agent:
    build: ./code/agent
    depends_on:
      - mining-news-mcp
      - mineral-pdf-mcp
      - commodity-price-mcp
    env_file:
      - .env
    environment:
      - MINING_NEWS_MCP_URL=http://mining-news-mcp:8001
      - MINERAL_PDF_MCP_URL=http://mineral-pdf-mcp:8002
      - COMMODITY_PRICE_MCP_URL=http://commodity-price-mcp:8003
    ports:
      - "8080:8080"

volumes:
  mineru_models:
```

**传输模式说明**：
- **Docker 模式**：MCP Server 使用 SSE（Server-Sent Events）传输，暴露 HTTP 端口，Agent 通过 HTTP 跨容器调用
- **本地 stdio 模式**：Claude Desktop / Cursor 直接以子进程方式启动 server，使用 stdio 传输（见 mcp-config.json）
- Server 代码需同时支持两种模式，通过 `MCP_TRANSPORT` 环境变量切换

---

## 九、mcp-config.json（Claude Desktop 直接用）

```json
{
  "mcpServers": {
    "mining-news": {
      "command": "python",
      "args": ["-m", "code.servers.mining_news.server"],
      "env": {}
    },
    "mineral-pdf": {
      "command": "python",
      "args": ["-m", "code.servers.mineral_pdf.server"],
      "env": {}
    },
    "commodity-price": {
      "command": "python",
      "args": ["-m", "code.servers.commodity_price.server"],
      "env": {
        "TRADING_ECONOMICS_API_KEY": "${TRADING_ECONOMICS_API_KEY}"
      }
    }
  }
}
```

### 9.1 环境变量配置 (.env.example)

```bash
# .env.example

# ── LLM 配置 ──────────────────────────────────────────────
LLM_PROVIDER=openai              # openai | anthropic
LLM_MODEL=gpt-4o                 # gpt-4o | claude-sonnet-4-20250514
LLM_TEMPERATURE=0
LLM_MAX_TOKENS=4096
OPENAI_API_KEY=sk-xxx            # OpenAI API Key（使用 OpenAI 时必填）
ANTHROPIC_API_KEY=sk-ant-xxx     # Anthropic API Key（使用 Anthropic 时必填）

# ── 价格数据源 ────────────────────────────────────────────
# Trading Economics: https://tradingeconomics.com/api
#   - 免费版：100 次/月，适合测试
#   - 付费版：$50/月起，适合生产环境
TRADING_ECONOMICS_API_KEY=xxx

# SMM 上海有色网: 无官方 API，通过爬虫获取
#   - 需遵守 robots.txt，建议请求间隔 >= 5 秒
#   - 可能被反爬封禁，建议作为备用数据源
SMM_ENABLED=true

# ── MCP Server 端口（Docker 模式） ────────────────────────
MINING_NEWS_MCP_PORT=8001
MINERAL_PDF_MCP_PORT=8002
COMMODITY_PRICE_MCP_PORT=8003

# ── 重试配置（可选，有默认值） ────────────────────────────
# MCP_MAX_RETRIES=3              # MCP 调用最大重试次数
# MCP_RETRY_BASE_DELAY=1.0      # 重试基础延迟（秒）
# MCP_CALL_TIMEOUT=60            # 单次调用超时（秒）
```

### 9.2 .gitignore

```gitignore
# 虚拟环境
.venv/
__pycache__/
*.pyc

# 环境变量
.env

# IDE
.vscode/
.idea/

# MinerU 模型缓存
.mineru_cache/
```

---

## 十、交付清单与执行顺序

### Phase 1：MCP Servers（先独立跑通每个 server）
1. `code/servers/mining_news/server.py` — 实现 search + article 工具
2. `code/servers/commodity_price/server.py` — 实现 get_price + get_trend 工具
3. `code/servers/mineral_pdf/server.py` — 实现 extract_resources 工具

### Phase 2：Agent 编排
4. `code/agent/state.py` — 状态定义
5. `code/agent/llm.py` — LLM 配置与实例化（独立模块）
6. `code/agent/mcp_client.py` — MCP 客户端封装
7. `code/agent/nodes/*.py` — 各节点实现
8. `code/agent/graph.py` — LangGraph 图
9. `code/agent/prompts.py` — 提示词
10. `code/agent/main.py` — 入口

### Phase 3：集成与部署
11. `docker-compose.yml` + 各 server 的 Dockerfile
12. `mcp-config.json`
13. `requirements.txt`
14. `.gitignore`
15. `RUN.md`
16. 测试用例

### 验证方式
```bash
# 0. 创建虚拟环境并安装依赖（本地开发模式）
python -m venv .venv
# Windows 激活：
.venv\Scripts\activate
# Linux/Mac 激活：
# source .venv/bin/activate
pip install -r requirements.txt

# 1. 启动服务（Docker 模式）
docker-compose up -d

# 2. Agent 端测试（本地模式，需先激活 .venv）
python -m code.agent.main "给我生成一份关于 Pilbara 锂矿的今日简报"

# 3. Claude Desktop 测试
# 将 mcp-config.json 复制到 Claude Desktop 配置目录
# 在 Claude Desktop 中直接问："搜索 Pilbara 锂矿的最新新闻"

# 4. MCP Inspector 测试（开发调试）
npx @modelcontextprotocol/inspector python -m code.servers.mining_news.server
```

---

## 十一、耗时预估

| 阶段 | 预估耗时 |
|------|----------|
| Docker Compose 首次拉镜像 + 模型下载 | 5-10 分钟 |
| 用户输入 → 简报输出（首次） | 1-2 分钟 |
| 后续运行（模型已缓存） | 30-60 秒 |

RUN.md 中需明确说明首次运行的额外等待时间。

---

## 十二、关键风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Google News RSS 被限流 | 新闻搜索失败 | GDELT + 垂直 RSS 兜底 |
| MinerU 首次下载模型慢 | 首次启动慢 | Docker 预置模型 or 预下载脚本 |
| NI 43-101 格式千差万别 | PDF 解析准确率低 | 置信度标注 + 原始文本片段供人工核实 |
| LME/Trading Economics 限流 | 价格查询失败 | 缓存 + SMM 兜底 |
| 无 GPU 环境 MinerU 太慢 | PDF 解析超时 | Docker 配置可选 GPU，CPU 模式设合理超时 |
