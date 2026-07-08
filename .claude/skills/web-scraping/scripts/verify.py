#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scrapling 安装与通道可用性自检。

用法: python scripts/verify.py [--full]
  --full  额外测试金融站点连通性（东方财富/雪球，可能因网络/SSL 失败，仅作参考）

退出码: 0=核心全过；1=有核心项失败
"""
import argparse
import sys
import time
import warnings

warnings.filterwarnings("ignore")

OK, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def _check(name, fn):
    t0 = time.time()
    try:
        msg = fn()
        results.append((OK, name, f"{msg} ({round(time.time()-t0,2)}s)"))
        return True
    except Exception as e:
        results.append((FAIL, name, f"{type(e).__name__}: {str(e)[:120]}"))
        return False


def _skip(name, why):
    results.append((SKIP, name, why))


def check_scrapling_import():
    import scrapling
    return f"scrapling {getattr(scrapling, '__version__', '?')}"


def check_parser():
    from scrapling.parser import Selector
    p = Selector("<html><body><div class='q'>hi</div></body></html>")
    assert p.css(".q::text").get() == "hi", "parser css 取值不对"
    return "Selector.css OK"


def check_fetchers_import():
    from scrapling.fetchers import Fetcher, DynamicFetcher, StealthyFetcher
    return "Fetcher/DynamicFetcher/StealthyFetcher 导入 OK"


def check_deps():
    import importlib.util as u
    missing = [m for m in ["playwright", "curl_cffi", "httpx", "msgspec"] if not u.find_spec(m)]
    camoufox = u.find_spec("camoufox") is not None
    if missing:
        _skip("可选依赖", f"缺失: {','.join(missing)}；fetchers 可能降级运行")
    else:
        msg = f"playwright/curl_cffi/httpx/msgspec 就位；camoufox={'有' if camoufox else '缺(StealthyFetcher 仍可降级)'}"
        results.append((OK, "可选依赖", msg))
    return True


def _fetch_http():
    from scrapling.fetchers import Fetcher
    p = Fetcher.get("https://example.com", timeout=20, verify=False)
    assert int(getattr(p, "status", 0)) == 200, f"status={getattr(p,'status',None)}"
    assert p.css("title::text").get() == "Example Domain"
    return "Fetcher.get 200 + title"


def _fetch_dynamic():
    from scrapling.fetchers import DynamicFetcher
    p = DynamicFetcher.fetch("https://example.com", headless=True, timeout=20000)
    assert int(getattr(p, "status", 0)) == 200
    return "DynamicFetcher 200 (Playwright JS)"


def _fetch_stealthy():
    from scrapling.fetchers import StealthyFetcher
    p = StealthyFetcher.fetch("https://example.com", headless=True, timeout=20000)
    assert int(getattr(p, "status", 0)) == 200
    return "StealthyFetcher 200 (反爬通道)"


def _extract_json_tolerant(text):
    """容错 JSON：先整段 parse；失败从首个 {/[ 到末尾 }/] 抽子串（东方财富 502-裹-HTML-JSON 怪象）。"""
    import json
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = -1
    for ch in ("{", "["):
        i = text.find(ch)
        if i != -1 and (start == -1 or i < start):
            start = i
    if start == -1:
        raise ValueError("无 JSON 起始符")
    close = "}" if text[start] == "{" else "]"
    end = text.rfind(close)
    return json.loads(text[start:end + 1])


def check_eastmoney():
    # 东方财富 push2his 实测 flaky：200纯JSON / 502裹HTML-JSON / curl(56) 连接断；重试 2 次
    from scrapling.fetchers import Fetcher
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
           "?secid=1.600519&fields1=f1&fields2=f51,f52,f53,f54,f55,f56"
           "&klt=101&fqt=1&beg=20260701&end=20260708")
    last_err = None
    for _ in range(3):
        try:
            p = Fetcher.get(url, timeout=20, verify=False, stealthy_headers=True, impersonate="chrome")
            data = _extract_json_tolerant(p.body.decode("utf-8", "ignore"))
            klines = (data.get("data") or {}).get("klines") or []
            assert klines, "klines 为空"
            return f"东方财富 push2his K线 JSON OK（{len(klines)} 根）"
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:80]}"
    raise AssertionError(f"重试3次仍失败：{last_err}")


def check_xueqiu():
    # 雪球强反爬：http 返回无 title 的 JS 外壳，dynamic 触发"滑动验证"，stealthy 实测可用
    from scrapling.fetchers import StealthyFetcher
    p = StealthyFetcher.fetch("https://xueqiu.com/S/SH600519", headless=True, timeout=30000)
    title = p.css("title::text").get() or ""
    assert "茅台" in title or "600519" in title, f"title={title!r}"
    return f"雪球个股页 OK（stealthy 通道，title={title[:24]}）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="额外测金融站点")
    args = ap.parse_args()

    print("Scrapling 自检\n" + "=" * 50)
    core_ok = True
    core_ok &= _check("scrapling 导入", check_scrapling_import)
    core_ok &= _check("Parser (Selector)", check_parser)
    _check("fetchers 导入", check_fetchers_import)
    check_deps()
    print("-" * 50)
    _check("Fetcher.get (HTTP+TLS伪装)", _fetch_http)
    _check("DynamicFetcher (Playwright)", _fetch_dynamic)
    _check("StealthyFetcher (反爬)", _fetch_stealthy)

    if args.full:
        print("-" * 50 + " (金融站点，参考用)")
        _check("东方财富 K线 JSON", check_eastmoney)
        _check("雪球个股页", check_xueqiu)

    print("=" * 50)
    for mark, name, msg in results:
        print(f"[{mark}] {name}: {msg}")
    print("-" * 50)
    print("结论:", "核心通道可用" if core_ok else "有核心项失败")
    return 0 if core_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
