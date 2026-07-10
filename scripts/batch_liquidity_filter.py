#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch liquidity filter + short-term factors for 36 candidate stocks <40 yuan.
Uses Tencent K-line (web.ifzq.gtimg.cn) for daily OHLCV + Tencent quote (qt.gtimg.cn) for snapshot.
Fixed: m[37]=万元(÷1e4得亿), m[44/45]=亿(直接用), STAR市场vol=股(不用×100)
"""
import urllib.request, json, sys, time, os, ssl

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
_CTX = ssl._create_unverified_context()

def _get(url, encoding='utf-8', timeout=25, retry=3):
    h = dict(UA)
    req = urllib.request.Request(url, headers=h)
    last = None
    for _ in range(retry):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                return r.read().decode(encoding, 'ignore')
        except Exception as e:
            last = e
            time.sleep(0.5)
    raise last

def fetch_kline(symbol):
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,30,qfq"
    try:
        txt = _get(url)
        j = json.loads(txt)
        data = j.get('data', {})
        arr = data.get(symbol, {}).get('qfqday', [])
        if not arr:
            arr = data.get(symbol, {}).get('day', [])
        return arr
    except Exception:
        return None

def fetch_snapshot(symbol):
    url = f"http://qt.gtimg.cn/q={symbol}"
    try:
        txt = _get(url, encoding='gbk')
        for line in txt.strip().split(';'):
            line = line.strip()
            if not line:
                continue
            m = line.split('~')
            if len(m) < 50:
                continue
            # m[37] = 成交额(万元) -> /1e4 = 亿
            # m[44] = 流通市值(亿), m[45] = 总市值(亿)
            amount_yi = round(float(m[37]) / 1e4, 2) if m[37] and m[37].strip() else 0
            return {
                'name': m[1],
                'price': float(m[3]),
                'prev_close': float(m[4]),
                'open': float(m[5]),
                'high': float(m[33]) if m[33] else 0,
                'low': float(m[34]) if m[34] else 0,
                'amount_yi': amount_yi,
                'turnover_pct': float(m[38]) if m[38] else 0,
                'volume_hand': float(m[6]) if m[6] else 0,
                'pct_chg': float(m[32]) if m[32] else 0,
                'float_mktcap_yi': round(float(m[44]), 2) if m[44] and m[44].strip() else None,
                'total_mktcap_yi': round(float(m[45]), 2) if m[45] and m[45].strip() else None,
                'pe_ttm': float(m[39]) if m[39] and m[39].strip() else None,
            }
    except Exception:
        pass
    return None

def compute_factors(klines, symbol):
    """Compute short-term factors. Handle STAR market (688xxx) vol=shares."""
    if not klines or len(klines) < 20:
        return None

    # Detect if STAR market by checking if any recent vol > 10M (shares unit)
    # Non-STAR vol is typically < 10M hands; STAR vol is typically > 10M shares
    recent_vols = [float(x[5]) for x in klines[-5:] if len(x) >= 6]
    is_star = any(v > 10000000 for v in recent_vols)
    vol_mult = 1 if is_star else 100  # shares vs hands

    rows = []
    for x in klines:
        if len(x) < 6:
            continue
        rows.append({
            'date': x[0],
            'close': float(x[2]),
            'high': float(x[3]),
            'low': float(x[4]),
            'vol': float(x[5]),
        })
    closes = [r['close'] for r in rows]
    vols = [r['vol'] for r in rows]
    last = rows[-1]

    def mom(d):
        if len(closes) > d:
            return (closes[-1] - closes[-1 - d]) / closes[-1 - d] * 100
        return None

    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20
    v5 = sum(vols[-5:]) / 5
    v20 = sum(vols[-20:]) / 20

    breakout = last['close'] > ma20 and last['vol'] > v5 * 1.5

    # 20-day avg daily amount with correct vol unit
    amt20 = sum(rows[i]['vol'] * vol_mult * rows[i]['close']
                for i in range(max(0, len(rows)-20), len(rows))) / min(20, len(rows))
    amt20_yi = amt20 / 1e8

    m5 = mom(5)
    m10 = mom(10)
    m20 = mom(20)

    return {
        'm5': round(m5, 2) if m5 is not None else None,
        'm10': round(m10, 2) if m10 is not None else None,
        'm20': round(m20, 2) if m20 is not None else None,
        'ma5': round(ma5, 2),
        'ma10': round(ma10, 2),
        'ma20': round(ma20, 2),
        'breakout': breakout,
        'amt20_yi': round(amt20_yi, 2),
        'above_ma20': last['close'] > ma20,
        'above_ma5': last['close'] > ma5,
        'above_ma10': last['close'] > ma10,
        'latest_vol': last['vol'],
        'latest_close': last['close'],
        'latest_date': last['date'],
        'v5_avg': round(v5, 0),
        'v20_avg': round(v20, 0),
        'is_star': is_star,
        'vol_mult': vol_mult,
    }

def liquidity_filter(factors, snapshot, code, name):
    reasons = []

    # 1. Avg daily amount >= 1亿
    if factors and factors.get('amt20_yi', 0) < 1:
        reasons.append(f"20日均成交额{factors['amt20_yi']}亿<1亿")

    # 2. Turnover rate 1%-7%
    tr = snapshot.get('turnover_pct', 0) if snapshot else 0
    if tr < 1:
        reasons.append(f"换手率{tr}%<1%偏冷")
    elif tr > 7:
        reasons.append(f"换手率{tr}%>7%高位派发警示")

    # 3. Float market cap >= 30亿
    fmc = snapshot.get('float_mktcap_yi') if snapshot else None
    if fmc is not None and fmc < 30:
        reasons.append(f"自由流通市值{fmc}亿<30亿")

    # 4. Not ST
    if 'ST' in name or '退' in name:
        reasons.append("ST/退市股")

    # 5. Limit up/down (STAR/ChiNext=20%, others=10%)
    if snapshot:
        pct = snapshot.get('pct_chg', 0)
        is_star_or_chinext = code.startswith('688') or code.startswith('300')
        limit_up = 19.9 if is_star_or_chinext else 9.9
        limit_down = -19.9 if is_star_or_chinext else -9.9
        if pct >= limit_up:
            reasons.append(f"涨停({pct:.1f}%)封死")
        elif pct <= limit_down:
            reasons.append(f"跌停({pct:.1f}%)封死")

    # 6. Dilution: any of 5/10/20 day cumulative > 30%
    if factors:
        m5 = factors.get('m5')
        m10 = factors.get('m10')
        m20 = factors.get('m20')
        if m5 is not None and m5 > 30:
            reasons.append(f"5日涨幅{m5}%>30%透支")
        if m10 is not None and m10 > 30:
            reasons.append(f"10日涨幅{m10}%>30%透支")
        if m20 is not None and m20 > 30:
            reasons.append(f"20日涨幅{m20}%>30%透支")
        # High-position pullback: 20-day > 20% but 5-day negative
        if m20 is not None and m20 > 20 and m5 is not None and m5 < 0:
            reasons.append(f"高位回调(20日+{m20}%,5日{m5}%)")

    return len(reasons) == 0, reasons

def main():
    candidates = [
        ('sz002405', '002405', '四维图新', 6.41, '信创/网络安全'),
        ('sz300369', '300369', '绿盟科技', 6.48, '信创/网络安全'),
        ('sz002413', '002413', '雷科防务', 8.66, '信创/网络安全'),
        ('sh603712', '603712', '七一二', 11.86, '信创/网络安全'),
        ('sz002777', '002777', '久远银海', 12.07, '信创/网络安全'),
        ('sh603927', '603927', '中科软', 12.86, '信创/网络安全'),
        ('sh600756', '600756', '浪潮软件', 13.23, '信创/网络安全'),
        ('sz002368', '002368', '太极股份', 13.84, '信创/网络安全'),
        ('sz300017', '300017', '网宿科技', 14.66, '信创/网络安全'),
        ('sz300166', '300166', '东方国信', 15.94, '信创/网络安全'),
        ('sz000997', '000997', '新大陆', 16.15, '信创/网络安全'),
        ('sh600602', '600602', '云赛智联', 16.38, '信创/网络安全'),
        ('sh600288', '600288', '大恒科技', 17.11, '信创/网络安全'),
        ('sh600845', '600845', '宝信软件', 19.40, '信创/网络安全'),
        ('sh603137', '603137', '恒尚节能', 22.91, '信创/网络安全'),
        ('sh603881', '603881', '数据港', 24.21, '信创/网络安全'),
        ('sh688561', '688561', '奇安信-U', 25.60, '信创/网络安全'),
        ('sh603039', '603039', '泛微网络', 35.09, '信创/网络安全'),
        ('sz300287', '300287', '飞利信', 3.85, '半导体'),
        ('sz000725', '000725', '京东方A', 7.63, '半导体'),
        ('sz300638', '300638', '广和通', 17.30, '半导体'),
        ('sz002185', '002185', '华天科技', 21.57, '半导体'),
        ('sh688126', '688126', '沪硅产业', 32.50, '半导体'),
        ('sz000564', '000564', '供销大集', 1.31, '油气'),
        ('sh600157', '600157', '永泰能源', 1.55, '油气'),
        ('sh600871', '600871', '石化油服', 2.06, '油气'),
        ('sz002554', '002554', '惠博普', 2.94, '油气'),
        ('sz002629', '002629', '仁智股份', 4.40, '油气'),
        ('sh600028', '600028', '中国石化', 4.83, '油气'),
        ('sh600583', '600583', '海油工程', 5.14, '油气'),
        ('sz000983', '000983', '山西焦煤', 6.24, '油气'),
        ('sz300164', '300164', '通源石油', 8.13, '油气'),
        ('sz000425', '000425', '徐工机械', 8.46, '油气'),
        ('sh601808', '601808', '中海油服', 11.63, '油气'),
        ('sh601089', '601089', '福元医药', 16.97, '油气'),
        ('sz002830', '002830', '名雕股份', 17.84, '油气'),
    ]

    pass_list = []
    reject_list = []
    factors_list = []

    total = len(candidates)

    for idx, (symbol, code, name, price, sector) in enumerate(candidates):
        print(f"[{idx+1}/{total}] {code} {name}...", file=sys.stderr)

        klines = fetch_kline(symbol)
        time.sleep(0.15)

        snapshot = fetch_snapshot(symbol)
        time.sleep(0.15)

        factors = compute_factors(klines, symbol)

        display_price = snapshot['price'] if snapshot else price

        passes, reasons = liquidity_filter(factors, snapshot, code, name)

        amt = factors['amt20_yi'] if factors else 'N/A'
        fmc = snapshot['float_mktcap_yi'] if snapshot else 'N/A'
        tr = snapshot['turnover_pct'] if snapshot else 'N/A'
        print(f"  amt20={amt}亿 fmc={fmc}亿 tr={tr}% m5={factors['m5'] if factors else 'N/A'}", file=sys.stderr)

        entry = {
            'code': code,
            'name': name,
            'price': round(display_price, 2),
            'sector': sector,
        }

        if factors:
            entry['avgAmount20d'] = factors['amt20_yi']
            entry['turnover20d'] = round(snapshot['turnover_pct'], 2) if snapshot else None
            entry['m5'] = factors['m5']
            entry['m10'] = factors['m10']
            entry['m20'] = factors['m20']
            entry['aboveMA20'] = factors['above_ma20']
            entry['breakout'] = factors['breakout']
            entry['ma5'] = factors['ma5']
            entry['ma10'] = factors['ma10']
            entry['ma20'] = factors['ma20']

            # Volume ratio (latest vol / 5-day avg vol)
            if klines and len(klines) >= 6:
                rows_v = [float(x[5]) for x in klines[-6:]]
                latest_vol = rows_v[-1]
                avg5_vol = sum(rows_v[:-1]) / 5
                entry['volumeRatio'] = round(latest_vol / avg5_vol, 2) if avg5_vol > 0 else None

        if snapshot:
            entry['marketCap'] = snapshot.get('total_mktcap_yi')
            entry['floatMarketCap'] = snapshot.get('float_mktcap_yi')
            entry['turnoverRate'] = snapshot.get('turnover_pct')
            entry['todayPct'] = snapshot.get('pct_chg')
            entry['amountTodayYi'] = snapshot.get('amount_yi')

        if passes:
            entry['pass'] = True
            pass_list.append(entry)
        else:
            entry['reject_reasons'] = reasons
            entry['pass'] = False
            reject_list.append(entry)

        # Factors entry
        factors_entry = {'code': code, 'name': name}
        if factors:
            factors_entry.update({
                'm5': factors['m5'],
                'm10': factors['m10'],
                'm20': factors['m20'],
                'breakout': factors['breakout'],
                'aboveMA20': factors['above_ma20'],
                'amt20_yi': factors['amt20_yi'],
                'latest_close': factors['latest_close'],
                'latest_date': factors['latest_date'],
            })
        else:
            factors_entry.update({'m5': None, 'm10': None, 'm20': None,
                                  'breakout': False, 'aboveMA20': False, 'amt20_yi': None})

        # Technical level
        if factors and factors.get('m5') is not None and factors.get('m10') is not None and factors.get('m20') is not None:
            m5, m10, m20 = factors['m5'], factors['m10'], factors['m20']
            if m5 > 0 and m10 > 0 and m20 > 0 and factors['above_ma20']:
                tech_level = '上升趋势'
            elif m20 > 20 and m5 < 0:
                tech_level = '高位回调'
            elif m20 < 0 and m5 > 0:
                tech_level = '超跌反弹'
            elif m5 > 0:
                tech_level = '强势整理'
            else:
                tech_level = '弱势/震荡'
        else:
            tech_level = 'K线数据缺失'

        factors_entry['technicalLevel'] = tech_level
        factors_entry['rps'] = None
        factors_list.append(factors_entry)

        time.sleep(0.2)

    # Compute RPS based on m5 ranking
    valid_m5 = [(fe['code'], fe['m5']) for fe in factors_list if fe.get('m5') is not None]
    valid_m5.sort(key=lambda x: x[1] if x[1] else -999, reverse=True)
    n_valid = len(valid_m5)
    for rank_pos, (code, m5) in enumerate(valid_m5):
        rps = round((rank_pos + 1) / n_valid * 100, 1)
        for fe in factors_list:
            if fe['code'] == code:
                fe['rps'] = rps

    result = {
        'pass': pass_list,
        'reject': reject_list,
        'factors': factors_list,
        'summary': f"共{total}只候选,过关{len(pass_list)}只,剔除{len(reject_list)}只",
    }

    print(f"\n=== SUMMARY ===", file=sys.stderr)
    print(f"Total: {total}, Pass: {len(pass_list)}, Reject: {len(reject_list)}", file=sys.stderr)

    rejected_codes = [r['code'] for r in reject_list]
    passed_codes = [p['code'] for p in pass_list]
    print(f"REJECT ({len(reject_list)}): {rejected_codes}", file=sys.stderr)
    print(f"PASS ({len(pass_list)}): {passed_codes}", file=sys.stderr)

    for r in reject_list:
        print(f"  {r['code']} {r['name']}: {r.get('reject_reasons', [])}", file=sys.stderr)

    # Write output
    out_dir = '/Volumes/Macintosh HD/project/finacial-claude/data/runs/20260708_short-term-picks'
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'technical-liquidity.json')

    output = {
        'runId': '20260708_short-term-picks',
        'asOf': '20260708',
        'goal': 'short-term-picks',
        'agent': 'technical-liquidity',
        'fetchedAt': '20260708',
        'data': result,
        'summary': result['summary'],
        'keyFields': {
            'codes_pass': passed_codes,
            'codes_reject': rejected_codes,
            'pass_count': len(pass_list),
            'reject_count': len(reject_list),
        }
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nWritten to {out_path}", file=sys.stderr)

if __name__ == '__main__':
    main()
