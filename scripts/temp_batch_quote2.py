#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""批量获取A股实时报价快照(腾讯qt.gtimg.cn HTTP通道) — 修正版"""
import urllib.request, ssl, json, sys

symbols_str = sys.argv[1] if len(sys.argv) > 1 else ''
if not symbols_str:
    print('Usage: temp_batch_quote2.py sym1,sym2,...', file=sys.stderr)
    sys.exit(1)

symbols = [s.strip() for s in symbols_str.split(',') if s.strip()]

def secid(sym):
    if sym.startswith('3') or sym.startswith('0'):
        return 'sz' + sym
    return 'sh' + sym

url = f'http://qt.gtimg.cn/q={",".join(secid(s) for s in symbols)}'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
ctx = ssl._create_unverified_context()
resp = urllib.request.urlopen(req, context=ctx, timeout=30).read().decode('gbk', 'ignore')

out = {}
for line in resp.strip().split(';'):
    line = line.strip()
    if '=' not in line:
        continue
    v = line.split('=', 1)[1].strip('"').rstrip('~;')
    if not v:
        continue
    m = v.split('~')
    if len(m) < 50:
        continue
    try:
        code = m[2]
        # m[35] format: "price/vol_hand/amount_yuan"
        parts35 = m[35].split('/') if m[35] else ['', '', '']
        amount_yuan = float(parts35[2]) if len(parts35) > 2 and parts35[2] else 0
        amount_yi = round(amount_yuan / 1e8, 2)
        # m[44] = total market cap in 亿元 (float)
        total_mktcap_yi = round(float(m[44]), 2) if m[44] and m[44] != '-' else None
        # m[38] = turnover rate %
        turnover_pct = round(float(m[38]), 2) if m[38] and m[38] != '-' else 0

        out[code] = {
            'name': m[1][:6],
            'price': float(m[3]),
            'prev_close': float(m[4]),
            'open': float(m[5]),
            'vol_hand': int(float(m[6])) if m[6] and m[6] != '-' else 0,
            'chg_pct': round(float(m[32]), 2) if m[32] and m[32] != '-' else None,
            'high': float(m[33]) if m[33] and m[33] != '-' else 0,
            'low': float(m[34]) if m[34] and m[34] != '-' else 0,
            'amount_yi': amount_yi,          # 今日成交额 亿元
            'turnover_pct': turnover_pct,     # 换手率 %
            'total_mktcap_yi': total_mktcap_yi,  # 总市值 亿
            'pe_ttm': float(m[39]) if m[39] and m[39] != '-' else None,
        }
    except Exception as e:
        print(f"parse error for {line[:40]}: {e}", file=sys.stderr)
        continue

print(json.dumps(out, ensure_ascii=False, indent=2))
