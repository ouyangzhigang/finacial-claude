# -*- coding: utf-8 -*-
"""深核 v2: 东财F10主要指标 (verify=False绕SSL) + 商誉"""
import sys, os, json, re, warnings
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
warnings.filterwarnings('ignore')
import urllib.request as ur, ssl
CTX = ssl._create_unverified_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch(url):
    req = ur.Request(url, headers={"User-Agent": UA})
    try:
        with ur.urlopen(req, timeout=15, context=CTX) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return f"ERR:{e}"

def main_targets(code):
    # 东财F10 主要财务指标(近6期): ROE/净利/营收/毛利率/净利率
    exch = "SH" if code.startswith(("6","9")) else ("BJ" if code.startswith(("8","4")) else "SZ")
    url = f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/MainTargetAjax?type=0&code={exch}{code}"
    txt = fetch(url)
    if txt.startswith("ERR"): return {"err": txt}
    try:
        arr = json.loads(txt)["Data"]
    except Exception as e:
        return {"err": f"parse:{e}|{txt[:120]}"}
    out = []
    for it in arr[:6]:
        out.append({
            "date": it.get("REPORT_DATE", "")[:10],
            "eps": it.get("EPSJB"),
            "rev_yoy": it.get("YYZSRTBZZ"),  # 营收同比%
            "np_yoy": it.get("YYJLRTBZZ"),    # 净利润同比%
            "roe": it.get("ROEJQ"),
            "npm": it.get("XSJLL"),           # 销售净利率
            "gpm": it.get("XSMLL"),           # 销售毛利率
        })
    return out

PICKS = ["002407","300319","002805","603386","603078","002579","002134","300285","300037","002446","300322","002549"]
def run():
    out = {}
    for c in PICKS:
        out[c] = main_targets(c)
        print(c, out[c], flush=True)
    print("\n===JSON===")
    print(json.dumps(out, ensure_ascii=False))
    return out

if __name__ == "__main__":
    run()
