#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Technical Liquency Agent — Batch screening K-line factors + liquidity hard-gates.
Uses Tencent snapshot + SINA K-line (more reliable than Tencent K-line in long-running scripts).
"""
import json, sys, time, ssl, urllib.request, os
from concurrent.futures import ThreadPoolExecutor, as_completed

SSL_NO_VERIFY = os.environ.get("CN_FETCH_SSL_NO_VERIFY", "1") in ("1","true","yes")
_CTX = ssl._create_unverified_context() if SSL_NO_VERIFY else ssl.create_default_context()
UA_SNAP = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
UA_KLINE = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}
TIMEOUT = 25

ALL_CODES = [
    # Banking / Financials
    "sh601318","sh600036","sh601166","sh600000","sz000001","sz000725",
    # Consumer / Food & Beverage
    "sz000858","sh603369","sh603198","sz002891",
    # Healthcare
    "sz002294","sh600196","sz300015","sz002001",
    # Auto / Industrial / Tech
    "sz002475","sz000333","sz000651","sz002230","sz002352","sz002714",
    # Utilities / Energy
    "sh600900","sh601985","sz003816","sh600795","sz000543","sh600011",
    "sz000899","sh601369","sh600236",
    # Manufacturing / Materials
    "sh601601","sh601888","sh600031","sh600585","sh601689","sh601225",
    "sh601728","sh601877","sh603259","sh601127",
]
PRICE_THRESHOLD = 40.0

def _fetch(url, headers=None):
    hdrs = dict(UA_SNAP)
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

# ── Snapshot (Tencent qt.gtimg.cn) ────────────────────────────────

def get_snap(code):
    txt = _fetch(f"http://qt.gtimg.cn/q={code}")
    if txt:
        p = txt.strip().split("~")
        if len(p) >= 50:
            try:
                price   = float(p[3]) if p[3] else 0.0
                pct     = float(p[32]) if p[32] else 0.0
                amt_wan = float(p[37]) if p[37] else 0.0
                tp      = float(p[38]) if p[38] else 0.0
                mc      = float(p[44]) if p[44] else 0.0
                name    = p[1] if len(p) > 1 else ""
                parts35 = p[35].split("/") if len(p) > 35 else []
                amt_pv  = float(parts35[0])*float(parts35[1])*100/1e8 if len(parts35)>=3 else 0.0
                if amt_wan > 0 and amt_pv > 0:
                    amt_yi = min(amt_wan/1e4, amt_pv)
                elif amt_wan > 0:
                    amt_yi = amt_wan / 1e4
                elif amt_pv > 0:
                    amt_yi = amt_pv
                else:
                    amt_yi = 0.0
                if amt_yi > 0:
                    return {"price": round(price,2), "pct": round(pct,2),
                            "amt_yi": round(amt_yi,2), "turnover_pct": round(tp,2),
                            "mktcap_yi": round(mc,2), "name": name}
            except Exception:
                pass
    # Fallback: Sina hq_str
    try:
        url = f"http://hq.sinajs.cn/list={code}"
        resp = urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA_SNAP, Referer="https://finance.sina.com.cn/")),
                                      timeout=TIMEOUT, context=_CTX)
        body = resp.read().decode("gbk", errors="ignore")
        if '="' in body:
            f = body.split('="')[1].rstrip('"\r\n').split(",")
            if len(f) >= 10:
                prev = float(f[2]) if f[2] else 0.0
                return {"price": round(float(f[3]),2),
                        "pct": round((float(f[3])-prev)/prev*100, 2) if prev > 0 else 0.0,
                        "amt_yi": round(float(f[9])/1e8, 2) if f[9] else 0.0,
                        "turnover_pct": 0.0, "mktcap_yi": 0.0, "name": f[0]}
    except Exception:
        pass
    return None

# ── K-line (SINA — more reliable in-process) ─────────────────────

def fetch_kline_sina(code):
    """Fetch daily K-line from SINA finance. Returns list of dicts or None."""
    url = (f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={code}&scale=240&ma=no&datalen=40")
    raw = _fetch(url, headers=UA_KLINE)
    if not raw:
        return None
    try:
        arr = json.loads(raw)
        parsed = []
        for x in arr:
            if not isinstance(x, dict):
                continue
            try:
                parsed.append({
                    "date": str(x.get("day", "")),
                    "open": float(x.get("open", 0)),
                    "close": float(x.get("close", 0)),
                    "high": float(x.get("high", 0)),
                    "low": float(x.get("low", 0)),
                    "vol": float(x.get("volume", 0)),
                })
            except (ValueError, TypeError):
                continue
        return parsed if parsed else None
    except Exception:
        return None

def batch_fetch_klines(codes, delay=0.3):
    """Serial fetch with small delay between requests."""
    result = {}
    for i, code in enumerate(codes):
        kd = fetch_kline_sina(code)
        result[code] = kd
        if i < len(codes) - 1:
            time.sleep(delay)
    return result

# ── Factors ───────────────────────────────────────────────────────

def compute_factors(closes, vols, code_name):
    n = len(closes)
    def mom(d):
        if n <= d: return None
        return round((closes[-1]-closes[-1-d])/closes[-1-d]*100, 2)
    m5v=mom(5); m10v=mom(10); m20v=mom(20)
    ma5=round(sum(closes[-5:])/5,2); ma10=round(sum(closes[-10:])/10,2); ma20=round(sum(closes[-20:])/20,2)
    v5=sum(vols[-5:])/5; v20=sum(vols[-20:])/20; vr=round(v5/v20,2) if v20>0 else 1.0
    am5=closes[-1]>ma5; am10=closes[-1]>ma10; am20=closes[-1]>ma20
    ud=sum(1 for i in range(-1,-6,-1) if i>=-(n-1) and closes[i]>closes[i-1])
    uv=[vols[-(i+1)] for i in range(5) if i<n and closes[-(i+1)]>closes[-(i+2)] and i+1<n]
    dv=[vols[-(i+1)] for i in range(5) if i+1<n and closes[-(i+1)]<=closes[-(i+2)]]
    vh=round(sum(uv)/len(uv)/max(sum(dv)/len(dv),1e-9),2) if uv else 0.0
    bt=am20 and (vols[-1]>v5*1.5 if v5>0 else False)
    h20=max(closes[-20:])
    pd=round((closes[-1]-h20)/h20*100,2) if h20>0 else 0.0
    sc=0; et="neutral"
    if am20 and -12<pd<-2 and vr<0.9 and (m5v or 0)<0: sc+=20; et="健康回调买点"
    elif m20v is not None and m20v<-15 and m5v is not None and m5v>0 and vr>1.1: sc+=10; et="超跌反弹启动"
    if m5v is not None and m5v>15 and pd>-3: sc-=15; et="追涨入场透支"
    if m20v is not None and m20v>20 and m5v is not None and m5v<0 and not am5: sc-=20; et="高位派发主升浪结束"
    if m20v is not None and m20v<-10 and m5v is not None and 0<m5v<10:
        sc+=5
        if et=="neutral": et="优质股超跌"
    ep=0.2; el="正常区间"
    if m20v is not None and m20v>25 and m5v is not None and m5v<0: ep=0.85; el="20d涨>25%且5日转负"
    elif m5v is not None and m5v>15 and pd>-3: ep=0.70; el="5d涨>15%且接近高位"
    elif m5v is not None and m5v>10: ep=0.30; el="启动期"
    if am5 and am10 and am20: tl="多头排列-上涨趋势"
    elif am20 and not am5: tl="站上MA20-MA5下方整理"
    elif am20: tl="站稳MA20-中性偏多"
    else: tl="跌破MA20-弱势整理"
    accel=round(((m5v or 0)/5-((m10v or 0)-(m5v or 0))/5),2)
    rps=round((m5v or 0)/max(abs(m20v or 0.1),0.1),2)
    return {"code": code_name.get("__code",""), "m5":m5v, "m10":m10v, "m20":m20v,
            "momentumUniformity":ud, "volumeHealth":vh, "momentumAccel":accel,
            "entryType":et, "entryScore":sc, "meanReversionSignal":"none",
            "pullbackDepth":pd, "pullbackVolume":vr,
            "exhaustionProb":ep, "exhaustionLabel":el,
            "breakout":bt, "breakoutLevel":round(h20,2) if h20>0 else None,
            "aboveMA20":am20, "aboveMA5":am5, "aboveMA10":am10,
            "rps":rps, "technicalLevel":tl}

# ── Main ───────────────────────────────────────────────────────────

def main():
    print("[TL] Starting...", file=sys.stderr)
    t0 = time.time()
    snap_cache = {}

    # Step 1: Snapshots (parallel OK)
    print("[TL] Fetching snapshots...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(get_snap, c): c.upper() for c in ALL_CODES}
        for f in as_completed(futs):
            code = futs[f]
            try:
                s = f.result()
                if s: snap_cache[code] = s
            except Exception:
                pass
    ok = sum(1 for s in snap_cache.values() if s)
    print("[TL] Snapshots OK: {}/{}".format(ok, len(ALL_CODES)), file=sys.stderr)

    # Step 2: Price filter (<40) + AMT preliminary (>0)
    pre_ok = []
    reject = []
    for code in ALL_CODES:
        uc = code.upper()
        s = snap_cache.get(uc)
        if not s:
            reject.append({"code": code, "name": "", "reason": "快照获取失败"})
            continue
        pr = s["price"]; amt = s.get("amt_yi", 0)
        if pr >= PRICE_THRESHOLD:
            reject.append({"code": code, "name": s.get("name",""),
                           "reason": "价格{:.2f}>40元(1w账户约束)".format(pr)})
            continue
        if amt <= 0:
            reject.append({"code": code, "name": s.get("name",""),
                           "reason": "成交额为0(行情异常)"})
            continue
        pre_ok.append((uc, s))
    print("[TL] Pre-filtered: {} remain, {} rejected".format(len(pre_ok), len(reject)), file=sys.stderr)

    # Step 3: K-lines (SINA API, serialized)
    k_codes = [uc for uc, _ in pre_ok]
    print("[TL] Fetching K-lines (SINA, serial)... ({})".format(len(k_codes)), file=sys.stderr)
    raw_klines = batch_fetch_klines(k_codes, delay=0.3)

    kline_map = {}
    for uc in k_codes:
        kd = raw_klines.get(uc)
        if kd and len(kd) >= 20:
            kline_map[uc] = {"kd": kd, "snap": snap_cache[uc]}
        else:
            nm = snap_cache[uc].get("name","") if uc in snap_cache else ""
            reject.append({"code": uc, "name": nm,
                           "reason": "K线数据不足(n={})".format(len(kd) if kd else 0)})
    print("[TL] K-lines OK: {}".format(len(kline_map)), file=sys.stderr)

    # Step 4: Compute factors + liquidity hard-gates
    pass_entries = []
    factor_list = []
    for uc, sinfo in pre_ok:
        kf = kline_map.get(uc)
        if not kf:
            continue
        kd = kf["kd"]; snap = kf["snap"]
        closes = [r["close"] for r in kd]; vols = [r["vol"] for r in kd]
        amt20 = snap.get("amt_yi",0); tp=snap.get("turnover_pct",0); mc=snap.get("mktcap_yi",0)
        gf = []
        if amt20 > 0 and amt20 < 1: gf.append("日均成交{:.2f}亿<1亿".format(amt20))
        if 0 < tp < 1: gf.append("换手{}%<1%(偏冷)".format(tp))
        elif tp > 7: gf.append("换手{}%>7%(高位派发警惕)".format(tp))
        if 0 < mc < 30: gf.append("市值{:.1f}亿<30亿".format(mc))
        if gf:
            reject.append({"code": uc, "name": snap.get("name",""),
                           "reason": "; ".join(gf)})
            continue
        fd = compute_factors(closes, vols, {"__code": uc})
        factor_list.append(fd)
        pass_entries.append({"code": uc, "name": snap.get("name",""),
                             "price": round(snap["price"],2),
                             "avgAmount20d": round(amt20,2),
                             "turnover20d": round(tp,2),
                             "marketCap": round(mc,2), "pass": True})

    elapsed = time.time() - t0
    print("[TL] Done in {:.1f}s: pass={}, reject={}".format(elapsed, len(pass_entries), len(reject)), file=sys.stderr)

    # Summary
    rc={}
    for r in reject:
        lb=r["reason"].split("(")[0].strip() if "(" in r["reason"] else r["reason"][:30]
        rc[lb]=rc.get(lb,0)+1
    ed={}
    for fd in factor_list: ed[fd.get("entryType","neutral")]=ed.get(fd.get("entryType","neutral"),0)+1
    td={}
    for fd in factor_list: td[fd.get("technicalLevel","?")]=td.get(fd.get("technicalLevel","?"),0)+1
    reason_parts=" | ".join("{}:{}只".format(k,v) for k,v in sorted(rc.items()))
    entry_parts=" ".join("{}:{}只".format(k,v) for k,v in sorted(ed.items()))
    tech_parts=" ".join("{}:{}只".format(k,v) for k,v in sorted(td.items()))
    summary=("总候选{}只,过关{}只,剔除{}只。|原因:{}|入场:{}|技术:".format(
        len(ALL_CODES), len(pass_entries), len(reject), reason_parts, entry_parts, tech_parts))

    output = {
        "runId": "20260720_short-term-picks", "asOf": "20260720",
        "goal": "short-term-picks", "agent": "technical-liquidity", "fetchedAt": "20260720",
        "data": {"pass": pass_entries, "reject": reject, "factors": factor_list},
        "summary": summary,
        "keyFields": {
            "passCodes": ",".join(x["code"] for x in pass_entries),
            "totalCandidates": len(ALL_CODES), "passCount": len(pass_entries),
            "rejectCount": len(reject)},
        "timing": {"wallClockSec": round(elapsed, 1)}}

    outdir = os.path.join(os.path.dirname(__file__), "..", "data", "runs", "20260720_short-term-picks")
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, "technical-liquidity.json")
    with open(outpath, "w", encoding="utf-8") as fout:
        json.dump(output, fout, ensure_ascii=False, indent=2)

    print("[TL] Written to {}".format(outpath), file=sys.stderr)
    result = {"path": outpath, "summary": summary, "keyFields": output["keyFields"]}
    print(json.dumps(result))

if __name__ == "__main__":
    main()
