#!/usr/bin/env python
"""Technical Liquidity Agent v3 - 20260721 hot-trends batch analysis.
Fixed: 科创板(688) volume in 股, main board/创业板 in 手.
Turnover >7% is soft warning, not hard rejection.
Hard thresholds: 日均成交额<1亿, 流通市值<30亿, 一字涨停/跌停, ST, 次新, 透支.
Uses Tencent HTTP (K-line + real-time) — self-handles SSL.
"""
import urllib.request, json, gzip, ssl, re, sys, os

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE
HDR = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Accept-Encoding': 'gzip, deflate'}

CANDIDATES = [
    {"code": "600667", "name": "太极实业", "sector": "存储芯片+先进封装", "note": "存储芯片+先进封装+无锡国资"},
    {"code": "600206", "name": "有研新材", "sector": "存储芯片+半导体材料", "note": "半导体靶材+存储芯片"},
    {"code": "002185", "name": "华天科技", "sector": "先进封装", "note": "先进封装+存储芯片,换手20.95%"},
    {"code": "000021", "name": "深科技", "sector": "存储芯片+先进封装", "note": "高端存储封测+央企"},
    {"code": "603005", "name": "晶方科技", "sector": "先进封装", "note": "先进封装+车规CIS"},
    {"code": "001399", "name": "惠科股份", "sector": "先进封装+半导体显示", "note": "先进封装+龙虎榜净买1.39亿"},
    {"code": "600641", "name": "先导基电", "sector": "半导体设备", "note": "拟收购先导微电子+半导体设备"},
    {"code": "600460", "name": "士兰微", "sector": "半导体+中报预增", "note": "SiC+中报预增+IDM"},
    {"code": "688371", "name": "菲沃泰", "sector": "半导体+液冷", "note": "纳米镀膜+科创板20%涨停"},
    {"code": "688729", "name": "屹唐股份", "sector": "半导体设备", "note": "半导体设备+科创板20%涨停"},
    {"code": "688549", "name": "中巨芯-U", "sector": "半导体材料", "note": "半导体电子化学品"},
    {"code": "688783", "name": "西安奕材-U", "sector": "半导体材料", "note": "半导体硅片,次新"},
    {"code": "688728", "name": "格科微", "sector": "数字芯片设计", "note": "CIS芯片+科创板20%涨停"},
    {"code": "603936", "name": "博敏电子", "sector": "PCB+光模块+存储芯片", "note": "PCB+光模块+存储芯片"},
    {"code": "688135", "name": "利扬芯片", "sector": "芯片测试", "note": "芯片测试+存储芯片"},
    {"code": "688262", "name": "国芯科技", "sector": "芯片设计", "note": "芯片设计+存储芯片"},
    {"code": "688216", "name": "气派科技", "sector": "先进封装", "note": "先进封装测试"},
    {"code": "688711", "name": "宏微科技", "sector": "功率半导体", "note": "功率半导体+IGBT"},
    {"code": "688209", "name": "英集芯", "sector": "电源管理芯片", "note": "电源管理芯片+快充"},
    {"code": "688595", "name": "芯海科技", "sector": "芯片设计", "note": "模拟芯片+MCU"},
    {"code": "688259", "name": "创耀科技", "sector": "通信芯片", "note": "通信芯片+光通信"},
    {"code": "688484", "name": "南芯科技", "sector": "电源管理芯片", "note": "电源管理芯片+快充"},
    {"code": "688106", "name": "金宏气体", "sector": "半导体材料", "note": "半导体特种气体"},
    {"code": "002396", "name": "星网锐捷", "sector": "光通信/CPO", "note": "数据中心交换机+CPO"},
    {"code": "600330", "name": "天通股份", "sector": "光通信/光模块", "note": "光模块上游+铌酸锂"},
    {"code": "600522", "name": "中天科技", "sector": "光通信", "note": "光纤光缆+海缆"},
    {"code": "002273", "name": "水晶光电", "sector": "光通信/CPO", "note": "AI光学+CPO"},
    {"code": "002245", "name": "蔚蓝锂芯", "sector": "中报预增+人形机器人", "note": "BBU电源+人形机器人"},
    {"code": "301282", "name": "金禄电子", "sector": "AI算力/PCB+中报预增", "note": "半年度业绩预增+AI算力PCB"},
    {"code": "605133", "name": "嵘泰股份", "sector": "人形机器人", "note": "人形机器人+行星滚柱丝杠"},
    {"code": "002448", "name": "中原内配", "sector": "人形机器人+中报预增", "note": "人形机器人+中报预增,PE=12.8"},
    {"code": "603890", "name": "春秋电子", "sector": "人形机器人+AI算力", "note": "液冷服务器+人形机器人"},
    {"code": "002669", "name": "康达新材", "sector": "AI算力/PCB", "note": "PCB概念+电子级环氧树脂"},
]

SUBNEW_CODES = {'688783'}

def is_kcb(code):
    """科创板(688xxx): volume in 股; others: volume in 手"""
    return code.startswith('688')

def fetch_qt(codes):
    tcodes = [f"sh{c}" if c.startswith('6') else f"sz{c}" for c in codes]
    url = f"https://qt.gtimg.cn/q={','.join(tcodes)}"
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as resp:
        raw = resp.read()
        if resp.headers.get('Content-Encoding') == 'gzip':
            raw = gzip.decompress(raw)
        return raw.decode('gbk', errors='replace')

def parse_qt_line(line):
    m = re.match(r'v_(?:sh|sz)(\d+)="(.+)"', line)
    if not m: return None
    code = m.group(1)
    f = m.group(2).split('~')
    if len(f) < 50: return None
    try:
        return {
            'code': code, 'name': f[1],
            'price': float(f[3]) if f[3] else 0,
            'prev_close': float(f[4]) if f[4] else 0,
            'open': float(f[5]) if f[5] else 0,
            'high': float(f[33]) if f[33] else 0,
            'low': float(f[34]) if f[34] else 0,
            'volume': float(f[6]) if f[6] else 0,
            'amount_wan': float(f[37]) if f[37] else 0,
            'turnover': float(f[38]) if f[38] else 0,
            'pe': float(f[39]) if f[39] else 0,
            'pb': float(f[46]) if f[46] else 0,
            'circ_mv_yi': float(f[44]) if f[44] else 0,
            'total_mv_yi': float(f[45]) if f[45] else 0,
            'vol_ratio': float(f[49]) if f[49] else 0,
            'day_pct': float(f[32]) if f[32] else 0,
            'amplitude': float(f[43]) if f[43] else 0,
        }
    except: return None

def fetch_kline(code, count=60):
    market = 'sh' if code.startswith('6') else 'sz'
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,,,{count},qfq"
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as resp:
            raw = resp.read()
            if resp.headers.get('Content-Encoding') == 'gzip':
                raw = gzip.decompress(raw)
            d = json.loads(raw.decode('utf-8', errors='replace'))
            key = f'{market}{code}'
            obj = d.get('data', {}).get(key, {})
            kls = obj.get('qfqday') or obj.get('day') or []
            return kls
    except: return None

def calc_momentum(klines, code, circ_mv_yi, price):
    if not klines or len(klines) < 25: return None
    closes, vols = [], []
    for k in klines[-30:]:
        try:
            if isinstance(k, list) and len(k) >= 6:
                closes.append(float(k[2]))
                vols.append(float(k[5]))
        except: continue
    if len(closes) < 21: return None
    cur = closes[-1]
    m5 = (cur / closes[-6] - 1) * 100 if len(closes) >= 6 and closes[-6] else 0
    m10 = (cur / closes[-11] - 1) * 100 if len(closes) >= 11 and closes[-11] else 0
    m20 = (cur / closes[-21] - 1) * 100 if len(closes) >= 21 and closes[-21] else 0
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20

    # Volume unit: 科创板(688) in 股, 主板/创业板 in 手
    kcb = is_kcb(code)
    vol_mult = 1 if kcb else 100  # convert to 股

    avg_vol_20_shares = sum(vols[-20:]) * vol_mult / 20
    avg_amt_20 = sum(v * vol_mult * c for v, c in zip(vols[-20:], closes[-20:])) / 20

    # Total shares from circ_mv
    total_shares = (circ_mv_yi * 1e8) / price if price > 0 else 1
    avg_turnover_20 = avg_vol_20_shares / total_shares * 100

    # 5-day momentum quality
    up_days = sum(1 for i in range(-5, 0) if closes[i] > closes[i-1])
    max_day_gain = max((closes[i] - closes[i-1]) / closes[i-1] * 100 for i in range(-5, 0))
    up_vol = sum(vols[i] for i in range(-5, 0) if closes[i] > closes[i-1])
    down_vol = sum(vols[i] for i in range(-5, 0) if closes[i] < closes[i-1])
    vol_health = up_vol / down_vol if down_vol > 0 else 2.0
    mom_accel = (m5 / 5) - ((m10 - m5) / 5) if m10 != m5 else 0
    recent_high = max(closes[-20:])
    pullback = (cur - recent_high) / recent_high * 100
    avg_vol_5_shares = sum(vols[-5:]) * vol_mult / 5
    pullback_vol_ratio = avg_vol_5_shares / avg_vol_20_shares if avg_vol_20_shares > 0 else 1.0

    # RSI-14
    gains, losses = 0, 0
    for i in range(-14, 0):
        if i >= -len(closes):
            diff = closes[i] - closes[i-1]
            if diff > 0: gains += diff
            else: losses += abs(diff)
    rs = gains / losses if losses > 0 else 100
    rsi = 100 - (100 / (1 + rs)) if rs else 50

    return {
        'm5': round(m5, 2), 'm10': round(m10, 2), 'm20': round(m20, 2),
        'ma5': round(ma5, 2), 'ma10': round(ma10, 2), 'ma20': round(ma20, 2),
        'avg_amt_20': avg_amt_20, 'avg_vol_20_shares': avg_vol_20_shares,
        'avg_turnover_20': round(avg_turnover_20, 2),
        'up_days_5': up_days, 'max_day_gain_5': round(max_day_gain, 2),
        'vol_health': round(vol_health, 2), 'mom_accel': round(mom_accel, 2),
        'pullback_depth': round(pullback, 2), 'pullback_vol_ratio': round(pullback_vol_ratio, 2),
        'rsi': round(rsi, 1), 'close': round(closes[-1], 2),
        'above_ma5': cur > ma5, 'above_ma10': cur > ma10, 'above_ma20': cur > ma20,
        'kcb': kcb, 'vol_mult': vol_mult,
    }

def main():
    print(f"Processing {len(CANDIDATES)} candidates...", file=sys.stderr)
    codes = [c['code'] for c in CANDIDATES]

    print("Fetching Tencent real-time quotes...", file=sys.stderr)
    qt_raw = fetch_qt(codes)
    qt_map = {}
    for line in qt_raw.strip().split('\n'):
        p = parse_qt_line(line)
        if p: qt_map[p['code']] = p
    print(f"  Got {len(qt_map)} quotes", file=sys.stderr)

    print("Fetching K-lines...", file=sys.stderr)
    mom_map = {}
    for i, c in enumerate(CANDIDATES):
        code = c['code']
        qt = qt_map.get(code)
        kls = fetch_kline(code, 60)
        if kls and qt:
            mom = calc_momentum(kls, code, qt['circ_mv_yi'], qt['price'])
            if mom: mom_map[code] = mom
        if (i+1) % 10 == 0:
            print(f"  {i+1}/{len(CANDIDATES)}...", file=sys.stderr)
    print(f"  Got {len(mom_map)} momentum results", file=sys.stderr)

    pass_list, reject_list, factors_list = [], [], []

    for c in CANDIDATES:
        code, name = c['code'], c['name']
        qt = qt_map.get(code)
        mom = mom_map.get(code)
        if not qt:
            reject_list.append({'code': code, 'name': name, 'reason': '行情数据缺失'})
            continue

        hard_reasons = []
        soft_warnings = []

        # === HARD THRESHOLDS ===
        if 'ST' in qt['name']: hard_reasons.append('ST股')
        if code in SUBNEW_CODES: hard_reasons.append('次新(上市<60交易日)')
        if qt['day_pct'] >= 9.9 and qt['turnover'] < 1.0: hard_reasons.append('一字涨停(换手<1%)')
        if qt['day_pct'] <= -9.9 and qt['turnover'] < 0.5: hard_reasons.append('封死跌停')
        if qt['circ_mv_yi'] < 30: hard_reasons.append(f'流通市值{qt["circ_mv_yi"]:.1f}亿<30亿')
        if qt['price'] > 40: hard_reasons.append(f'股价{qt["price"]}元>40元(1w不可配)')

        if mom:
            avg_amt_yi = mom['avg_amt_20'] / 1e8
            if avg_amt_yi < 1.0: hard_reasons.append(f'日均成交额{avg_amt_yi:.2f}亿<1亿')

        # === SOFT WARNINGS ===
        if mom:
            if mom['avg_turnover_20'] > 7: soft_warnings.append(f'20日均换手率{mom["avg_turnover_20"]:.1f}%>7%(高位警惕派发)')
            if mom['avg_turnover_20'] < 1: soft_warnings.append(f'20日均换手率{mom["avg_turnover_20"]:.1f}%<1%(偏冷)')
        if qt['vol_ratio'] < 0.8: soft_warnings.append(f'量比{qt["vol_ratio"]:.2f}<0.8(地量)')
        if qt['vol_ratio'] > 3: soft_warnings.append(f'量比{qt["vol_ratio"]:.2f}>3(天量)')
        if qt['turnover'] > 15: soft_warnings.append(f'当日换手率{qt["turnover"]:.1f}%极高(>15%)')

        # Exhaustion
        if mom:
            if mom['m20'] > 25 and mom['m5'] < 0: hard_reasons.append(f'透支(近20日+{mom["m20"]:.1f}%但近5日{mom["m5"]:.1f}%)')
            if mom['m5'] > 15: hard_reasons.append(f'透支(近5日+{mom["m5"]:.1f}%>15%)')

        if hard_reasons:
            reject_list.append({
                'code': code, 'name': name,
                'reason': '; '.join(hard_reasons),
                'warnings': soft_warnings if soft_warnings else None,
                'price': qt['price'], 'dayPct': qt['day_pct'],
            })
            continue

        # Passed
        pass_list.append({
            'code': code, 'name': name, 'price': qt['price'],
            'avgAmount20d': f"{mom['avg_amt_20']/1e8:.2f}亿" if mom else 'N/A',
            'turnover20d': f"{mom['avg_turnover_20']:.1f}%" if mom else 'N/A',
            'turnoverToday': f"{qt['turnover']:.2f}%",
            'volumeRatio': qt['vol_ratio'],
            'marketCap': f"{qt['circ_mv_yi']:.1f}亿",
            'warnings': soft_warnings if soft_warnings else None,
            'pass': True,
        })

        # Factors
        if mom:
            entry_type, entry_score = None, 0
            exhaustion_prob = '低(<30%)'

            if mom['above_ma20'] and -8 <= mom['m5'] <= -3 and mom['pullback_vol_ratio'] < 0.8 and 40 <= mom['rsi'] <= 50:
                entry_type, entry_score = '健康回调买点', 20
            elif mom['above_ma20'] and -3 < mom['m5'] < 0 and mom['pullback_vol_ratio'] < 0.9:
                entry_type, entry_score = '突破回踩确认', 15
            elif mom['m20'] < -15 and mom['m5'] > 0 and mom['pullback_vol_ratio'] > 1.2:
                entry_type, entry_score = '超跌反弹启动', 10
            elif mom['m5'] > 10 and mom['pullback_vol_ratio'] > 1.5 and mom['pullback_depth'] > -3:
                entry_type, entry_score = '追涨入场(动量透支)', -15
            elif mom['m20'] > 20 and mom['pullback_vol_ratio'] > 1.2 and not mom['above_ma5']:
                entry_type, entry_score = '高位派发', -20
            if mom['m20'] < -25 and mom['rsi'] < 30 and mom['m5'] > 0:
                if not entry_type:
                    entry_type, entry_score = '均值回归(超跌反弹)', 8

            if mom['m5'] > 15: exhaustion_prob = '高概率(>70%)'
            elif mom['m20'] > 25 and mom['m5'] < 0: exhaustion_prob = '极高(>80%)'
            elif 5 <= mom['m5'] <= 15: exhaustion_prob = '低(<30%)'

            if mom['above_ma20'] and mom['m5'] > 0 and mom['m10'] > 0 and mom['m20'] > 0:
                tech_level = "上升趋势(5/10/20日动量全正,站上MA20)"
            elif mom['m20'] > 20 and mom['m5'] < 0:
                tech_level = f"高位回调(20日+{mom['m20']:.1f}%但5日{mom['m5']:.1f}%)"
            elif mom['m20'] < 0 and mom['m5'] > 0:
                tech_level = f"超跌反弹(20日{mom['m20']:.1f}%但5日+{mom['m5']:.1f}%)"
            elif mom['above_ma20']:
                tech_level = "站上MA20但动量不全正"
            else:
                tech_level = f"跌破MA20(MA5={mom['ma5']:.2f}/MA10={mom['ma10']:.2f}/MA20={mom['ma20']:.2f})"

            factors_list.append({
                'code': code, 'name': name,
                'm5': mom['m5'], 'm10': mom['m10'], 'm20': mom['m20'],
                'momentumUniformity': f"{mom['up_days_5']}/5天涨,最大单日{mom['max_day_gain_5']}%",
                'volumeHealth': mom['vol_health'],
                'momentumAccel': mom['mom_accel'],
                'entryType': entry_type, 'entryScore': entry_score,
                'meanReversionSignal': '均值回归(超跌反弹)' if (mom['m20'] < -25 and mom['rsi'] < 30) else None,
                'pullbackDepth': mom['pullback_depth'],
                'pullbackVolume': '缩量' if mom['pullback_vol_ratio'] < 0.8 else ('放量' if mom['pullback_vol_ratio'] > 1.2 else '平量'),
                'exhaustionProb': exhaustion_prob,
                'breakout': f"{'站上' if mom['above_ma20'] else '跌破'}MA20",
                'aboveMA20': mom['above_ma20'],
                'rsi': mom['rsi'],
                'technicalLevel': tech_level,
                'momentumQualityScore': (5 if mom['up_days_5'] >= 4 else 0) + (5 if mom['max_day_gain_5'] < 8 else 0) + (5 if mom['vol_health'] > 1.2 else 0),
            })
        else:
            factors_list.append({
                'code': code, 'name': name,
                'm5': None, 'm10': None, 'm20': None,
                'momentumUniformity': 'K线数据缺失',
                'volumeHealth': None, 'momentumAccel': None,
                'entryType': None, 'entryScore': 0,
                'meanReversionSignal': None, 'pullbackDepth': None, 'pullbackVolume': None,
                'exhaustionProb': None, 'breakout': 'N/A', 'aboveMA20': None, 'rsi': None,
                'technicalLevel': 'K线数据缺失-降级为快照粗判',
                'momentumQualityScore': 0,
            })

    entry_types = [f['entryType'] for f in factors_list if f.get('entryType')]
    reject_reasons = [r['reason'] for r in reject_list]
    top_reject = max(set(reject_reasons), key=reject_reasons.count) if reject_reasons else 'N/A'
    warning_count = sum(1 for p in pass_list if p.get('warnings'))

    output = {
        'pass': pass_list,
        'reject': reject_list,
        'factors': factors_list,
        'summary': f"过关{len(pass_list)}只/剔除{len(reject_list)}只({warning_count}只带软警告);入场优势分布:{entry_types};主要剔除原因:{top_reject}",
    }
    return output

if __name__ == '__main__':
    output = main()
    out_dir = 'e:/finacial-invest/data/runs/20260721_hot-trends'
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'technical-liquidity.json')
    envelope = {
        'runId': '20260721_hot-trends', 'asOf': '20260721',
        'goal': 'hot-trends', 'agent': 'technical-liquidity',
        'fetchedAt': '20260721', 'data': output,
        'summary': output['summary'],
        'keyFields': {
            'passCodes': ','.join(p['code'] for p in output['pass']),
            'passed': len(output['pass']), 'rejected': len(output['reject']),
            'dataSource': '腾讯qt.gtimg.cn(行情)+web.ifzq.gtimg.cn(K线),SSL自处理',
            'note': 'ifind/akshare/wind MCP全挂SSL,走腾讯HTTP兜底',
        }
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)
    print(f'\nOutput written to {out_path}', file=sys.stderr)
    print(json.dumps(envelope['keyFields'], ensure_ascii=False, indent=2))