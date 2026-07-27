#!/usr/bin/env python
"""Rebuild technical-liquidity.json with correct volume handling for 科创板."""
import json, os, ssl, urllib.request, time

# ============================================================
# Re-fetch everything with correct volume handling
# ============================================================

codes = ['002185','002436','688709','688685','300480','688549','600667','300802','002388',
         '000063','002415','600522','002396','002491','300007','300045','002407','300444',
         '601179','300040','300062','300593','300580','600775','000676','300433']

def tc(c):
    return ('sh' if c.startswith('6') else 'sz') + c

def is_kcb(code):
    """科创板 (688xxx)"""
    return code.startswith('688')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# --- Fetch quotes ---
print('Fetching quotes...')
tcs = ','.join(tc(c) for c in codes)
url = f'http://qt.gtimg.cn/q={tcs}'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, context=ctx, timeout=15)
raw = resp.read().decode('gbk', errors='replace')

quotes = {}
for line in raw.strip().split('\n'):
    if not line.strip():
        continue
    parts = line.split('"')
    if len(parts) < 2:
        continue
    data = parts[1]
    fields = data.split('~')
    if len(fields) < 50:
        continue
    code = fields[2]
    quotes[code] = {
        'name': fields[1],
        'price': float(fields[3]) if fields[3] else 0,
        'volume': int(fields[6]) if fields[6] else 0,
        'amount': float(fields[37]) if fields[37] else 0,  # 万元
        'turnover': float(fields[38]) if fields[38] else 0,
        'pe': float(fields[39]) if fields[39] else 0,
        'mktcap': float(fields[45]) if fields[45] else 0,
        'high': float(fields[33]) if fields[33] else 0,
        'low': float(fields[34]) if fields[34] else 0,
    }

# --- Load klines ---
print('Loading klines...')
with open('data/runs/20260727_short-term-picks/klines.json', 'r') as f:
    klines_data = json.load(f)

# --- Kline amount helper ---
def kline_amount(vol, close, code):
    """Convert K-line volume to amount in 万元.

    科创板 (688xxx): volume is in shares → amount = vol * close / 10000
    主板/创业板: volume is in 手 (100 shares) → amount = vol * 100 * close / 10000 = vol * close / 100
    """
    if is_kcb(code):
        return vol * close / 10000
    else:
        return vol * close / 100

# --- Compute factors ---
print('Computing factors...')
results = []
for code in codes:
    q = quotes.get(code, {})
    klines = klines_data.get(code, [])

    if not q or not klines:
        results.append({
            'code': code, 'name': q.get('name', code),
            'reason': 'K线或行情数据缺失', 'pass': False
        })
        continue

    bars = []
    for k in klines:
        if len(k) < 6:
            continue
        bars.append({
            'open': float(k[1]),
            'close': float(k[2]),
            'high': float(k[3]),
            'low': float(k[4]),
            'volume': float(k[5]),
        })

    if len(bars) < 20:
        results.append({
            'code': code, 'name': q.get('name', code),
            'reason': 'K线不足20日(仅{}日)'.format(len(bars)), 'pass': False
        })
        continue

    closes = [b['close'] for b in bars]
    volumes = [b['volume'] for b in bars]
    highs = [b['high'] for b in bars]
    lows = [b['low'] for b in bars]

    # Momentum
    m5 = (closes[-1] / closes[-6] - 1) * 100 if len(closes) >= 6 else 0
    m10 = (closes[-1] / closes[-11] - 1) * 100 if len(closes) >= 11 else 0
    m20 = (closes[-1] / closes[-21] - 1) * 100 if len(closes) >= 21 else 0

    # Moving Averages
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20

    # 20-day avg turnover amount (万元) - FIXED: use code-specific volume conversion
    amounts_20d = []
    for i in range(min(20, len(bars))):
        idx = -(i+1)
        amt = kline_amount(bars[idx]['volume'], bars[idx]['close'], code)
        amounts_20d.append(amt)
    avg_amount_20d = sum(amounts_20d) / len(amounts_20d)

    # Today's amount (from quote, already in 万元)
    today_amount = q['amount']

    # Volume ratio
    volume_ratio = today_amount / avg_amount_20d if avg_amount_20d > 0 else 0

    # Above MA20
    above_ma20 = q['price'] > ma20

    # Breakout
    high_20d = max(highs[-20:])
    breakout = q['high'] >= high_20d * 0.995

    # Momentum quality
    up_days_5 = sum(1 for i in range(1, min(6, len(closes)))
                    if closes[-i] > closes[-(i+1)])
    momentum_uniformity = up_days_5 / 5

    # Volume health (using raw K-line volume, unit doesn't matter for ratio)
    up_vol = 0.0
    down_vol = 0.0
    for i in range(1, min(6, len(bars))):
        vol = bars[-(i+1)]['volume']
        if closes[-i] > closes[-(i+1)]:
            up_vol += vol
        else:
            down_vol += vol
    volume_health = up_vol / down_vol if down_vol > 0 else 1.0

    # Momentum acceleration
    momentum_accel = (m5/5) - ((m10 - m5)/5) if m5 != 0 else 0

    # Pullback depth
    recent_high_20d = max(highs[-20:])
    pullback_depth = (q['price'] / recent_high_20d - 1) * 100

    # Pullback volume ratio
    avg_vol_5d = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else 0
    avg_vol_20d = sum(volumes[-20:]) / 20
    pullback_volume_ratio = avg_vol_5d / avg_vol_20d if avg_vol_20d > 0 else 0

    # RSI(14)
    gains = []
    losses = []
    for i in range(1, min(15, len(closes))):
        chg = closes[-i] - closes[-(i+1)]
        if chg > 0:
            gains.append(chg)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(chg))
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100

    # Exhaustion probability
    exhaustion_prob = 0
    if m5 > 15:
        exhaustion_prob = 70  # high prob
    elif m5 > 10:
        exhaustion_prob = 40
    elif m20 > 25 and m5 < 0:
        exhaustion_prob = 80
    elif 5 < m5 <= 15:
        exhaustion_prob = 30

    # Entry type detection
    entry_type = 'neutral'
    entry_score = 0
    if above_ma20 and -8 <= m5 <= -3 and pullback_volume_ratio < 0.8 and 40 <= rsi <= 50:
        entry_type = '健康回调买点'
        entry_score = 20
    elif breakout and m5 < 0 and pullback_volume_ratio < 0.8 and q['price'] > ma20:
        entry_type = '突破回踩确认'
        entry_score = 15
    elif m20 < -15 and m5 > 0 and volume_ratio > 1.2:
        entry_type = '超跌反弹启动'
        entry_score = 10
    elif m5 > 10 and q['price'] >= highs[-1] * 0.98 and volume_ratio > 1.5:
        entry_type = '追涨入场'
        entry_score = -15
    elif m20 > 20 and m5 < 0 and volume_ratio > 1.2 and q['price'] < ma5:
        entry_type = '高位派发'
        entry_score = -20

    # Mean reversion
    mean_reversion = ''
    if m10 < -8:
        mean_reversion = '近10日跌>8%(超跌信号)'
    if above_ma20 and m5 < 0 and m20 > 0:
        if mean_reversion:
            mean_reversion += ';'
        mean_reversion += '上升趋势中回调'

    # Technical level
    tech_level = '站上MA20' if above_ma20 else '跌破MA20'
    tech_level += '+MA5' if q['price'] > ma5 else ',MA5下方'
    tech_level += '+MA10' if q['price'] > ma10 else ',MA10下方'

    results.append({
        'code': code,
        'name': q.get('name', code),
        'price': round(q['price'], 2),
        'mktcap': round(q['mktcap'], 2),
        'amountYi': round(today_amount / 10000, 2),
        'avgAmount20dYi': round(avg_amount_20d / 10000, 2),
        'turnover': round(q['turnover'], 2),
        'volumeRatio': round(volume_ratio, 2),
        'm5': round(m5, 2),
        'm10': round(m10, 2),
        'm20': round(m20, 2),
        'ma5': round(ma5, 2),
        'ma10': round(ma10, 2),
        'ma20': round(ma20, 2),
        'aboveMA20': above_ma20,
        'momentumUniformity': round(momentum_uniformity, 2),
        'volumeHealth': round(volume_health, 2),
        'momentumAccel': round(momentum_accel, 2),
        'entryType': entry_type,
        'entryScore': entry_score,
        'meanReversionSignal': mean_reversion,
        'pullbackDepth': round(pullback_depth, 2),
        'pullbackVolume': round(pullback_volume_ratio, 2),
        'exhaustionProb': exhaustion_prob,
        'breakout': breakout,
        'rsi': round(rsi, 1),
        'technicalLevel': tech_level,
        'pass': None
    })

# ============================================================
# Apply independent hard filters
# ============================================================
print('Applying filters...')
pass_list = []
reject_list = []

for r in results:
    if r.get('pass') is False:
        reject_list.append(r)
        continue

    reasons = []

    amt20 = r.get('avgAmount20dYi', 0)
    t_o = r.get('turnover', 0)
    mktcap = r.get('mktcap', 0)
    m5 = r.get('m5', 0)
    m20 = r.get('m20', 0)

    # 1. 日均成交额(20日) >= 1亿元
    if amt20 < 1.0:
        reasons.append('日均成交额不足({:.2f}亿<1亿)'.format(amt20))

    # 2. 换手率 < 1% (冷门)
    if t_o < 1.0:
        reasons.append('换手率过低({:.2f}%<1%)'.format(t_o))

    # 3. 自由流通市值 >= 30亿
    if mktcap < 30:
        reasons.append('市值不足({:.2f}亿<30亿)'.format(mktcap))

    # 4. 近5日>30%透支剔除
    if m5 > 30:
        reasons.append('近5日涨幅透支({:.2f}%>30%)'.format(m5))

    # 5. 高位派发: 20日涨>20% + 5日转负
    if m20 > 20 and m5 < 0:
        reasons.append('高位派发风险(m20={:.2f}%>20%且m5={:.2f}%<0)'.format(m20, m5))

    # 6. 换手率>7%警告
    turnover_warning = t_o > 7

    if reasons:
        r['pass'] = False
        r['reason'] = '; '.join(reasons)
        reject_list.append(r)
    else:
        r['pass'] = True
        r['turnoverWarning'] = turnover_warning
        pass_list.append(r)

# Price > 40 rejects
price_rejects = [
    {'code': '688825', 'name': 'N长鑫', 'reason': '价格>40元(49.00),1w账户不可配'},
    {'code': '000636', 'name': '风华高科', 'reason': '价格>40元(44.24),1w账户不可配'},
    {'code': '002409', 'name': '雅克科技', 'reason': '价格>40元(169.35),1w账户不可配'},
    {'code': '603986', 'name': '兆易创新', 'reason': '价格>40元(436.31),1w账户不可配'},
    {'code': '688525', 'name': '佰维存储', 'reason': '价格>40元(241.00),1w账户不可配'},
    {'code': '688766', 'name': '普冉股份', 'reason': '价格>40元(372.49),1w账户不可配'},
    {'code': '002371', 'name': '北方华创', 'reason': '价格>40元(769.08),1w账户不可配'},
    {'code': '688981', 'name': '中芯国际', 'reason': '价格>40元(143.17),1w账户不可配'},
    {'code': '688041', 'name': '海光信息', 'reason': '价格>40元(315.11),1w账户不可配'},
    {'code': '688256', 'name': '寒武纪', 'reason': '价格>40元(1240.36),1w账户不可配'},
    {'code': '688008', 'name': '澜起科技', 'reason': '价格>40元(228.97),1w账户不可配'},
    {'code': '600584', 'name': '长电科技', 'reason': '价格>40元(82.71),1w账户不可配'},
    {'code': '300666', 'name': '江丰电子', 'reason': '价格>40元(240.00),1w账户不可配'},
    {'code': '688596', 'name': '正帆科技', 'reason': '价格>40元(53.86),1w账户不可配'},
    {'code': '300285', 'name': '国瓷材料', 'reason': '价格>40元(62.47),1w账户不可配'},
    {'code': '000938', 'name': '紫光股份', 'reason': '价格>40元(41.27),1w账户不可配'},
    {'code': '300308', 'name': '中际旭创', 'reason': '价格>40元(1067.80),1w账户不可配'},
    {'code': '300502', 'name': '新易盛', 'reason': '价格>40元(490.01),1w账户不可配'},
    {'code': '002384', 'name': '东山精密', 'reason': '价格>40元(208.94),1w账户不可配'},
    {'code': '601138', 'name': '工业富联', 'reason': '价格>40元(61.34),1w账户不可配'},
    {'code': '603019', 'name': '中科曙光', 'reason': '价格>40元(96.93),1w账户不可配'},
    {'code': '000977', 'name': '浪潮信息', 'reason': '价格>40元(84.88),1w账户不可配'},
    {'code': '002281', 'name': '光迅科技', 'reason': '价格>40元(193.56),1w账户不可配'},
    {'code': '300394', 'name': '天孚通信', 'reason': '价格>40元(208.72),1w账户不可配'},
    {'code': '002463', 'name': '沪电股份', 'reason': '价格>40元(117.30),1w账户不可配'},
]

all_rejects = price_rejects + reject_list
pass_codes = ','.join(r['code'] for r in pass_list)

# Print summary
print('\n=== PASS: {} stocks ==='.format(len(pass_list)))
for r in pass_list:
    w = 'HIGH_TURNOVER' if r.get('turnoverWarning') else ''
    print('  {} {} | {}元 | mktcap={}亿 | amt20d={:.1f}亿 | t/o={:.2f}% {} | m5={:.2f}% m20={:.2f}% | entry={}({}) | RSI={:.1f} | exhProb={}%'.format(
        r['code'], r['name'], r['price'], r['mktcap'], r['avgAmount20dYi'],
        r['turnover'], w, r['m5'], r['m20'], r['entryType'], r['entryScore'], r['rsi'], r['exhaustionProb']))

print('\n=== REJECT: {} stocks ==='.format(len(all_rejects)))
for r in all_rejects:
    print('  {} {} | {}'.format(r['code'], r['name'], r.get('reason', 'N/A')))

# Build output
output = {
    'agent': 'technical-liquidity',
    'asOf': '20260727',
    'data': {
        'pass': pass_list,
        'reject': all_rejects,
        'passCodes': pass_codes,
        'summary': '过关{}只/剔除{}只(价格>40元25只+流动性硬门槛{}只)。主要剔除原因:价格约束+市值不足+近5日透支。'.format(
            len(pass_list), len(all_rejects), len(reject_list))
    }
}

OUTPUT = 'data/runs/20260727_short-term-picks/technical-liquidity.json'
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('\nOutput: {}'.format(OUTPUT))
print('passCodes: {}'.format(pass_codes))
print('Summary: {}'.format(output['data']['summary']))