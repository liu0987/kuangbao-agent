"""
OCR 引擎
使用 MinerU 进行扫描件 OCR 识别
"""
import os
import sys
from typing import Optional


def ocr_pdf(pdf_bytes: bytes) -> dict:
    """
    对扫描件 PDF 进行 OCR 识别

    Args:
        pdf_bytes: PDF 文件的字节内容

    Returns:
        {
            "text": "识别后的文本",
            "pages": [{"page_num": 1, "text": "..."}],
            "engine": "mineru"
        }
    """
    try:
        # 尝试使用 MinerU (magic-pdf)
        return _ocr_with_mineru(pdf_bytes)
    except ImportError:
        print("MinerU not installed, falling back to basic OCR", file=sys.stderr)
        return _ocr_fallback(pdf_bytes)
    except Exception as e:
        print(f"MinerU OCR failed: {e}, falling back", file=sys.stderr)
        return _ocr_fallback(pdf_bytes)


def _ocr_with_mineru(pdf_bytes: bytes) -> dict:
    """
    使用 MinerU 进行 OCR

    MinerU (magic-pdf) 安装：
    pip install magic-pdf[full]

    首次运行会自动下载模型（约 1GB）
    """
    import tempfile
    import magic_pdf

    # 写入临时文件
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        # MinerU 解析
        result = magic_pdf(tmp_path)

        pages = []
        full_text = []

        for i, page_result in enumerate(result):
            page_text = page_result.get("text", "")
            full_text.append(page_text)
            pages.append({
                "page_num": i + 1,
                "text": page_text,
            })

        return {
            "text": "\n\n".join(full_text),
            "pages": pages,
            "engine": "mineru",
        }
    finally:
        # 清理临时文件
        os.unlink(tmp_path)


def _ocr_fallback(pdf_bytes: bytes) -> dict:
    """
    降级 OCR 方案
    当 MinerU 不可用时，返回空结果
    """
    return {
        "text": "",
        "pages": [],
        "engine": "none",
        "error": "OCR engine not available. Install MinerU: pip install magic-pdf[full]",
    }


def is_gpu_available() -> bool:
    """检测是否有可用的 GPU"""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False
