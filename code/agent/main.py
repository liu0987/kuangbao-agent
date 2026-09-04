"""
Agent 入口
接收用户输入，执行 Agent 流程，输出简报
"""
import asyncio
import argparse
import io
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

# 加载 .env 文件
load_dotenv()

# Windows 终端 UTF-8 支持
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from .graph import build_graph
from .state import AgentState
from .llm import get_llm
from .prompts import EXTRACT_TARGET_PROMPT
from .logger import get_logger, init_logger

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"


async def extract_target(query: str) -> str:
    """从用户查询中提取目标矿区/公司"""
    logger = get_logger()
    llm = get_llm()

    try:
        logger.log_llm_call("提取目标矿区")
        response = await llm.ainvoke([
            SystemMessage(content="你是一个信息提取助手。"),
            HumanMessage(content=EXTRACT_TARGET_PROMPT.format(query=query))
        ])
        target = response.content.strip()
        # 清理可能的引号
        target = target.strip('"\'')
        return target if target else query
    except Exception as e:
        logger.warning(f"LLM 调用失败，使用默认目标: {e}")
        return query


def get_report_path(target: str) -> Path:
    """
    生成报告文件路径

    Args:
        target: 目标矿区/公司名称

    Returns:
        报告文件路径
    """
    # 确保 reports 目录存在
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 生成文件名：日期_时间_目标.md
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 清理目标名称中的特殊字符
    safe_target = "".join(c for c in target if c.isalnum() or c in "._- ").strip()
    safe_target = safe_target.replace(" ", "_")[:50]  # 限制长度

    filename = f"{timestamp}_{safe_target}.md"
    return REPORTS_DIR / filename


async def run_agent(query: str, output_file: str = None) -> str:
    """
    运行 Agent

    Args:
        query: 用户查询
        output_file: 输出文件路径（可选，默认自动保存到 reports 目录）

    Returns:
        生成的简报
    """
    logger = get_logger()
    logger.print_banner(query)

    # ── 阶段1: 提取目标 ──────────────────────────────────
    logger.start_stage("提取目标", "从查询中提取目标矿区/公司")
    try:
        target = await extract_target(query)
        logger.end_stage("success")
        logger.info(f"目标: {target}")
    except Exception as e:
        logger.end_stage("failed", str(e))
        target = query

    # ── 阶段2: 构建初始状态 ──────────────────────────────
    initial_state: AgentState = {
        "query": query,
        "target": target,
        "news": [],
        "pdf_results": [],
        "prices": [],
        "report": "",
        "sources": [],
        "warnings": [],
        "errors": [],
    }

    # ── 阶段3: 执行 Agent 图 ──────────────────────────────
    logger.start_stage("执行Agent", "运行数据采集和报告生成流程")
    try:
        graph = build_graph()
        result = await graph.ainvoke(initial_state)
        logger.end_stage("success")
    except Exception as e:
        logger.end_stage("failed", str(e))
        logger.error(f"Agent 执行失败: {e}", exc_info=True)
        raise

    # ── 阶段4: 处理结果 ──────────────────────────────────
    logger.start_stage("处理结果", "整理报告和统计数据")
    try:
        report = result.get("report", "简报生成失败")
        warnings = list(set(result.get("warnings", [])))  # 去重
        sources = list(set(result.get("sources", [])))  # 去重

        # 添加警告信息（如果有且简报中未包含）
        if warnings and "数据警告" not in report:
            warnings_text = "\n".join(f"- {w}" for w in warnings[:5])
            report = f"{report}\n\n---\n## 数据警告\n{warnings_text}"

        # 添加引用源（如果有且简报中未包含）
        if sources and "引用源" not in report:
            sources_text = "\n".join(f"[{i}] {s}" for i, s in enumerate(sources, 1))
            report = f"{report}\n\n---\n## 引用源\n{sources_text}"

        logger.end_stage("success")
    except Exception as e:
        logger.end_stage("failed", str(e))
        raise

    # ── 阶段5: 保存报告 ──────────────────────────────────
    logger.start_stage("保存报告", "将报告写入文件")
    try:
        if output_file:
            output_path = Path(output_file)
        else:
            output_path = get_report_path(target)

        # 确保父目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

        logger.end_stage("success")
    except Exception as e:
        logger.end_stage("failed", str(e))
        raise

    # ── 打印摘要 ──────────────────────────────────────────
    logger.print_summary(str(output_path))

    # 同时输出报告到控制台
    if not logger.quiet:
        print("\n" + "=" * 60)
        print(report)
        print("=" * 60)

    return report


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="矿权日报 Agent")
    parser.add_argument("query", nargs="?", help="用户查询")
    parser.add_argument("-o", "--output", help="输出文件路径（默认保存到 reports 目录）")
    parser.add_argument("--target", help="直接指定目标矿区/公司")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="日志级别 (默认: INFO)")
    parser.add_argument("--log-file", help="日志文件路径")
    parser.add_argument("--quiet", action="store_true", help="静默模式（只输出报告）")

    args = parser.parse_args()

    # 初始化日志器
    log_file = args.log_file
    if not log_file:
        # 默认保存到 logs 目录
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = str(LOGS_DIR / f"agent_{timestamp}.log")

    init_logger(
        log_level=args.log_level,
        log_file=log_file,
        quiet=args.quiet,
    )

    # 获取查询
    query = args.query
    if not query:
        query = input("请输入查询: ")

    # 运行 Agent
    asyncio.run(run_agent(query, args.output))


if __name__ == "__main__":
    main()
