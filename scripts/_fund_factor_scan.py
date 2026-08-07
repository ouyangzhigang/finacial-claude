# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, r'E:\finacial-invest\scripts')
import cn_fetch as C
import astock_data as A

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

def sym(code):
    return f'sh{code}' if code.startswith(('6','9')) else f'sz{code}'

out = {}
for code, name, sector in CANDS:
    item = {'code': code, 'name': name, 'sector': sector}
    # tencent quote for price/pe/mktcap/turnover
    q = A.tencent_quote(sym(code))
    rec = q.get(code) or {}
    item['price'] = rec.get('price')
    item['pe'] = rec.get('pe')
    item['mktcap_yi'] = rec.get('mktcap')  # 腾讯返亿元
    item['turnover'] = rec.get('turnover')
    # factors m5/m10/m20
    try:
        f = C.factors(sym(code), 25)
        if f:
            item['m5'] = f.get('m5'); item['m10'] = f.get('m10'); item['m20'] = f.get('m20')
            item['ma20'] = f.get('ma20'); item['above_ma20'] = f.get('above_ma20')
            item['amt20_yi'] = f.get('amt20_yi')
        else:
            item['factors_err'] = 'no kline'
    except Exception as e:
        item['factors_err'] = str(e)
    out[code] = item

print(json.dumps(out, ensure_ascii=False, indent=2))
