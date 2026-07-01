# -*- coding: utf-8 -*-
"""全志科技 300458 综合分析:读取三轮 JSON,计算技术/估值/财务/题材/宏观指标"""
import sys, json, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import warnings; warnings.filterwarnings('ignore')

D = r"E:\project\toolkit\output"
def load(n):
    p = os.path.join(D, n)
    if not os.path.exists(p): return {}
    with open(p, encoding='utf-8') as f: return json.load(f)

stock = load("_data_300458.json")
v2 = load("_data_300458_v2.json")
mkt = load("_data_market.json")
A = {"_src": {"stock_keys": list(stock.keys()), "v2_keys": list(v2.keys()), "mkt_keys": list(mkt.keys())}}

def num(x):
    try:
        if x is None: return None
        return float(x)
    except: return None

# ============ 技术面 ============
k5 = v2.get("kline_daily_5y") or []
kd = v2.get("kline_daily") or []
K = k5 if len(k5) >= 250 else kd
A["tech_klen"] = len(K)
if K:
    closes = [num(r.get("close")) for r in K]
    highs = [num(r.get("high")) for r in K]
    lows = [num(r.get("low")) for r in K]
    vols = [num(r.get("volume")) for r in K]
    amts = [num(r.get("amount")) for r in K]
    turns = [num(r.get("turnover")) for r in K]
    n = len(K)
    last = K[-1]
    def ma(i, p):
        if i + 1 < p: return None
        seg = closes[i-p+1:i+1]
        return sum(seg)/p if None not in seg else None
    li = n - 1
    m5, m10, m20, m60, m120, m250 = ma(li,5), ma(li,10), ma(li,20), ma(li,60), ma(li,120), ma(li,250)
    hi250 = max(h for h in highs[-250:] if h is not None)
    lo250 = min(l for l in lows[-250:] if l is not None)
    hi60 = max(h for h in highs[-60:] if h is not None)
    lo60 = min(l for l in lows[-60:] if l is not None)
    last_close = closes[-1]
    pct_rank = (last_close - lo250)/(hi250 - lo250)*100 if hi250 != lo250 else None
    # 月线聚合(近12月)
    monthly = {}
    for r in K:
        ym = str(r.get("date",""))[:7]
        if ym: monthly[ym] = r.get("close")
    months = sorted(monthly.keys())[-12:]
    monthly_closes = [monthly[m] for m in months]
    # 周线聚合(近26周):按 date 截断到周一近似,这里用每5日采样
    weekly_closes = closes[::5][-26:]
    tech = {
        "last_date": last.get("date"),
        "last_close": round(last_close,2) if last_close else None,
        "MA5": round(m5,2) if m5 else None,
        "MA10": round(m10,2) if m10 else None,
        "MA20": round(m20,2) if m20 else None,
        "MA60": round(m60,2) if m60 else None,
        "MA120": round(m120,2) if m120 else None,
        "MA250_年线": round(m250,2) if m250 else None,
        "above_year_line": last_close > m250 if (m250 and last_close) else None,
        "dev_year_line_pct": round((last_close/m250-1)*100,1) if (m250 and last_close) else None,
        "alignment_bull": all(x and closes[-1] > x for x in [m5,m10,m20]) and (m20 and m5>m10>m20),
        "high_250_52w": round(hi250,2),
        "low_250_52w": round(lo250,2),
        "high_60": round(hi60,2),
        "low_60": round(lo60,2),
        "price_pct_rank_250": round(pct_rank,1) if pct_rank is not None else None,
        "dist_to_52w_high_pct": round((last_close/hi250-1)*100,1) if hi250 else None,
        "ret_5d_pct": round((closes[-1]/closes[-6]-1)*100,2) if n>=6 else None,
        "ret_20d_pct": round((closes[-1]/closes[-21]-1)*100,2) if n>=21 else None,
        "ret_60d_pct": round((closes[-1]/closes[-61]-1)*100,2) if n>=61 else None,
        "vol_ma5": round(sum(vols[-5:])/5,0) if n>=5 else None,
        "vol_ma60": round(sum(vols[-60:])/60,0) if n>=60 else None,
        "vol_ratio_5v60": round((sum(vols[-5:])/5)/(sum(vols[-60:])/60),2) if n>=60 else None,
        "turnover_20d_avg_pct": round(sum(turns[-20:])/20*100,2) if n>=20 else None,
        "turnover_5d_avg_pct": round(sum(turns[-5:])/5*100,2) if n>=5 else None,
        "amount_5d_avg_yi": round(sum(amts[-5:])/5/1e8,2) if n>=5 else None,
        "amount_last_yi": round(amts[-1]/1e8,2) if amts[-1] else None,
        "monthly_recent_3": [round(monthly_closes[-1],2), round(monthly_closes[-2],2), round(monthly_closes[-3],2)] if len(monthly_closes)>=3 else None,
        "monthly_trend_up": monthly_closes[-1] > monthly_closes[-3] if len(monthly_closes)>=3 else None,
        "weekly_recent_4": [round(weekly_closes[-1],2), round(weekly_closes[-2],2), round(weekly_closes[-3],2), round(weekly_closes[-4],2)] if len(weekly_closes)>=4 else None,
        "support_near": round(lo60,2),
        "resist_near": round(hi60,2),
        "year_line_price": round(m250,2) if m250 else None,
    }
    A["tech"] = tech

# ============ spot 实时(保留原始+动态解析) ============
spot = v2.get("spot")
A["spot_raw"] = spot
if spot and isinstance(spot, list) and spot:
    s0 = spot[0]
    A["spot_keys"] = list(s0.keys())
    # 动态匹配常见字段
    def find(keys, *hints):
        for k in keys:
            kk = str(k)
            for h in hints:
                if h in kk: return k
        return None
    ks = list(s0.keys())
    pe_k = find(ks,"市盈率","PE","pe")
    pb_k = find(ks,"市净率","PB","pb")
    mv_k = find(ks,"总市值","市值")
    cmv_k = find(ks,"流通")
    close_k = find(ks,"最新价","最新","trade","price") or find(ks,"收盘")
    chg_k = find(ks,"涨跌幅","涨幅")
    turn_k = find(ks,"换手")
    A["spot_parsed"] = {
        "pe": num(s0.get(pe_k)) if pe_k else None,
        "pb": num(s0.get(pb_k)) if pb_k else None,
        "total_mkv": num(s0.get(mv_k)) if mv_k else None,
        "circ_mkv": num(s0.get(cmv_k)) if cmv_k else None,
        "last": num(s0.get(close_k)) if close_k else None,
        "chg_pct": num(s0.get(chg_k)) if chg_k else None,
        "turnover": num(s0.get(turn_k)) if turn_k else None,
    }

# ============ 财务趋势 ============
fi = stock.get("fin_indicator") or []
A["fin_count"] = len(fi)
def find_fi(d):
    for r in fi:
        if r.get("日期") == d: return r
    return None
def pick(r, *keys):
    if not r: return None
    for k in keys:
        if k in r and r[k] is not None: return r.get(k)
    return None
periods = ["2023-03-31","2023-12-31","2024-03-31","2024-12-31","2025-03-31","2025-09-30","2025-12-31","2026-03-31"]
ft = {}
for p in periods:
    r = find_fi(p)
    if r:
        ft[p] = {
            "营收增速_pct": pick(r,"主营业务收入增长率(%)"),
            "净利润增速_pct": pick(r,"净利润增长率(%)"),
            "ROE_pct": pick(r,"净资产收益率(%)","加权净资产收益率(%)"),
            "净利率_pct": pick(r,"销售净利率(%)"),
            "毛利率代理_主营利润率_pct": pick(r,"主营业务利润率(%)"),
            "资产负债率_pct": pick(r,"资产负债率(%)"),
            "流动比率": pick(r,"流动比率"),
            "速动比率": pick(r,"速动比率"),
            "经营现金流_净利润比": pick(r,"经营现金净流量与净利润的比率(%)"),
            "存货周转天数": pick(r,"存货周转天数(天)"),
            "扣非净利润_元": pick(r,"扣除非经常性损益后的净利润(元)"),
            "EPS": pick(r,"摊薄每股收益(元)"),
            "每股经营现金流": pick(r,"每股经营性现金流(元)"),
            "总资产_元": pick(r,"总资产(元)"),
        }
A["fin_trend"] = ft

# fin_abstract 样本(看结构以取营收/净利润年度绝对值)
fa = stock.get("fin_abstract") or []
A["fin_abstract_keys"] = list(fa[0].keys()) if fa else []
A["fin_abstract_sample"] = fa[:8]

fath = stock.get("fin_abstract_ths") or []
A["fin_abstract_ths_keys"] = list(fath[0].keys()) if fath else []
A["fin_abstract_ths_sample"] = fath[:6]

# ============ 概念板块涨幅榜 ============
cl = v2.get("concept_list")
if cl and isinstance(cl, dict):
    rows = cl.get("rows") or []
    A["concept_via"] = cl.get("_via")
    A["concept_count"] = len(rows)
    A["concept_keys"] = list(rows[0].keys()) if rows else []
    if rows:
        ks = list(rows[0].keys())
        name_k = ks[0]
        pct_k = None
        for k in ks:
            kk = str(k)
            if "涨跌幅" in kk or "涨幅" in kk or "change" in kk.lower():
                pct_k = k; break
        if pct_k:
            rs = sorted(rows, key=lambda r: num(r.get(pct_k)) if num(r.get(pct_k)) is not None else -99999, reverse=True)
            A["concept_top25"] = [{"name": r.get(name_k), "pct": r.get(pct_k)} for r in rs[:25]]
            A["concept_bottom10"] = [{"name": r.get(name_k), "pct": r.get(pct_k)} for r in rs[-10:]]

# ============ 宏观 ============
A["shrzgm_recent6"] = (mkt.get("shrzgm") or [])[-6:]
A["usd_cny_recent8"] = (mkt.get("usd_cny") or [])[-8:]
A["market_activity_raw"] = mkt.get("market_activity")
if mkt.get("market_activity") and isinstance(mkt.get("market_activity"), list):
    A["market_activity_keys"] = list(mkt["market_activity"][0].keys()) if mkt["market_activity"] else []

# ============ 数据缺失声明 ============
missing = []
for k in ["northbound","fund_flow","gdhs","info_em"]:
    v = v2.get(k)
    if isinstance(v, dict) and "_error" in v: missing.append(k)
for k in ["gdp","pmi","cpi","ppi","money_supply","lpr","zt_pool"]:
    if isinstance(mkt.get(k), dict) and "_error" in mkt.get(k): missing.append(k)
A["data_missing"] = missing

out = os.path.join(D, "_analysis.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(A, f, ensure_ascii=False, default=str, indent=1)
print("=== analysis done ->", out, "===")
print(json.dumps({k: (v if not isinstance(v,(list,dict)) else f"<{type(v).__name__} len={len(v)}>") for k,v in A.items()}, ensure_ascii=False, indent=1))
