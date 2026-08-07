#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json, sys, warnings, os, re
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import astock_data as A

# Candidate pool: macro tailwinds (energy chain / storage / auto / robotics) + value-reversal bias
CANDS = {
 # 核电/电网设备
 '601611':'中国核建','600468':'百利电气','601700':'风范股份','002471':'中超控股',
 '002879':'长缆科技','002692':'远程股份','600089':'特变电工','600550':'保变电气',
 # 电力/公用事业
 '600396':'华电辽能','000037':'深南电A','600027':'华电国际','600886':'国投电力',
 '600025':'华能水电','600674':'川投能源','601985':'中国核电','600905':'三峡能源',
 # 存储芯片
 '603986':'兆易创新','603501':'韦尔股份','002049':'紫光国微','300223':'北京君正',
 # 商业航天
 '002361':'神剑股份','300853':'申昊科技',
 # 智驾/汽车
 '002405':'四维图新','300496':'中科创达','601799':'星宇股份','002126':'银轮股份',
 # 机器人/具身
 '002747':'埃斯顿','300024':'机器人',
}

def pullback(code):
    """近20日最高价到当前价的回撤%, 及20日涨跌幅."""
    d = A.baidu_kline_with_ma(code, days=60)
    rows = d.get('rows', [])
    if len(rows) < 21:
        return None, None
    keys = d.get('keys', [])
    # find close col
    try:
        ci = keys.index('close')
        hi = keys.index('high')
    except Exception:
        ci, hi = 2, 3
    closes = [r[ci] for r in rows if isinstance(r[ci],(int,float))]
    highs = [r[hi] for r in rows if isinstance(r[hi],(int,float))]
    if len(closes) < 21:
        return None, None
    last = closes[-1]
    win = closes[-20:]
    hi20 = max(highs[-20:])
    ret20 = (last - closes[-21]) / closes[-21] * 100
    pb = (hi20 - last) / hi20 * 100
    return round(pb,2), round(ret20,2)

out = {'quotes':{}, 'pullback':{}, 'fin':{}}

# quotes in chunks
codes = list(CANDS.keys())
for i in range(0, len(codes), 10):
    chunk = codes[i:i+10]
    qstr = ','.join(f'sh{c}' if c.startswith(('6','9')) else f'sz{c}' for c in chunk)
    q = A.tencent_quote(qstr)
    if q:
        out['quotes'].update(q)

# pullback
for c in codes:
    out['pullback'][c] = pullback(c)

print(json.dumps(out, ensure_ascii=False))
