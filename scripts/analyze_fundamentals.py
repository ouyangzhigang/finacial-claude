#!/usr/bin/env python
"""Final fundamentals analysis v2: compile financials, PE, red flags, verdict."""
import json, sys

# Load financial data
with open('e:/finacial-invest/data/temp_financials.json', 'r', encoding='utf-8') as f:
    fin_data = json.load(f)

# PE data from tencent_quote
pe_data = {
    '001399': 53.74, '300433': 58.77, '688729': 143.4, '000021': 50.75,
    '600460': 119.21, '688728': 424.02, '002203': 40.62, '002273': 31.99,
    '600667': 76.0, '600206': 116.93, '688538': -17.14, '600641': -245.0,
    '688403': 269.61, '002396': 59.51, '600330': -92.54, '600988': 18.8,
    '000426': 19.72, '600884': 37.05, '000603': 23.46, '002747': 248.53,
    '002245': 38.48, '300735': 57.31, '000048': -56.33, '603890': 29.25,
    '300450': 34.2, '002459': -5.83, '688772': 39.36
}

names = {
    '001399': '惠科股份', '300433': '蓝思科技', '688729': '屹唐股份',
    '000021': '深科技', '600460': '士兰微', '688728': '格科微',
    '002203': '海亮股份', '002273': '水晶光电', '600667': '太极实业',
    '600206': '有研新材', '688538': '和辉光电-U', '600641': '先导基电',
    '688403': '汇成股份', '002396': '星网锐捷', '600330': '天通股份',
    '600988': '赤峰黄金', '000426': '兴业银锡', '600884': '杉杉股份',
    '000603': '盛达资源', '002747': '埃斯顿', '002245': '蔚蓝锂芯',
    '300735': '光弘科技', '000048': '京基智农', '603890': '春秋电子',
    '300450': '先导智能', '002459': '晶澳科技', '688772': '珠海冠宇'
}

def est_pe_percentile(pe):
    """Estimate PE percentile based on PE level."""
    if pe is None or pe <= 0:
        return None, '亏损/PE无效'
    if pe < 15:
        return '<30%', '低估'
    elif pe < 30:
        return '30-50%', '偏低'
    elif pe < 50:
        return '50-70%', '合理偏高'
    elif pe < 80:
        return '70-90%', '高位'
    elif pe < 200:
        return '>90%', '极度高估'
    else:
        return '>95%', '泡沫'

def analyze(code, fin, pe):
    name = names.get(code, code)
    r = {
        'code': code, 'name': name,
        'redFlags': [], 'warnings': [],
        'financials': {}, 'valuation': {},
        'verdict': '通过'
    }

    f = fin if isinstance(fin, dict) else {}
    if 'error' in f:
        r['financials'] = {'error': f['error']}
        r['verdict'] = '数据缺失'
        r['valuation'] = {'peTtm': pe, 'note': '数据缺失-仅技术维背书'}
        return r

    roe = f.get('roe')
    dr = f.get('debtRatio')
    gm = f.get('grossMargin')
    nm = f.get('netMargin')
    pg = f.get('netProfitGrowth')
    rg = f.get('revenueGrowth')
    cf2p = f.get('cfToProfit')
    ar2r = f.get('arToRevenue')
    nr = f.get('nonRecurringRatio')
    gw2eq = f.get('goodwillToEquity', 0)
    sdg = f.get('sdg', False)
    cr = f.get('cashToAsset')
    br = f.get('borrowToAsset')

    r['financials'] = {
        'roe': roe, 'debtRatio': dr, 'grossMargin': gm, 'netMargin': nm,
        'netProfitGrowth': pg, 'revenueGrowth': rg,
        'cfToProfit': cf2p, 'arToRevenue': ar2r,
        'nonRecurringRatio': nr,
        'goodwillToEquity': gw2eq,
        'cashToAsset': cr, 'borrowToAsset': br,
        'reportDate': f.get('reportDate', 'N/A'),
        'reportType': f.get('reportType', 'N/A'),
    }

    # === HARD RED FLAGS (一票否决, per methodology) ===
    # 1. 商誉占净资产 > 40%
    if gw2eq > 40:
        r['redFlags'].append({
            'flag': '商誉占净资产>40%',
            'severity': 'hard',
            'threshold': '>40%',
            'actual': f'{gw2eq:.1f}%',
            'action': '剔除'
        })

    # 2. 存贷双高
    if sdg:
        r['redFlags'].append({
            'flag': '存贷双高',
            'severity': 'hard',
            'threshold': '货币资金和借款均>总资产20%',
            'actual': f'现金/总资产={cr:.1f}%, 借款/总资产={br:.1f}%',
            'action': '剔除'
        })

    # 3. 毛利率持续为负 + ROE严重亏损(<-15%) = 经营实质性恶化
    if gm is not None and gm < 0 and roe is not None and roe < -15:
        r['redFlags'].append({
            'flag': '毛利率为负且ROE严重亏损',
            'severity': 'hard',
            'threshold': '毛利率<0且ROE<-15%',
            'actual': f'毛利率={gm:.1f}%, ROE={roe:.1f}%',
            'action': '剔除'
        })

    # === SOFT WARNINGS (降权) ===
    # 经营现金流为负
    if cf2p is not None and cf2p < 0:
        r['warnings'].append({
            'flag': '经营现金流为负',
            'severity': 'severe',
            'threshold': '<0',
            'actual': f'{cf2p:.2f}',
            'action': '降权'
        })
    # 经营现金流/净利润 < 0.5
    elif cf2p is not None and cf2p < 0.5:
        r['warnings'].append({
            'flag': '经营现金流/净利润<0.5',
            'severity': 'soft',
            'threshold': '<0.5',
            'actual': f'{cf2p:.2f}',
            'action': '降权'
        })

    # 应收账款/收入 > 40%
    if ar2r is not None and ar2r > 0.4:
        r['warnings'].append({
            'flag': '应收账款/收入>40%',
            'severity': 'soft',
            'threshold': '>40%',
            'actual': f'{ar2r*100:.1f}%',
            'action': '降权'
        })

    # 非经常性损益/利润 > 20%
    if nr is not None and nr > 0.2:
        r['warnings'].append({
            'flag': '非经常性损益/利润>20%',
            'severity': 'soft',
            'threshold': '>20%',
            'actual': f'{nr*100:.1f}%',
            'action': '降权'
        })

    # 资产负债率 > 70%
    if dr is not None and dr > 70:
        r['warnings'].append({
            'flag': '资产负债率>70%',
            'severity': 'soft',
            'threshold': '>70%',
            'actual': f'{dr:.1f}%',
            'action': '降权'
        })

    # 净利润大幅下滑 < -20%
    if pg is not None and pg < -20:
        r['warnings'].append({
            'flag': '净利润大幅下滑',
            'severity': 'soft',
            'threshold': '<-20%',
            'actual': f'{pg:.1f}%',
            'action': '降权'
        })

    # 毛利率 < 10%
    if gm is not None and gm < 10:
        r['warnings'].append({
            'flag': '毛利率<10%',
            'severity': 'soft',
            'threshold': '<10%',
            'actual': f'{gm:.1f}%',
            'action': '降权'
        })

    # ROE为负（亏损）
    if roe is not None and roe < 0:
        r['warnings'].append({
            'flag': 'ROE为负(亏损)',
            'severity': 'severe',
            'threshold': '<0',
            'actual': f'{roe:.1f}%',
            'action': '降权'
        })

    # 毛利率为负(但ROE未到-15%硬红线)
    if gm is not None and gm < 0 and (roe is None or roe >= -15):
        r['warnings'].append({
            'flag': '毛利率为负',
            'severity': 'severe',
            'threshold': '<0',
            'actual': f'{gm:.1f}%',
            'action': '降权'
        })

    # === Valuation ===
    pe_pct, pe_label = est_pe_percentile(pe)
    r['valuation'] = {
        'peTtm': pe,
        'pePercentileEst': pe_pct,
        'peLabel': pe_label,
        'note': 'PE分位为估算值(iFind/Wind MCP全SSL挂,基于PE绝对值+行业经验估算);PB数据缺失'
    }

    # === Verdict ===
    if r['redFlags']:
        r['verdict'] = '剔除'
    elif len(r['warnings']) >= 3:
        r['verdict'] = '降权'
    elif r['warnings']:
        r['verdict'] = '降权'
    else:
        r['verdict'] = '通过'

    return r

# Analyze all
results = {}
for code in fin_data:
    fin = fin_data[code]
    pe = pe_data.get(code)
    result = analyze(code, fin, pe)
    results[code] = result

passed = sum(1 for r in results.values() if r['verdict'] == '通过')
warned = sum(1 for r in results.values() if r['verdict'] == '降权')
rejected = sum(1 for r in results.values() if r['verdict'] == '剔除')

def sort_key(r):
    order = {'剔除': 0, '降权': 1, '通过': 2}
    return order.get(r['verdict'], 3)

sorted_results = sorted(results.values(), key=sort_key)

# Print summary
print(f"Total: {len(results)} | Passed: {passed} | Warned: {warned} | Rejected: {rejected}")
print(f"\n--- REJECTED ({rejected}) ---")
for r in sorted_results:
    if r['verdict'] == '剔除':
        flags = ', '.join(f['flag'] for f in r['redFlags'])
        print(f"  {r['code']} {r['name']}: {flags}")

print(f"\n--- WARNED ({warned}) ---")
for r in sorted_results:
    if r['verdict'] == '降权':
        sev = sum(1 for w in r['warnings'] if w['severity'] == 'severe')
        print(f"  {r['code']} {r['name']} ({len(r['warnings'])}w/{sev}s): PE={r['valuation'].get('peTtm')} ROE={r['financials'].get('roe')}%")

print(f"\n--- PASSED ({passed}) ---")
for r in sorted_results:
    if r['verdict'] == '通过':
        print(f"  {r['code']} {r['name']}: PE={r['valuation'].get('peTtm')} ROE={r['financials'].get('roe')}% GM={r['financials'].get('grossMargin')}%")

# Build output
output = {
    'agent': 'fundamentals-analyst',
    'asOf': '20260721',
    'data': {
        'summary': {
            'total': len(results),
            'passed': passed,
            'warned': warned,
            'rejected': rejected,
            'dataSource': '东财datacenter(财务,verify=False)+新浪(商誉)+腾讯(PE,qt.gtimg.cn)',
            'dataMissing': '股东质押(Z值/M值/审计意见/业绩预告)因API无返回未核验;PE分位为估算值;PB数据缺失',
            'note': 'iFind/Wind/akshare MCP全SSL挂,走HTTP兜底通道'
        },
        'stocks': {}
    }
}

for r in sorted_results:
    code = r['code']
    output['data']['stocks'][code] = {
        'name': r['name'],
        'financials': r['financials'],
        'valuation': r['valuation'],
        'redFlags': r['redFlags'],
        'warnings': r['warnings'],
        'verdict': r['verdict']
    }

outpath = 'e:/finacial-invest/data/runs/20260721_short-term-picks/fundamentals-analyst.json'
with open(outpath, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f'\nSaved to {outpath}')