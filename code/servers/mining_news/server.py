"""
Mining News MCP Server
提供矿业新闻搜索和文章提取功能
"""
import asyncio
import json
import logging
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .sources import GoogleNewsSource, GDELTSource, RSSFeedSource, RegulatoryReportSource
from .parsers import extract_article

# 配置日志输出到stderr（避免污染stdout的JSON-RPC通信）
logging.basicConfig(
    level=logging.WARNING,
    format="[%(asctime)s] %(levelname)s %(message)s",
    stream=sys.stderr,
    force=True,
)

# 创建 MCP Server 实例
mcp = FastMCP("mining-news-mcp", log_level="WARNING")

# 初始化数据源（按优先级排序）
rss_source = RSSFeedSource()
gdelt_source = GDELTSource()
google_source = GoogleNewsSource()
regulatory_source = RegulatoryReportSource()


@mcp.tool()
async def search(query: str, max_results: int = 10) -> str:
    """
    搜索矿业新闻，返回标题+摘要+URL+来源+发布时间

    Args:
        query: 搜索关键词，如公司名、矿区名、矿种等
        max_results: 最大返回数量，默认10

    Returns:
        JSON 格式的新闻列表
    """
    if not query:
        return json.dumps({"error": "query is required", "results": []}, ensure_ascii=False)

    # 按优先级尝试数据源
    results = []

    # 1. 优先使用垂直媒体 RSS
    try:
        rss_results = await rss_source.search(query, max_results)
        results.extend(rss_results)
    except Exception as e:
        print(f"RSS source failed: {e}", file=sys.stderr)

    # 2. 如果结果不足，补充 GDELT
    if len(results) < max_results:
        try:
            remaining = max_results - len(results)
            gdelt_results = await gdelt_source.search(query, remaining)
            results.extend(gdelt_results)
        except Exception as e:
            print(f"GDELT source failed: {e}", file=sys.stderr)

    # 3. 如果仍然不足，补充 Google News
    if len(results) < max_results:
        try:
            remaining = max_results - len(results)
            google_results = await google_source.search(query, remaining)
            results.extend(google_results)
        except Exception as e:
            print(f"Google News source failed: {e}", file=sys.stderr)

    # 去重（按 URL）
    seen_urls = set()
    unique_results = []
    for item in results:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            unique_results.append(item)

    return json.dumps({
        "query": query,
        "total": len(unique_results),
        "results": unique_results[:max_results]
    }, ensure_ascii=False, default=str)


@mcp.tool()
async def article(url: str) -> str:
    """
    提取文章全文，同时提取页面中的 PDF 链接

    Args:
        url: 文章URL

    Returns:
        JSON 格式的文章内容和 PDF 链接
    """
    if not url:
        return json.dumps({"error": "url is required"}, ensure_ascii=False)

    result = await extract_article(url)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def search_reports(
    company: str = "",
    project: str = "",
    report_type: str = "43-101",
    max_results: int = 5,
) -> str:
    """
    搜索矿业技术报告 PDF（从监管平台和公司官网）

    Args:
        company: 公司名称，如 "Pilbara Minerals", "Rio Tinto"
        project: 项目名称，如 "Pilgangoora", "Oyu Tolgoi"
        report_type: 报告类型，可选值:
            - "43-101" (NI 43-101 技术报告，加拿大标准)
            - "jorc" (JORC 报告，澳大利亚标准)
            - "feasibility" (可行性研究)
            - "pre-feasibility" (预可行性研究)
            - "resource" (资源量估算)
            - "annual" (年度报告)
        max_results: 最大返回数量，默认5

    Returns:
        JSON 格式的报告列表，包含标题、URL、来源、类型等信息
    """
    # 验证参数
    if not company and not project:
        return json.dumps(
            {"error": "company or project is required", "results": []},
            ensure_ascii=False,
        )

    # 验证报告类型
    valid_types = ["43-101", "jorc", "feasibility", "pre-feasibility", "resource", "annual"]
    if report_type not in valid_types:
        return json.dumps(
            {"error": f"Invalid report_type: {report_type}. Valid types: {valid_types}", "results": []},
            ensure_ascii=False,
        )

    # 搜索报告
    try:
        results = await regulatory_source.search(
            company=company,
            project=project,
            report_type=report_type,
            max_results=max_results,
        )

        return json.dumps(
            {
                "query": {
                    "company": company,
                    "project": project,
                    "report_type": report_type,
                },
                "total": len(results),
                "results": results,
            },
            ensure_ascii=False,
            default=str,
        )
    except Exception as e:
        return json.dumps(
            {"error": f"Search failed: {str(e)}", "results": []},
            ensure_ascii=False,
        )


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "sse":
        mcp.run(transport="sse", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8001")))
    else:
        mcp.run(transport="stdio")
