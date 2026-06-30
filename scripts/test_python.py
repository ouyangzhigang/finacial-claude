import json, requests, ssl
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

def mk(check_off):
    class A(HTTPAdapter):
        def init_poolmanager(self, *a, **k):
            c = create_urllib3_context()
            if check_off: c.check_hostname = False
            c.minimum_version = ssl.TLSVersion.TLSv1_2
            k["ssl_context"] = c; return super().init_poolmanager(*a, **k)
    s = requests.Session(); s.mount("https://", A()); return s

cfg = json.load(open("e:/finacial-invest/.mcp.json", encoding="utf-8"))

print("=== 1. 东方财富 push2his (verify=False, 等价 curl -k) ===")
s = mk(True)
try:
    r = s.get("https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={"fields1":"f1,f2,f3","fields2":"f51,f52,f53,f54,f55,f56",
                "ut":"7eea3edcaed734bea9cbfc24409ed989","klt":"101","fqt":"1",
                "secid":"1.600519","beg":"20260101","end":"20260629"},
        timeout=20, verify=False)
    print("status", r.status_code, "| body:", r.text[:150])
except Exception as e: print("EXC", type(e).__name__, str(e)[:150])

print("=== 2. iFind initialize (verify=False) ===")
s = mk(True)
tok = cfg["mcpServers"]["ifind"]["env"]["IFIND_AUTH_TOKEN"]
try:
    r = s.post("https://api-mcp.51ifind.com:8643/ds-mcp-servers/hexin-ifind-ds-stock-mcp",
        json={"jsonrpc":"2.0","id":1,"method":"initialize",
              "params":{"protocolVersion":"2025-03-26","capabilities":{},
                        "clientInfo":{"name":"t","version":"1"}}},
        headers={"Content-Type":"application/json",
                 "Accept":"application/json, text/event-stream","Authorization":tok},
        verify=False, timeout=25)
    print("status", r.status_code, "| session:", r.headers.get("Mcp-Session-Id","NONE"),
          "| body:", r.text[:150])
except Exception as e: print("EXC", type(e).__name__, str(e)[:150])

print("=== 3. Wind initialize (verify=False) ===")
s = mk(True)
key = cfg["mcpServers"]["wind"]["env"]["WIND_API_KEY"]
try:
    r = s.post("https://mcp.wind.com.cn/vserver_stock_data/mcp/",
        json={"jsonrpc":"2.0","id":1,"method":"initialize",
              "params":{"protocolVersion":"2025-03-26","capabilities":{},
                        "clientInfo":{"name":"t","version":"1"}}},
        headers={"Content-Type":"application/json",
                 "Accept":"application/json, text/event-stream","Authorization":"Bearer "+key},
        timeout=25)
    print("status", r.status_code, "| body:", r.text[:150])
except Exception as e: print("EXC", type(e).__name__, str(e)[:150])