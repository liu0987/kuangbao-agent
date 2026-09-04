"""
PDF 解析器
使用 PyMuPDF 提取文本，判断是否为扫描件
"""
import io
import logging
from typing import Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_bytes: bytes) -> dict:
    """
    从 PDF 提取文本

    Args:
        pdf_bytes: PDF 文件的字节内容

    Returns:
        {
            "text": "全文文本",
            "pages": [{"page_num": 1, "text": "..."}],
            "is_scanned": bool,
            "total_pages": int,
            "metadata": {...}
        }
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    pages = []
    full_text = []
    total_chars = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        full_text.append(text)
        pages.append({
            "page_num": page_num + 1,
            "text": text,
            "char_count": len(text),
        })
        total_chars += len(text)

    # 判断是否为扫描件（平均每页字符数 < 100 认为是扫描件）
    total_pages = len(doc)
    avg_chars_per_page = total_chars / total_pages if total_pages > 0 else 0
    is_scanned = avg_chars_per_page < 100

    # 提取元数据
    metadata = doc.metadata or {}

    doc.close()

    return {
        "text": "\n\n".join(full_text),
        "pages": pages,
        "is_scanned": is_scanned,
        "total_pages": total_pages,
        "metadata": {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "creator": metadata.get("creator", ""),
        },
        "avg_chars_per_page": avg_chars_per_page,
    }


def extract_tables_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    从 PDF 提取表格（简化版本）

    Args:
        pdf_bytes: PDF 文件的字节内容

    Returns:
        表格列表
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    tables = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # PyMuPDF 的表格提取功能
        try:
            tab = page.find_tables()
            if tab.tables:
                for i, table in enumerate(tab.tables):
                    tables.append({
                        "page": page_num + 1,
                        "table_index": i,
                        "rows": table.extract(),
                    })
        except Exception as e:
            logger.warning(f"Page {page_num + 1} table extraction failed: {e}")

    doc.close()
    return tables
