"""
简报生成节点
使用 LLM 生成最终的 Markdown 简报
优化：改进上下文构建，提高简报质量
"""
from datetime import datetime
from langchain_core.messages import SystemMessage, HumanMessage

from ..state import AgentState
from ..llm import get_llm
from ..prompts import REPORT_PROMPT
from ..logger import get_logger

# ── 上下文长度限制 ────────────────────────────────────────
MAX_NEWS_CONTENT_LEN = 1500
MAX_PDF_SNIPPET_LEN = 2000
MAX_CONTEXT_CHARS = 25000


def _truncate(text: str, max_len: int) -> str:
    """截断文本，保留首尾"""
    if not text or len(text) <= max_len:
        return text
    half = max_len // 2
    return text[:half] + f"\n... [已截断，共 {len(text)} 字符] ...\n" + text[-half:]


def build_context(state: AgentState) -> str:
    """构建 LLM 上下文，控制总长度"""
    logger = get_logger()
    parts = []
    today = datetime.now().strftime("%Y-%m-%d")
    target = state.get("target", "未知矿区")

    parts.append(f"# 分析目标：{target}")
    parts.append(f"# 报告日期：{today}\n")

    # 1. 新闻摘要
    news = state.get("news", [])
    if news:
        parts.append("## 新闻数据\n")
        for i, item in enumerate(news[:5], 1):  # 最多5条新闻
            content = _truncate(item.snippet, MAX_NEWS_CONTENT_LEN)
            parts.append(f"### [{i}] {item.title}")
            parts.append(f"- 来源: {item.source}")
            parts.append(f"- URL: {item.url}")
            parts.append(f"- 摘要: {content}\n")
        logger.debug(f"上下文包含 {len(news)} 条新闻")
    else:
        parts.append("## 新闻数据\n未找到相关新闻。\n")

    # 2. PDF 解析结果
    pdf_results = state.get("pdf_results", [])
    if pdf_results:
        parts.append("## 矿产资源报告\n")
        for i, pdf in enumerate(pdf_results[:2], 1):  # 最多2份报告
            if isinstance(pdf, dict):
                title = pdf.get("report_title", "未知报告")
                snippet = _truncate(pdf.get("raw_text_snippet", ""), MAX_PDF_SNIPPET_LEN)
                confidence = pdf.get("parse_confidence", 0)
            else:
                title = pdf.report_title
                snippet = _truncate(pdf.raw_text_snippet, MAX_PDF_SNIPPET_LEN)
                confidence = pdf.parse_confidence

            parts.append(f"### [{i}] {title}")
            parts.append(f"- 解析置信度: {confidence:.0%}")
            parts.append(f"- 内容摘要: {snippet}\n")
        logger.debug(f"上下文包含 {len(pdf_results)} 份 PDF 报告")
    else:
        parts.append("## 矿产资源报告\n未找到 NI 43-101 / JORC 技术报告。\n")

    # 3. 价格数据（重点展示）
    prices = state.get("prices", [])
    if prices:
        parts.append("## 价格数据\n")
        for p in prices:
            if isinstance(p, dict):
                commodity = p.get('commodity', '')
                price = p.get('price', 0)
                currency = p.get('currency', '')
                unit = p.get('unit', '')
                change = p.get('change_pct', 0)
                trend = p.get('trend', {})
            else:
                commodity = p.commodity
                price = p.price
                currency = p.currency
                unit = p.unit
                change = p.change_pct
                trend = p.trend

            # 格式化价格显示
            trend_desc = trend.get("trend", "未知") if isinstance(trend, dict) else "未知"
            high = trend.get("high", 0) if isinstance(trend, dict) else 0
            low = trend.get("low", 0) if isinstance(trend, dict) else 0

            parts.append(f"### {commodity}")
            parts.append(f"- 当前价格: {price:,.2f} {currency}/{unit}")
            parts.append(f"- 30日涨跌幅: {change:+.2f}%")
            parts.append(f"- 趋势: {trend_desc}")
            if high and low:
                parts.append(f"- 30日区间: {low:,.2f} - {high:,.2f}")
            parts.append("")
        logger.debug(f"上下文包含 {len(prices)} 种价格数据")
    else:
        parts.append("## 价格数据\n未获取到价格数据。\n")

    # 4. 已有警告（去重）
    warnings = list(set(state.get("warnings", [])))
    if warnings:
        parts.append("## 数据说明\n")
        for w in warnings[:5]:  # 最多5条警告
            parts.append(f"- {w}")
        parts.append("")

    context = "\n".join(parts)

    # 总长度截断
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + f"\n\n... [总上下文已截断] ..."
        logger.debug(f"上下文已截断至 {MAX_CONTEXT_CHARS} 字符")

    return context


def collect_sources(state: AgentState) -> list[str]:
    """收集所有引用源（去重）"""
    sources = set()

    # 新闻来源
    for item in state.get("news", []):
        sources.add(f"[新闻] {item.title[:50]} - {item.source}")

    # PDF 来源
    for pdf in state.get("pdf_results", []):
        if isinstance(pdf, dict):
            sources.add(f"[报告] {pdf.get('report_title', '未知报告')[:50]}")
        else:
            sources.add(f"[报告] {pdf.report_title[:50]}")

    # 价格来源
    for price in state.get("prices", []):
        if isinstance(price, dict):
            sources.add(f"[价格] {price['commodity']} - {price.get('source', '未知')}")
        else:
            sources.add(f"[价格] {price.commodity}")

    return list(sources)


async def generate_report_node(state: AgentState) -> dict:
    """
    简报生成节点

    使用 LLM 生成最终的 Markdown 简报
    """
    logger = get_logger()
    logger.start_stage("生成报告", "使用 LLM 生成最终简报")

    # 构建上下文
    context = build_context(state)
    logger.add_stage_detail(f"→ 上下文长度: {len(context)} 字符")

    llm = get_llm()
    logger.log_llm_call("生成简报")

    try:
        logger.debug("开始 LLM 调用...")
        report = await llm.ainvoke([
            SystemMessage(content=REPORT_PROMPT),
            HumanMessage(content=context)
        ])
        report_text = report.content
        logger.add_stage_detail(f"→ 报告长度: {len(report_text)} 字符")
        logger.debug("LLM 调用完成")
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}", exc_info=True)
        report_text = f"""# 简报生成失败

**错误信息**: {str(e)}

**已收集的数据**:
- 新闻: {len(state.get('news', []))} 条
- 价格: {len(state.get('prices', []))} 个
- 报告: {len(state.get('pdf_results', []))} 份

请检查 LLM 配置后重试。
"""

    sources = collect_sources(state)
    logger.add_stage_detail(f"→ 收集引用源: {len(sources)} 条")

    logger.end_stage("success")
    return {
        "report": report_text,
        "sources": sources,
    }
