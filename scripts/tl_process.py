# -*- coding: utf-8 -*-
"""技术流动性分析师 - 批量处理脚本 v2"""
import json, sys, os

# Force UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ── 加载 sector-analyst.json ──
with open('E:/finacial-invest/data/runs/20260722_short-term-picks/sector-analyst.json', 'r', encoding='utf-8') as f:
    sector_data = json.load(f)

candidates = sector_data['data']['candidates']

# ── 加载 factors 数据 (从标准输入读取) ──
factors_raw = {}
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        f = json.loads(line)
        factors_raw[f['symbol']] = f
    except:
        pass

# ── 加载 quote 数据 (从文件) ──
with open('E:/finacial-invest/data/runs/20260722_short-term-picks/temp_quotes.json', 'r', encoding='utf-8') as f:
    quotes_raw = json.load(f)

# ── 构建候选索引 ──
cand_by_code = {}
for c in candidates:
    code = c['code']
    pure = code[2:]
    cand_by_code[pure] = c

# ── 硬门槛过滤 ──
pass_list = []
reject_list = []

for c in candidates:
    code = c['code']
    name = c['name']
    pure = code[2:]
    sym = code

    f = factors_raw.get(sym)
    q = quotes_raw.get(pure, {})

    # 1. K线数据缺失
    if f is None:
        reject_list.append({'code': code, 'name': name, 'reason': 'K线数据缺失,无法计算因子'})
        continue

    # 2. 日均成交额(20日) >= 1亿
    amt20 = f.get('amt20_yi', 0)
    if amt20 < 1.0:
        reject_list.append({'code': code, 'name': name, 'reason': f'日均成交额{amt20:.2f}亿<1亿,流动性不足'})
        continue

    # 3. ST检查
    if 'ST' in name or '退' in name:
        reject_list.append({'code': code, 'name': name, 'reason': 'ST或退市风险股'})
        continue

    # 4. 自由流通市值检查 - 仅当明确已知且<30亿时拒绝
    mktcap = c.get('mktcapYi')
    if mktcap is not None and isinstance(mktcap, (int, float)) and mktcap < 30:
        reject_list.append({'code': code, 'name': name, 'reason': f'市值{mktcap:.1f}亿<30亿,盘子过小'})
        continue

    # 5. 近5日涨幅>30% → 透支剔除
    m5 = f.get('m5')
    if m5 is not None and m5 > 30:
        reject_list.append({'code': code, 'name': name, 'reason': f'近5日涨幅{m5:.1f}%>30%,严重透支'})
        continue

    # 6. 一字涨停检查 (开盘=最高=收盘=涨停价, 且涨幅>9.5%)
    price = q.get('price', 0)
    open_p = q.get('open', 0)
    high = q.get('high', 0)
    pct = q.get('pct', 0)
    if open_p > 0 and high > 0 and price > 0:
        if abs(open_p - high) < 0.01 and abs(price - high) < 0.01 and pct > 9.5:
            reject_list.append({'code': code, 'name': name, 'reason': '一字涨停,无法买入'})
            continue

    # 7. 封死跌停
    prev = q.get('prev', 0)
    if prev > 0 and price <= prev * 0.9 and pct <= -9.9:
        reject_list.append({'code': code, 'name': name, 'reason': '封死跌停,无法卖出'})
        continue

    # 过关
    pass_list.append({'code': code, 'name': name, 'symbol': sym, 'pure': pure, 'c': c, 'f': f, 'q': q})

# ── 短线因子计算 ──
factors_out = []

for item in pass_list:
    code = item['code']
    name = item['name']
    sym = item['symbol']
    f = item['f']
    q = item['q']
    c = item['c']

    m5 = f.get('m5', 0) or 0
    m10 = f.get('m10', 0) or 0
    m20 = f.get('m20', 0) or 0
    above_ma20 = f.get('above_ma20', False)
    above_ma5 = f.get('above_ma5', False)
    breakout = f.get('breakout', False)
    amt20 = f.get('amt20_yi', 0)
    v5 = f.get('v5', 0)
    v20 = f.get('v20', 0)
    turnover = q.get('turnover', 0)
    price = q.get('price', 0)
    mktcap = c.get('mktcapYi') or 0

    # ── A. 动量质量因子 ──
    if m5 > 0 and m10 > 0:
        ratio = m5 / m10 if m10 else 0
        if 0.35 < ratio < 0.65:
            uniformity = 'high'
        else:
            uniformity = 'medium'
    elif m5 > 0 and m10 < 0:
        uniformity = 'short_term_recovery'
    else:
        uniformity = 'low'

    # 量价健康度
    if v20 > 0:
        vol_ratio_5_20 = v5 / v20
        if m5 > 0 and vol_ratio_5_20 > 1.2:
            vol_health = 'healthy'
        elif m5 < 0 and vol_ratio_5_20 < 0.8:
            vol_health = 'healthy'
        elif m5 > 0 and vol_ratio_5_20 < 0.8:
            vol_health = 'weak'
        else:
            vol_health = 'neutral'
    else:
        vol_health = 'unknown'
        vol_ratio_5_20 = 0

    # 动量加速度
    if m5 != 0 and m10 != 0:
        m5_daily = m5 / 5
        m10_5_daily = (m10 - m5) / 5
        if m5_daily > m10_5_daily:
            accel = 'accelerating'
        else:
            accel = 'decelerating'
    else:
        accel = 'unknown'

    # ── B. 入场优势因子 ──
    entry_type = 'neutral'
    entry_score = 0

    if m5 is not None and -8 <= m5 <= -3 and above_ma20 and v20 > 0 and v5 / v20 < 0.8:
        entry_type = 'healthy_pullback'
        entry_score = 20
    elif breakout and above_ma20:
        entry_type = 'breakout_confirm'
        entry_score = 15
    elif m5 is not None and m5 > 10 and above_ma5:
        entry_type = 'chasing'
        entry_score = -15
    elif m20 is not None and m20 > 20 and m5 is not None and m5 < 0 and v20 > 0 and v5 / v20 > 1.2:
        entry_type = 'distribution'
        entry_score = -20
    elif m5 is not None and m5 > 0 and above_ma20:
        entry_type = 'trend_continuation'
        entry_score = 5
    elif m20 is not None and m20 < -15 and m5 is not None and m5 > 0:
        entry_type = 'oversold_bounce'
        entry_score = 10
    elif m5 is not None and m5 < 0:
        entry_type = 'pullback'
        entry_score = -5

    # ── C. 均值回归因子 ──
    mean_reversion = 0
    if not above_ma20 and m20 is not None and m20 < -20:
        mean_reversion = 8

    # ── D. 透支概率 ──
    exhaustion_prob = 'low'
    if m5 is not None and m5 > 15:
        exhaustion_prob = 'high'
    elif m20 is not None and m20 > 25 and m5 is not None and m5 < 0:
        exhaustion_prob = 'extreme'
    elif m5 is not None and 5 <= m5 <= 15:
        exhaustion_prob = 'low'

    # ── 回调深度 ──
    pullback_depth = None
    if m5 is not None and m5 < 0:
        pullback_depth = m5

    pullback_volume = 'unknown'
    if m5 is not None and m5 < 0 and v20 > 0:
        if v5 / v20 < 0.8:
            pullback_volume = 'shrinking'
        elif v5 / v20 > 1.2:
            pullback_volume = 'expanding'

    # ── 技术位 ──
    technical_level = []
    if above_ma5:
        technical_level.append('above_ma5')
    if above_ma20:
        technical_level.append('above_ma20')
    if breakout:
        technical_level.append('breakout')
    if m5 > 0 and m10 > 0 and m20 > 0:
        technical_level.append('uptrend_all_positive')
    elif m5 > 0 and m20 < 0:
        technical_level.append('short_term_recovery')
    elif m5 < 0 and m20 > 0:
        technical_level.append('pullback_in_uptrend')

    # ── 成交量比 ──
    volume_ratio = round(v5 / v20, 2) if v20 > 0 else 0

    factors_out.append({
        'code': code,
        'name': name,
        'price': round(price, 2),
        'm5': round(m5, 2) if m5 else None,
        'm10': round(m10, 2) if m10 else None,
        'm20': round(m20, 2) if m20 else None,
        'momentumUniformity': uniformity,
        'volumeHealth': vol_health,
        'momentumAccel': accel,
        'entryType': entry_type,
        'entryScore': entry_score,
        'meanReversionSignal': mean_reversion,
        'pullbackDepth': round(pullback_depth, 2) if pullback_depth is not None else None,
        'pullbackVolume': pullback_volume,
        'exhaustionProb': exhaustion_prob,
        'breakout': breakout,
        'aboveMA20': above_ma20,
        'volumeRatio': volume_ratio,
        'technicalLevel': technical_level,
        'amt20_yi': round(amt20, 2),
        'turnover': turnover,
        'mktcap_yi': mktcap,
    })

# ── 构建输出 ──
n_pass = len(factors_out)
n_reject = len(reject_list)

# 统计
entry_types = {}
for f in factors_out:
    et = f['entryType']
    entry_types[et] = entry_types.get(et, 0) + 1

reject_reasons = {}
for r in reject_list:
    reason = r['reason'].split(',')[0] if ',' in r['reason'] else r['reason'][:30]
    reject_reasons[reason] = reject_reasons.get(reason, 0) + 1

entry_summary = ', '.join([f'{k}:{v}只' for k, v in sorted(entry_types.items(), key=lambda x: -x[1])])
top_reject = max(reject_reasons.items(), key=lambda x: x[1]) if reject_reasons else ('无', 0)

output = {
    'agent': 'technical-liquidity',
    'asOf': '20260722',
    'data': {
        'pass': [{
            'code': p['code'],
            'name': p['name'],
            'price': p['price'],
            'avgAmount20d': p['amt20_yi'],
            'turnover20d': p['turnover'],
            'mktcapYi': p['mktcap_yi'],
            'pass': True
        } for p in factors_out],
        'reject': reject_list,
        'factors': factors_out,
        'passCodes': ','.join([p['code'] for p in factors_out]),
        'summary': f"过关{n_pass}只/剔除{n_reject}只。入场分布:{entry_summary}。主要剔除原因:{top_reject[0]}({top_reject[1]}只)"
    }
}

print(json.dumps(output, ensure_ascii=False, indent=2))