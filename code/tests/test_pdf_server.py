"""
Mineral PDF MCP Server 测试
使用 pytest

注意：由于项目目录 'code' 与 Python 标准库模块 'code' 冲突，
需要使用 sys.path 来正确导入模块
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
from code.servers.mineral_pdf.pdf_parser import extract_text_from_pdf
from code.servers.mineral_pdf.resource_extractor import extract_mineral_resources


class TestPDFParser:
    """PDF 解析器测试"""

    def test_extract_text_empty_pdf(self):
        """测试空PDF处理"""
        # 创建一个最小的有效PDF
        minimal_pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
xref
0 3
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
trailer
<< /Size 3 /Root 1 0 R >>
startxref
109
%%EOF"""

        result = extract_text_from_pdf(minimal_pdf)

        assert "text" in result
        assert "is_scanned" in result
        assert "total_pages" in result
        assert result["total_pages"] == 0

    def test_extract_mineral_resources_empty(self):
        """测试空文本资源提取"""
        result = extract_mineral_resources("")

        assert "mineral_resources" in result
        assert "report_title" in result

    def test_extract_mineral_resources_with_data(self):
        """测试包含数据的资源提取"""
        sample_text = """
        NI 43-101 Technical Report
        Pilgangoora Lithium Project

        Mineral Resource Estimate:
        - Measured: 50 Mt @ 1.25% Li2O
        - Indicated: 100 Mt @ 1.15% Li2O
        - Inferred: 30 Mt @ 1.05% Li2O
        """

        result = extract_mineral_resources(sample_text)

        assert "mineral_resources" in result
        assert "report_title" in result


class TestResourceExtractor:
    """资源提取器测试"""

    def test_extract_from_empty_text(self):
        """测试空文本"""
        result = extract_mineral_resources("")
        assert isinstance(result, dict)

    def test_extract_with_keywords(self):
        """测试包含关键词的文本"""
        text = """
        Measured and Indicated Resources: 150 million tonnes
        Inferred Resources: 50 million tonnes
        Grade: 1.2% Li2O
        """
        result = extract_mineral_resources(text)
        assert isinstance(result, dict)
