#!/usr/bin/env python
"""Fix filter logic and rebuild technical-liquidity.json with proper hard filters."""
import json, os

INPUT = 'data/runs/20260727_short-term-picks/technical-liquidity.json'
OUTPUT = INPUT

with open(INPUT, 'r', encoding='utf-8') as f:
    data = json.load(f)

factors = data['data']['factors']

# --- Apply independent hard filters ---
pass_list = []
reject_list = []

for r in factors:
    if r.get('pass') is False:
        reject_list.append(r)
        continue

    reasons = []

    # 1. 日均成交额(20日) >= 1亿元
    amt20 = r.get('avgAmount20dYi', 0)
    if amt20 < 1.0:
        reasons.append('日均成交额不足({:.2f}亿<1亿)'.format(amt20))

    # 2. 换手率 < 1% (过低)
    t_o = r.get('turnover', 0)
    if t_o < 1.0:
        reasons.append('换手率过低({:.2f}%<1%)'.format(t_o))

    # 3. 自由流通市值 >= 30亿
    mktcap = r.get('mktcap', 0)
    if mktcap < 30:
        reasons.append('市值不足({:.2f}亿<30亿)'.format(mktcap))

    # 4. 近5日>30%透支剔除
    m5 = r.get('m5', 0)
    if m5 > 30:
        reasons.append('近5日涨幅透支({:.2f}%>30%)'.format(m5))

    # 5. 高位派发: 20日涨>20% + 5日转负
    m20 = r.get('m20', 0)
    if m20 > 20 and m5 < 0:
        reasons.append('高位派发风险(m20={:.2f}%>20%且m5={:.2f}%<0)'.format(m20, m5))

    # 6. 换手率>7%是警告但非硬剔除
    turnover_warning = t_o > 7

    if reasons:
        r['pass'] = False
        r['reason'] = '; '.join(reasons)
        reject_list.append(r)
    else:
        r['pass'] = True
        r['turnoverWarning'] = turnover_warning
        pass_list.append(r)

# --- Price > 40 yuan rejects (1w account constraint) ---
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

# --- Print summary ---
print('=== PASS: {} stocks ==='.format(len(pass_list)))
for r in pass_list:
    w = 'HIGH_TURNOVER' if r.get('turnoverWarning') else ''
    print('  {} {} | {}元 | mktcap={}亿 | amt20d={:.1f}亿 | t/o={:.2f}% {} | m5={:.2f}% m20={:.2f}% | entry={}({}) | RSI={:.1f}'.format(
        r['code'], r['name'], r['price'], r['mktcap'], r['avgAmount20dYi'],
        r['turnover'], w, r['m5'], r['m20'], r['entryType'], r['entryScore'], r['rsi']))

print('\n=== REJECT: {} stocks ==='.format(len(all_rejects)))
for r in all_rejects:
    print('  {} {} | {}'.format(r['code'], r['name'], r.get('reason', 'N/A')))

# --- Rebuild output ---
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

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('\npassCodes: {}'.format(pass_codes))
print('Summary: {}'.format(output['data']['summary']))