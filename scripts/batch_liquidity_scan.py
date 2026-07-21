#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Batch technical liquidity scan — Real-time quotes for hot-trends candidates.
Note: sector-analyst.json encoding is corrupted; candidates are hardcoded below.
"""
import subprocess, json, sys, os, time

RUN_ID = "20260720_hot-trends"
ASOF = "2026-07-20"
DATA_DIR = rf"E:\finacial-invest\data\runs\{RUN_ID}"
os.makedirs(DATA_DIR, exist_ok=True)

###############################################################################
# Hardcoded candidate pool (from previous sector-analyst run, before corruption)
# Note: 601088 中国神华 price=46.14 excluded (>40 yuan threshold)
###############################################################################
CANDIDATES = [
    {"code":"600938","name":"中国海油","sector":"煤炭/石油","price":31.87,"mktCapYi":5890,"tags":"央企+煤炭+涨停"},
    {"code":"600188","name":"兖矿能源","sector":"煤炭","price":20.79,"mktCapYi":2220,"tags":"煤炭+央企+涨停"},
    {"code":"600985","name":"淮北矿业","sector":"煤炭","price":15.62,"mktCapYi":431,"tags":"煤炭+煤化工+高股息"},
    {"code":"601898","name":"中煤能源","sector":"煤炭","price":13.79,"mktCapYi":1240,"tags":"煤炭+央企+涨停"},
    {"code":"601666","name":"平煤股份","sector":"煤炭","price":7.98,"mktCapYi":298,"tags":"煤炭+涨停"},
    {"code":"600403","name":"大有能源","sector":"煤炭","price":5.28,"mktCapYi":42,"tags":"煤炭+涨停"},
    {"code":"000983","name":"山西焦煤","sector":"煤炭","price":6.29,"mktCapYi":224,"tags":"焦煤+山西国资"},
    {"code":"601001","name":"晋控煤业","sector":"煤炭","price":19.28,"mktCapYi":276,"tags":"煤炭+国企改革"},
    {"code":"600863","name":"华能蒙电","sector":"电力","price":5.02,"mktCapYi":76,"tags":"火电+央企+涨停"},
    {"code":"600744","name":"华银电力","sector":"电力","price":6.56,"mktCapYi":178,"tags":"火电+央企+涨停+PE偏高"},
    {"code":"600396","name":"华电辽能","sector":"电力","price":5.8,"mktCapYi":None,"tags":"绿色电力+火力发电"},
    {"code":"600821","name":"金开新能","sector":"电力","price":5.5,"mktCapYi":None,"tags":"电力+涨停"},
    {"code":"600578","name":"京能电力","sector":"电力","price":5.72,"mktCapYi":205,"tags":"风光火储一体化+涨停"},
    {"code":"600726","name":"华电能源","sector":"电力","price":5.83,"mktCapYi":126,"tags":"火电+央企+PE高"},
    {"code":"601991","name":"大唐发电","sector":"电力","price":6.38,"mktCapYi":855,"tags":"超超临界火电+央企+涨停"},
    {"code":"000600","name":"建投能源","sector":"电力","price":8.98,"mktCapYi":77,"tags":"火电+储能+河北国资+涨停"},
    {"code":"600032","name":"浙江新能","sector":"电力/国企改革","price":11.07,"mktCapYi":None,"tags":"绿色电力+海上风电"},
    {"code":"000722","name":"湖南发展","sector":"电力/国企改革","price":10.5,"mktCapYi":None,"tags":"水力发电+中报预增"},
    {"code":"001258","name":"立新能源","sector":"电力/国企改革","price":10.2,"mktCapYi":None,"tags":"风电光伏+定增获批"},
    {"code":"603980","name":"吉华集团","sector":"化工/中报预增","price":13.5,"mktCapYi":None,"tags":"中报净利+1272%染料提价"},
    {"code":"300515","name":"三德科技","sector":"设备/中报预增","price":21.3,"mktCapYi":None,"tags":"半年报预增+煤炭检测仪器"},
    {"code":"002490","name":"山东墨龙","sector":"设备/中报预增","price":11.8,"mktCapYi":None,"tags":"油气装备+海外大单"},
    {"code":"000815","name":"美利云","sector":"算力/央企改革","price":12.5,"mktCapYi":None,"tags":"算力租赁+东数西算"},
    {"code":"600864","name":"哈尔滨空调","sector":"电力设备/国企","price":12.3,"mktCapYi":None,"tags":"电力设备+黑龙江国资"},
    {"code":"601101","name":"恒逸石化","sector":"化工/央企","price":10.8,"mktCapYi":None,"tags":"石化+央企改革"},
    {"code":"600900","name":"长江电力","sector":"电力","price":28.5,"mktCapYi":5580,"tags":"水电龙头+防御+高股息"},
    {"code":"000548","name":"四川九洲","sector":"央企改革","price":18.2,"mktCapYi":None,"tags":"军工电子+四川国资+国企改革"},
    {"code":"600674","name":"川投能源","sector":"电力","price":11.5,"mktCapYi":520,"tags":"水电+西藏矿业参股"},
    {"code":"601985","name":"中国核电","sector":"电力","price":22.8,"mktCapYi":2600,"tags":"核电龙头+央企"},
]

###############################################################################
# Step 1 — Real-time quotes via curl + qt.gtimg.cn (GBK, proven working)
###############################################################################
print("[1/3] Fetching real-time quotes...")

def qstr(codes):
    """Build Qt query string: sh600938,sz000983,..."""
    return ",".join(f"sh{c}" if c.startswith("6") else f"sz{c}" for c in codes)

curl_codes = [c["code"] for c in CANDIDATES]
result = subprocess.run(
    ["curl", "-k", "-s", "--max-time", "30", f"http://qt.gtimg.cn/q={qstr(curl_codes)}"],
    capture_output=True, text=True, timeout=35
)
raw_text = result.stdout

if not raw_text or len(raw_text) < 100:
    print(f"  ERROR: curl returned too little data ({len(raw_text)} chars)")
    sys.exit(1)

print(f"  Received {len(raw_text)} chars of quote data")

# Parse Tencent GBK quote response
# Field positions (~ separated, 0-indexed):
#   1=name, 2=code, 3=price, 4=prev_close, 5=open
#   6=vol_hands, 31=chg_amt, 32=pct%, 33=high, 34=low
#   37=amount(wan-yuan or yuan), 38=turnover%, 39=PE_TTM
#   44=float_mktcap(yuan), 45=total_mktcap(yuan)

quotes_map = {}
for line in raw_text.strip().split(";"):
    parts = line.split("~")
    if len(parts) < 45:
        continue
    code = parts[2].strip()
    try:
        price_s = parts[3].strip()
        prev_s = parts[4].strip()
        if not price_s or price_s == '-':
            continue
        price = float(price_s)
        prev_close = float(prev_s) if prev_s and prev_s != '-' else 0

        def sf(s):
            s = s.strip()
            if not s or s == '-':
                return None
            try:
                return float(s)
            except (ValueError, TypeError):
                return None

        # Amount interpretation: position 37 values from known stocks
        # 600938=528292 -> 52.8亿 means it's in wan-yuan (/10000)
        amt_raw = sf(parts[37])
        if amt_raw is not None and amt_raw > 0:
            if amt_raw > 1e8:
                amount_yi = round(amt_raw / 1e8, 2)  # already yuan
            elif amt_raw > 1e4:
                amount_yi = round(amt_raw / 1e4, 2)  # wan -> yi
            else:
                amount_yi = round(amt_raw, 2)
        else:
            amount_yi = None

        mktcap_total = sf(parts[45])
        quotes_map[code] = {
            "name": parts[1].strip(),
            "code": code,
            "price": price,
            "prev_close": prev_close,
            "open": sf(parts[5]) or 0,
            "vol_hands": sf(parts[6]) or 0,
            "amount_yi": amount_yi,
            "pct": sf(parts[32]) or 0,
            "high": sf(parts[33]) or 0,
            "low": sf(parts[34]) or 0,
            "turnover_pct": sf(parts[38]),
            "pe_ttm": sf(parts[39]),
            "float_mktcap_yuan": sf(parts[44]),
            "mktcap_yi": round(mktcap_total / 1e8, 2) if mktcap_total else None,
        }
    except Exception as e:
        print(f"  WARN parse {parts[2][:10]}: {e}", file=sys.stderr)

print(f"  Parsed {len(quotes_map)} quotes")

time.sleep(0.3)

###############################################################################
# Step 2 — K-line attempt via cn_fetch.kline per-stock
###############################################################################
print("\n[2/3] Attempting K-line data...")
try:
    from scripts.cn_fetch import kline
    kline_ok = True
except ImportError:
    kline_ok = False

klines_map = {}
if kline_ok:
    for i, code in enumerate([c["code"] for c in CANDIDATES]):
        try:
            arr = kline(code, 30)
            if arr and len(arr) >= 20:
                klines_map[code] = arr
                print(f"  {code}: {len(arr)} bars OK")
            else:
                print(f"  {code}: EMPTY({len(arr) if arr else 0})")
        except Exception as e:
            print(f"  {code}: ERR {e}")
        if i % 5 == 0 and i > 0:
            time.sleep(0.3)
else:
    print("  cn_fetch unavailable -- K-line N/A")

###############################################################################
# Step 3 — Hard-filters + factor calculation
###############################################################################
print("\n[3/3] Applying filters & computing factors...")

pass_list = []
reject_list = []
factor_list = []

ST_KEYWORDS = {"ST", "*ST", "退市"}

for cand in CANDIDATES:
    code = cand["code"]
    name = cand["name"]
    sector = cand.get("sector", "")
    tags = cand.get("tags", "")
    src_price = cand.get("price", 0)
    src_cap = cand.get("mktCapYi")

    q = quotes_map.get(code, {})
    if not q:
        reject_list.append({"code": code, "name": name, "reason": "实时报价不可得"})
        continue

    price = q["price"] if q["price"] > 0 else src_price
    amount_yi = q.get("amount_yi") or 0
    turnover = q.get("turnover_pct")
    pe = q.get("pe_ttm")
    pct = q.get("pct", 0)

    kl = klines_map.get(code, [])
    has_kline = len(kl) >= 20

    reasons = []

    # 1. ST check
    if any(kw in name for kw in ST_KEYWORDS):
        reasons.append("ST/*ST风险标的")

    # 2. Daily turnover >= 1亿
    if amount_yi < 1:
        reasons.append(f"今日成交额仅{amount_yi:.2f}亿(<1亿)")

    # Turnover estimation
    turnover_val = turnover
    if turnover_val is None:
        mk_cap = q.get("mktcap_yi") or src_cap
        if isinstance(mk_cap, (int, float)) and mk_cap > 0:
            turnover_val = round(amount_yi / mk_cap * 100, 2)

    if turnover_val is not None:
        if turnover_val < 1:
            reasons.append(f"换手率{turnover_val}%<1%(冷僻)")
        elif turnover_val > 7:
            reasons.append(f"换手率{turnover_val}%>7%(警惕派发)")

    # 4. Limit up/down
    is_limit_up = abs(pct) > 9.5 and pct > 0
    is_limit_down = abs(pct) > 9.5 and pct < 0
    if is_limit_up:
        reasons.append(f"涨停({pct}%),无法买入")
    if is_limit_down:
        reasons.append(f"跌停({pct}%),无法卖出")

    # Momentum variables defaults
    m5 = m10 = m20 = ma5_v = ma10_v = ma20_v = None
    vol_health = "N/A"
    vol_ratio = None
    mom_uniformity = "unknown"
    breakout_flag = False
    above_ma5_v = above_ma10_v = above_ma20_v = False
    avg_amt20d = 0
    daily_chgs = []
    exhaust_prob = "未知"
    mr_signal_str = "无K线数据"

    if has_kline:
        closes = [row[2] for row in kl]
        amounts_day = [row[5] for row in kl]
        n = len(closes)

        def m_func(d):
            return round((closes[-1]/closes[-1-d]-1)*100, 2) if n > d else None

        m5 = m_func(5); m10 = m_func(10); m20 = m_func(20)

        def ma_func(d):
            return round(sum(closes[-d:])/d, 3) if n >= d else None

        ma5_v = ma_func(5); ma10_v = ma_func(10); ma20_v = ma_func(20)

        amt_slice = amounts_day[-min(20,n):]
        avg_amt20d = sum(amt_slice)/len(amt_slice)/10000 if amt_slice else 0

        vol_today_wan = amounts_day[-1] if amounts_day else 0
        vol_ratio = round(vol_today_wan/(avg_amt20d*10000), 2) if avg_amt20d > 0 else None

        above_ma5_v = closes[-1] > ma5_v if ma5_v else False
        above_ma10_v = closes[-1] > ma10_v if ma10_v else False
        above_ma20_v = closes[-1] > ma20_v if ma20_v else False
        breakout_5d = closes[-1] >= max(r[3] for r in kl[-5:]) if n >= 5 else False
        breakout_flag = breakout_5d

        for i in range(n-1, max(n-6, 0), -1):
            pc = closes[i-1]; cc = closes[i]
            if pc > 0:
                daily_chgs.append(round((cc-pc)/pc*100, 2))

        up_days = sum(1 for c in daily_chgs if c > 0)
        mom_uniformity = "uniform" if up_days >= 3 else ("concentrated" if up_days == 1 else "mixed")

        nc = min(5, len(daily_chgs))
        up_amts = [kl[n-1-i][5] for i,c in enumerate(daily_chgs[:nc]) if c > 0]
        dn_amts = [kl[n-1-i][5] for i,c in enumerate(daily_chgs[:nc]) if c <= 0]
        au = sum(up_amts)/len(up_amts) if up_amts else 0
        ad = sum(dn_amts)/len(dn_amts) if dn_amts else 1
        vol_health = "healthy" if au >= ad else "unhealthy"

        # Exhaustion
        if m20 is not None and m5 is not None and m20 > 25 and m5 < 0:
            reasons.append(f"主升浪结束透支持除(20日涨{m20}%,5日跌{m5}%)")
        elif m5 is not None and m5 > 15:
            reasons.append(f"近5日涨{m5}%,追涨高风险剔除")

        if above_ma20_v and m5 is not None and m5 < -10:
            mr_signal_str = "优质股短期超跌"
        elif m5 is not None and m5 > 8:
            mr_signal_str = "短期涨幅偏大"
        else:
            mr_signal_str = "正常区间"

        if m20 is not None and m5 is not None and m20 > 25 and m5 < 0:
            exhaust_prob = "极高(>80%)"
        elif m5 is not None and m5 > 15:
            exhaust_prob = "高(>70%)"
        elif m20 is not None and m20 > 20:
            exhaust_prob = "中(40%)"
        else:
            exhaust_prob = "低(<30%)"
    else:
        print(f"  WARNING: No K-line for {code}")

    if reasons:
        reject_list.append({"code": code, "name": name, "reason": "; ".join(reasons)})
        factor_list.append({
            "code": code, "name": name, "price": price,
            "m5": m5, "m10": m10, "m20": m20,
            "momentumUniformity": mom_uniformity,
            "volumeHealth": vol_health,
            "entryType": "REJECTED", "entryScore": -50,
            "meanReversionSignal": mr_signal_str,
            "aboveMA20": above_ma20_v,
            "breakout": breakout_flag,
            "avgAmount20dYi": round(avg_amt20d, 2),
            "turnoverEst": turnover_val,
            "volumeRatio": vol_ratio,
            "pe_ttm": pe,
            "rejected": True,
            "rejectionReasons": reasons,
            "hasKline": has_kline,
        })
        continue

    entry_type = "观望"; entry_score = 5

    if has_kline:
        if above_ma20_v and m5 is not None and -15 < m5 < -3:
            entry_type = "健康回调买点"; entry_score = 20 if vol_health == "healthy" else 12
        elif above_ma20_v and m5 is not None and 0 < m5 < 8:
            entry_type = "上升趋势持有"; entry_score = 12
        elif breakout_flag and 0 < m5 < 10:
            entry_type = "突破回踩确认"; entry_score = 15
        elif m20 is not None and m20 < -15 and m5 is not None and m5 > 0:
            entry_type = "超跌反弹启动"; entry_score = 10
        elif above_ma20_v and m5 is not None and m5 > 0:
            entry_type = "趋势向上"; entry_score = 8
        else:
            entry_type = "横盘观望"; entry_score = 3

        if mr_signal_str == "优质股短期超跌":
            entry_score += 10
        elif mr_signal_str == "短期涨幅偏大":
            entry_score -= 5
        if pe is not None and 5 < pe < 15:
            entry_score += 5
        elif pe is not None and pe > 100:
            entry_score -= 5
    else:
        if pct > 0 and pe is not None and pe < 20:
            entry_type = "正收益待观察"; entry_score = 8
        elif pct < -3:
            entry_type = "当日下跌需更多数据"; entry_score = 3
        else:
            entry_type = "无明显信号"; entry_score = 5

    pass_list.append({
        "code": code, "name": name, "price": price,
        "avgAmount20d": round(avg_amt20d, 2),
        "turnover20d": turnover_val,
        "volumeRatio": vol_ratio,
        "mktCapYi": src_cap,
        "pass": True,
    })

    factor_list.append({
        "code": code, "name": name, "price": price,
        "m5": m5, "m10": m10, "m20": m20,
        "momentumUniformity": mom_uniformity,
        "volumeHealth": vol_health,
        "entryType": entry_type,
        "entryScore": entry_score,
        "meanReversionSignal": mr_signal_str,
        "aboveMA5": above_ma5_v if has_kline else None,
        "aboveMA10": above_ma10_v if has_kline else None,
        "aboveMA20": above_ma20_v if has_kline else None,
        "breakout": breakout_flag,
        "avgAmount20dYi": round(avg_amt20d, 2),
        "turnoverEst": turnover_val,
        "volumeRatio": vol_ratio,
        "pe_ttm": pe,
        "exhaustionProb": exhaust_prob,
        "isLimitUp": is_limit_up,
        "isLimitDown": is_limit_down,
        "hasKline": has_kline,
        "rejected": False,
    })

###############################################################################
# Summary & output
###############################################################################
entry_types_dist = {}
for f in factor_list:
    et = f["entryType"]
    entry_types_dist[et] = entry_types_dist.get(et, 0) + 1

reason_counts = {}
for r in reject_list:
    primary = r["reason"].split(";")[0]
    reason_counts[primary] = reason_counts.get(primary, 0) + 1
top_reasons = sorted(reason_counts.items(), key=lambda x: -x[1])[:3]

summary_parts = [
    f"过关{len(pass_list)}只/剔除{len(reject_list)}只",
    f"入场分布: {', '.join(f'{k}:{v}' for k,v in sorted(entry_types_dist.items()))}",
]
if top_reasons:
    rs = "、".join(f"{r}({c})" for r, c in top_reasons)
    summary_parts.append(f"主要剔除原因: {rs}")

if len(klines_map) == 0:
    summary_parts.append("注: K线数据源不可用(腾讯API返回空数组),动量因子均为N/A")

summary = " | ".join(summary_parts)

key_fields = {
    "passCodes": ",".join(p["code"] for p in pass_list),
    "passTickers": "、".join(f"{p['code']}{p['name']}" for p in pass_list[:8]),
    "rejectCodes": ",".join(r["code"] for r in reject_list),
    "passCount": len(pass_list),
    "rejectCount": len(reject_list),
    "excludedOver40": 1,
    "topPicks": [(f["code"], f["name"], f["entryScore"], f["entryType"])
                 for f in sorted(factor_list, key=lambda x: -x["entryScore"])
                 if not f.get("rejected")][:3],
}

output = {
    "runId": RUN_ID,
    "asOf": ASOF,
    "goal": "hot-trends",
    "agent": "technical-liquidity",
    "fetchedAt": ASOF,
    "data": {
        "pass": pass_list,
        "reject": reject_list,
        "factors": factor_list,
        "quoteSummary": {code: {
            "price": v["price"],
            "amount_yi": v["amount_yi"],
            "turnover_pct": v["turnover_pct"],
            "pe_ttm": v["pe_ttm"],
            "pct": v["pct"],
        } for code, v in quotes_map.items()},
    },
    "summary": summary,
    "keyFields": key_fields,
}

output_path = os.path.join(DATA_DIR, "technical-liquidity.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"WROTE: {output_path}")
print(f"Pass: {len(pass_list)} | Reject: {len(reject_list)} | K-line OK: {len(klines_map)}/{len(CANDIDATES)}")
print(f"\n--- PASS LIST ---")
for p in pass_list:
    print(f"  P {p['code']} {p['name']} price={p['price']} amt20d={p['avgAmount20d']:.2f}亿 turn={p['turnover20d']}")
print(f"\n--- REJECT LIST ---")
for r in reject_list:
    print(f"  R {r['code']} {r['name']} => {r['reason']}")
print(f"\n--- SUMMARY ---")
print(summary)
