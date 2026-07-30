# -*- coding: utf-8 -*-
"""临时网络诊断:测各数据源在 trust_env=True/False 下的实际返回,定位 MCP 全挂根因。
跑完即可删。"""
import os
import sys
import warnings
warnings.filterwarnings("ignore")
import urllib3
urllib3.disable_warnings()

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests


def test(name, url, trust_env, verify=True):
    s = requests.Session()
    s.trust_env = trust_env
    try:
        r = s.get(url, timeout=15, verify=verify)
        body = r.text[:80].replace("\n", " ")
        return f"[{name}] trust_env={trust_env} verify={verify}: HTTP {r.status_code} | {body}"
    except Exception as e:
        return f"[{name}] trust_env={trust_env} verify={verify}: ERR {type(e).__name__}: {str(e)[:140]}"


print("=== HTTP_PROXY/HTTPS_PROXY/NO_PROXY env ===")
print(f"HTTP_PROXY={os.environ.get('HTTP_PROXY')!r} HTTPS_PROXY={os.environ.get('HTTPS_PROXY')!r} NO_PROXY={os.environ.get('NO_PROXY')!r}")

print("\n=== iFind (api-mcp.51ifind.com:8643) ===")
u = "https://api-mcp.51ifind.com:8643/ds-mcp-servers"
print(test("iFind", u, False, False))
print(test("iFind", u, True, False))

print("\n=== Wind (mcp.wind.com.cn) ===")
print(test("Wind", "https://mcp.wind.com.cn", False, False))
print(test("Wind", "https://mcp.wind.com.cn", True, False))

print("\n=== EastMoney push2 (akshare 内部用) ===")
em = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=1&fields=f12&fid=f3&po=1&fs=m:0+t:6"
print(test("EM", em, False, False))
print(test("EM", em, True, False))

print("\n=== 腾讯 qt.gtimg.cn (HTTP, 记忆称最稳) ===")
print(test("QQ", "http://qt.gtimg.cn/q=sh000001", False, False))

print("\n=== akshare 实测 (默认 trust_env=True) ===")
try:
    import akshare as ak
    try:
        df = ak.stock_zh_a_spot()
        print(f"akshare stock_zh_a_spot default: OK rows={len(df)} cols={list(df.columns)[:5]}")
    except Exception as e:
        print(f"akshare stock_zh_a_spot default: ERR {type(e).__name__}: {str(e)[:160]}")
except Exception as e:
    print(f"akshare import: ERR {e}")
