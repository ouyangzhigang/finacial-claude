# -*- coding: utf-8 -*-
"""超跌+低估值+业绩预增扫描 — fundamentals-analyst 用"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
from astock_data import sina_financial_report, EM_SESSION
from cn_fetch import factors, quote

# 候选宇宙: 顺风三主线(电子特气/固态电池/6G-通信/PCB) + 低价(≤40元)
CANDIDATES = {
    # 电子特气/半导体材料
    "603078": ("江化微", "电子特气"), "688549": ("中巨芯", "电子特气"),
    "688268": ("华特气体", "电子特气"), "300346": ("南大光电", "电子特气"),
    "002409": ("雅克科技", "电子特气"), "002549": ("凯美特气", "电子特气"),
    "603859": ("和远气体", "电子特气"), "600160": ("巨化股份", "电子特气"),
    "300655": ("晶瑞股份", "电子特气"),
    # 固态电池/硫化物电解质/锂电材料
    "300285": ("国瓷材料", "固态电池"), "300073": ("当升科技", "固态电池"),
    "688005": ("容百科技", "固态电池"), "002805": ("丰元股份", "固态电池"),
    "603200": ("上海洗霸", "固态电池"), "003024": ("联泓新科", "固态电池"),
    "002407": ("多氟多", "固态电池"), "002709": ("天赐材料", "固态电池"),
    "688779": ("长远锂科", "固态电池"), "300890": ("翔丰华", "固态电池"),
    "002340": ("格林美", "固态电池"), "300037": ("新宙邦", "固态电池"),
    # 6G/卫星互联网/通信
    "002194": ("武汉凡谷", "6G通信"), "300134": ("大富科技", "6G通信"),
    "002792": ("通宇通讯", "6G通信"), "603220": ("中贝通信", "6G通信"),
    "688237": ("信科移动", "6G通信"), "300322": ("硕贝德", "6G通信"),
    "300319": ("麦捷科技", "6G通信"), "002446": ("盛路通信", "6G通信"),
    # PCB产业链(钨/钴针扰动)
    "002463": ("沪电股份", "PCB"), "002579": ("中京电子", "PCB"),
    "002134": ("天津普林", "PCB"), "603386": ("广东骏亚", "PCB"),
    "603773": ("沃格光电", "PCB"), "002936": ("中颖电子", "PCB"),
}

def run():
    codes = list(CANDIDATES.keys())
    # 1) 腾讯报价: PE/市值
    sym = ",".join(("sh"+c if c.startswith(("6","9")) else "sz"+c) for c in codes)
    q = quote(sym.split(","))
    # 2) factors: m20 超跌
    rows = []
    for c in codes:
        name, sector = CANDIDATES[c]
        symx = "sh"+c if c.startswith(("6","9")) else "sz"+c
        f = factors(symx, 30)  # 5min缓存
        qt = q.get(c, {})
        pe = qt.get("pe_ttm")
        mcap = qt.get("mktcap_yi")
        price = qt.get("price")
        pct = qt.get("pct")
        turnover = qt.get("turnover")
        m20 = f.get("m20") if f else None
        m5 = f.get("m5") if f else None
        ma20 = f.get("ma20") if f else None
        above_ma20 = f.get("above_ma20") if f else None
        rows.append({
            "code": c, "name": name, "sector": sector,
            "price": price, "pct": pct, "pe": pe, "mktcap": mcap,
            "turnover": turnover, "m20": m20, "m5": m5, "ma20": ma20,
            "above_ma20": above_ma20, "amt20_yi": f.get("amt20_yi") if f else None,
        })
    # 排序: 优先超跌(m20最负) + PE合理(0-40)
    def score(r):
        pe = r["pe"]
        m20 = r["m20"]
        pe_ok = (pe is not None and 0 < pe < 50)
        m20_neg = m20 if (m20 is not None and m20 < 0) else 0
        return (1 if pe_ok else 0, m20_neg)  # pe_ok在前, 越跌越前
    rows.sort(key=score)
    print(json.dumps(rows, ensure_ascii=False, indent=1))
    return rows

if __name__ == "__main__":
    run()
