# KuangBao Agent
#
# 注意：此包名 'code' 与 Python 标准库模块 'code' 冲突。
# 为了解决这个冲突，我们需要在这里导入标准库的 code 模块，
# 并将其作为属性暴露出来，这样当其他模块需要标准库的 code 模块时可以使用。

import sys
import importlib
import importlib.util

# 尝试从标准库路径导入 code 模块
def _load_stdlib_code():
    """加载标准库的 code 模块"""
    # 获取标准库路径
    stdlib_paths = [p for p in sys.path if 'site-packages' not in p and p != '']

    for path in stdlib_paths:
        try:
            spec = importlib.util.spec_from_file_location(
                'code',
                f'{path}/code.py',
                submodule_search_locations=[]
            )
            if spec:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
        except (FileNotFoundError, ImportError):
            continue
    return None


# 尝试加载标准库模块
_stdlib_code = _load_stdlib_code()

if _stdlib_code:
    # 将标准库模块的关键属性添加到当前模块
    InteractiveConsole = getattr(_stdlib_code, 'InteractiveConsole', None)
    InteractiveInterpreter = getattr(_stdlib_code, 'InteractiveInterpreter', None)

    # 保存标准库模块供内部使用
    _STDLIB_CODE = _stdlib_code
