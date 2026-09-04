"""
垂直媒体 RSS 数据源
优化：更新可用源，添加备用源，改进错误处理
"""
import asyncio
from datetime import datetime
from typing import Optional

import feedparser
import httpx

# 矿业垂直媒体 RSS 源配置（2026年验证可用的源）
MINING_RSS_FEEDS = [
    # 英文源
    {
        "name": "Northern Miner",
        "url": "https://www.northernminer.com/feed/",
        "language": "en",
        "priority": 1,
    },
    {
        "name": "Mining.com",
        "url": "https://www.mining.com/feed/",
        "language": "en",
        "priority": 1,
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    },
    {
        "name": "Mining Journal",
        "url": "https://www.mining-journal.com/rss/news",
        "language": "en",
        "priority": 2,
    },
    {
        "name": "Mining Magazine",
        "url": "https://www.miningmagazine.com/rss/news",
        "language": "en",
        "priority": 2,
    },
    {
        "name": "Resource World",
        "url": "https://resourceworld.com/feed/",
        "language": "en",
        "priority": 2,
    },
    {
        "name": "Mining Review",
        "url": "https://miningreview.com/feed/",
        "language": "en",
        "priority": 3,
    },
    # 中文源
    {
        "name": "上海有色网",
        "url": "https://news.smm.cn/rss/mining",
        "language": "zh",
        "priority": 2,
    },
]

# 通用新闻 RSS（作为兜底）
GENERAL_NEWS_FEEDS = [
    {
        "name": "Reuters Mining",
        "url": "https://www.reuters.com/markets/commodities/mining/rss",
        "language": "en",
        "priority": 3,
    },
]


class RSSFeedSource:
    """垂直媒体 RSS 数据源"""

    def __init__(self):
        self.feeds = MINING_RSS_FEEDS + GENERAL_NEWS_FEEDS
        # 按优先级排序
        self.feeds.sort(key=lambda x: x.get("priority", 99))

    async def search(self, query: str, max_results: int = 10) -> list[dict]:
        """
        从多个 RSS 源搜索新闻

        Args:
            query: 搜索关键词
            max_results: 最大返回数量

        Returns:
            新闻列表，按发布时间倒序
        """
        all_items = []
        tasks = [self._fetch_feed(feed) for feed in self.feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for feed_config, result in zip(self.feeds, results):
            if isinstance(result, Exception):
                continue  # 跳过失败的源
            if not result:
                continue
            for item in result:
                if self._matches_query(item, query):
                    all_items.append(self._normalize_item(item, feed_config["name"]))

        # 按发布时间倒序，去重
        all_items.sort(key=lambda x: x.get("published", ""), reverse=True)
        seen_urls = set()
        unique_items = []
        for item in all_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique_items.append(item)

        return unique_items[:max_results]

    async def _fetch_feed(self, feed_config: dict) -> list[dict]:
        """获取单个 RSS 源"""
        headers = feed_config.get("headers", {})
        headers.setdefault("User-Agent", "KuangBao-Agent/1.0 (Mining News Aggregator)")

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                response = await client.get(feed_config["url"], headers=headers)
                response.raise_for_status()
                feed = feedparser.parse(response.text)
                return feed.entries
            except Exception as e:
                # 静默失败，不影响其他源
                return []

    def _matches_query(self, item: dict, query: str) -> bool:
        """检查条目是否匹配查询关键词（改进匹配逻辑）"""
        query_terms = query.lower().split()
        title = item.get("title", "").lower()
        summary = item.get("summary", "").lower()
        content = title + " " + summary

        # 支持多词匹配（任意一个词匹配即可）
        return any(term in content for term in query_terms)

    def _normalize_item(self, item: dict, source_name: str) -> dict:
        """标准化 RSS 条目格式"""
        # 解析发布时间
        published = None
        if hasattr(item, "published_parsed") and item.published_parsed:
            try:
                published = datetime(*item.published_parsed[:6]).isoformat()
            except Exception:
                published = None

        # 提取内容摘要
        summary = item.get("summary", "")
        if not summary:
            summary = item.get("description", "")
        # 清理 HTML 标签
        summary = self._clean_html(summary)

        return {
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "source": source_name,
            "published": published,
            "snippet": summary[:500],
            "has_pdf_link": self._check_pdf_link(item),
        }

    def _clean_html(self, text: str) -> str:
        """简单清理 HTML 标签"""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)

    def _check_pdf_link(self, item: dict) -> bool:
        """检查条目是否包含 PDF 链接"""
        content = item.get("summary", "") + str(item.get("content", ""))
        return ".pdf" in content.lower()
