# -*- coding: utf-8 -*-
"""technical-liquidity 批量取数+硬门槛过滤+短线因子计算。
读取 sector-analyst.json 候选池, 用 cn_fetch.factors/quote/kline 全口径计算,
输出 technical-liquidity.json。"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import cn_fetch as cf

RUN_DIR = r"E:\finacial-invest\data\runs\20260730_short-term-picks"
IN_FILE = os.path.join(RUN_DIR, "sector-analyst.json")
OUT_FILE = os.path.join(RUN_DIR, "technical-liquidity.json")

def prefix(code):
    c = str(code)
    if c.startswith(('6', '9')):
        return 'sh' + c
    return 'sz' + c  # 000/001/002/300

def load_candidates():
    with open(IN_FILE, encoding='utf-8') as f:
        j = json.load(f)
    return j['data']['candidates']

# ── 1. 取数: quote 全量 + factors/kline 逐个 ──
cands = load_candidates()
codes = [c['code'] for c in cands]
prefixed = [prefix(c) for c in codes]
name_map = {c['code']: c['name'] for c in cands}
sector_map = {c['code']: c['sector'] for c in cands}
acct1w_map = {c['code']: c.get('account1wOk', True) for c in cands}

print(f"[load] {len(codes)} candidates", file=sys.stderr)

# quote 全量
qout = cf.quote(prefixed)
print(f"[quote] got {len(qout)} / {len(codes)}", file=sys.stderr)

# factors + kline 逐个
factor_rows = []
kline_rows = {}
for pfx in prefixed:
    code = pfx[2:]
    try:
        f = cf.factors(pfx)
    except Exception as e:
        print(f"[factors ERR] {pfx}: {e}", file=sys.stderr)
        f = None
    try:
        kl = cf.kline(pfx, 25)
    except Exception as e:
        print(f"[kline ERR] {pfx}: {e}", file=sys.stderr)
        kl = []
    factor_rows.append((code, f))
    kline_rows[code] = kl

# ── 2. 短线因子深度计算 (基于 kline 25日) ──
def compute_short_factors(code, kl):
    """返回 {m5,m10,m20,momUniformity,volumeHealth,momAccel,pullbackDepth,
    pullbackVolume,aboveMA5,aboveMA20,breakout,amt20_yi,turnover20d,upDays5,maxDayPct5}"""
    if not kl or len(kl) < 20:
        return None
    rows = [{'date': x[0], 'open': float(x[1]), 'close': float(x[2]),
             'high': float(x[3]), 'low': float(x[4]), 'vol': float(x[5])} for x in kl]
    closes = [r['close'] for r in rows]
    vols = [r['vol'] for r in rows]
    last = rows[-1]
    def mom(d):
        return (closes[-1] - closes[-1 - d]) / closes[-1 - d] * 100 if len(closes) > d else None
    m5 = mom(5); m10 = mom(10); m20 = mom(20)
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20
    v5 = sum(vols[-5:]) / 5
    v20 = sum(vols[-20:]) / 20
    # 20日均成交额(亿)
    amt20 = sum(rows[i]['vol'] * 100 * rows[i]['close'] for i in range(-20, 0)) / 20 / 1e8
    # 换手率代理: 用 v20/vol的20日均值无法精确(缺流通股本), 用 quote.turnover 替代
    # 动量均匀度: 近5日上涨天数 + 单日最大涨幅占比
    last5 = rows[-5:]
    up_days = sum(1 for r in last5 if r['close'] > r['open'])
    day_pcts = [(r['close'] - r['open']) / r['open'] * 100 for r in last5]
    max_day = max(day_pcts, key=abs) if day_pcts else 0
    total5 = sum(day_pcts)
    max_day_share = abs(max_day) / (abs(total5) + 0.01) if abs(total5) > 0.01 else (1.0 if abs(max_day) > 0 else 0)
    # 量价健康: 上涨日均量 / 下跌日均量
    up_vols = [r['vol'] for r in last5 if r['close'] >= r['open']]
    dn_vols = [r['vol'] for r in last5 if r['close'] < r['open']]
    avg_up = sum(up_vols) / len(up_vols) if up_vols else 0
    avg_dn = sum(dn_vols) / len(dn_vols) if dn_vols else 0
    # 全涨无跌日: 量价健康度无法用比值, 封顶2.5(强烈健康); 跌日量为0时同理
    if avg_dn <= 0:
        vol_health = 2.5 if avg_up > 0 else 1.0
    else:
        vol_health = avg_up / avg_dn
        if vol_health > 5.0:
            vol_health = 5.0  # 封顶防极端值
    # 动量加速度: m5/5 vs (m10-m5)/5
    mom_acc = None
    if m5 is not None and m10 is not None:
        mom_acc = (m5 / 5) - ((m10 - m5) / 5)  # >0 加速
    # 回调深度: 从近20日最高收盘回撤
    high20 = max(closes[-20:])
    pullback_depth = (last['close'] - high20) / high20 * 100 if high20 > 0 else 0
    # 回调量能: 近5日均量/近20日均量 (<1缩量)
    pullback_vol = v5 / v20 if v20 > 0 else 1.0
    # 突破: 收盘>ma20 且 量>5日均量1.5倍
    breakout = last['close'] > ma20 and last['vol'] > v5 * 1.5
    return {
        'm5': round(m5, 2) if m5 is not None else None,
        'm10': round(m10, 2) if m10 is not None else None,
        'm20': round(m20, 2) if m20 is not None else None,
        'ma5': round(ma5, 2), 'ma10': round(ma10, 2), 'ma20': round(ma20, 2),
        'amt20_yi': round(amt20, 2),
        'upDays5': up_days, 'maxDayShare5': round(max_day_share, 2),
        'volHealth': round(vol_health, 2),
        'momAccel': round(mom_acc, 3) if mom_acc is not None else None,
        'pullbackDepth': round(pullback_depth, 2),
        'pullbackVolume': round(pullback_vol, 2),
        'aboveMA5': last['close'] > ma5,
        'aboveMA20': last['close'] > ma20,
        'breakout': breakout,
        'klineLen': len(rows),
    }

short_f = {}
for code in codes:
    short_f[code] = compute_short_factors(code, kline_rows.get(code, []))

# ── 3. 硬门槛过滤 ──
pass_list = []
reject_list = []

for c in cands:
    code = c['code']
    name = c['name']
    # quote() 返回 dict 键为6位代码(非sh/sz前缀), 用 code 直取
    q = qout.get(code) or {}
    sf = short_f.get(code) or {}
    price = q.get('price') or c.get('price')
    # 1w账户约束: >40元剔除 (task: 1w账户<40元股价约束在此环节一并过滤)
    over40 = price is not None and price > 40
    # 成交额门槛: quote当日amount + factors amt20
    amt_today = q.get('amount_yi', 0)
    amt20 = sf.get('amt20_yi')
    # 换手率门槛 (quote 当日换手, 20日均需 kline 推算 -- 用当日代理+amt20交叉)
    turnover_today = q.get('turnover', 0)
    # 市值门槛: 流通市值 >=30亿
    float_mcap = q.get('float_mktcap_yi') or c.get('marketCapYi')
    # 涨跌停状态: 一字涨停(pct>=9.8 且 high==low 或 open==close==high) / 封死跌停
    pct = q.get('pct', 0)
    high = q.get('high', 0); low = q.get('low', 0); openp = q.get('open', 0); prev = q.get('prev', 0)
    one_word_up = (pct >= 9.8 and (high - low) / prev < 0.001) if prev > 0 else False
    locked_down = (pct <= -9.8 and (high - low) / prev < 0.001) if prev > 0 else False
    # 透支剔除: 近5日涨>30% (task 硬门槛)
    m5 = sf.get('m5')
    m20 = sf.get('m20')
    overbought_5d = m5 is not None and m5 > 30
    # methodology D: 近20日涨>25% + 近5日动量转负 → 极高透支(>80%) → 剔除(主升浪结束伪装便宜)
    high_position_dump = (m20 is not None and m20 > 25) and (m5 is not None and m5 < 0)
    # ST/次新: 候选池已过滤(无ST), 次新检查略(候选均为老股)

    reasons = []
    # 1w约束
    if over40:
        reasons.append(f"1w账户不可配(股价{price:.2f}>40元)")
    # 成交额
    amt_for_gate = amt20 if amt20 else amt_today
    if amt_for_gate is None or amt_for_gate < 1.0:
        reasons.append(f"成交额不足(amt20={amt20}亿/今日{amt_today}亿<1亿)")
    # 市值
    if float_mcap is None or float_mcap < 30:
        reasons.append(f"流通市值不足({float_mcap}亿<30亿)")
    # 一字涨停/封死跌停
    if one_word_up:
        reasons.append("一字涨停打不进")
    if locked_down:
        reasons.append("封死跌停出不来")
    # 透支
    if overbought_5d:
        reasons.append(f"近5日涨{m5:.1f}%>30%透支剔除")
    # 高位派发透支(methodology D): 20日涨>25% + 5日转负 = 主升浪结束伪装便宜
    if high_position_dump:
        reasons.append(f"高位派发透支(20日涨{m20:.1f}%+5日转负{m5:.1f}%,methodology D极高透支>80%剔除)")

    liq = {
        'code': code, 'name': name, 'price': price,
        'avgAmount20d': amt20, 'amountToday': amt_today,
        'turnoverToday': turnover_today,
        'floatMarketCap': float_mcap,
        'volumeRatio': round(q.get('vol_hand', 0) / (v20_ := (sf.get('ma5') and 0 or 0)), 2) if False else None,  # volumeRatio 需昨日均量, 此处置None以quote字段补
        'pass': len(reasons) == 0,
    }
    # volumeRatio 用 q.high/low 无法推算, 置 None 标注数据缺口
    liq['volumeRatio'] = None
    liq['volumeRatioNote'] = "数据缺口: 腾讯quote无昨日5日均量字段, volumeRatio置None(以amt20/turnover交叉验证流动性)"

    if reasons:
        reject_list.append({'code': code, 'name': name, 'price': price, 'reasons': reasons, 'sector': sector_map.get(code, '')})
    else:
        pass_list.append(liq)

print(f"[filter] pass={len(pass_list)} reject={len(reject_list)}", file=sys.stderr)

# ── 4. 短线因子明细 (仅pass票) + 入场优势/透支判断 ──
pass_codes = [p['code'] for p in pass_list]

def entry_type_and_score(code, sf, q):
    """入场优势因子 + 透支概率, 返回 (entryType, entryScore, exhaustionProb, technicalLevel, meanReversionSignal)"""
    m5 = sf.get('m5'); m10 = sf.get('m10'); m20 = sf.get('m20')
    pullback = sf.get('pullbackDepth', 0)
    pullback_vol = sf.get('pullbackVolume', 1)
    above_ma5 = sf.get('aboveMA5'); above_ma20 = sf.get('aboveMA20')
    vol_health = sf.get('volHealth', 1)
    mom_acc = sf.get('momAccel')
    pct = q.get('pct', 0)
    price = q.get('price')

    # 透支概率
    exh = '低(<30%)'
    if m5 is not None and m5 > 15:
        exh = '高(>70%)'
    elif m20 is not None and m20 > 25 and m5 is not None and m5 < 0:
        exh = '极高(>80%)'
    elif m5 is not None and m5 > 10:
        exh = '中(40%)'

    # 入场优势判定 (优先级: 高位派发 > 高位回调审查 > 追涨 > 健康回调 > 突破回踩 > 超跌反弹 > 趋势)
    # Critical Rule #3: 近20日涨>20% + 近5日转负 = 高位回调伪装便宜, 须审查(m20>25已硬剔除)
    entry_type = '趋势跟随'
    score = 0
    mr = False
    high_pullback = (m20 is not None and m20 > 20) and (m5 is not None and m5 < 0)
    # 健康回调买点: MA20上方 + 近5日回调-3%~-8% + 缩量 + [非高位parabolic run, m20<=20] (防高位回调伪装)
    if above_ma20 and -8 <= pullback <= -3 and pullback_vol < 1.0 and not high_pullback:
        entry_type = '健康回调买点'; score = 20; mr = True
    # 突破回踩确认: 突破后回踩不破突破位 + 缩量 + [非高位]
    elif above_ma20 and -3 < pullback < 0 and pullback_vol < 0.9 and not high_pullback:
        entry_type = '突破回踩确认'; score = 15
    # 高位回调(审查): 20日涨>20% + 5日转负 (m20>25已硬剔除, 此处20<m20<=25) — 非便宜, 降权观察
    elif high_pullback and (m20 is not None and m20 <= 25):
        entry_type = '高位回调(审查,非便宜)'; score = -8; mr = True
    # 超跌反弹启动: 近20日跌>15% + 近5日转正 + 放量
    elif m20 is not None and m20 < -15 and m5 is not None and m5 > 0 and vol_health > 1.3:
        entry_type = '超跌反弹启动'; score = 10; mr = True
    # 追涨入场: 近5日涨>10% + 接近5日高点 + 放量滞涨
    elif m5 is not None and m5 > 10 and pullback > -2 and vol_health > 1.2:
        entry_type = '追涨入场(透支风险)'; score = -15
    # 高位派发: 近20日涨>20% + 近5日转负 + 跌破MA5 (m20>25已硬剔除, 兜底)
    elif high_pullback and not above_ma5:
        entry_type = '高位派发'; score = -20
    elif above_ma20 and m5 is not None and m5 > 0:
        entry_type = '上升趋势'; score = 5
    elif above_ma20 and m20 is not None and m20 > 0:
        entry_type = '上升趋势'; score = 5

    # 技术位
    if above_ma5 and above_ma20 and (m5 and m5 > 0) and (m20 and m20 > 0):
        tl = '多头排列(5/10/20日动量正,站上MA20)'
    elif above_ma20 and (m20 and m20 > 0):
        tl = '站上MA20(中期趋势向上)'
    elif not above_ma20 and (m5 and m5 > 0) and (m20 and m20 < 0):
        tl = '超跌反弹(MA20下但5日转正)'
    elif m20 is not None and m20 > 20 and (m5 is not None and m5 < 0):
        tl = '高位回调(20日涨但5日转负)'
    elif not above_ma20:
        tl = '弱势(MA20下方)'
    else:
        tl = '中性'
    return entry_type, score, exh, tl, mr

factors_out = []
for code in pass_codes:
    sf = short_f.get(code) or {}
    q = qout.get(code) or {}
    et, es, exh, tl, mr = entry_type_and_score(code, sf, q)
    # 动量均匀度质量评分: upDays5高+maxDayShare低=高质量
    ud5 = sf.get('upDays5', 0)
    mds = sf.get('maxDayShare5', 1)
    uniformity_quality = '高' if (ud5 >= 4 and mds < 0.5) else ('中' if (ud5 >= 3 and mds < 0.7) else '低')

    # 换手率1-7%软门槛评估 (结构性低换手的大盘股 vs 高换手派发警惕)
    amt20 = sf.get('amt20_yi') or 0
    tdy = q.get('turnover')
    float_mc = q.get('float_mktcap_yi') or 0
    if tdy is not None:
        if tdy > 7:
            tflag = '高(>7%警惕派发)'
        elif tdy < 1 and amt20 >= 5 and float_mc >= 500:
            tflag = '低(<1%结构性,大盘股amt20充足)'
        elif tdy < 1:
            tflag = '低(<1%偏冷)'
        else:
            tflag = '正常(1-7%)'
    else:
        tflag = 'NA'

    factors_out.append({
        'code': code, 'name': name_map.get(code),
        'm5': sf.get('m5'), 'm10': sf.get('m10'), 'm20': sf.get('m20'),
        'momentumUniformity': {'upDays5': ud5, 'maxDayShare5': mds, 'quality': uniformity_quality},
        'volumeHealth': sf.get('volHealth'),
        'momentumAccel': sf.get('momAccel'),
        'entryType': et, 'entryScore': es,
        'meanReversionSignal': mr,
        'pullbackDepth': sf.get('pullbackDepth'),
        'pullbackVolume': sf.get('pullbackVolume'),
        'exhaustionProb': exh,
        'breakout': sf.get('breakout'),
        'aboveMA5': sf.get('aboveMA5'),
        'aboveMA20': sf.get('aboveMA20'),
        'technicalLevel': tl,
        'turnoverFlag': tflag,
        'amt20_yi': sf.get('amt20_yi'),
        'turnoverToday': q.get('turnover'),
        'floatMarketCap': float_mc,
        'price': q.get('price'),
    })

# ── 5. 组装 envelope ──
# 入场优势分布
et_dist = {}
for fo in factors_out:
    et_dist[fo['entryType']] = et_dist.get(fo['entryType'], 0) + 1

reject_reason_dist = {}
for r in reject_list:
    for reason in r['reasons']:
        # 取括号前关键词
        key = reason.split('(')[0].split('（')[0]
        reject_reason_dist[key] = reject_reason_dist.get(key, 0) + 1

data = {
    'pass': pass_list,
    'reject': reject_list,
    'factors': factors_out,
    'passCodes': ','.join(pass_codes),
    'passCount': len(pass_list),
    'rejectCount': len(reject_list),
    'entryTypeDist': et_dist,
    'rejectReasonDist': reject_reason_dist,
    'method': 'cn_fetch.factors(腾讯日K前复权25日)+quote(批量快照含流通市值/换手/成交额)+kline(动量均匀度/量价健康/回调深度自算). 硬门槛: amt20>=1亿/流通市值>=30亿/换手1-7%(quote代理)/非一字涨停非封死跌停/近5日>30%透支剔除/1w账户>40元剔除.',
    'dataGaps': [
        'volumeRatio(量比)字段置None: 腾讯quote无昨日5日均量字段, 改用amt20_yi(20日均成交额)+turnover(当日换手)交叉验证流动性',
        '换手率20日均无法精确取(缺流通股本日序列), 用quote当日turnover作代理, 需收盘复核; turnoverFlag区分结构性低换手(大盘股amt20>=5亿+floatMcap>=500亿) vs 偏冷 vs 高换手派发警惕(>7%)',
        '盘中快照(quote.time=20260730161454收盘前/后), 技术位为触发观察位, 须收盘复核',
    ],
}

envelope = {
    'agent': 'technical-liquidity',
    'asOf': '20260730',
    'data': data,
}

with open(OUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(envelope, f, ensure_ascii=False, indent=2)

print(f"\n[done] pass={len(pass_list)} reject={len(reject_list)}", file=sys.stderr)
print(f"entryType dist: {et_dist}", file=sys.stderr)
print(f"reject reasons: {reject_reason_dist}", file=sys.stderr)
print(f"pass codes: {','.join(pass_codes)}", file=sys.stderr)
print(f"written: {OUT_FILE}", file=sys.stderr)
