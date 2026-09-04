"""
PDF 解析节点
对提取的 PDF 结果进行进一步处理和标准化
"""
from ..state import AgentState, MineralResource
from ..logger import get_logger


async def parse_pdfs_node(state: AgentState) -> dict:
    """
    PDF 解析节点

    对 extract_pdfs 节点的结果进行标准化处理
    """
    logger = get_logger()
    logger.start_stage("标准化PDF", "将PDF解析结果转换为标准格式")

    pdf_results = state.get("pdf_results", [])
    warnings = list(state.get("warnings", []))

    # 标准化资源数据
    standardized = []
    for result in pdf_results:
        if isinstance(result, dict):
            resource = MineralResource(
                report_title=result.get("report_title", "未知报告"),
                measured=result.get("mineral_resources", {}).get("measured"),
                indicated=result.get("mineral_resources", {}).get("indicated"),
                inferred=result.get("mineral_resources", {}).get("inferred"),
                parse_confidence=result.get("parse_confidence", 0),
                raw_text_snippet=result.get("raw_text_snippet", ""),
            )
            standardized.append(resource)
            logger.add_stage_detail(f"→ {resource.report_title}")

    if not standardized:
        logger.add_stage_detail("→ 无 PDF 数据需要标准化")
    else:
        logger.add_stage_detail(f"→ 已标准化 {len(standardized)} 份报告")

    logger.end_stage("success")
    return {"pdf_results": standardized, "warnings": warnings}
