#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Technical Liquidity Agent — batch screening of 73 candidates (2026-07-21).
Uses East Money push2his HTTP + NO_PROXY='*' bypass for Whistle proxy.
Reads sector-analyst.json, writes technical-liquidity.json."""
import json, os, sys, time
from datetime import datetime

os.chdir(r"E:/finacial-invest")
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import pandas as pd
import requests
requests.packages.urllib3.disable_warnings()

INPUT  = r"E:/finacial-invest/data/runs/20260721_short-term-picks/sector-analyst.json"
OUTPUT = r"E:/finacial-invest/data/runs/20260721_short-term-picks/technical-liquidity.json"
EM_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
BEG    = "20260601"
END    = "20260721"

def secid_prefix(code):
    c = code.strip()
    if c.startswith(("6", "688", "9")):
        return "1." + c
    return "0." + c

# ==== STEP 1: Load candidates ====
with open(INPUT, "r", encoding="utf-8") as f:
    sdata = json.load(f)

candidates = []
for item in sdata["candidates"]:
    candidates.append({
        "code":       item["code"],
        "name":       item["name"],
        "sector":     item.get("sector",""),
        "price":      item.get("price", 0),
        "amountYi":   item.get("amountYi", 0),
        "turnover":   item.get("turnover", 0),
        "marketCapYi":item.get("marketCapYi", 0),
        "changePct":  item.get("changePct", 0),
        "pe":         item.get("pe", None),
        "source":     item.get("source", ""),
    })
print("[1] Loaded {} candidates.".format(len(candidates)), flush=True)

# ==== STEP 2: Fetch K-line ====
results_raw = {}

for idx, c in enumerate(candidates):
    code = c["code"]
    try:
        r = requests.get(EM_URL, params={
            "secid": secid_prefix(code),
            "fields1":"f1,f2,f3,f4,f5,f6",
            "fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt":"101","fqt":"1","beg":BEG,"end":END,"lmt":"35"
        }, timeout=8)
        d = r.json()
        klines_raw = d.get("data",{}).get("klines",[])
        if not klines_raw:
            results_raw[code] = None
            continue
        rows = []
        for ln in klines_raw:
            p = ln.split(",")
            if len(p)<8: continue
            rows.append({"date":p[0],"open":float(p[1]),"close":float(p[2]),
                          "high":float(p[3]),"low":float(p[4]),
                          "volume":float(p[5]),"amount":float(p[6]),
                          "pctChg":float(p[7])})
        df = pd.DataFrame(rows)
        if len(df) < 20:
            results_raw[code] = None
            continue
        results_raw[code] = df
    except Exception as e:
        results_raw[code] = None
        print("  WARN: {} fetch error: {}".format(code, e))
    if (idx+1)%15==0:
        print("  [2] Fetched {}/{}".format(idx+1,len(candidates)))

valid_n = sum(1 for v in results_raw.values() if v is not None)
print("[2] K-line done. Valid: {} / {}".format(valid_n, len(candidates)), flush=True)

# ==== STEP 3: Calculate factors ====
def calc_factors(code, df):
    c = df["close"].values.astype(float)
    v = df["volume"].values.astype(float)
    a = df["amount"].values.astype(float)
    h = df["high"].values.astype(float)
    n = len(c)

    def ret(d):
        return round((c[-1]/c[-(d+1)]-1)*100, 2) if n>d else None

    m5=ret(4); m10=ret(9); m20=ret(19)
    ma5=round(c[-5:].mean(),2) if n>=5 else None
    ma10=round(c[-10:].mean(),2) if n>=10 else None
    ma20=round(c[-min(20,n):].mean(),2) if n>=3 else None

    avg_amt20 = a[-20:].mean() if n>=20 else a.mean()
    avg_amt_yi = round(avg_amt20/1e8, 2)

    above_ma5  = bool(c[-1]/ma5>1.0)  if ma5 else False
    above_ma10 = bool(c[-1]/ma10>1.0) if ma10 else False
    above_ma20 = bool(c[-1]/ma20>1.0) if ma20 else False
    pct_above_m5  = round((c[-1]/ma5-1)*100, 2)  if ma5 else 0
    pct_above_m20 = round((c[-1]/ma20-1)*100, 2) if ma20 else 0

    pct = [(c[i]/c[i-1]-1)*100 for i in range(1,n)]
    up_days5 = sum(1 for x in pct[-5:] if x>0) if pct else 0

    vol_up=[v[i] for i in range(1,n) if pct[i-1]>0]
    vol_down=[v[i] for i in range(1,n) if pct[i-1]<=0]
    if vol_up and vol_down:
        vu=sum(vol_up)/len(vol_up); vd=sum(vol_down)/len(vol_down)
        vol_ratio=round(vu/vd, 2)
        vol_hs=min(100, vu/vd*40)
    else:
        vol_ratio=1.0; vol_hs=50.0

    accel=round(m5/5-(m10-m5)/5,2) if m5 is not None and m10 is not None else 0
    breakout=bool(h[-1]>=max(h[-20:])*0.998) if n>=20 else False

    std20=float(pd.Series(c[-20:]).std()) if n>=20 else 0
    boll_lower=(ma20-2*std20) if std20 and ma20 else None
    near_boll=bool(boll_lower and c[-1]<=boll_lower*1.02)

    gains=[max(p,0) for p in pct[-14:]]
    losses=[abs(p) for p in pct[-14:] if p<0]
    rs_a=sum(gains)/14 if gains else 0
    ls_a=sum(losses)/14 if losses else 1.0
    rsi14=round(100-100/(1+rs_a/ls_a),2) if ls_a else 50.0

    peak20=max(c[:-20]) if n>20 else c[0]
    low20=min(c[:20]) if n>20 else c[0]
    mean_rev=bool(c[-1]<low20*1.05 and peak20>low20*1.15)
    peak_p=float(max(c))
    pullback_depth=round((peak_p-c[-1])/peak_p*100, 2)
    if n>=3:
        pv="缩量" if v[-1]<v[-3:].mean()*0.8 else "放量" if v[-1]>v[-3:].mean()*1.2 else "持平"
    else: pv="N/A"

    # Exhaustion probability
    ex_prob=30
    if m5 is not None and m20 is not None:
        if m20>25 and m5<0: ex_prob=85
        elif m5>15 and m20>25: ex_prob=80
        elif m5>20 and m20>0: ex_prob=75
        elif m5>15 and m20>0: ex_prob=60
        elif m5<0 and m20>20: ex_prob=50
        elif m5<0 and m20<0: ex_prob=5
        elif m5>0 and m20>0: ex_prob=10
    elif m5 is not None:
        if m5>15: ex_prob=50
        elif m5>5: ex_prob=25
        elif m5<-5: ex_prob=15

    # Entry type & score
    sc=0; etype="观望"
    if ex_prob>=70:
        etype="透支排除"; sc-=20
    elif ex_prob>=50:
        etype="高位回调审查"; sc-=10

    if ex_prob<70:
        if ma20 and above_ma20 and m5 is not None and -8<=m5<=-2:
            etype="健康回调买点"; sc+=20
        elif breakout and above_ma5:
            etype="突破回踩确认"; sc+=15
        elif m20 is not None and m5 is not None and m20<-15 and m5>0 and vol_hs>50:
            etype="超跌反弹启动"; sc+=10
        elif m5 is not None and m5>10 and pct_above_m5>5 and vol_hs<30:
            etype="追涨入场"; sc-=15

    mr_sig="无"
    if mean_rev: mr_sig="优质超跌"; sc+=12
    elif near_boll and len(pct)>0 and pct[-1]>0: mr_sig="布林下轨企稳"; sc+=8
    sc=max(-20,min(20,sc))

    if m5 and m10 and m20 and m5>0 and m10>0 and m20>0 and above_ma20:
        tlevel="多头排列上升趋势"
    elif ex_prob>=70:
        tlevel="高位回调派发区"
    elif m20 is not None and m20<-15 and m5 and m5>0:
        tlevel="超跌反弹启动区"
    elif above_ma20:
        tlevel="站上MA20蓄势"
    elif above_ma10:
        tlevel="跌破MA20震荡"
    else:
        tlevel="弱势整理"

    return {
        "m5":m5,"m10":m10,"m20":m20,
        "ma5":ma5,"ma10":ma10,"ma20":ma20,
        "momentumUniformity":up_days5,
        "volumeHealthScore":vol_hs,
        "volumeRatio":vol_ratio,
        "momentumAccel":accel,
        "breakout":breakout,
        "aboveMA20":above_ma20,
        "aboveMA5":above_ma5,
        "aboveMA10":above_ma10,
        "rsi14":rsi14,
        "bollNearLower":near_boll,
        "pullbackDepth":pullback_depth,
        "pullbackVolume":pv,
        "entryType":etype,
        "entryScore":sc,
        "meanReversionSignal":mr_sig,
        "exhaustionProb":ex_prob,
        "technicalLevel":tlevel,
        "avgAmount20d":avg_amt_yi,
    }

print("[3] Computing factors...", flush=True)
factor_cache = {}
codes_with_data = sorted(results_raw.keys(), key=lambda x: results_raw[x] is not None, reverse=True)
for idx, code in enumerate(codes_with_data):
    if results_raw[code] is not None:
        factor_cache[code] = calc_factors(code, results_raw[code])
    if (idx+1)%20==0:
        print("  [3] Factors: {}/{}".format(idx+1, len(codes_with_data)))

print("[3] Factor computation done: {} valid".format(len(factor_cache)), flush=True)

# ==== STEP 4: Hard Gate Filtering ====
pass_list = []
reject_list = []

for c in candidates:
    code=c["code"]; name=c["name"]
    fac=factor_cache.get(code)
    reasons=[]

    # Price >= 40 => 1w account constraint
    price=c["price"]
    if price>=40:
        reasons.append("价格{:.2f}>40元(1w账户不可配)".format(price))

    # ST check
    if "ST" in name.upper():
        reasons.append("ST股")

    # Turnover (snapshot proxy)
    tv=c["turnover"]
    if tv<1.0:
        reasons.append("换手率{:.2f}%<1%(偏冷)".format(tv))
    elif tv>7.0:
        reasons.append("换手率{:.2f}%>7%(偏高)".format(tv))

    # Market cap >= 30亿
    mc=c["marketCapYi"]
    if mc and mc<30:
        reasons.append("流通市值{:.1f}亿<30亿".format(mc))

    # Amount >= 1亿 (K-line derived)
    if fac and fac["avgAmount20d"]<1.0:
        reasons.append("日均成交额{:.2f}亿<1亿".format(fac["avgAmount20d"]))

    # Exhaustion: M5 > 30%
    if fac and fac["m5"] is not None and fac["m5"]>30:
        reasons.append("近5日涨幅{:.1f}%>30%(透支)".format(fac["m5"]))

    # Exhaustion: M20 > 30%
    if fac and fac["m20"] is not None and fac["m20"]>30:
        reasons.append("近20日涨幅{:.1f}%>30%(透支)".format(fac["m20"]))

    # Limit up
    cp=c["changePct"]
    if cp is not None and cp>=9.5:
        reasons.append("+{:.1f}%涨停封死".format(cp))

    if reasons:
        reject_list.append({"code":code,"name":name,"reason":"; ".join(reasons)})
    else:
        pass_list.append({
            "code":code,"name":name,"price":round(price,2),
            "avgAmount20d":fac["avgAmount20d"] if fac else round(c["amountYi"],2),
            "turnover20d":round(tv,2),
            "marketCap":round(mc,2) if mc else None,
            "pass":True
        })

print("[4] Gate: {} pass, {} reject out of {}".format(
    len(pass_list), len(reject_list), len(candidates)), flush=True)

# ==== STEP 5: Build factor output for pass stocks ====
factors_out = []
for p in pass_list:
    code=p["code"]; fac=factor_cache.get(code)
    if not fac:
        # Minimal entry for no-KLINE pass
        factors_out.append({
            "code":code,"m5":None,"m10":None,"m20":None,
            "momentumUniformity":None,"volumeHealthScore":None,
            "volumeRatio":None,"momentumAccel":None,
            "entryType":"数据缺失降级","entryScore":0,
            "meanReversionSignal":"未知","pullbackDepth":None,
            "pullbackVolume":"未知","exhaustionProb":50,
            "breakout":False,"aboveMA20":False,
            "rps":None,"technicalLevel":"数据缺失"
        })
        continue

    factors_out.append({
        "code":code,
        "m5":fac["m5"],"m10":fac["m10"],"m20":fac["m20"],
        "momentumUniformity":fac["momentumUniformity"],
        "volumeHealthScore":fac["volumeHealthScore"],
        "volumeRatio":fac["volumeRatio"],
        "momentumAccel":fac["momentumAccel"],
        "entryType":fac["entryType"],
        "entryScore":fac["entryScore"],
        "meanReversionSignal":fac["meanReversionSignal"],
        "pullbackDepth":fac["pullbackDepth"],
        "pullbackVolume":fac["pullbackVolume"],
        "exhaustionProb":fac["exhaustionProb"],
        "breakout":fac["breakout"],
        "aboveMA20":fac["aboveMA20"],
        "rsi14":fac["rsi14"],
        "bollNearLower":fac["bollNearLower"],
        "rps":fac["m5"],
        "technicalLevel":fac["technicalLevel"],
    })

factors_out.sort(key=lambda x: x.get("entryScore",0), reverse=True)

# ==== STEP 6: Summary & Output ====
rej_grp={}
for r in reject_list:
    first=r["reason"].split("; ")[0]
    rej_grp[first]=rej_grp.get(first,0)+1

summary_parts=["候选{}只,过关{}只,剔除{}只".format(len(candidates),len(pass_list),len(reject_list))]
for reason,count in sorted(rej_grp.items(),key=lambda x:-x[1]):
    summary_parts.append("{}:{}只".format(reason,count))

etype_cnt={}
for ff in factors_out:
    et=ff.get("entryType","?")
    etype_cnt[et]=etype_cnt.get(et,0)+1
eparts="|".join(["{}:{}".format(k,v) for k,v in etype_cnt.items()])
summary_parts.append("入场分布:"+eparts)

final_summary="|".join(summary_parts)

pass_codes=[pp["code"] for pp in pass_list]

result={
    "runId":"20260721_short-term-picks",
    "asOf":"20260721",
    "goal":"short-term-picks",
    "agent":"technical-liquidity",
    "fetchedAt":"20260721",
    "data":{
        "pass":pass_list,
        "reject":reject_list,
        "factors":factors_out,
    },
    "summary":final_summary,
    "keyFields":{
        "passCodes":",".join(pass_codes),
        "passCount":len(pass_list),
        "rejectCount":len(reject_list),
        "totalCandidates":len(candidates),
        "validKLine":valid_n,
    },
}

outdir=os.path.dirname(OUTPUT)
os.makedirs(outdir, exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as fout:
    json.dump(result, fout, ensure_ascii=False, indent=2)

print("\n[DONE] Written to {}".format(OUTPUT), flush=True)
print(final_summary, flush=True)
