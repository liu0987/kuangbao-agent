"""
矿产资源数据提取器
从 PDF 文本中提取结构化的资源储量数据
支持 NI 43-101 和 JORC 报告格式
"""
import re
from typing import Optional


def extract_mineral_resources(text: str) -> dict:
    """
    从文本中提取矿产资源数据

    Args:
        text: PDF 全文文本

    Returns:
        {
            "report_title": "...",
            "report_date": "...",
            "qualified_person": "...",
            "mineral_resources": {...},
            "cut_off_grade": "...",
            "effective_date": "...",
            "source_pages": [...],
            "parse_confidence": 0.85,
            "raw_text_snippet": "..."
        }
    """
    # 提取报告标题
    report_title = _extract_report_title(text)

    # 提取报告日期
    report_date = _extract_date(text)

    # 提取合格人员
    qualified_person = _extract_qualified_person(text)

    # 提取资源数据
    resources = _extract_resources(text)

    # 提取截止品位
    cut_off_grade = _extract_cut_off_grade(text)

    # 提取生效日期
    effective_date = _extract_effective_date(text) or report_date

    # 计算置信度
    parse_confidence = _calculate_confidence(resources, text)

    # 提取相关文本片段
    raw_text_snippet = _extract_relevant_snippet(text)

    return {
        "report_title": report_title,
        "report_date": report_date,
        "qualified_person": qualified_person,
        "mineral_resources": resources,
        "cut_off_grade": cut_off_grade,
        "effective_date": effective_date,
        "source_pages": [],  # 需要更复杂的解析来确定页码
        "parse_confidence": parse_confidence,
        "raw_text_snippet": raw_text_snippet[:2000],
    }


def _extract_report_title(text: str) -> str:
    """提取报告标题"""
    # 常见标题模式
    patterns = [
        r"NI\s*43-101\s*Technical\s*Report",
        r"JORC\s*Mineral\s*Resource",
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Project|Mine|Property))",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    # 返回前100个字符作为标题
    return text[:100].strip()


def _extract_date(text: str) -> Optional[str]:
    """提取日期"""
    patterns = [
        r"(?:dated?|effective|report\s+date)[:\s]*(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?:dated?|effective|report\s+date)[:\s]*(\d{1,2}\s+\w+\s+\d{4})",
        r"(?:dated?|effective|report\s+date)[:\s]*(\d{4}-\d{2}-\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def _extract_qualified_person(text: str) -> Optional[str]:
    """提取合格人员（Qualified Person）"""
    patterns = [
        r"(?:Qualified\s+Person|QP)[:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+(?:,?\s+(?:P\.Geo\.|P\.Eng\.|PhD|MSc)))",
        r"(?:prepared\s+by|authored\s+by)[:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def _extract_resources(text: str) -> dict:
    """提取资源储量数据"""
    resources = {
        "measured": _extract_category(text, "measured"),
        "indicated": _extract_category(text, "indicated"),
        "inferred": _extract_category(text, "inferred"),
    }
    return resources


def _extract_category(text: str, category: str) -> Optional[dict]:
    """提取单个资源类别（Measured/Indicated/Inferred）"""
    # 模式：类别名 + 数字（吨数）+ 品位 + 含量
    pattern = rf"""
        {category}\s*(?:Resource)?\s*[:\s]*
        ([\d,.]+)\s*(?:Mt|million\s+tonnes?)\s*
        (?:at|@)\s*
        ([\d.]+)\s*%\s*(?:Li₂O|Li2O|lithium)
        (?:\s*,?\s*(?:containing)?\s*([\d,.]+)\s*(?:kt|kt\s+Li₂O))?
    """

    match = re.search(pattern, text, re.IGNORECASE | re.VERBOSE)
    if match:
        try:
            tonnes = float(match.group(1).replace(",", ""))
            grade = float(match.group(2))
            contained = float(match.group(3).replace(",", "")) if match.group(3) else None

            return {
                "tonnes_mt": tonnes,
                "grade_l2o_pct": grade,
                "contained_l2o_kt": contained,
            }
        except (ValueError, IndexError):
            pass

    # 简化模式：只匹配吨数和品位
    simple_pattern = rf"{category}.*?([\d,.]+)\s*(?:Mt).*?([\d.]+)\s*%"
    match = re.search(simple_pattern, text, re.IGNORECASE)
    if match:
        try:
            return {
                "tonnes_mt": float(match.group(1).replace(",", "")),
                "grade_l2o_pct": float(match.group(2)),
                "contained_l2o_kt": None,
            }
        except (ValueError, IndexError):
            pass

    return None


def _extract_cut_off_grade(text: str) -> Optional[str]:
    """提取截止品位"""
    patterns = [
        r"(?:cut-?off|cut\s+off)\s*(?:grade)?[:\s]*([\d.]+\s*%\s*(?:Li₂O|Li2O))",
        r"(?:cut-?off|cut\s+off)[:\s]*([\d.]+\s*%)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def _extract_effective_date(text: str) -> Optional[str]:
    """提取生效日期"""
    return _extract_date(text)  # 复用日期提取


def _calculate_confidence(resources: dict, text: str) -> float:
    """计算解析置信度"""
    score = 0.0
    max_score = 5.0

    # 1. 检查是否包含 NI 43-101 或 JORC 关键词
    if re.search(r"NI\s*43-101|JORC", text, re.IGNORECASE):
        score += 1.0

    # 2. 检查是否包含 Measured/Indicated/Inferred
    categories_found = sum(1 for cat in ["measured", "indicated", "inferred"]
                          if resources.get(cat) is not None)
    score += categories_found * 0.5

    # 3. 检查是否包含吨数和品位数据
    if any(r and r.get("tonnes_mt") for r in resources.values() if r):
        score += 1.0

    # 4. 检查是否包含合格人员
    if _extract_qualified_person(text):
        score += 0.5

    # 5. 检查是否包含截止品位
    if _extract_cut_off_grade(text):
        score += 0.5

    return min(score / max_score, 1.0)


def _extract_relevant_snippet(text: str) -> str:
    """提取包含资源数据的相关文本片段"""
    # 查找包含资源关键词的段落
    keywords = ["mineral resource", "measured", "indicated", "inferred", "tonnes", "grade"]

    sentences = text.split(".")
    relevant = []

    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(keyword in sentence_lower for keyword in keywords):
            relevant.append(sentence.strip())
            if len(relevant) >= 5:
                break

    return ". ".join(relevant) if relevant else text[:1000]
