"""
文章全文提取和 PDF 链接解析
"""
import re
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


async def extract_article(url: str) -> dict:
    """
    提取文章全文和 PDF 链接

    Args:
        url: 文章 URL

    Returns:
        {
            "title": "文章标题",
            "content": "全文文本",
            "published": "发布时间",
            "author": "作者",
            "pdf_links": [{"url": "...", "text": "..."}]
        }
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            response.raise_for_status()
        except Exception as e:
            return {
                "title": "",
                "content": "",
                "published": None,
                "author": None,
                "pdf_links": [],
                "error": str(e),
            }

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # 提取标题
    title = _extract_title(soup)

    # 提取正文
    content = _extract_content(soup)

    # 提取发布时间
    published = _extract_published(soup)

    # 提取作者
    author = _extract_author(soup)

    # 提取 PDF 链接
    pdf_links = _extract_pdf_links(soup, url)

    return {
        "title": title,
        "content": content[:5000],  # 限制长度
        "published": published,
        "author": author,
        "pdf_links": pdf_links,
    }


def _extract_title(soup: BeautifulSoup) -> str:
    """提取文章标题"""
    # 尝试多种选择器
    selectors = [
        "h1",
        "article h1",
        ".article-title",
        ".post-title",
        "meta[property='og:title']",
    ]

    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            if element.name == "meta":
                return element.get("content", "")
            return element.get_text(strip=True)

    return soup.title.string if soup.title else ""


def _extract_content(soup: BeautifulSoup) -> str:
    """提取文章正文"""
    # 移除无关元素
    for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    # 尝试多种选择器
    selectors = [
        "article",
        ".article-content",
        ".post-content",
        ".entry-content",
        "main",
        "#content",
    ]

    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            return element.get_text(separator="\n", strip=True)

    # 兜底：返回 body 文本
    return soup.body.get_text(separator="\n", strip=True)[:3000] if soup.body else ""


def _extract_published(soup: BeautifulSoup) -> Optional[str]:
    """提取发布时间"""
    # 尝试 meta 标签
    meta_selectors = [
        "meta[property='article:published_time']",
        "meta[name='pubdate']",
        "meta[name='date']",
        "time[datetime]",
    ]

    for selector in meta_selectors:
        element = soup.select_one(selector)
        if element:
            if element.name == "meta":
                return element.get("content")
            return element.get("datetime")

    return None


def _extract_author(soup: BeautifulSoup) -> Optional[str]:
    """提取作者"""
    meta_selectors = [
        "meta[name='author']",
        "meta[property='article:author']",
        ".author",
        ".byline",
    ]

    for selector in meta_selectors:
        element = soup.select_one(selector)
        if element:
            if element.name == "meta":
                return element.get("content")
            return element.get_text(strip=True)

    return None


def _extract_pdf_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """提取页面中的 PDF 链接"""
    pdf_links = []

    # 查找所有链接
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(strip=True)

        # 检查是否为 PDF 链接
        if _is_pdf_link(href, text):
            full_url = urljoin(base_url, href)
            pdf_links.append({
                "url": full_url,
                "text": text or "PDF Document",
            })

    return pdf_links


def _is_pdf_link(href: str, text: str) -> bool:
    """判断是否为 PDF 链接"""
    href_lower = href.lower()
    text_lower = text.lower()

    # URL 以 .pdf 结尾
    if href_lower.endswith(".pdf"):
        return True

    # 文本包含 PDF 相关关键词
    pdf_keywords = ["pdf", "report", "technical", "43-101", "jorc", "feasibility"]
    if any(keyword in text_lower for keyword in pdf_keywords):
        return True

    return False
