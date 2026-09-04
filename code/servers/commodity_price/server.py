"""
Commodity Price MCP Server
提供商品价格查询和趋势分析功能
"""
import json
import logging
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .sources.mock_source import MockPriceSource

# 配置日志输出到stderr（避免污染stdout的JSON-RPC通信）
logging.basicConfig(
    level=logging.WARNING,
    format="[%(asctime)s] %(levelname)s %(message)s",
    stream=sys.stderr,
    force=True,
)

# 创建 MCP Server 实例
mcp = FastMCP("commodity-price-mcp", log_level="WARNING")

# 初始化价格数据源
price_source = MockPriceSource()


@mcp.tool()
async def get_price(commodity: str, date: str = "latest", source: str = "auto") -> str:
    """
    获取商品最新价格或历史价格

    Args:
        commodity: 商品名称，如 lithium_carbonate, copper, nickel 等
        date: 日期，'latest' 或 'YYYY-MM-DD' 格式
        source: 数据源：lme | smm | auto

    Returns:
        JSON 格式的价格数据
    """
    if not commodity:
        return json.dumps({"error": "commodity is required"}, ensure_ascii=False)

    result = price_source.get_price(commodity, date)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def get_trend(commodity: str, days: int = 30, source: str = "auto") -> str:
    """
    获取商品价格趋势（含历史数据点）

    Args:
        commodity: 商品名称
        days: 查询天数，默认30
        source: 数据源：lme | smm | auto

    Returns:
        JSON 格式的趋势数据
    """
    if not commodity:
        return json.dumps({"error": "commodity is required"}, ensure_ascii=False)

    result = price_source.get_trend(commodity, days)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def infer_commodities(target: str) -> str:
    """
    根据矿区/公司名称推断相关商品

    Args:
        target: 矿区/公司名称

    Returns:
        JSON 格式的相关商品列表
    """
    if not target:
        return json.dumps({"error": "target is required"}, ensure_ascii=False)

    commodities = MockPriceSource.infer_commodities(target)
    return json.dumps({
        "target": target,
        "commodities": commodities
    }, ensure_ascii=False)


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "sse":
        mcp.run(transport="sse", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8003")))
    else:
        mcp.run(transport="stdio")
