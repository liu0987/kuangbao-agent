"""
Mineral PDF MCP Server
提供矿产资源报告 PDF 解析功能
含 SSRF 防护
"""
import ipaddress
import json
import logging
import os
import sys
from typing import Any
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP

from .pdf_parser import extract_text_from_pdf
from .ocr_engine import ocr_pdf, is_gpu_available
from .resource_extractor import extract_mineral_resources

# 配置日志输出到stderr（避免污染stdout的JSON-RPC通信）
logging.basicConfig(
    level=logging.WARNING,
    format="[%(asctime)s] %(levelname)s %(message)s",
    stream=sys.stderr,
    force=True,
)

# 创建 MCP Server 实例
mcp = FastMCP("mineral-pdf-mcp", log_level="WARNING")

# ── SSRF 防护配置 ─────────────────────────────────────────
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # 云元数据服务
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

BLOCKED_HOSTS = ["169.254.169.254", "metadata.google.internal"]
ALLOWED_DOMAINS: list[str] = []  # 空表示不限制
MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB


def _validate_pdf_url(url: str) -> None:
    """校验 PDF URL，防止 SSRF 攻击"""
    parsed = urlparse(url)

    # 1. 只允许 http/https
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"不支持的 URL 协议: {parsed.scheme}")

    # 2. 域名白名单（如果配置了）
    if ALLOWED_DOMAINS and parsed.hostname not in ALLOWED_DOMAINS:
        raise ValueError(f"域名不在白名单中: {parsed.hostname}")

    # 3. 禁止内网 IP
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        for network in BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError(f"禁止访问内网地址: {ip}")
    except ValueError as e:
        # 如果是我们抛出的禁止访问异常，继续抛出
        if "禁止访问" in str(e):
            raise
        # 否则 hostname 不是 IP，是域名，跳过 IP 检查

    # 4. 禁止常见云元数据域名
    if parsed.hostname in BLOCKED_HOSTS:
        raise ValueError(f"禁止访问云元数据服务: {parsed.hostname}")


# 默认请求头（模拟浏览器）
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
}


async def _download_pdf(url: str) -> bytes:
    """下载 PDF 文件（带安全校验）"""
    _validate_pdf_url(url)

    async with httpx.AsyncClient(
        timeout=60.0,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        # 先获取 HEAD 检查大小
        head_response = await client.head(url)
        content_length = head_response.headers.get("content-length")
        if content_length and int(content_length) > MAX_PDF_SIZE:
            raise ValueError(f"PDF 文件过大: {int(content_length) / 1024 / 1024:.1f}MB > {MAX_PDF_SIZE / 1024 / 1024}MB")

        # 下载文件
        response = await client.get(url)
        response.raise_for_status()

        if len(response.content) > MAX_PDF_SIZE:
            raise ValueError("PDF 文件超过大小限制")

        return response.content


@mcp.tool()
async def extract_resources(pdf_url: str) -> str:
    """
    下载并解析 NI 43-101 / JORC 矿产资源报告 PDF，提取结构化的资源储量数据

    Args:
        pdf_url: PDF 文件 URL

    Returns:
        JSON 格式的矿产资源数据
    """
    if not pdf_url:
        return json.dumps({"error": "pdf_url is required"}, ensure_ascii=False)

    try:
        # 1. 下载 PDF
        pdf_bytes = await _download_pdf(pdf_url)
    except ValueError as e:
        return json.dumps({"error": f"URL 校验失败: {str(e)}"}, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"下载失败: HTTP {e.response.status_code}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"下载失败: {str(e)}"}, ensure_ascii=False)

    try:
        # 2. PyMuPDF 提取文本
        pdf_result = extract_text_from_pdf(pdf_bytes)
        text = pdf_result["text"]

        # 3. 如果是扫描件，使用 OCR
        if pdf_result["is_scanned"]:
            print(f"PDF 是扫描件，使用 OCR... (GPU: {is_gpu_available()})", file=sys.stderr)
            ocr_result = ocr_pdf(pdf_bytes)
            if ocr_result.get("text"):
                text = ocr_result["text"]

        # 4. 结构化提取资源数据
        resources = extract_mineral_resources(text)

        # 5. 添加元信息
        resources["source_url"] = pdf_url
        resources["is_scanned"] = pdf_result["is_scanned"]
        resources["total_pages"] = pdf_result["total_pages"]
        resources["ocr_engine"] = "mineru" if pdf_result["is_scanned"] else "none"

        return json.dumps(resources, ensure_ascii=False, default=str)

    except Exception as e:
        return json.dumps({
            "error": f"PDF 解析失败: {str(e)}",
            "source_url": pdf_url,
        }, ensure_ascii=False)


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "sse":
        mcp.run(transport="sse", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "8002")))
    else:
        mcp.run(transport="stdio")
