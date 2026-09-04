"""
新闻搜索节点
调用 mining-news-mcp 搜索新闻
优化：改进搜索词构建，添加中英文支持，集成监管平台报告搜索
"""
import asyncio
import re
from ..state import AgentState, NewsItem
from .. import mcp_client
from ..logger import get_logger


def extract_english_keywords(text: str) -> str:
    """从文本中提取英文关键词"""
    # 提取英文单词
    english_words = re.findall(r'[a-zA-Z]+', text)
    # 过滤常见停用词
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                  "have", "has", "had", "do", "does", "did", "will", "would", "could",
                  "should", "may", "might", "can", "shall", "about", "for", "with"}
    keywords = [w for w in english_words if w.lower() not in stop_words and len(w) > 2]
    return " ".join(keywords[:5])  # 最多5个关键词


def extract_company_name(text: str) -> str:
    """从文本中提取公司名称（简单的启发式方法）"""
    # 常见矿业公司名称模式
    company_patterns = [
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Mining|Minerals|Resources|Corp|Ltd|Inc|PLC))',
        r'((?:Pilbara|Rio Tinto|BHP|Fortescue|Glencore|Newmont|Barrick|Anglo|Vale|Teck))',
    ]
    for pattern in company_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


async def search_news_node(state: AgentState) -> dict:
    """
    搜索新闻节点

    1. 调用 mining-news-mcp 的 search 工具获取新闻列表
    2. 并行调用 search_reports 搜索监管平台技术报告
    3. 并行调用 article 工具获取文章详情和 PDF 链接
    """
    logger = get_logger()
    logger.start_stage("搜索新闻", "从多个数据源搜索相关新闻和监管报告")

    target = state.get("target", "")
    query = state.get("query", target)

    # 构建搜索查询：优先使用英文关键词
    english_keywords = extract_english_keywords(target + " " + query)
    if english_keywords:
        search_query = english_keywords + " mining"
    else:
        search_query = "mining mineral resource lithium"

    # 提取公司名称（用于报告搜索）
    company_name = extract_company_name(target + " " + query)

    logger.debug(f"搜索查询: {search_query}")
    logger.debug(f"公司名称: {company_name}")

    # 1. 并行搜索新闻和监管报告
    async def search_news():
        """搜索新闻"""
        try:
            logger.log_mcp_call("mining-news-mcp", "search")
            result = await mcp_client.call(
                "mining-news-mcp",
                "search",
                {"query": search_query, "max_results": 10}
            )
            return result
        except Exception as e:
            logger.warning(f"新闻搜索失败: {e}")
            return {"error": str(e)}

    async def search_reports():
        """搜索监管平台技术报告"""
        if not company_name:
            return {"results": []}
        try:
            logger.log_mcp_call("mining-news-mcp", "search_reports")
            result = await mcp_client.call(
                "mining-news-mcp",
                "search_reports",
                {
                    "company": company_name,
                    "report_type": "43-101",
                    "max_results": 3,
                }
            )
            return result
        except Exception as e:
            logger.debug(f"报告搜索失败: {e}")
            return {"results": []}

    # 并行执行搜索
    news_result, reports_result = await asyncio.gather(
        search_news(),
        search_reports(),
        return_exceptions=True,
    )

    # 处理新闻结果
    if isinstance(news_result, Exception):
        logger.warning(f"新闻搜索异常: {news_result}")
        news_results = []
        warnings = [f"新闻搜索失败: {str(news_result)}"]
    elif isinstance(news_result, dict) and "error" in news_result:
        logger.warning(f"新闻搜索失败: {news_result['error']}")
        news_results = []
        warnings = [f"新闻搜索失败: {news_result['error']}"]
    else:
        news_results = news_result.get("results", []) if isinstance(news_result, dict) else []
        warnings = []

    # 处理报告结果
    report_items = []
    if isinstance(reports_result, dict) and "results" in reports_result:
        report_items = reports_result.get("results", [])
        if report_items:
            logger.add_stage_detail(f"→ 找到 {len(report_items)} 份监管报告")
            # 将报告转换为新闻格式，添加到结果中
            for report in report_items:
                news_results.append({
                    "title": report.get("title", "Technical Report"),
                    "url": report.get("url", ""),
                    "source": report.get("source", "Regulatory"),
                    "snippet": f"类型: {report.get('type', '')} | 来源: {report.get('source', '')}",
                    "is_report": True,
                })

    top_items = news_results[:8]  # 增加返回数量，包含报告

    if not top_items:
        logger.warning("未找到相关新闻和报告")
        logger.end_stage("success")
        return {
            "news": [],
            "warnings": warnings + ["未找到相关新闻和报告"],
        }

    logger.add_stage_detail(f"→ 找到 {len(news_results)} 条结果，准备获取详情...")

    # 2. 并行获取文章详情（报告链接直接使用，不需要再提取）
    async def fetch_article(item: dict) -> NewsItem:
        # 如果是监管报告，直接返回
        if item.get("is_report"):
            return NewsItem(
                title=item.get("title", ""),
                url=item.get("url", ""),
                source=item.get("source", "Regulatory"),
                snippet=item.get("snippet", ""),
                pdf_links=[{"url": item.get("url", ""), "text": item.get("title", "")}],
            )

        # 否则获取文章详情
        try:
            logger.log_mcp_call("mining-news-mcp", "article")
            article = await mcp_client.call(
                "mining-news-mcp",
                "article",
                {"url": item["url"]}
            )
            pdf_links = article.get("pdf_links", []) if isinstance(article, dict) else []
            logger.debug(f"获取文章成功: {item.get('title', '')[:50]}")
        except Exception as e:
            logger.debug(f"获取文章失败: {e}")
            pdf_links = []

        return NewsItem(
            title=item.get("title", ""),
            url=item.get("url", ""),
            source=item.get("source", ""),
            snippet=item.get("snippet", ""),
            pdf_links=pdf_links,
        )

    # 并行抓取，单个失败不影响其他
    fetch_results = await asyncio.gather(
        *[fetch_article(item) for item in top_items],
        return_exceptions=True
    )

    news_items = []
    for i, result in enumerate(fetch_results):
        if isinstance(result, Exception):
            warnings.append(f"文章抓取失败: {top_items[i].get('url', '')[:50]}")
            logger.debug(f"文章抓取异常: {result}")
        else:
            news_items.append(result)
            # 记录新闻来源
            logger.log_news_search(result.source, 1)

    # 去重新闻来源统计
    source_counts = {}
    for item in news_items:
        source_counts[item.source] = source_counts.get(item.source, 0) + 1

    for source, count in source_counts.items():
        logger.add_stage_detail(f"→ {source}: {count} 条")

    logger.add_stage_detail(f"→ 共获取 {len(news_items)} 条结果详情")
    logger.end_stage("success")

    return {"news": news_items, "warnings": warnings}
