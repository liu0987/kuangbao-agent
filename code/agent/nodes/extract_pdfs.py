"""
PDF 链接提取节点
从新闻中筛选含 PDF 链接的条目，调用 PDF 解析
"""
from ..state import AgentState
from .. import mcp_client
from ..logger import get_logger


async def extract_pdfs_node(state: AgentState) -> dict:
    """
    PDF 提取节点

    1. 从新闻中筛选含 PDF 链接的条目
    2. 过滤出 NI 43-101 / JORC 相关的 PDF
    3. 调用 mineral-pdf-mcp 解析 PDF
    """
    logger = get_logger()
    logger.start_stage("提取PDF", "从新闻中筛选并解析技术报告")

    news = state.get("news", [])
    pdf_results = []
    warnings = list(state.get("warnings", []))

    # 收集所有 PDF 链接
    pdf_candidates = []
    for item in news:
        for pdf_link in item.pdf_links:
            text = pdf_link.get("text", "").upper()
            # 只处理 NI 43-101 / JORC / Resource 相关的 PDF
            if any(keyword in text for keyword in ["43-101", "JORC", "RESOURCE", "REPORT", "TECHNICAL"]):
                pdf_candidates.append({
                    "url": pdf_link["url"],
                    "text": pdf_link.get("text", ""),
                    "source_title": item.title,
                })

    if not pdf_candidates:
        logger.add_stage_detail("→ 未找到 NI 43-101 / JORC 技术报告 PDF 链接")
        warnings.append("未找到 NI 43-101 / JORC 技术报告 PDF 链接")
        logger.end_stage("success")
        return {"pdf_results": [], "warnings": warnings}

    logger.add_stage_detail(f"→ 发现 {len(pdf_candidates)} 个 PDF 链接")

    # 解析每个 PDF（最多 3 个，避免耗时过长）
    for i, candidate in enumerate(pdf_candidates[:3], 1):
        logger.add_stage_detail(f"→ [{i}/{min(len(pdf_candidates), 3)}] 下载并解析: {candidate['text'][:50]}...")
        logger.log_mcp_call("mineral-pdf-mcp", "extract_resources")

        try:
            result = await mcp_client.call(
                "mineral-pdf-mcp",
                "extract_resources",
                {"pdf_url": candidate["url"]}
            )

            if isinstance(result, dict) and "error" in result:
                logger.log_pdf_download(i, min(len(pdf_candidates), 3), candidate['url'], False, result['error'])
                warnings.append(f"PDF 解析失败: {candidate['url']} - {result['error']}")
                continue

            # 检查置信度
            confidence = result.get("parse_confidence", 0)
            if confidence < 0.6:
                logger.add_stage_detail(f"  ⚠ 解析置信度低 ({confidence:.0%})")
                warnings.append(
                    f"{result.get('report_title', '未知报告')} 解析置信度低"
                    f"({confidence:.0%})，请核实原始报告"
                )

            logger.log_pdf_download(i, min(len(pdf_candidates), 3), candidate['url'], True)
            pdf_results.append(result)
            logger.debug(f"PDF 解析成功: {result.get('report_title', '未知报告')}")

        except Exception as e:
            logger.log_pdf_download(i, min(len(pdf_candidates), 3), candidate['url'], False, str(e))
            warnings.append(f"PDF 解析异常: {candidate['url']} - {str(e)}")

    if not pdf_results and not any("PDF" in w for w in warnings):
        warnings.append("未找到可解析的 NI 43-101 / JORC 技术报告")

    logger.end_stage("success")
    return {"pdf_results": pdf_results, "warnings": warnings}
