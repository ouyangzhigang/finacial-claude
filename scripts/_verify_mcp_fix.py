# -*- coding: utf-8 -*-
"""验证 MCP server.py 的 SSL 修复是否生效。直接加载新代码调用,不走已运行的旧 MCP 进程。跑完可删。"""
import os
import sys
import importlib.util

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- Wind ----
os.environ["WIND_API_KEY"] = "ak_0sVjT4eDeanB_8-LsWflIcfnoH4P0tEf"
os.environ["WIND_SSL_NO_VERIFY"] = "1"
print("=== Wind get_stock_basicinfo (修复前: Cannot set verify_mode to CERT_NONE) ===")
try:
    wind = load("mcp-servers/wind-mcp/server.py", "wind_srv")
    r = wind._call_wind("stock_data", "get_stock_basicinfo", {"question": "600519.SH公司基本档案"})
    print(r[:600])
except Exception as e:
    print(f"LOAD/CALL ERR: {type(e).__name__}: {e}")

# ---- akshare ----
print("\n=== akshare get_quote (修复前: SSL CERTIFICATE_VERIFY_FAILED @82.push2) ===")
try:
    ak = load("mcp-servers/akshare-mcp/server.py", "ak_srv")
    r2 = ak.get_quote("600519")
    print(r2[:600])
except Exception as e:
    print(f"LOAD/CALL ERR: {type(e).__name__}: {e}")

# ---- china-news ----
print("\n=== china-news get_stock_news (修复前: 空 DataFrame SSL 失败) ===")
try:
    cn = load("mcp-servers/china-news-mcp/server.py", "cn_srv")
    r3 = cn.get_stock_news("600519")
    print(r3[:600])
except Exception as e:
    print(f"LOAD/CALL ERR: {type(e).__name__}: {e}")
