"""
Pytest configuration
解决 'code' 包名与标准库冲突的问题

由于项目目录 'code' 与 Python 标准库模块 'code' 冲突，
pytest 在初始化时会尝试导入标准库的 pdb 模块，而 pdb 依赖标准库的 code 模块，
导致冲突。

解决方案：在 pytest 配置阶段，手动将标准库的 code 模块注入到 sys.modules 中。
"""
import sys
import importlib


def pytest_configure(config):
    """pytest 配置钩子 - 在 pytest 初始化时修复模块冲突"""
    # 如果我们的 code 包已经被导入，需要特殊处理
    if 'code' in sys.modules:
        our_code = sys.modules['code']
        # 尝试从标准库位置重新导入
        try:
            # 使用 importlib 从标准库路径导入
            spec = importlib.util.find_spec('code', [])
            if spec and spec.origin and 'site-packages' not in spec.origin:
                stdlib_code = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(stdlib_code)
                # 将标准库模块保存为 _stdlib_code
                sys.modules['_stdlib_code'] = stdlib_code
        except (ImportError, AttributeError):
            pass


# 设置 asyncio 模式
pytest_plugins = ['pytest_asyncio']
