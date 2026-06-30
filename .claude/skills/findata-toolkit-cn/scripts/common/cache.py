"""
数据缓存层 — SQLite 本地缓存，减少重复 API 调用。

所有数据获取函数都可以通过 @cached 装饰器自动缓存，
避免重复请求上游数据源，防止限流和节省带宽。

缓存数据库位置：./.claude/skills/findata-toolkit-cn/cache/data_cache.db
（在项目目录内，不依赖外部环境变量）

缓存 TTL 按数据类型区分：
  - 实时行情：交易时段 30 秒，非交易时段 5 分钟
  - 历史 K 线：1 小时（仅在收盘后变化）
  - 财务数据：24 小时（季度数据，极少变动）
  - 公司信息：24 小时
  - 板块成分：24 小时
  - 宏观数据：7 天（月/季度数据）
  - 默认：10 分钟
"""
import json
import os
import time
import sqlite3
import hashlib
import functools
from datetime import datetime, date
from pathlib import Path
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# 缓存数据库路径 — 放在项目目录下
# ---------------------------------------------------------------------------

# 尝试从环境变量获取，否则使用项目默认路径
_CACHE_ENV = os.environ.get("FINANCIAL_CACHE_DIR")
if _CACHE_ENV:
    _CACHE_DIR = Path(_CACHE_ENV)
else:
    # 默认：技能目录下的 cache/
    _CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "cache"

_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = str(_CACHE_DIR / "data_cache.db")


def _get_db() -> sqlite3.Connection:
    """获取或创建缓存数据库连接。"""
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            expires REAL NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires)"
    )
    conn.commit()
    return conn


def _cleanup_expired():
    """清理过期缓存（每次写入时顺便做）。"""
    try:
        conn = _get_db()
        conn.execute("DELETE FROM cache WHERE expires < ?", (time.time(),))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 时间辅助
# ---------------------------------------------------------------------------

def _is_market_hours() -> bool:
    """判断当前是否在中国 A 股交易时段（UTC+8）。"""
    now = datetime.now()
    # 简单判断：周一至周五 9:30-11:30 或 13:00-15:00（北京时间）
    if now.weekday() >= 5:  # 周末
        return False
    beijing_hour = now.hour + 8
    beijing_min = now.minute
    if beijing_hour >= 24:
        beijing_hour -= 24
    if (beijing_hour == 9 and beijing_min >= 30) or beijing_hour == 10:
        return True
    if beijing_hour == 11 and beijing_min <= 30:
        return True
    if beijing_hour == 13 or (beijing_hour == 14):
        return True
    return False


def _market_ttl(default: float = 600) -> float:
    """根据是否在交易时段返回合适的 TTL（秒）。"""
    if _is_market_hours():
        return min(default, 30)  # 交易时段最多缓存 30 秒
    return max(default, 300)  # 非交易时段最少 5 分钟


# ---------------------------------------------------------------------------
# 数据类型预设 TTL（秒）
# ---------------------------------------------------------------------------

TTL_MAP = {
    "quote": 30,               # 实时行情
    "history": 3600,           # 历史 K 线
    "financials": 86400,       # 财务报表
    "metrics": 3600,           # 财务指标
    "northbound": 300,         # 北向资金
    "insider": 86400,          # 董监高增减持
    "macro": 604800,           # 宏观数据（7 天）
    "screen": 3600,            # 筛选结果
    "basic_info": 86400,       # 基本信息
    "default": 600,            # 默认 10 分钟
}


# ---------------------------------------------------------------------------
# 核心装饰器
# ---------------------------------------------------------------------------

def cached(ttl: Optional[float] = None, key_prefix: str = ""):
    """
    SQLite 缓存装饰器。

    Args:
        ttl: 缓存有效期（秒），如果不指定则从 TTL_MAP 按函数名推断。
        key_prefix: 缓存键前缀，用于区分不同模块的缓存。

    Usage:
        @cached(ttl=30)
        def fetch_quote(symbol): ...

        # 自动从 TTL_MAP 推断
        @cached()
        def fetch_history(symbol):  # 使用 history: 3600s
            ...
    """
    def decorator(func: Callable) -> Callable:
        # 确定默认 TTL
        func_ttl = ttl
        if func_ttl is None:
            func_name = func.__name__
            # 尝试从函数名匹配 TTL_MAP 键
            for map_key, map_ttl in TTL_MAP.items():
                if map_key in func_name:
                    func_ttl = map_ttl
                    break
            if func_ttl is None:
                func_ttl = TTL_MAP["default"]

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            raw_key = f"{key_prefix}{func.__module__}.{func.__qualname__}:{args}:{sorted(kwargs.items())}"
            cache_key = hashlib.sha256(raw_key.encode()).hexdigest()[:64]
            effective_ttl = _market_ttl(func_ttl)
            expires = time.time() + effective_ttl

            # 查缓存
            try:
                conn = _get_db()
                row = conn.execute(
                    "SELECT data FROM cache WHERE key = ? AND expires > ?",
                    (cache_key, time.time())
                ).fetchone()
                conn.close()
                if row:
                    return json.loads(row[0])
            except Exception:
                pass

            # 查数据源
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                # 出错也缓存错误（短暂 TTL），避免频繁重试
                try:
                    err_data = json.dumps({"error": str(e)}, ensure_ascii=False)
                    conn = _get_db()
                    conn.execute(
                        "INSERT OR REPLACE INTO cache (key, data, expires) VALUES (?, ?, ?)",
                        (cache_key, err_data, time.time() + 60)
                    )
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
                raise

            # 写缓存
            try:
                _cleanup_expired()
                conn = _get_db()
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, data, expires) VALUES (?, ?, ?)",
                    (cache_key, json.dumps(result, ensure_ascii=False, default=_json_default),
                     expires)
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

            return result

        # 暴露清除缓存方法
        def clear_cache():
            """清除该函数的所有缓存。"""
            try:
                conn = _get_db()
                prefix = f"{key_prefix}{func.__module__}.{func.__qualname__}:"
                conn.execute("DELETE FROM cache WHERE key LIKE ?", (prefix + "%",))
                conn.commit()
                conn.close()
            except Exception:
                pass

        wrapper.clear_cache = clear_cache  # type: ignore
        wrapper._ttl = func_ttl  # type: ignore
        return wrapper

    return decorator


def _json_default(obj):
    """JSON 序列化时的默认处理。"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    try:
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    return str(obj)


# ---------------------------------------------------------------------------
# 手动缓存 API（用于非装饰器场景）
# ---------------------------------------------------------------------------

def cache_get(key: str) -> Any | None:
    """手动获取缓存数据。"""
    cache_key = hashlib.sha256(key.encode()).hexdigest()[:64]
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT data FROM cache WHERE key = ? AND expires > ?",
            (cache_key, time.time())
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def cache_set(key: str, value: Any, ttl: float = 600) -> None:
    """手动写入缓存。"""
    cache_key = hashlib.sha256(key.encode()).hexdigest()[:64]
    expires = time.time() + ttl
    try:
        _cleanup_expired()
        conn = _get_db()
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, data, expires) VALUES (?, ?, ?)",
            (cache_key, json.dumps(value, ensure_ascii=False, default=_json_default), expires)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def cache_clear_all() -> int:
    """清除所有缓存，返回删除的记录数。"""
    try:
        conn = _get_db()
        cursor = conn.execute("DELETE FROM cache")
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count
    except Exception:
        return 0


def cache_stats() -> dict:
    """获取缓存统计信息。"""
    try:
        conn = _get_db()
        total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        expired_before_cleanup = conn.execute(
            "SELECT COUNT(*) FROM cache WHERE expires < ?", (time.time(),)
        ).fetchone()[0]
        conn.close()
        return {
            "total_entries": total,
            "expired_pending": expired_before_cleanup,
            "db_path": _DB_PATH,
        }
    except Exception:
        return {"error": "无法读取缓存统计"}
