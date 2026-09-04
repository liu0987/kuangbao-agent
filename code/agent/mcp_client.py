"""
MCP 客户端封装，支持两种传输模式：
- stdio：本地开发 / Claude Desktop，以子进程方式启动 server
- SSE：Docker 跨容器通信，通过 HTTP 调用 server

内置指数退避重试机制，处理网络抖动等瞬时故障
"""
import asyncio
import json
import logging
import os
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)

# ── 重试配置 ──────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 10.0
CALL_TIMEOUT = 60

# 使用当前 Python 解释器路径，确保子进程使用相同的虚拟环境
PYTHON_EXECUTABLE = sys.executable


# ── 服务器配置 ────────────────────────────────────────────
MCP_SERVERS = {
    "mining-news-mcp": {
        "stdio": {"command": PYTHON_EXECUTABLE, "args": ["-m", "code.servers.mining_news.server"]},
        "sse_url": os.getenv("MINING_NEWS_MCP_URL", "http://localhost:8001"),
    },
    "mineral-pdf-mcp": {
        "stdio": {"command": PYTHON_EXECUTABLE, "args": ["-m", "code.servers.mineral_pdf.server"]},
        "sse_url": os.getenv("MINERAL_PDF_MCP_URL", "http://localhost:8002"),
    },
    "commodity-price-mcp": {
        "stdio": {"command": PYTHON_EXECUTABLE, "args": ["-m", "code.servers.commodity_price.server"]},
        "sse_url": os.getenv("COMMODITY_PRICE_MCP_URL", "http://localhost:8003"),
    },
}

# 传输模式：auto（自动检测）| stdio | sse
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "auto")


def _detect_transport() -> str:
    """自动检测传输模式：Docker 环境用 SSE，本地用 stdio"""
    if MCP_TRANSPORT != "auto":
        return MCP_TRANSPORT
    if os.getenv("MINING_NEWS_MCP_URL"):
        return "sse"
    return "stdio"


async def call(server_name: str, tool_name: str, arguments: dict) -> Any:
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
            # 不可重试的错误，直接抛出
            raise

    raise last_exception


async def _call_once(server_name: str, tool_name: str, arguments: dict) -> Any:
    """单次 MCP 调用（无重试）"""
    config = MCP_SERVERS[server_name]
    transport = _detect_transport()

    if transport == "sse":
        async with sse_client(config["sse_url"]) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return _parse_result(result)
    else:
        params = StdioServerParameters(
            command=config["stdio"]["command"],
            args=config["stdio"]["args"],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return _parse_result(result)


def _parse_result(result) -> Any:
    """解析 MCP 工具调用结果"""
    if result.content and len(result.content) > 0:
        text = result.content[0].text
        # 尝试解析 JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return {}
