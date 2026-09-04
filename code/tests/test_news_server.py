"""
Mining News MCP Server 测试
使用 pytest + pytest-asyncio

注意：由于项目目录 'code' 与 Python 标准库模块 'code' 冲突，
需要使用 sys.path 来正确导入模块
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
import pytest_asyncio

from code.servers.mining_news.sources.rss_feeds import RSSFeedSource
from code.servers.mining_news.sources.gdelt import GDELTSource
from code.servers.mining_news.sources.google_news import GoogleNewsSource
from code.servers.mining_news.sources.regulatory_reports import RegulatoryReportSource


@pytest.mark.asyncio
async def test_rss_search():
    """测试 RSS 搜索"""
    source = RSSFeedSource()
    results = await source.search("lithium mining", max_results=5)

    assert isinstance(results, list)
    assert len(results) <= 5
    if results:
        assert "title" in results[0]
        assert "url" in results[0]
        assert "source" in results[0]


@pytest.mark.asyncio
async def test_gdelt_search():
    """测试 GDELT 搜索"""
    source = GDELTSource()
    results = await source.search("Pilbara lithium", max_results=5)

    assert isinstance(results, list)
    assert len(results) <= 5
    if results:
        assert "title" in results[0]
        assert "url" in results[0]


@pytest.mark.asyncio
async def test_google_search():
    """测试 Google News 搜索"""
    source = GoogleNewsSource()
    results = await source.search("mining resource", max_results=5)

    assert isinstance(results, list)
    assert len(results) <= 5
    if results:
        assert "title" in results[0]
        assert "url" in results[0]


@pytest.mark.asyncio
async def test_regulatory_search():
    """测试监管平台报告搜索"""
    source = RegulatoryReportSource()
    results = await source.search(
        company="Pilbara Minerals",
        report_type="43-101",
        max_results=3,
    )

    assert isinstance(results, list)
    assert len(results) <= 3
    if results:
        assert "title" in results[0]
        assert "url" in results[0]
        assert "source" in results[0]


@pytest.mark.asyncio
async def test_search_empty_query():
    """测试空查询处理"""
    source = RSSFeedSource()
    results = await source.search("", max_results=5)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_search_no_results():
    """测试无结果查询"""
    source = RSSFeedSource()
    results = await source.search("xyzabc123nonexistent", max_results=5)
    assert isinstance(results, list)
    assert len(results) == 0
