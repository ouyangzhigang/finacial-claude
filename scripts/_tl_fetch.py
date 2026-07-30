#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Technical-liquidity consolidated fetcher for 40 candidates.
- chunked quote (8/batch) -> amount1d/turnover/pct/float_mktcap/open/high/low/name
- kline(25) per code -> detailed short-term factors
- factors() -> amt20_yi/breakout cross-check
Dumps one JSON to stdout.
"""
import sys, json, math
sys.path.insert(0, 'scripts')
import cn_fetch

# code -> name (from sector-analyst, for join safety) ; also used to map quote key (no prefix)
CANDS = [
 ("sh600028","中国石化"),("sh601600","中国铝业"),("sz000506","招金黄金"),("sh603993","洛阳钼业"),
 ("sh601225","陕西煤业"),("sh600547","山东黄金"),("sh601899","紫金矿业"),("sh600111","北方稀土"),
 ("sh600362","江西铜业"),("sh601088","中国神华"),("sh600309","万华化学"),("sh601857","中国石油"),
 ("sz002258","利尔化学"),("sh603327","福蓉科技"),("sh601003","柳钢股份"),("sz000009","中国宝安"),
 ("sz300505","川金诺"),("sz002827","高争民爆"),("sz002428","云南锗业"),("sh601390","中国中铁"),
 ("sh601668","中国建筑"),("sh601669","中国电建"),("sh601766","中国中车"),("sh601800","中国交建"),
 ("sh601919","中远海控"),("sh600667","太极实业"),("sh601618","中国中冶"),("sh601186","中国铁建"),
 ("sz000025","特力A"),("sh600629","华建集团"),("sz000721","西安饮食"),("sh600712","南宁百货"),
 ("sh600900","长江电力"),("sh600396","华电辽能"),("sh601318","中国平安"),("sz002185","华天科技"),
 ("sz002657","中科金财"),("sh600418","江淮汽车"),("sh600513","联环药业"),("sz002846","英联股份"),
]
CODES = [c for c,_ in CANDS]

def rsi(closes, n=14):
    if len(closes) < n+1: return None
    gains=[]; losses=[]
    for i in range(1, n+1):
        d = closes[-(n+1)+i] - closes[-(n+1)+i-1]
        # index: closes[len-n-1 .. len-1]; simpler recompute
    # redo cleanly
    seg = closes[-(n+1):]
    g=l=0.0
    for i in range(1,len(seg)):
        d=seg[i]-seg[i-1]
        if d>0: g+=d
        else: l+=-d
    ag=g/n; al=l/n
    if al==0: return 100.0
    rs=ag/al
    return round(100-100/(1+rs),1)

def analyze(code):
    arr = cn_fetch.kline(code, 25)
    f = cn_fetch.factors(code, 25) or {}
    if not arr or len(arr) < 20:
        return {"code": code, "kline_missing": True, "factors": f}
    closes=[float(r[2]) for r in arr]
    highs=[float(r[3]) for r in arr]
    lows=[float(r[4]) for r in arr]
    vols=[float(r[5]) if r[5] else 0.0 for r in arr]
    opens=[float(r[1]) for r in arr]
    dates=[r[0] for r in arr]
    last=closes[-1]
    def mom(d):
        return round((closes[-1]-closes[-1-d])/closes[-1-d]*100,2) if len(closes)>d else None
    m5=mom(5); m10=mom(10); m20=mom(20)
    ma5=round(sum(closes[-5:])/5,3); ma10=round(sum(closes[-10:])/10,3)
    ma20=round(sum(closes[-20:])/20,3) if len(closes)>=20 else None
    above_ma20 = (ma20 is not None and last>ma20)
    above_ma5 = last>ma5
    # breakout: close > max high of prior 20 (exclude today)
    prior_high=max(highs[-21:-1]) if len(highs)>=21 else max(highs[:-1])
    breakout = last>prior_high
    # daily returns last 5
    rets=[ (closes[i]-closes[i-1])/closes[i-1]*100 for i in range(len(closes)-5,len(closes)) ]
    up_days=sum(1 for r in rets if r>0)
    total5=(closes[-1]/closes[-6]-1)*100 if len(closes)>6 else None
    max_day=max(rets) if rets else None
    min_day=min(rets) if rets else None
    concentration=round(abs(max_day)/abs(total5),2) if (total5 and abs(total5)>0.01 and max_day is not None) else None
    uniformity=round(up_days/5*(1-(concentration if concentration and total5 and total5>0 else 0)),2)
    # volume health: last 10 days up vs down vol
    r10=[ (closes[i]-closes[i-1])/closes[i-1] for i in range(len(closes)-10,len(closes)) ]
    v10=vols[-10:]
    upv=[v10[i] for i in range(10) if r10[i]>0]
    dnv=[v10[i] for i in range(10) if r10[i]<=0]
    up_avg=sum(upv)/len(upv) if upv else 0
    dn_avg=sum(dnv)/len(dnv) if dnv else 0
    vol_health=round(up_avg/dn_avg,2) if dn_avg>0 else None
    # momentum acceleration: recent5 rate vs prior5 rate (m5/5 vs (m10-m5)/5)
    if m5 is not None and m10 is not None:
        recent=m5/5.0; prior=(m10-m5)/5.0
        accel=round(recent-prior,2)
    else:
        accel=None
    # pullback depth from 20-day peak close
    peak=max(closes[-20:]) if len(closes)>=20 else max(closes)
    pullback_depth=round((last-peak)/peak*100,2)  # negative = below peak
    # pullback volume: last5 vs prior5
    v5avg=sum(vols[-5:])/5 if len(vols)>=5 else None
    v5prev=sum(vols[-10:-5])/5 if len(vols)>=10 else None
    pullback_vol=round(v5avg/v5prev,2) if (v5prev and v5prev>0) else None
    r=rsi(closes,14)
    return {
        "code":code,"last":last,"date":dates[-1],
        "m5":m5,"m10":m10,"m20":m20,"ma5":ma5,"ma10":ma10,"ma20":ma20,
        "above_ma20":above_ma20,"above_ma5":above_ma5,"breakout":breakout,
        "up_days5":up_days,"max_day_gain":max_day,"min_day":min_day,
        "total5":round(total5,2) if total5 is not None else None,
        "concentration":concentration,"uniformity":uniformity,
        "vol_health":vol_health,"momentum_accel":accel,
        "pullback_depth":pullback_depth,"pullback_vol":pullback_vol,
        "v5avg":round(v5avg) if v5avg else None,"v5prev":round(v5prev) if v5prev else None,
        "rsi14":r,
        "amt20_yi":f.get("amt20_yi"),"breakout_f":f.get("breakout"),
        "v5f":f.get("v5"),"v20f":f.get("v20"),
        "kline_len":len(arr),
    }

def main():
    # chunked quote
    quotes={}
    for i in range(0,len(CODES),8):
        chunk=CODES[i:i+8]
        q=cn_fetch.quote(chunk)
        if isinstance(q,dict): quotes.update(q)
    # quote key is bare code e.g. '600028'
    analyses={}
    for code in CODES:
        try:
            analyses[code]=analyze(code)
        except Exception as e:
            analyses[code]={"code":code,"error":str(e)}
    out={"quotes":quotes,"analyses":analyses}
    print(json.dumps(out,ensure_ascii=False))

if __name__=='__main__':
    main()
