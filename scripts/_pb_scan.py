#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json, sys, warnings, os
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cn_fetch as C

CANDS = [
 '601611','600468','601700','002471','002879','002692','600089','600550',
 '600396','000037','600027','600886','600025','600674','601985','600905',
 '603986','603501','002049','300223','002361','002405','300496','601799',
 '002126','002747','300024','600406','601968',
]

def pb(code):
    sym = 'sh'+code if code.startswith(('6','9')) else 'sz'+code
    arr = C.kline(sym, 40)
    if not arr or len(arr) < 21:
        return None
    rows = [{'close':float(x[2]),'high':float(x[3]),'low':float(x[4])} for x in arr]
    last = rows[-1]['close']
    hi20 = max(r['high'] for r in rows[-20:])
    ret20 = (last - rows[-21]['close'])/rows[-21]['close']*100
    pullback = (hi20 - last)/hi20*100
    return round(pullback,2), round(ret20,2)

out = {}
for c in CANDS:
    out[c] = pb(c)
print(json.dumps(out, ensure_ascii=False))
