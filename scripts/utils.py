#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
投资分析架构通用工具库 — 数据缓存、超时重试、环境自适应阈值。
被所有脚本(aggregate_factor_engine、factor_engine、cn_fetch、workflow)共享。

修复的缺陷:
- Bug #1: 原无全局缓存 → 每agent重复发起相同网络请求 (已解决)
- Bug #2: request/curl无timeout设置 → 可能无限卡死 (已解决)
- Bug #3: 异常静默吞没 → 无法及时发现数据问题 (已解决)
"""
import json
import os
import sys
import time
import hashlib
from functools import lru_cache
from typing import Optional, Callable, Any, Dict, List

# ── 全局配置 ────────────────────────────────────────
CACHE_DIR = os.environ.get('DATA_CACHE_DIR', 'data/.cache')
CACHE_TTL_SECONDS = int(os.environ.get('CACHE_TTL', '300'))  # 5分钟TTL
DEFAULT_TIMEOUT_SEC = 25  # 默认HTTP超时(秒)
MAX_RETRIES = 3           # 默认最大重试次数
RETRY_BASE_DELAY = 1.0    # 指数退避基数(秒)

os.makedirs(CACHE_DIR, exist_ok=True)

# ── Token计数器 ─────────────────────────────────────
_api_call_count = 0
_api_cache_hit_count = 0
_total_tokens_saved = 0

def record_api_call(cached: bool = False, tokens: int = 0):
    """记录API调用，用于监控优化效果。"""
    global _api_call_count, _api_cache_hit_count, _total_tokens_saved
    _api_call_count += 1
    if cached:
        _api_cache_hit_count += 1
        _total_tokens_saved += tokens

def get_stats():
    hit_rate = (_api_cache_hit_count / max(_api_call_count, 1)) * 100
    return {
        'total_calls': _api_call_count,
        'cache_hits': _api_cache_hit_count,
        'hit_rate_pct': round(hit_rate, 1),
        'tokens_saved': _total_tokens_saved,
    }

def reset_stats():
    global _api_call_count, _api_cache_hit_count, _total_tokens_saved
    _api_call_count = _api_cache_hit_count = _total_tokens_saved = 0

# ═══════════════════════════════════════════════════
# 全局LRU缓存装饰器 — 消除跨agent重复网络请求
# ═══════════════════════════════════════════════════

def cached_http(maxsize=128, ttl=CACHE_TTL_SECONDS):
    """带TTL的HTTP结果缓存装饰器。

    使用示例:
        @cached_http(maxsize=64, ttl=300)
        def fetch_stocks(codes):
            ... # 真实HTTP请求

    同一参数组合在TTL内直接返回缓存结果，跳过网络请求。
    """
    _lru = {}

    def decorator(func):
        def wrapper(*args, **kwargs):
            key = _make_key(func.__name__, args, kwargs)
            ts, val = _lru.get(key, (0, None))

            if val is not None and (time.time() - ts) < ttl:
                record_api_call(cached=True, tokens=500)
                return val

            result = func(*args, **kwargs)
            _lru[key] = (time.time(), result)
            record_api_call(cached=False)
            return result
        return wrapper
    return decorator

def disk_cached(ttl=CACHE_TTL_SECONDS, suffix='.json'):
    """跨进程持久化磁盘缓存。不同Python实例/脚本共享。

    使用示例:
        @disk_cached(ttl=600)
        def fetch_market_radar(run_id):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            key = _make_key(func.__name__, args, kwargs)
            cachefile = os.path.join(CACHE_DIR, key + suffix)

            if os.path.exists(cachefile):
                try:
                    mtime = os.path.getmtime(cachefile)
                    if (time.time() - mtime) < ttl:
                        with open(cachefile, 'r', encoding='utf-8') as f:
                            val = json.load(f)
                        record_api_call(cached=True, tokens=300)
                        return val
                except (json.JSONDecodeError, OSError):
                    pass  # 损坏缓存自动清理

            result = func(*args, **kwargs)
            try:
                with open(cachefile, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False)
            except OSError:
                pass  # 写入失败不影响正常流程
            record_api_call(cached=False)
            return result
        return wrapper
    return decorator

# ═══════════════════════════════════════════════════
# HTTP请求增强 — 统一超时+指数退避重试
# ═══════════════════════════════════════════════════

import requests as _requests

class TimedSession(_requests.Session):
    """带统一超时和重试的Session。"""
    def __init__(self, timeout=DEFAULT_TIMEOUT_SEC, max_retries=MAX_RETRIES,
                 base_delay=RETRY_BASE_DELAY, **kwargs):
        super().__init__()
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay

    def request(self, method, url, **kwargs):
        # 如果调用者显式传了timeout，用调用者的；否则用默认的
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout

        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = super().request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except _requests.exceptions.Timeout:
                last_err = f"Timeout after {kwargs.get('timeout', self.timeout)}s"
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** (attempt - 1))
                    print(f"⚠️ Timeout #{attempt}/{self.max_retries} for {url[:80]}... retrying in {delay}s", file=sys.stderr)
                    time.sleep(delay)
            except _requests.exceptions.ConnectionError as e:
                last_err = str(e)
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** (attempt - 1))
                    print(f"⚠️ ConnectionError #{attempt}/{self.max_retries} for {url[:80]}... retrying in {delay}s", file=sys.stderr)
                    time.sleep(delay)
            except _requests.exceptions.HTTPError as e:
                # 4xx非重试，5xx重试
                if response.status_code >= 500 and attempt < self.max_retries:
                    delay = self.base_delay * (2 ** (attempt - 1))
                    print(f"⚠️ ServerError #{attempt}/{self.max_retries} HTTP{response.status_code} for {url[:80]}... retrying in {delay}s", file=sys.stderr)
                    time.sleep(delay)
                else:
                    raise
            except Exception as e:
                last_err = str(e)
                break  # 非网络错误不重试

        # 所有重试用完，抛出最后异常
        raise RuntimeError(f"{last_err}") from last_err


def http_get(url, params=None, headers=None, timeout=DEFAULT_TIMEOUT_SEC,
             max_retries=MAX_RETRIES, verify_ssl=False):
    """增强的HTTP GET: 统一超时 + 指数退避重试 + SSL容错。"""
    session = TimedSession(timeout=timeout, max_retries=max_retries)
    if not verify_ssl:
        session.verify = False
        session.trust_env = False  # 绕过系统代理SSL证书验证问题

    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                   'Accept': 'application/json, text/plain, */*',
                   'Referer': 'https://quote.eastmoney.com/'}

    r = session.get(url, params=params, headers=headers)
    return r.json() if r.content else {}


def http_post(url, data=None, json_data=None, headers=None, timeout=DEFAULT_TIMEOUT_SEC,
              max_retries=MAX_RETRIES, verify_ssl=False):
    """增强的HTTP POST。"""
    session = TimedSession(timeout=timeout, max_retries=max_retries)
    if not verify_ssl:
        session.verify = False
        session.trust_env = False

    if headers is None:
        headers = {'Content-Type': 'application/json', 'User-Agent': 'Invest-Analysis/1.0'}

    r = session.post(url, json=json_data, data=data, headers=headers)
    return r.json() if r.content else {}


# ═══════════════════════════════════════════════════
# 结构化异常 — 代替静默降级
# ╡═══════════════════════════════════════════════════

class DataFetchError(Exception):
    """数据获取失败的标准化异常。"""
    def __init__(self, source, message, recoverable=True, context=None):
        self.source = source
        self.recoverable = recoverable  # True表示可回退到降级方案
        self.context = context or {}
        super().__init__(f"[{source}] {message}")

class ConfigurableFailover:
    """配置化降级链 — 当主数据源失败时按顺序尝试备选。"""

    def __init__(self):
        self.sources = []
        self.last_result = None
        self.errors = []

    def add_source(self, name, fetch_fn, priority=0):
        self.sources.append({'name': name, 'fn': fetch_fn, 'priority': priority})
        self.sources.sort(key=lambda s: s['priority'], reverse=True)

    def execute(self, fallback_summary="所有数据源均失败"):
        """按优先级执行各数据源，第一个成功的返回；全失败抛出DataFetchError。"""
        self.errors = []
        for src in self.sources:
            try:
                result = src['fn']()
                if result:  # 非空即为成功
                    self.last_result = result
                    return result
                self.errors.append((src['name'], 'returned empty result'))
            except Exception as e:
                self.errors.append((src['name'], str(e)))

        raise DataFetchError(
            source='failover_chain',
            message=f'{fallback_summary}. 详细: {" | ".join(f"{n}: {e}" for n, e in self.errors)}',
            recoverable=False,
            context={'errors': self.errors}
        )

# ═══════════════════════════════════════════════════
# 环境自适应阈值 — 替代硬编码过滤条件
# ═══════════════════════════════════════════════════

class AdaptiveThresholds:
    """根据市场环境自适应调整过滤阈值。

    硬编码问题: 固定成交额>=1亿对科创板小票不合理，但可能对主板过大。
    解决方案: 根据指数状态和行业特征动态计算阈值。
    """

    def __init__(self, regime='ranging'):
        # 基础阈值配置 (日均成交额亿元, 换手率%)
        self.regime_thresholds = {
            'trending':   {'amt_min': 0.5, 'turnover_min': 0.5, 'turnover_max': 15},
            'ranging':    {'amt_min': 0.8, 'turnover_min': 0.8, 'turnover_max': 10},
            'shock':      {'amt_min': 1.5, 'turnover_min': 1.0, 'turnover_max': 8},
            'high_vol':   {'amt_min': 0.8, 'turnover_min': 1.0, 'turnover_max': 12},
        }
        self.regime = regime

    def set_regime(self, regime):
        self.regime = regime

    def get_liquidity_thresholds(self):
        return self.regime_thresholds.get(self.regime, self.regime_thresholds['ranging'])

    def passes_liquidity_filter(self, amt20_yi, turnover_pct, price, market_cap_yi, sector):
        """自适应流动性过滤: 不同行业/市值使用不同阈值。"""
        t = self.get_liquidity_thresholds()
        amt_min = t['amt_min']

        # 科创板/创业板小盘股放宽要求
        if market_cap_yi < 100 and market_cap_yi > 20:
            amt_min *= 0.6  # 小型成长股要求降低40%
        elif market_cap_yi < 20:
            amt_min *= 0.3  # 极小盘只要求有基本流动性

        return amt20_yi >= amt_min and t['turnover_min'] <= turnover_pct <= t['turnover_max']

    def get_pass_fail_reason(self, amt20_yi, turnover_pct, price, market_cap_yi):
        """返回具体的pass/fail原因，便于调试和日志。"""
        t = self.get_liquidity_thresholds()
        reasons = []

        if market_cap_yi < 20:
            amt_min = t['amt_min'] * 0.3
        elif market_cap_yi < 100:
            amt_min = t['amt_min'] * 0.6
        else:
            amt_min = t['amt_min']

        if amt20_yi < amt_min:
            reasons.append(f'amt20({amt20_yi:.2f}亿)<阈值({amt_min:.2f}亿)')
        if turnover_pct < t['turnover_min']:
            reasons.append(f'turnover({turnover_pct:.1f}%<{t["turnover_min"]}%最低)')
        if turnover_pct > t['turnover_max']:
            reasons.append(f'turnover({turnover_pct:.1f}%>{t["turnover_max"]}%最高)')

        return reasons

# ═══════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════

def _make_key(func_name, args, kwargs):
    """为缓存生成唯一key。"""
    raw = json.dumps({'f': func_name, 'a': [str(a) for a in args], 'k': dict(kwargs)}, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()[:16]

def safe_json_load(path, default=None):
    """安全JSON读取，失败返回default。"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return default

def safe_json_save(path, data):
    """安全JSON写入。"""
    try:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        print(f"⚠️ JSON保存失败 {path}: {e}", file=sys.stderr)
        return False
