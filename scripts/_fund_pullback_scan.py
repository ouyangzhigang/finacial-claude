# -*- coding: utf-8 -*-
import sys, json, os
sys.path.insert(0, r'E:\finacial-invest\scripts')
import astock_data as A

# Candidate pool: low-price (<=41) names across nextRotation themes + 电子特气
# + value-repair / earnings-pre-increase alignment
CANDS = [
    ("300052", "中青宝", "AI应用"),
    ("301171", "易点天下", "AI应用"),
    ("301382", "蜂助手", "AI应用/算力"),
    ("600378", "昊华科技", "电子特气"),
    ("688593", "新相微", "显示驱动/半导体"),
    ("688222", "成都先导", "AI制药"),
    ("688758", "赛分科技", "生物医药"),
    ("300943", "春晖智控", "智控/汽配"),
    ("300363", "博腾股份", "CXO"),
    ("300935", "盈建科", "软件"),
    ("300131", "英唐智控", "电子分销"),
    ("688512", "慧智微", "射频芯片"),
    ("688057", "金达莱", "环保"),
    ("300814", "中富电路", "PCB"),
    ("688328", "深科达", "半导体设备"),
    ("300420", "五洋自控", "机械"),
    ("688316", "青云科技", "算力"),
    ("301018", "申菱环境", "液冷"),
]

codes_str = ','.join(c[0] for c in CANDS)
q = A.tencent_quote(','.join((f'sh{c[0]}' if c[0].startswith(('6','9')) else f'sz{c[0]}') for c in CANDS))

out = {}
for code, name, sector in CANDS:
    # tencent key uses bare code per data[2]
    rec = q.get(code) or q.get(f'sh{code}') or q.get(f'sz{code}')
    item = {'code': code, 'name': name, 'sector': sector}
    if rec:
        item.update({'price': rec.get('price'), 'pe': rec.get('pe'),
                     'mktcap': rec.get('mktcap'), 'turnover': rec.get('turnover')})
    else:
        item['quote_err'] = 'no tencent data'
    # 20-day pullback via baidu kline
    k = A.baidu_kline_with_ma(code, 120)
    rows = k.get('rows', [])
    if rows:
        # rows: [date, open, close, high, low, vol, amt, ma5, ma10, ma20,...]
        # last row index of close
        closes = [r[2] for r in rows if len(r) > 2 and isinstance(r[2], (int, float))]
        if len(closes) >= 21:
            today_close = closes[-1]
            close_20d_ago = closes[-21]
            pb = (today_close - close_20d_ago) / close_20d_ago * 100 if close_20d_ago else None
            # also 5d and 60d high pullback
            high_60 = max(closes[-60:]) if len(closes) >= 60 else max(closes)
            pullback_from_high = (today_close - high_60)/high_60*100 if high_60 else None
            item['chg_20d_pct'] = round(pb, 2) if pb is not None else None
            item['pullback_from_60d_high_pct'] = round(pullback_from_high, 2) if pullback_from_high is not None else None
        else:
            item['chg_20d_pct'] = 'insufficient'
    else:
        item['kline_err'] = 'no baidu kline'
    out[code] = item

print(json.dumps(out, ensure_ascii=False, indent=2))
