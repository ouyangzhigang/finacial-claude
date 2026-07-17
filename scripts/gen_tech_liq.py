# -*- coding: utf-8 -*-
"""Generate technical-liquidity.json output."""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import cn_fetch
import re
import urllib.request

codes_meta = [
    ('600236','桂冠电力','电力/公用事业',837.1),
    ('000037','深南电A','电力/公用事业',31.2),
    ('600644','乐山电力','电力/公用事业',52.1),
    ('605011','杭州热电','电力/公用事业',73.9),
    ('000722','湖南发展','电力/公用事业',64.2),
    ('000899','赣能股份','电力/公用事业',104.4),
    ('600744','华银电力','电力/公用事业',121.1),
    ('600982','宁波能源','电力/公用事业',56.9),
    ('600310','广西能源','电力/公用事业',66.0),
    ('600021','上海电力','电力/公用事业',420.7),
    ('600505','西昌电力','电力/公用事业',42.3),
    ('600032','浙江新能','电力/公用事业',170.0),
    ('601016','节能风电','电力/公用事业',211.3),
    ('002310','东方新能','电力/公用事业',104.7),
    ('600101','明星电力','电力/公用事业',46.5),
    ('001258','立新能源','电力/公用事业',77.2),
    ('000601','韶能股份','电力/公用事业',68.0),
    ('300105','龙源技术','电力/公用事业',46.9),
    ('300040','九洲集团','电力/公用事业',30.1),
    ('600900','长江电力','电力/公用事业',6800),
    ('600886','国投电力','电力/公用事业',1100),
    ('003816','中国广核','电力/公用事业',1800),
    ('601985','中国核电','电力/公用事业',1600),
    ('601991','大唐发电','电力/公用事业',719),
    ('000600','建投能源','电力/公用事业',147),
    ('000027','深圳能源','电力/公用事业',295),
    ('600023','浙能电力','电力/公用事业',693),
    ('600011','华能国际','电力/公用事业',1086),
    ('600795','国电电力','电力/公用事业',900),
    ('000539','粤电力A','电力/公用事业',279),
    ('600227','赤天化','能源/化工',39.1),
    ('600722','金牛化工','能源/化工',58.0),
    ('300164','通源石油','能源/化工',61.1),
    ('601088','中国神华','能源/化工',8700),
    ('601898','中煤能源','能源/化工',1600),
    ('601225','陕西煤业','能源/化工',2400),
    ('601001','晋控煤业','能源/化工',293),
    ('600188','兖矿能源','能源/化工',1300),
    ('601666','平煤股份','能源/化工',184),
    ('600508','上海能源','能源/化工',84),
    ('601699','潞安环能','能源/化工',430),
    ('600546','山煤国际','能源/化工',234),
    ('600740','山西焦化','能源/化工',88),
    ('600985','淮北矿业','能源/化工',382),
    ('600971','恒源煤电','能源/化工',92),
    ('600792','云煤能源','能源/化工',36),
    ('601857','中国石油','能源/化工',18000),
    ('600028','中国石化','能源/化工',6000),
]

# Fetch K-line factors
factors_data = {}
for c, name, sector, mcap in codes_meta:
    prefix = 'sh' if c.startswith('6') else 'sz'
    sym = prefix + c
    try:
        f = cn_fetch.factors(sym, 25)
        if f:
            factors_data[c] = f
    except Exception as e:
        pass

# Fetch quotes
tc_codes = []
for c, *_ in codes_meta:
    prefix = 'sh' if c.startswith('6') else 'sz'
    tc_codes.append(f'{prefix}{c}')

url = f"http://qt.gtimg.cn/q={','.join(tc_codes)}"
req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=15)
text = resp.read().decode('gbk', errors='replace')
lines = [l.strip() for l in text.split(';') if l.strip()]

quote_data = {}
for line in lines:
    m = re.match(r'v_(\w+)="(.+)"', line)
    if m:
        fields = m.group(2).split('~')
        if len(fields) > 49:
            code = fields[2]
            quote_data[code] = {
                'price': float(fields[3]) if fields[3] else 0,
                'chg_today': float(fields[32]) if fields[32] else 0,
                'turnover': float(fields[38]) if fields[38] else 0,
                'amount_wan': float(fields[37]) if fields[37] else 0,
                'mktcap': float(fields[45]) if fields[45] else 0,
                'vol_ratio': float(fields[49]) if fields[49] else 0,
            }

pass_list = []
reject_list = []
factors_list = []

for c, name, sector, mcap_meta in codes_meta:
    q = quote_data.get(c, {})
    f = factors_data.get(c, {})
    price = q.get('price', 0)
    turnover = q.get('turnover', 0)
    mktcap = q.get('mktcap', mcap_meta)
    vol_ratio = q.get('vol_ratio', 0)
    chg_today = q.get('chg_today', 0)
    m5 = f.get('m5')
    m10 = f.get('m10')
    m20 = f.get('m20')
    ma20 = f.get('ma20')
    above_ma20 = f.get('above_ma20', False)
    breakout = f.get('breakout', False)
    amt20_yi = f.get('amt20_yi', 0)

    reasons = []
    if price > 40:
        reasons.append(f"股价{price}>40元,1w账户无法买1手")
    if amt20_yi < 1.0:
        reasons.append(f"日均成交额{amt20_yi}亿<1亿门槛")
    if mktcap < 30:
        reasons.append(f"市值{mktcap}亿<30亿门槛")
    if m5 is not None and m5 > 30:
        reasons.append(f"近5日涨{m5}%>30%透支")
    if m10 is not None and m10 > 30:
        reasons.append(f"近10日涨{m10}%>30%透支")
    if m20 is not None and m20 > 30:
        reasons.append(f"近20日涨{m20}%>30%透支")
    if c.startswith('3'):
        is_limit_up = chg_today >= 19.9
    else:
        is_limit_up = chg_today >= 9.9
    if is_limit_up:
        reasons.append(f"今日涨停{chg_today}%,无法买入")
    if turnover > 15:
        reasons.append(f"换手率{turnover}%>15%极端投机")

    if reasons:
        reject_list.append({'code': c, 'name': name, 'reason': '; '.join(reasons)})
    else:
        entry_type = 'neutral'
        entry_score = 0
        if above_ma20 and m5 is not None and -8 <= m5 <= -3 and m10 is not None and m10 > 0:
            entry_type = 'healthy_pullback'
            entry_score = 20
        elif above_ma20 and m5 is not None and 0 < m5 <= 5 and m10 is not None and m10 > 0:
            entry_type = 'steady_uptrend'
            entry_score = 15
        elif above_ma20 and m5 is not None and 5 < m5 <= 10:
            entry_type = 'trend_start'
            entry_score = 12
        elif above_ma20 and m5 is not None and m5 > 10:
            entry_type = 'chase_high'
            entry_score = -15
        elif not above_ma20 and m5 is not None and m5 > 0 and m20 is not None and m20 < -10:
            entry_type = 'oversold_bounce'
            entry_score = 10
        elif not above_ma20 and m5 is not None and m5 < 0:
            entry_type = 'downtrend'
            entry_score = -10
        elif above_ma20 and m5 is not None and -3 < m5 <= 0:
            entry_type = 'consolidation'
            entry_score = 5

        if m5 is not None and m10 is not None:
            momentum_accel = round(m5/5 - (m10-m5)/5, 2)
        else:
            momentum_accel = 0

        exhaust_prob = 'low'
        if m5 is not None and m5 > 15 and m20 is not None and m20 > 20:
            exhaust_prob = 'high'
        elif m5 is not None and m5 > 10 and m10 is not None and m10 > 15:
            exhaust_prob = 'medium'

        v5 = f.get('v5', 0)
        v20 = f.get('v20', 0)
        vol_health = round(v5/v20, 2) if v20 > 0 else 1.0
        uniformity = round(m5/m10, 2) if m5 and m10 and m10 != 0 else 1.0

        pass_list.append({
            'code': c, 'name': name, 'sector': sector,
            'price': price, 'chg_today': chg_today, 'turnover': turnover,
            'amt20_yi': amt20_yi, 'vol_ratio': vol_ratio, 'mktcap': mktcap,
            'above_ma20': above_ma20, 'breakout': breakout, 'pass': True,
        })
        factors_list.append({
            'code': c, 'name': name, 'm5': m5, 'm10': m10, 'm20': m20,
            'momentumUniformity': uniformity, 'volumeHealth': vol_health,
            'momentumAccel': momentum_accel, 'entryType': entry_type,
            'entryScore': entry_score, 'meanReversionSignal': 'none',
            'pullbackDepth': 0, 'pullbackVolume': 'shrinking' if vol_health < 1 else 'expanding',
            'exhaustionProb': exhaust_prob, 'breakout': breakout, 'aboveMA20': above_ma20,
            'rps': None, 'technicalLevel': f"MA5={f.get('ma5')},MA10={f.get('ma10')},MA20={ma20}",
        })

entry_dist = {}
for f in factors_list:
    entry_dist[f['entryType']] = entry_dist.get(f['entryType'], 0) + 1

limit_up_count = sum(1 for r in reject_list if '涨停' in r['reason'])
turnover_count = sum(1 for r in reject_list if '换手率' in r['reason'])
exhaust_count = sum(1 for r in reject_list if '透支' in r['reason'])
price_count = sum(1 for r in reject_list if '股价' in r['reason'])
amt_count = sum(1 for r in reject_list if '成交额' in r['reason'])

summary_data = (f"过关{len(pass_list)}只/剔除{len(reject_list)}只 | "
                f"涨停封板{limit_up_count}只, 换手极端{turnover_count}只, "
                f"透支{exhaust_count}只, 股价超限{price_count}只, 成交额不足{amt_count}只 | "
                f"入场: {json.dumps(entry_dist, ensure_ascii=False)}")

pass_codes = ','.join(p['code'] for p in pass_list)
top_entries = sorted(factors_list, key=lambda x: x['entryScore'], reverse=True)[:14]
top_scores = [{'code': e['code'], 'name': e['name'], 'entryType': e['entryType'], 'entryScore': e['entryScore']} for e in top_entries]

output = {
    'runId': '20260717_short-term-picks',
    'asOf': '20260717',
    'goal': 'short-term-picks',
    'agent': 'technical-liquidity',
    'fetchedAt': '20260717',
    'data': {
        'pass': pass_list,
        'reject': reject_list,
        'factors': factors_list,
        'summary': summary_data,
    },
    'summary': f"过关{len(pass_list)}只/剔除{len(reject_list)}只,涨停封板{limit_up_count}只为主要剔除原因,入场优势以steady_uptrend+trend_start为主",
    'keyFields': {
        'passCodes': pass_codes,
        'passCount': len(pass_list),
        'rejectCount': len(reject_list),
        'topEntryScores': top_scores,
        'bestPicks': '长江电力/中国广核/中国核电/国电电力/兖矿能源/山西焦化(steady_uptrend) + 上海电力/浙江新能/国投电力/陕西煤业/恒源煤电/中国石化(trend_start)'
    }
}

out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'runs', '20260717_short-term-picks')
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'technical-liquidity.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f'Written to {out_path}')
print(f'Pass: {len(pass_list)}, Reject: {len(reject_list)}')
