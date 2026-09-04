"""
矿权日报 Agent 日志系统
提供结构化日志、进度追踪、统计汇总
"""
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


# ── 日志格式 ──────────────────────────────────────────────
LOG_FORMAT = "[%(asctime)s] %(levelname)-7s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ── 进度阶段定义 ──────────────────────────────────────────
@dataclass
class StageInfo:
    """阶段信息"""
    name: str
    description: str
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "pending"  # pending, running, success, failed
    details: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        return 0.0

    @property
    def duration_str(self) -> str:
        d = self.duration
        if d < 1:
            return f"{d*1000:.0f}ms"
        elif d < 60:
            return f"{d:.1f}s"
        else:
            return f"{d/60:.1f}min"


# ── 统计数据 ──────────────────────────────────────────────
@dataclass
class AgentStats:
    """Agent 执行统计"""
    news_count: int = 0
    pdf_count: int = 0
    pdf_success: int = 0
    pdf_failed: int = 0
    price_count: int = 0
    total_duration: float = 0.0
    llm_calls: int = 0
    mcp_calls: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ── Agent 日志器 ──────────────────────────────────────────
class AgentLogger:
    """
    Agent 专用日志器

    功能：
    1. 控制台输出：简洁的进度信息
    2. 文件输出：详细的调试日志
    3. 阶段追踪：记录每个阶段的状态和耗时
    4. 统计汇总：记录执行统计数据
    """

    def __init__(
        self,
        name: str = "agent",
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        quiet: bool = False,
    ):
        self.name = name
        self.quiet = quiet
        self.stages: list[StageInfo] = []
        self.current_stage: Optional[StageInfo] = None
        self.stats = AgentStats()
        self.start_time = time.time()

        # 配置 logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        # 清除已有的 handler
        self.logger.handlers.clear()

        # 控制台 handler（输出到stderr，避免与stdout的JSON-RPC通信冲突）
        if not quiet:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
            self.logger.addHandler(console_handler)

        # 文件 handler（始终记录 DEBUG 级别）
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
            self.logger.addHandler(file_handler)

    # ── 基础日志方法 ──────────────────────────────────────
    def debug(self, msg: str):
        self.logger.debug(msg)

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)
        self.stats.warnings.append(msg)

    def error(self, msg: str, exc_info: bool = False):
        self.logger.error(msg, exc_info=exc_info)
        self.stats.errors.append(msg)

    # ── 阶段控制 ──────────────────────────────────────────
    def start_stage(self, name: str, description: str) -> StageInfo:
        """开始一个新阶段"""
        # 结束上一个阶段（如果有的话）
        if self.current_stage and self.current_stage.status == "running":
            self.end_stage("success")

        stage = StageInfo(
            name=name,
            description=description,
            start_time=time.time(),
            status="running",
        )
        self.stages.append(stage)
        self.current_stage = stage

        if not self.quiet:
            print(f"\n{'─' * 60}")
            print(f"  [{name}] {description}...")
        self.info(f"开始阶段: {name} - {description}")

        return stage

    def end_stage(self, status: str = "success", error: Optional[str] = None):
        """结束当前阶段"""
        if not self.current_stage:
            return

        self.current_stage.end_time = time.time()
        self.current_stage.status = status
        self.current_stage.error = error

        # 输出结果
        if not self.quiet:
            status_icon = "✓" if status == "success" else "✗"
            print(f"  {status_icon} {status.upper()} ({self.current_stage.duration_str})")

            # 输出阶段详情
            for detail in self.current_stage.details:
                print(f"     {detail}")

            if error:
                print(f"     错误: {error}")

        # 记录到日志
        if status == "success":
            self.info(f"完成阶段: {self.current_stage.name} ({self.current_stage.duration_str})")
        else:
            self.error(f"失败阶段: {self.current_stage.name} - {error}")

        self.current_stage = None

    def add_stage_detail(self, detail: str):
        """向当前阶段添加详情"""
        if self.current_stage:
            self.current_stage.details.append(detail)
        self.debug(detail)

    # ── 便捷方法 ──────────────────────────────────────────
    def log_news_search(self, source: str, count: int):
        """记录新闻搜索结果"""
        self.add_stage_detail(f"→ {source}: 获取 {count} 条")
        self.stats.news_count += count

    def log_pdf_download(self, index: int, total: int, url: str, success: bool, error: Optional[str] = None):
        """记录 PDF 下载结果"""
        self.stats.pdf_count += 1
        if success:
            self.stats.pdf_success += 1
            self.add_stage_detail(f"→ [{index}/{total}] 下载成功")
        else:
            self.stats.pdf_failed += 1
            self.add_stage_detail(f"→ [{index}/{total}] 下载失败: {error}")

    def log_price(self, commodity: str, price: float, currency: str):
        """记录价格数据"""
        self.add_stage_detail(f"→ {commodity}: {price:,.2f} {currency}")
        self.stats.price_count += 1

    def log_llm_call(self, purpose: str):
        """记录 LLM 调用"""
        self.stats.llm_calls += 1
        self.debug(f"LLM 调用: {purpose}")

    def log_mcp_call(self, server: str, tool: str):
        """记录 MCP 调用"""
        self.stats.mcp_calls += 1
        self.debug(f"MCP 调用: {server}/{tool}")

    # ── 启动和结束 ──────────────────────────────────────
    def print_banner(self, query: str):
        """打印启动横幅"""
        if self.quiet:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║              矿权日报 Agent - Mining Rights Daily        ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║  时间: {now}                              ║")
        print(f"║  查询: {query:<48s} ║")
        print("╚══════════════════════════════════════════════════════════╝")
        self.info(f"启动 Agent - 查询: {query}")

    def print_summary(self, report_path: Optional[str] = None):
        """打印执行摘要"""
        self.stats.total_duration = time.time() - self.start_time

        if self.quiet:
            return

        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║                      执行摘要                            ║")
        print("╠══════════════════════════════════════════════════════════╣")

        # 阶段统计
        print("║  阶段执行情况:                                           ║")
        for stage in self.stages:
            status_icon = "✓" if stage.status == "success" else "✗"
            print(f"║    {status_icon} {stage.name:<12s} {stage.duration_str:>8s}                        ║")

        print("╠══════════════════════════════════════════════════════════╣")

        # 数据统计
        print(f"║  新闻数据: {self.stats.news_count:>3d} 条                                        ║")
        print(f"║  PDF报告: {self.stats.pdf_success:>3d}/{self.stats.pdf_count:<3d} 成功                                    ║")
        print(f"║  价格数据: {self.stats.price_count:>3d} 种                                        ║")
        print(f"║  LLM调用: {self.stats.llm_calls:>4d} 次                                       ║")
        print(f"║  MCP调用: {self.stats.mcp_calls:>4d} 次                                       ║")
        print(f"║  总耗时: {self.stats.total_duration:>6.1f}s                                       ║")

        if self.stats.warnings:
            print("╠══════════════════════════════════════════════════════════╣")
            print(f"║  警告: {len(self.stats.warnings)} 个                                           ║")

        if self.stats.errors:
            print(f"║  错误: {len(self.stats.errors)} 个                                           ║")

        print("╠══════════════════════════════════════════════════════════╣")
        if report_path:
            print(f"║  报告已保存: {report_path:<42s} ║")
        print("╚══════════════════════════════════════════════════════════╝")

        # 记录到日志文件
        self.info(f"执行完成 - 耗时: {self.stats.total_duration:.1f}s, "
                  f"新闻: {self.stats.news_count}, PDF: {self.stats.pdf_success}/{self.stats.pdf_count}, "
                  f"价格: {self.stats.price_count}")


# ── 全局日志器实例 ────────────────────────────────────────
_logger: Optional[AgentLogger] = None


def get_logger() -> AgentLogger:
    """获取全局日志器实例"""
    global _logger
    if _logger is None:
        _logger = AgentLogger()
    return _logger


def init_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    quiet: bool = False,
) -> AgentLogger:
    """初始化全局日志器"""
    global _logger
    _logger = AgentLogger(
        name="agent",
        log_level=log_level,
        log_file=log_file,
        quiet=quiet,
    )
    return _logger
