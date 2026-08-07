# -*- coding: utf-8 -*-
"""估值修复+业绩预增扫描: 中报快报预增 -> 腾讯取价/PB/市值+快报EPS算forward PE -> 20日超跌 -> 低价 -> 排雷"""
import sys, json, time, re
sys.path.insert(0, 'E:/finacial-invest')
import scripts.astock_data as a
import scripts.cn_fetch as c
import requests

UA = a.UA

def tq_raw(codes):
    """腾讯批量,返回 {code: {name,price,pe_ttm,pb,mcap_yi,circ_yi,turnover}}"""
    url = f'http://qt.gtimg.cn/q={",".join(codes)}'
    try:
        r = requests.get(url, timeout=12, headers={'User-Agent': UA},
                          proxies={'http': None, 'https': None})
        if r.status_code != 200: return {}
        raw = r.content.decode('gbk', errors='ignore')
        out = {}
        for m in re.finditer(r'v_(\w+)="([^"]*)"', raw):
            d = m.group(2).split('~')
            if len(d) < 50: continue
            code = d[2]
            def f(i):
                try: return float(d[i]) if d[i] else None
                except: return None
            out[code] = {
                'name': d[1], 'price': f(3),
                'pe_ttm': f(39), 'pb': f(46) if len(d)>46 else None,
                'mcap_yi': f(44), 'circ_yi': f(45) if len(d)>45 else None,
                'turnover': f(38),
            }
        return out
    except Exception as e:
        print('tq_raw err', e, file=sys.stderr); return {}

# 1. 中报快报 预增(净利润同比>50%)+扭转后真实盈利为正+ROE>0+非ST
data = a.eastmoney_datacenter('RPT_LICO_FN_CPD', page_size=500, sort_columns='NOTICE_DATE', sort_types='-1')
cands = [d for d in data if d.get('SJLTZ') and d['SJLTZ'] > 50
         and d.get('PARENT_NETPROFIT') and d['PARENT_NETPROFIT'] > 0
         and d.get('WEIGHTAVG_ROE') and d['WEIGHTAVG_ROE'] > 0
         and d.get('BASIC_EPS') and d['BASIC_EPS'] > 0
         and not d['SECURITY_NAME_ABBR'].startswith('ST')
         and d.get('DATEMMDD') == '半年报']
print('预增+正盈利+正EPS+半年报:', len(cands), file=sys.stderr)

# 排除北交所(8/4/9开头非主板)
cands = [d for d in cands if d['SECURITY_CODE'][:2] in ('00','30','60','68')]
print('excl 北交所:', len(cands), file=sys.stderr)

meta = {d['SECURITY_CODE']: d for d in cands}
codes = list(meta.keys())

def pref(code):
    return ('sz' if code.startswith(('0','3')) else 'sh') + code

# 2. 腾讯行情
quotes = {}
for i in range(0, len(codes), 35):
    batch = [pref(x) for x in codes[i:i+35]]
    q = tq_raw(batch)
    quotes.update(q)
    time.sleep(0.2)
print('quotes:', len(quotes), file=sys.stderr)

rows = []
for code, d in meta.items():
    q = quotes.get(code)
    if not q or not q.get('price'): continue
    price = q['price']
    if price > 40: continue  # 1w账户低价
    if price < 1.5: continue  # 排除毛票
    # forward PE: 半年报EPS*2 年化
    fwd_eps = d['BASIC_EPS'] * 2
    fwd_pe = round(price / fwd_eps, 1) if fwd_eps > 0 else None
    pb = round(q['pb'], 2) if q.get('pb') else None
    # 低估值: forward PE < 35 或 PB<2.5
    if (fwd_pe is None or fwd_pe > 50) and (pb is None or pb > 3):
        continue
    rows.append({
        'code': code, 'name': d['SECURITY_NAME_ABBR'], 'sector': d.get('PUBLISHNAME'),
        'price': price, 'fwd_pe': fwd_pe, 'pb': pb, 'pe_ttm': q.get('pe_ttm'),
        'mcap_yi': round(q['mcap_yi'],1) if q.get('mcap_yi') else None,
        'sjltz': round(d['SJLTZ'],1), 'sjlhz': round(d.get('SJLHZ',0),1),
        'roe': round(d['WEIGHTAVG_ROE'],2), 'eps_h1': d['BASIC_EPS'],
        'netprofit_yi': round(d['PARENT_NETPROFIT']/1e8,3),
        'mgjyjje': d.get('MGJYXJJE'),
        'reportDate': d.get('REPORTDATE','')[:10], 'noticeDate': d.get('NOTICE_DATE','')[:10]
    })
print('低价+低估值:', len(rows), file=sys.stderr)

# 3. 20日超跌 + 5日涨跌
def kline_pullback(code):
    sym = 'sz'+code if code.startswith(('0','3')) else 'sh'+code
    try:
        k = c.kline(sym, 30)
        if not k: return None,None,None
        closes = [float(x[2]) for x in k]
        if len(closes) < 5: return None,None,None
        cur = closes[-1]
        win20 = closes[-21:] if len(closes)>=21 else closes
        hi20 = max(win20)
        lo20 = min(win20)
        pbk = (cur/hi20 - 1)*100 if hi20>0 else None
        win5 = closes[-6:] if len(closes)>=6 else closes
        chg5 = (cur/win5[0] - 1)*100 if win5[0]>0 else None
        chg1 = (cur/closes[-2] - 1)*100 if len(closes)>=2 else None
        return round(pbk,1) if pbk is not None else None, round(chg5,1) if chg5 is not None else None, round(chg1,2) if chg1 is not None else None
    except Exception:
        return None,None,None

out = []
for r in rows:
    pbk, chg5, chg1 = kline_pullback(r['code'])
    if pbk is None: continue
    r['pullback20'] = pbk
    r['chg5'] = chg5
    r['chg1'] = chg1
    out.append(r)
    time.sleep(0.12)
print('kline:', len(out), file=sys.stderr)

# 排序: 超跌深的优先(更负=跌更多), 且预增幅大
out.sort(key=lambda x: (x['pullback20'] or 0))
print(json.dumps(out, ensure_ascii=False, indent=1))
