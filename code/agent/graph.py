"""
LangGraph 图定义
定义 Agent 的执行流程
"""
from langgraph.graph import StateGraph, END, START

from .state import AgentState
from .nodes.search_news import search_news_node
from .nodes.extract_pdfs import extract_pdfs_node
from .nodes.parse_pdfs import parse_pdfs_node
from .nodes.get_prices import get_prices_node
from .nodes.generate_report import generate_report_node


def build_graph() -> StateGraph:
    """
    构建 Agent 执行图

    流程：
    search_news
        ├── extract_pdfs → parse_pdfs ─┐
        └── get_prices ────────────────┤
                                       ▼
                               generate_report
    """
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("search_news", search_news_node)
    graph.add_node("extract_pdfs", extract_pdfs_node)
    graph.add_node("parse_pdfs", parse_pdfs_node)
    graph.add_node("get_prices", get_prices_node)
    graph.add_node("generate_report", generate_report_node)

    # 入口 → 搜索新闻
    graph.add_edge(START, "search_news")

    # search_news 完成后，fan-out 到两条并行路径
    graph.add_conditional_edges(
        "search_news",
        lambda state: ["extract_pdfs", "get_prices"],  # 并行执行
    )

    # 路径 A: PDF 提取链
    graph.add_edge("extract_pdfs", "parse_pdfs")

    # 两条路径汇入 generate_report（自动等待 fan-in）
    graph.add_edge("parse_pdfs", "generate_report")
    graph.add_edge("get_prices", "generate_report")

    # 终点
    graph.add_edge("generate_report", END)

    return graph.compile()
