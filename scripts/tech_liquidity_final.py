#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Technical Liquidity Analysis 2026-07-20
Hard-gate + short-term factor on candidates from rankChangePct (sector agent failed).
Uses Sina rank + Tencent K-lines, keyless HTTP channel.
"""
import json, os, sys, urllib.request, ssl, time

os.chdir(r"E:/finacial-invest")

# === SSL context ===
_CN_FETCH_SSL_NO_VERIFY = os.environ.get("CN_FETCH_SSL_NO_VERIFY", "1").strip() in ("1", "true", "yes")
_CTX = ssl._create_unverified_context() if _CN_FETCH_SSL_NO_VERIFY else ssl.create_default_context()
_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def _get(url, enc='utf-8', timeout=25):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return r.read().decode(enc, 'ignore')

# ================================================================
# Step 1: Load candidates from rankChangePct in _shared.json
#         (sector/macro agents failed, rankChangePct has top gainer stocks)
# ================================================================
with open("data/runs/20260720_short-term-picks/_shared.json", "r", encoding="utf-8") as f:
    shared = json.load(f)

tsv = shared['rankChangePct']['tsv']
raw_rows = tsv.strip().split('\n')
stocks_raw = []
for row in raw_rows:
    parts = row.split('\t')
    if len(parts) < 9:
        continue
    code_prefix, name = parts[0], parts[1]
    price = float(parts[2])
    pct = float(parts[3])
    amount_yi = float(parts[4])      # from Sina: amount/1e8
    turnover = float(parts[5])       # turnover ratio %
    mktcap_nyc = float(parts[6])     # nmc/1e8 = floating market cap (亿)
    pe = float(parts[7]) if parts[7] != 'NA' else None
    pb = float(parts[8]) if parts[8] != 'NA' else None

    sym = code_prefix.lower()
    if sym.startswith('sh'):
        sym_code = sym
    elif sym.startswith('sz'):
        sym_code = sym
    else:
        sym_code = 'sh' + sym if len(sym) == 6 else sym

    stocks_raw.append({
        'sym_prefix': sym,
        'sym_code': sym_code,
        'name': name.strip(),
        'price': price,
        'pct': pct,
        'amount_yi_sina': amount_yi,
        'turnover': turnover,
        'mktcap_nyc': mktcap_nyc,
        'pe_ttm': pe,
        'pb': pb,
    })

total_candidates = len(stocks_raw)
print("[1] Parsed {} candidates from rankChangePct.".format(total_candidates), file=sys.stderr)

# ================================================================
# Step 2: Fetch real-time quotes from Tencent qt.gtimg.cn
# ================================================================
ctx = ssl._create_unverified_context()

def secid(code):
    """Ensure code has proper prefix."""
    c = code.lower().strip()
    if not c.startswith(('sh', 'sz')):
        c = 'sh' + c if int(c[:1]) >= 6 else 'sz' + c
    return c

all_syms = [secid(s['sym_code']) for s in stocks_raw]

quote_lookup = {}

# Batch by 30
for i in range(0, len(all_syms), 30):
    batch = all_syms[i:i+30]
    q_str = ','.join(batch)
    url = 'http://qt.gtimg.cn/q={}'.format(q_str)
    try:
        txt = _get(url, 'gbk')
        for line in txt.strip().split(';'):
            line = line.strip()
            if '=' not in line or '~' not in line:
                continue
            v = line.split('=', 1)[1].strip('"').rstrip('~;')
            if not v or '~' not in v:
                continue
            m = v.split('~')
            if len(m) < 50:
                continue
            code_key = m[2]
            quote_lookup[code_key] = {
                'name': m[1][:6],
                'price': float(m[3]) if m[3] else 0,
                'prev_close': float(m[4]) if m[4] else 0,
                'open': float(m[5]) if m[5] else 0,
                'vol_hand': float(m[6]) if m[6] else 0,
                'chg_pct': float(m[32]) if m[32] and m[32] != '-' else 0,
                'high': float(m[33]) if m[33] and m[33] != '-' else 0,
                'low': float(m[34]) if m[34] and m[34] != '-' else 0,
                'amount_yuan': float(m[37]) if m[37] and m[37] != '-' else 0,
                'turnover_pct': float(m[38]) if m[38] and m[38] != '-' else 0,
                'pe_ttm': float(m[39]) if m[39] and m[39] != '-' else None,
                'float_mktcap': float(m[44]) if m[44] and m[44] != '-' else 0,
                'total_mktcap': float(m[45]) if m[45] and m[45] != '-' else 0,
            }
    except Exception as e:
        print("  WARN: quote batch {} failed: {}".format(i//30+1, e), file=sys.stderr)
    time.sleep(0.3)

# Merge quote data into stocks_raw
matched_count = 0
for st in stocks_raw:
    prefix = st['sym_prefix'].lower()
    quoted = quote_lookup.get(prefix) or quote_lookup.get(prefix.lstrip('szShSZ'))
    if quoted:
        st.update({
            'q_price': quoted['price'],
            'q_chg_pct': quoted['chg_pct'],
            'q_amount_yi': round(quoted['amount_yuan'] / 1e8, 2),
            'q_turnover': round(quoted['turnover_pct'], 2),
            'q_float_mktcap': round(quoted['float_mktcap'] / 1e8, 2),
            'q_total_mktcap': round(quoted['total_mktcap'] / 1e8, 2),
            'q_pe': quoted['pe_ttm'],
            'matched': True,
        })
        st['name'] = quoted['name']
        matched_count += 1
    else:
        st.update({
            'q_price': st['price'],
            'q_chg_pct': st['pct'],
            'q_amount_yi': st['amount_yi_sina'],
            'q_turnover': st['turnover'],
            'q_float_mktcap': st['mktcap_nyc'],
            'q_total_mktcap': st['mktcap_nyc'],
            'q_pe': st['pe_ttm'],
            'matched': False,
        })

print("[2] Quote match: {}/{} matched.".format(matched_count, total_candidates), file=sys.stderr)

# ================================================================
# Step 3: Fetch K-line data for ALL candidates
# ================================================================
def kline(symbol, datalen=30):
    """Fetch Tencent daily K-line (forward-adjusted)."""
    try:
        url = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={},".format(symbol) + "day,,," + str(datalen) + ",qfq"
        j = json.loads(_get(url))
        data = j.get('data')
        if not isinstance(data, dict):
            return []
        sym_data = data.get(symbol)
        if not isinstance(sym_data, dict):
            return []
        arr = sym_data.get('qfqday') or sym_data.get('day', [])
        return arr or []
    except Exception as e:
        print("  WARN: kline({}): {}".format(symbol, e), file=sys.stderr)
        return []

factor_cache = {}
KL_BATCH = 15
codes_for_kline = [secid(s['sym_code']) for s in stocks_raw]

for i in range(0, len(codes_for_kline), KL_BATCH):
    end_idx = min(i + KL_BATCH, len(codes_for_kline))
    batch = codes_for_kline[i:end_idx]
    print("[3] K-line batch [{:d}-{:d}]/{}".format(i+1, end_idx, len(codes_for_kline)), file=sys.stderr)
    for sym in batch:
        arr = kline(sym, 30)
        if not arr or len(arr) < 22:
            factor_cache[sym] = None
            continue

        rows = [{'date': x[0], 'close': float(x[2]), 'high': float(x[3]),
                 'low': float(x[4]), 'vol': float(x[5])} for x in arr]
        closes = [r['close'] for r in rows]
        vols = [r['vol'] for r in rows]
        last = rows[-1]

        def mom(d, _closes=closes):
            if len(_closes) > d:
                return round((_closes[-1] - _closes[-1-d]) / _closes[-1-d] * 100, 2)
            return None

        ma5 = round(sum(closes[-5:]) / 5, 2)
        ma10 = round(sum(closes[-10:]) / 10, 2)
        ma20 = round(sum(closes[-20:]) / 20, 2)
        v5 = sum(vols[-5:]) / 5
        v20 = sum(vols[-20:]) / 20
        breakout_flag = last['close'] > ma20 and last['vol'] > v5 * 1.5

        amt_start = max(0, len(rows) - 20)
        amt20 = sum(rows[j]['vol'] * 100 * rows[j]['close'] for j in range(amt_start, len(rows))) / 20 if len(rows) >= 20 else 0

        above_ma20 = last['close'] > ma20
        above_ma5 = last['close'] > ma5
        above_ma10 = last['close'] > ma10
        peak_high = max(closes[-20:])
        pullback_depth = round((last['close'] - peak_high) / peak_high * 100, 2)

        if len(vols) > 6:
            recent_vol = sum(vols[-3:]) / 3
            prior_vol = sum(vols[-6:-3]) / 3
            vol_health = round(recent_vol / prior_vol, 2) if prior_vol > 0 else 1.0
        else:
            vol_health = 1.0

        factor_cache[sym] = {
            'last': round(last['close'], 2), 'date': last['date'],
            'm5': mom(5), 'm10': mom(10), 'm20': mom(20),
            'ma5': ma5, 'ma10': ma10, 'ma20': ma20,
            'v5': v5, 'v20': v20, 'breakout': breakout_flag,
            'amt20_yi': round(amt20 / 1e8, 2),
            'above_ma20': above_ma20, 'above_ma5': above_ma5, 'above_ma10': above_ma10,
            'peak_high': round(peak_high, 2),
            'pullback_depth': pullback_depth,
            'vol_health': vol_health,
        }
    time.sleep(0.3)

print("[3] K-line factor computation done.", file=sys.stderr)

# ================================================================
# Step 4: Hard Gate Filtering
# ================================================================
PRICE_MAX = 40
MARKET_CAP_MIN = 30
AMOUNT_MIN = 1.0
TURNOVER_LOW = 1.0
TURNOVER_HIGH = 7.0

pass_list = []
reject_list = []

for st in stocks_raw:
    code = secid(st['sym_code'])
    name = st['name']
    fac = factor_cache.get(code)
    reasons = []

    # 1. Price < 40 yuan (1w account constraint)
    price = st['q_price'] if st['q_price'] > 0 else st['price']
    if price >= PRICE_MAX:
        reasons.append("价格{:.2f}>40元(1w账户约束)".format(price))

    # 2. Turnover gate: 1% <= turnover <= 7%
    turnover = st['q_turnover'] if st['q_turnover'] > 0 else st['turnover']
    if turnover < TURNOVER_LOW:
        reasons.append("换手率{:.2f}%<1%(偏冷)".format(turnover))
    elif turnover > TURNOVER_HIGH:
        reasons.append("换手率{:.2f}%>7%(高位派发风险)".format(turnover))

    # 3. Market cap >= 30亿
    mktcap = st['q_total_mktcap'] if st['q_total_mktcap'] and st['q_total_mktcap'] > 0 else (st['q_float_mktcap'] if st['q_float_mktcap'] else st['mktcap_nyc'])
    if mktcap and mktcap < MARKET_CAP_MIN:
        reasons.append("流通市值{:.1f}亿<30亿".format(mktcap))

    # 4. Avg daily amount >= 1亿
    if fac:
        if fac['amt20_yi'] < AMOUNT_MIN:
            reasons.append("日均成交额{:.2f}亿<1亿".format(fac['amt20_yi']))

    # 5. Exhaustion filter
    if fac:
        m5_val = fac.get('m5')
        m20_val = fac.get('m20')
        if m5_val is not None and m5_val > 30:
            reasons.append("近5日涨幅{:.1f}%>30%(透支剔除)".format(m5_val))
        if m20_val is not None and m20_val > 30:
            reasons.append("近20日涨幅{:.1f}%>30%(透支剔除)".format(m20_val))

    # 6. Limit up (+9.5%+)
    qchg = st['q_chg_pct'] if st['q_chg_pct'] != 0 else st['pct']
    if qchg is not None and qchg >= 9.5:
        reasons.append("+{:.1f}%涨停封死买不进".format(qchg))

    if reasons:
        reject_list.append({'code': code, 'name': name, 'reason': '; '.join(reasons)})
    else:
        avg_amt = fac['amt20_yi'] if fac else round(st['q_amount_yi'], 2)
        pass_list.append({
            'code': code, 'name': name, 'price': round(price, 2),
            'avgAmount20d': round(avg_amt, 2),
            'turnover20d': round(turnover, 2),
            'marketCap': round(mktcap, 2) if mktcap else None,
            'pass': True
        })

print("[4] Hard gate: {} pass, {} reject out of {} total.".format(len(pass_list), len(reject_list), total_candidates), file=sys.stderr)

# ================================================================
# Step 5: Short-Term Factor Computation for Pass Stocks
# ================================================================
factors_out = []

for p in pass_list:
    code = p['code']
    fac = factor_cache.get(code)
    if not fac:
        continue

    m5 = fac.get('m5') or 0
    m10 = fac.get('m10') or 0
    m20 = fac.get('m20') or 0
    above_m20 = fac['above_ma20']
    above_m5 = fac['above_ma5']
    above_m10 = fac['above_ma10']
    breakout_flag = fac['breakout']
    peak = fac['peak_high']
    pd_ = fac['pullback_depth']
    vol_h = fac['vol_health']

    # --- Momentum Uniformity (up days in last 5) ---
    kl_up = kline(code, 6)
    if kl_up and len(kl_up) >= 5:
        cl = [float(r[2]) for r in kl_up[-5:]]
        up_days = sum(1 for j in range(1, len(cl)) if cl[j] >= cl[j-1])
        momentum_uniformity = min(up_days, 5)
    else:
        momentum_uniformity = 3

    volume_health = vol_h if vol_h else 1.0

    accel = round((m5/5 if m5 else 0) - ((m10-m5)/5 if m10 and m5 else 0), 2)

    # --- Entry Type & Score ---
    entry_score = 0
    entry_type = "neutral"

    if above_m20 and -8 <= m5 <= -3 and vol_h < 1.2:
        entry_type = "health_pullback"
        entry_score = 20
    elif breakout_flag and above_m20:
        entry_type = "breakout_retest"
        entry_score = 15
    elif m20 < -15 and m5 > 0 and vol_h > 0.8:
        entry_type = "oversold_bounce"
        entry_score = 10
    elif m5 > 10 and fac['last'] >= peak * 0.95 and vol_h > 1.5:
        entry_type = "chase_high"
        entry_score = -15
    elif m20 > 20 and m5 < 0 and vol_h > 1.2:
        entry_type = "high_distribution"
        entry_score = -20

    # --- Mean Reversion Signal ---
    mr_signal = "none"
    if m20 < -10 and m5 > 0 and above_m5:
        mr_signal = "quality_oversold"
    elif m5 < -5 and above_m20:
        mr_signal = "temporary_pullback"

    # --- Exhaustion Probability ---
    exhaustion_prob = 0.2
    if m5 > 15:
        exhaustion_prob = 0.5
    if m20 > 25 and m5 < 0:
        exhaustion_prob = 0.8
    if m5 < -10:
        exhaustion_prob = 0.15
    if exhaustion_prob >= 0.7:
        exhaustion_label = "极高"
    elif exhaustion_prob >= 0.5:
        exhaustion_label = "较高"
    elif exhaustion_prob >= 0.3:
        exhaustion_label = "启动期"
    elif exhaustion_prob <= 0.15:
        exhaustion_label = "超跌修复"
    else:
        exhaustion_label = "正常区间"

    # --- Technical Level Classification ---
    if above_m5 and above_m10 and above_m20:
        tech_level = "多头排列-上涨趋势" if (m5 > 3 and m10 > 3) else "多头排列-横盘蓄势"
    elif above_m20:
        tech_level = "站上MA20-MA5下方整理"
    elif above_m10:
        tech_level = "跌破MA20-MA10附近震荡"
    else:
        tech_level = "跌破MA20-弱势整理"

    factors_out.append({
        'code': code,
        'm5': m5, 'm10': m10, 'm20': m20,
        'momentumUniformity': momentum_uniformity,
        'volumeHealth': volume_health,
        'momentumAccel': accel,
        'entryType': entry_type,
        'entryScore': entry_score,
        'meanReversionSignal': mr_signal,
        'pullbackDepth': pd_,
        'pullbackVolume': vol_h,
        'exhaustionProb': exhaustion_prob,
        'exhaustionLabel': exhaustion_label,
        'breakout': breakout_flag,
        'aboveMA20': above_m20,
        'aboveMA5': above_m5,
        'aboveMA10': above_m10,
        'rps': round(m5, 2),
        'technicalLevel': tech_level,
    })

factors_out.sort(key=lambda x: x['entryScore'], reverse=True)

# ================================================================
# Step 6: Summary & Output
# ================================================================
reject_reasons_grouped = {}
for r in reject_list:
    reason = r['reason'].split('; ')[0]
    reject_reasons_grouped[reason] = reject_reasons_grouped.get(reason, 0) + 1

summary_parts = ["总候选{}只,过关{}只,剔除{}只".format(total_candidates, len(pass_list), len(reject_list))]
for reason, count in sorted(reject_reasons_grouped.items(), key=lambda x: -x[1]):
    summary_parts.append("{}:{}只".format(reason, count))

entry_dist = {}
for ff in factors_out:
    et = ff['entryType']
    entry_dist[et] = entry_dist.get(et, 0) + 1
entry_parts = ["{}:{}".format(et, cnt) for et, cnt in entry_dist.items()]
summary_parts.append("入场:" + ','.join(entry_parts))

final_summary = "|".join(summary_parts)

result = {
    'runId': '20260720_short-term-picks',
    'asOf': '20260720',
    'goal': 'short-term-picks',
    'agent': 'technical-liquidity',
    'fetchedAt': '20260720',
    'data': {
        'pass': pass_list,
        'reject': reject_list,
        'factors': factors_out,
    },
    'summary': final_summary,
    'keyFields': {
        'passCodes': ','.join([pp['code'] for pp in pass_list]),
        'totalCandidates': total_candidates,
        'passCount': len(pass_list),
        'rejectCount': len(reject_list),
    },
}

outdir = "data/runs/20260720_short-term-picks"
os.makedirs(outdir, exist_ok=True)
outpath = os.path.join(outdir, "technical-liquidity.json")
with open(outpath, 'w', encoding='utf-8') as fout:
    json.dump(result, fout, ensure_ascii=False, indent=2)

print("\n[DONE] Written to {}".format(outpath), file=sys.stderr)
print(json.dumps(result, ensure_ascii=False, indent=2))
