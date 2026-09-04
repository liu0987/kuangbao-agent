"""
LLM 配置与实例化模块（懒加载）
支持 OpenAI / Anthropic / 其他兼容 API，通过环境变量切换

使用懒加载避免 import 时因环境变量未配置而报错
"""
import os
from functools import lru_cache
from langchain_openai import ChatOpenAI

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None


@lru_cache(maxsize=1)
def get_llm():
    """
    懒加载 LLM 实例（首次调用时创建，之后复用缓存）
    使用 @lru_cache 确保全局单例，且线程安全
    """
    provider = os.getenv("LLM_PROVIDER", "openai")
    model = os.getenv("LLM_MODEL")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    if provider == "anthropic":
        if ChatAnthropic is None:
            raise ImportError("langchain-anthropic is not installed. Run: pip install langchain-anthropic")
        return ChatAnthropic(
            model=model or "claude-sonnet-4-20250514",
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:  # openai (默认，支持兼容 API)
        kwargs = {
            "model": model or "gpt-4o",
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": os.getenv("OPENAI_API_KEY"),
        }
        api_base = os.getenv("OPENAI_API_BASE")
        if api_base:
            kwargs["base_url"] = api_base
        return ChatOpenAI(**kwargs)


# 向后兼容的属性式访问（from ..llm import llm）
class _LLMProxy:
    """代理对象，延迟初始化实际 LLM"""
    def __getattr__(self, name: str):
        return getattr(get_llm(), name)

    def __repr__(self) -> str:
        try:
            llm_instance = get_llm()
            return f"<LLMProxy: {llm_instance.__class__.__name__}({llm_instance.model_name})>"
        except Exception:
            return "<LLMProxy: not initialized>"

    def __dir__(self) -> list[str]:
        try:
            return dir(get_llm())
        except Exception:
            return ["get_llm"]

llm = _LLMProxy()
