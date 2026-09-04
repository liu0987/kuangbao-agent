"""
监管平台矿业报告搜索源
通过DuckDuckGo搜索间接访问 SEDAR、EDGAR、ASX 等监管平台的报告
"""
import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urljoin, quote_plus, unquote

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# 报告类型关键词映射
REPORT_TYPE_KEYWORDS = {
    "43-101": ["43-101", "technical report", "ni 43-101"],
    "jorc": ["jorc", "jorc code", "ore reserve"],
    "feasibility": ["feasibility study", "fs", "definitive feasibility"],
    "pre-feasibility": ["pre-feasibility", "pfs", "preliminary feasibility"],
    "resource": ["mineral resource", "resource estimate", "m&i", "measured indicated"],
    "annual": ["annual report", "yearly report"],
}


class RegulatoryReportSource:
    """监管平台矿业报告搜索源"""

    def __init__(self):
        self.timeout = 30.0
        # 缓存已访问的URL，避免重复请求
        self._visited_urls: set[str] = set()

    async def search(
        self,
        company: str = "",
        project: str = "",
        report_type: str = "43-101",
        max_results: int = 5,
    ) -> list[dict]:
        """
        搜索矿业技术报告

        Args:
            company: 公司名称
            project: 项目名称
            report_type: 报告类型
            max_results: 最大返回数量

        Returns:
            报告列表
        """
        results = []
        tasks = []

        # 构建搜索查询
        query_parts = []
        if company:
            query_parts.append(company)
        if project:
            query_parts.append(project)

        # 获取报告类型关键词
        report_keywords = REPORT_TYPE_KEYWORDS.get(report_type, [report_type])

        # 并行搜索多个查询
        for keyword in report_keywords[:2]:  # 取前两个关键词
            query = " ".join(query_parts) + f" {keyword}"
            tasks.append(self._search_duckduckgo(query))

        # 等待所有任务完成
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in task_results:
            if isinstance(result, list):
                results.extend(result)
            elif isinstance(result, Exception):
                logger.debug(f"Search task failed: {result}")

        # 去重
        seen_urls = set()
        unique_results = []
        for item in results:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(item)

        return unique_results[:max_results]

    async def _search_duckduckgo(self, query: str) -> list[dict]:
        """通过DuckDuckGo搜索报告"""
        results = []

        # 使用DuckDuckGo HTML版本
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        async with httpx.AsyncClient(
            timeout=self.timeout, follow_redirects=True, headers=HEADERS
        ) as client:
            try:
                response = await client.get(search_url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")

                # 解析DuckDuckGo搜索结果
                for result_div in soup.find_all("div", class_="result"):
                    link = result_div.find("a", class_="result__a")
                    if not link:
                        continue

                    title = link.get_text(strip=True)
                    href = link.get("href", "")

                    # 获取摘要
                    snippet_elem = result_div.find("a", class_="result__snippet")
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                    # 规范化URL（处理DuckDuckGo重定向）
                    full_url = self._normalize_ddg_url(href)
                    if not full_url or full_url in self._visited_urls:
                        continue

                    # 检查是否为报告链接
                    if self._is_report_link(full_url, title, snippet):
                        self._visited_urls.add(full_url)

                        # 确定来源
                        source = self._determine_source(full_url)

                        results.append({
                            "title": title,
                            "url": full_url,
                            "source": source,
                            "snippet": snippet[:200] if snippet else "",
                            "type": self._detect_report_type(title, snippet),
                        })

            except Exception as e:
                logger.debug(f"DuckDuckGo search failed: {e}")

        return results

    def _is_report_link(self, href: str, text: str, snippet: str) -> bool:
        """判断是否为报告链接"""
        href_lower = href.lower()
        text_lower = (text + " " + snippet).lower()

        # PDF链接
        if href_lower.endswith(".pdf"):
            return True

        # 包含报告关键词的链接
        report_keywords = [
            "report", "technical", "43-101", "jorc", "feasibility",
            "pre-feasibility", "pfs", "fs", "mineral resource",
            "ore reserve", "annual report"
        ]
        if any(kw in href_lower or kw in text_lower for kw in report_keywords):
            return True

        # 监管平台文档链接
        doc_paths = ["/documents/", "/reports/", "/filings/", "/edgar/", "/Archives/"]
        if any(path in href_lower for path in doc_paths):
            return True

        return False

    def _determine_source(self, url: str) -> str:
        """根据URL确定来源"""
        url_lower = url.lower()

        if "sedar" in url_lower:
            return "SEDAR (加拿大)"
        elif "sec.gov" in url_lower or "edgar" in url_lower:
            return "EDGAR (美国)"
        elif "asx.com.au" in url_lower:
            return "ASX (澳大利亚)"
        elif "mining.com" in url_lower:
            return "Mining.com"
        elif "northernminer" in url_lower:
            return "Northern Miner"
        elif "miningjournal" in url_lower:
            return "Mining Journal"
        elif "minedocs" in url_lower:
            return "MineDocs"
        elif "docslib" in url_lower:
            return "DocsLib"
        else:
            return "Web"

    def _detect_report_type(self, title: str, snippet: str) -> str:
        """检测报告类型"""
        text = (title + " " + snippet).lower()

        for report_type, keywords in REPORT_TYPE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return report_type

        return "report"

    def _normalize_ddg_url(self, url: str) -> Optional[str]:
        """规范化DuckDuckGo重定向URL"""
        if not url:
            return None

        # 处理DuckDuckGo重定向
        if "duckduckgo.com/l/" in url:
            # 提取实际URL
            match = re.search(r'uddg=([^&]+)', url)
            if match:
                url = unquote(match.group(1))

        # 确保是完整的URL
        if url.startswith("http"):
            return url

        return None
