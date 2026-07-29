"""影子迁移期: 复用 scripts/utils.py 的基础设施, 不重造轮子。

迁完后 utils.py 本身也会进 core/, 此处指向 core 内部实现。
当前 core 内部用 `from core._compat import disk_cached` 即可拿到
跨进程磁盘缓存/HTTP/异常/JSON 工具, 与 scripts/ 共享同一份缓存。
"""
import os
import sys

# 把 scripts/ 加入 path 以 import utils (影子迁移期, 迁完移除此块)
_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from utils import (  # type: ignore[no-redef]
    CACHE_DIR,
    CACHE_TTL_SECONDS,
    AdaptiveThresholds,
    ConfigurableFailover,
    DataFetchError,
    cached_http,
    disk_cached,
    http_get,
    http_post,
    safe_json_load,
    safe_json_save,
)

__all__ = [
    "CACHE_DIR",
    "CACHE_TTL_SECONDS",
    "AdaptiveThresholds",
    "ConfigurableFailover",
    "DataFetchError",
    "cached_http",
    "disk_cached",
    "http_get",
    "http_post",
    "safe_json_load",
    "safe_json_save",
]
