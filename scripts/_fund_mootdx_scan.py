# -*- coding: utf-8 -*-
"""深核 v3: mootdx TCP 财务快照(37字段) + F10财务分析(商誉) — 绕SSL"""
import sys, os, json, re, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

def tdx_client(market='std'):
    from mootdx.quotes import Quotes
    servers = [
        ('119.147.212.81', 7709), ('112.74.214.43', 7727),
        ('221.231.141.116', 7709), ('101.227.93.22', 7709),
        ('101.227.93.21', 7709), ('218.75.126.9', 7709),
        ('115.238.56.101', 7709), ('115.238.90.165', 7709),
        ('60.12.136.250', 7709), ('218.108.98.38', 7709),
    ]
    for ip, port in servers:
        try:
            c = Quotes.factory(market=market, bestip=(ip, port), timeout=6)
            # 探测
            c.stocks(market=1, start=0, offset=1)
            return c
        except Exception as e:
            continue
    # 兜底默认
    return Quotes.factory(market=market, timeout=8)

PICKS = ["002407","300319","002805","603386","603078","002579","002134","300285","300037","002446","300322","002549","688549"]

def run():
    try:
        client = tdx_client()
    except Exception as e:
        print(json.dumps({"err": f"tdx_client失败:{e}"}, ensure_ascii=False))
        return
    out = {}
    for code in PICKS:
        sym = "0" + code if code.startswith(("0","3")) else "1" + code  # mootdx: 0深/1沪前缀? 实际finance(symbol=纯代码)
        # mootdx finance symbol 直接传6位代码(无前缀)
        try:
            fin = client.finance(symbol=code)
            if fin is None:
                fin = client.finance(symbol=sym)
        except Exception as e:
            fin = {"err": str(e)}
        # F10 财务分析(含商誉文本)
        try:
            f10 = client.F10(symbol=code, name="财务分析")
            if not f10:
                f10 = client.F10(symbol=sym, name="财务分析")
        except Exception as e:
            f10 = f"ERR:{e}"
        # 商誉提取
        gw = None
        if isinstance(f10, str):
            m = re.search(r"商誉[^\d]{0,6}([\d,\.]+)\s*亿?", f10)
            if m:
                gw = m.group(1)
        out[code] = {"finance": fin if isinstance(fin, dict) else (fin.df.to_dict('records') if hasattr(fin, 'df') else str(fin)), "goodwill_raw": gw, "f10_len": len(f10) if isinstance(f10, str) else 0}
        print(code, out[code], flush=True)
        time.sleep(0.3)
    print("\n===JSON===")
    print(json.dumps(out, ensure_ascii=False, default=str))
    return out

if __name__ == "__main__":
    run()
