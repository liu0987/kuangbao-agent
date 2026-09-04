"""
Google News RSS 数据源
优化：改进查询构建，添加备用方案
"""
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

import feedparser
import httpx

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"


class GoogleNewsSource:
    """Google News RSS 数据源"""

    def __init__(self):
        self.base_url = GOOGLE_NEWS_RSS_URL

    async def search(self, query: str, max_results: int = 10) -> list[dict]:
        """
        从 Google News RSS 搜索新闻

        Args:
            query: 搜索关键词
            max_results: 最大返回数量

        Returns:
            新闻列表
        """
        # 构建查询：只用英文关键词
        import re
        english_terms = re.findall(r'[a-zA-Z]+', query)
        if not english_terms:
            search_terms = ["mining", "mineral"]
        else:
            search_terms = english_terms[:2]

        search_query = " ".join(search_terms) + " mining resource"
        encoded_query = quote_plus(search_query)

        url = f"{self.base_url}?q={encoded_query}&hl=en&gl=US&ceid=US:en"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                response.raise_for_status()
                feed = feedparser.parse(response.text)

                items = []
                for entry in feed.entries[:max_results]:
                    items.append(self._normalize_item(entry))

                return items

            except Exception:
                return []

    def _normalize_item(self, entry: dict) -> dict:
        """标准化 Google News 条目格式"""
        # 解析发布时间
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6]).isoformat()
            except Exception:
                published = None

        # 提取实际来源
        source = "Google News"
        if hasattr(entry, "source") and hasattr(entry.source, "title"):
            source = entry.source.title

        # 提取摘要
        summary = entry.get("summary", "")
        if not summary:
            summary = entry.get("description", "")

        return {
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "source": source,
            "published": published,
            "snippet": summary[:500],
            "has_pdf_link": self._check_pdf_link(entry),
        }

    def _check_pdf_link(self, entry: dict) -> bool:
        """检查条目是否包含 PDF 链接"""
        content = entry.get("summary", "") + str(entry.get("content", ""))
        return ".pdf" in content.lower()
