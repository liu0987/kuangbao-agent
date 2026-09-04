"""
GDELT 2.0 DOC API 数据源
优化：添加延迟避免限流，改进查询逻辑
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

GDELT_API_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"


class GDELTSource:
    """GDELT 2.0 DOC API 数据源"""

    def __init__(self):
        self.base_url = GDELT_API_BASE
        self._last_request_time = 0
        self._min_interval = 2.0  # 最小请求间隔（秒）

    async def search(self, query: str, max_results: int = 10) -> list[dict]:
        """
        从 GDELT 搜索新闻

        Args:
            query: 搜索关键词
            max_results: 最大返回数量

        Returns:
            新闻列表
        """
        # 避免请求过于频繁
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)

        # 构建查询：简化查询词，提高匹配率
        # 移除中文字符，只保留英文关键词
        import re
        english_terms = re.findall(r'[a-zA-Z]+', query)
        if not english_terms:
            # 如果没有英文词，使用默认矿业关键词
            search_terms = ["mining", "mineral", "resource"]
        else:
            search_terms = english_terms[:3]  # 最多3个词

        gdelt_query = " ".join(search_terms) + " mining"

        params = {
            "query": gdelt_query,
            "mode": "artlist",
            "maxrecords": min(max_results, 25),
            "format": "json",
            "sort": "DateDesc",
            "sourcelang": "english",
            "startdatetime": (datetime.now() - timedelta(days=30)).strftime("%Y%m%d%H%M%S"),
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.get(self.base_url, params=params)
                self._last_request_time = asyncio.get_event_loop().time()

                if response.status_code == 429:
                    # 被限流，返回空结果
                    return []

                response.raise_for_status()
                data = response.json()

                articles = data.get("articles", [])
                return [self._normalize_item(article) for article in articles]

            except Exception:
                return []

    def _normalize_item(self, article: dict) -> dict:
        """标准化 GDELT 文章格式"""
        # 解析发布时间
        published = None
        if "seendate" in article:
            try:
                date_str = article["seendate"]
                published = datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").isoformat()
            except Exception:
                published = article.get("seendate")

        return {
            "title": article.get("title", ""),
            "url": article.get("url", ""),
            "source": article.get("domain", "GDELT"),
            "published": published,
            "snippet": article.get("title", "")[:500],
            "has_pdf_link": article.get("url", "").lower().endswith(".pdf"),
        }
