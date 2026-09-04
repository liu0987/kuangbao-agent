"""
Agent 状态定义
定义 LangGraph 的状态结构
"""
from typing import TypedDict, Optional, Annotated
from dataclasses import dataclass, field
import operator


@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    url: str
    source: str
    snippet: str
    pdf_links: list[dict] = field(default_factory=list)


@dataclass
class MineralResource:
    """矿产资源数据"""
    report_title: str
    indicated: Optional[dict] = None
    inferred: Optional[dict] = None
    measured: Optional[dict] = None
    parse_confidence: float = 0.0
    raw_text_snippet: str = ""


@dataclass
class PriceData:
    """价格数据"""
    commodity: str
    price: float
    currency: str
    unit: str
    change_pct: float
    trend: dict = field(default_factory=dict)


class AgentState(TypedDict):
    """
    Agent 状态定义

    LangGraph 使用 TypedDict 定义状态结构
    节点返回 partial dict，LangGraph 自动合并

    使用 Annotated[list, operator.add] 支持并行节点追加列表
    """
    # 输入
    query: str                    # 用户查询
    target: str                   # 目标矿区/公司

    # 中间数据（使用 Annotated 支持并行追加）
    news: Annotated[list[NewsItem], operator.add]          # 新闻列表
    pdf_results: Annotated[list[MineralResource], operator.add]  # PDF 解析结果
    prices: Annotated[list[PriceData], operator.add]       # 价格数据

    # 输出
    report: str                   # 最终 Markdown 简报
    sources: Annotated[list[str], operator.add]            # 引用源列表
    warnings: Annotated[list[str], operator.add]           # 警告/缺失数据提示

    # 控制
    errors: Annotated[list[str], operator.add]             # 错误记录
