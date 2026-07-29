"""测试 fixtures — 影子迁移期 path 设置。

让测试既能 import core 包, 又能 import scripts/cn_fetch 做新旧比对。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_ROOT, "scripts")
for _p in (_ROOT, _SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)
