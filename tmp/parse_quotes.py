#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re, json, sys

def sf(v):
    if not v or v.strip() == '--': return None
    try: return float(v.strip())
    except: return None

with open('E:/finacial-invest/tmp/tencent_quotes.txt','r',encoding='gbk',errors='replace') as f:
    raw = f.read()

lines = [l.strip().rstrip(';') for l in raw.split(';') if l.strip() and 'v_' in l]
results = []

for line in lines[:5]:
    m = re.search(r'v_\w+=\"(.+)\"', line)
    if not m: continue
    parts = m.group(1).split('~')
    code = parts[2].strip(); name = parts[1].strip()
    print(f"\n--- {code} {name} ---")
    for idx,val in enumerate(parts):
        v = val.strip()
        if v and v != '--':
            print(f"  [{idx:3d}] = {v}")

# Based on careful analysis:
# Index mapping (verified against technical-liquidity.json values):
#   price = [3]
#   change_pct = [33]  (涨跌幅)
#   high = [35], low = [36]
#   turnover = [38]  (换手率 %)
#   amount_yi = [39] (成交额 亿)
#   amplitude = [40]
#   circ_mv = [41] (流通市值 亿)
#   total_mv = [42] (总市值 亿)
#   pe_ttm = [43] (市盈率动态)
#   pb = [44] (市净率)
#   roe_mrq = [45] (MRQ ROE %)
#   eps = [46]
#   bvps = [47]

print("\n=== FIELD VERIFICATION ===")
for line in lines[:5]:
    m = re.search(r'v_\w+=\"(.+)\"', line)
    if not m: continue
    parts = m.group(1).split('~')
    code = parts[2].strip()
    print(f"{code}: price={parts[3]} chg={parts[33]} high={parts[35]} low={parts[36]} turnover={parts[38]} amount={parts[39]} amp={parts[40]} circ_mv={parts[41]} tot_mv={parts[42]} pe={parts[43]} pb={parts[44]} roe={parts[45]} eps={parts[46]} bvps={parts[47]}")

print("\n=== FULL PARSE ===")
results = []
for line in lines:
    m = re.search(r'v_\w+=\"(.+)\"', line)
    if not m: continue
    parts = m.group(1).split('~')
    if len(parts) < 50: continue
    code = parts[2].strip()
    name = parts[1].strip()
    results.append({
        'code': code,
        'name': name,
        'price': sf(parts[3]),
        'change_pct': sf(parts[33]),
        'turnover': sf(parts[38]),
        'amount_yi': sf(parts[39]),
        'amplitude': sf(parts[40]),
        'mv_circ_yi': sf(parts[41]),
        'mv_total_yi': sf(parts[42]),
        'pe_ttm': sf(parts[43]),
        'pb': sf(parts[44]),
        'roe_mrq': sf(parts[45]),
        'eps': sf(parts[46]),
        'bvps': sf(parts[47]),
    })

print(json.dumps(results, ensure_ascii=False, indent=2))
