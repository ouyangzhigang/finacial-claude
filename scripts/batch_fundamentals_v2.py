#!/usr/bin/env python
"""Batch financial red-flag screening for all candidates.
Data sources: 东方财富 datacenter (financials) + 新浪 finance (goodwill/equity) + 东方财富 (pledge).
Bypasses Whistle proxy with proxies={'http':None,'https':None}.
"""
import requests, urllib3, re, json, sys, time
urllib3.disable_warnings()

PROXY = {'http': None, 'https': None}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# All 65 candidates
ALL_CODES = [
    '000021','000938','001399','002156','002185','002245','002273','002281',
    '002371','002396','002409','002448','002669','002913','300308','300604',
    '301205','301282','301308','301583','600183','600206','600330','600460',
    '600522','600584','600641','600667','603005','603890','603936','603986',
    '605133','688002','688003','688012','688037','688072','688106','688110',
    '688120','688135','688141','688147','688209','688216','688259','688261',
    '688262','688328','688347','688361','688371','688409','688484','688525',
    '688549','688595','688596','688627','688711','688728','688729','688783',
    '688809',
]

def sh_secucode(code):
    if code.startswith('6'):
        return f'{code}.SH'
    elif code.startswith('0') or code.startswith('3'):
        return f'{code}.SZ'
    else:
        return f'{code}.SH'

def sf(v, default=None):
    if v is None: return default
    try: return float(v)
    except: return default

def get_financials(code):
    """Get financial indicators from 东方财富 datacenter."""
    secu = sh_secucode(code)
    url = f'https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_FINANCE_MAINFINADATA&sty=APP_F10_MAINFINADATA&filter=(SECUCODE=%22{secu}%22)&p=1&ps=10&sr=-1&st=REPORT_DATE&source=HSF10&client=PC'
    try:
        r = requests.get(url, verify=False, timeout=15, proxies=PROXY, headers=HEADERS)
        if r.status_code != 200: return None
        d = r.json()
        if not d.get('result') or not d['result'].get('data'): return None
        return d['result']['data']
    except: return None

def get_balance_sheet(code):
    """Get balance sheet from 东方财富 datacenter for 大存大贷 check."""
    secu = sh_secucode(code)
    url = f'https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_DMSK_FN_BALANCE&sty=ALL&filter=(SECUCODE=%22{secu}%22)&p=1&ps=3&sr=-1&st=REPORT_DATE&source=HSF10&client=PC'
    try:
        r = requests.get(url, verify=False, timeout=15, proxies=PROXY, headers=HEADERS)
        if r.status_code != 200: return None
        d = r.json()
        if not d.get('result') or not d['result'].get('data'): return None
        return d['result']['data']
    except: return None

def get_sina_goodwill_equity(code):
    """Get goodwill and equity from 新浪 balance sheet."""
    try:
        r = requests.get(f'https://money.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/{code}/ctrl/2025/displaytype/4.phtml',
                        verify=False, timeout=15, proxies=PROXY, headers=HEADERS)
        r.encoding = 'gbk'
        html = r.text

        goodwill = None
        pos = html.find('商誉')
        if pos > 0:
            snippet = html[pos:pos+500]
            clean = re.sub(r'<[^>]+>', ' ', snippet)
            nums = re.findall(r'[\d,]+\.?\d*', clean)
            if nums: goodwill = float(nums[0].replace(',', ''))

        equity = None
        for keyword in ['归属于母公司股东权益合计', '归属于母公司所有者权益合计', '股东权益合计']:
            pos = html.find(keyword)
            if pos > 0:
                snippet = html[pos:pos+500]
                clean = re.sub(r'<[^>]+>', ' ', snippet)
                nums = re.findall(r'[\d,]+\.?\d*', clean)
                if nums: equity = float(nums[0].replace(',', ''))
                break

        return goodwill, equity
    except: return None, None

def get_pledge(code):
    """Get pledge ratio from 东方财富."""
    secu = sh_secucode(code)
    url = f'https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_EQUITY_PLEDGE&sty=ALL&filter=(SECUCODE=%22{secu}%22)&p=1&ps=5&sr=-1&st=NOTICE_DATE&source=HSF10&client=PC'
    try:
        r = requests.get(url, verify=False, timeout=15, proxies=PROXY, headers=HEADERS)
        if r.status_code != 200: return 0
        d = r.json()
        if not d.get('result') or not d['result'].get('data'): return 0
        max_ratio = 0
        for row in d['result']['data']:
            ratio = sf(row.get('PLEDGE_RATIO'), 0)
            if ratio > max_ratio: max_ratio = ratio
        return max_ratio
    except: return 0

def analyze(code, name, fin_list, bs_list, gw, eq, pledge_ratio):
    """Analyze one stock and return red flags."""
    result = {
        'code': code,
        'name': name,
        'redFlags': [],
        'warnings': [],
        'financials': {},
        'valuation': {},
        'verdict': '通过'
    }

    # Find latest annual report from financial data
    annual = None
    latest = None
    if fin_list:
        for row in fin_list:
            rt = row.get('REPORT_TYPE', '')
            if '年报' in rt and annual is None:
                annual = row
            if latest is None:
                latest = row

    d = annual if annual else (latest or {})

    # --- Financial indicators ---
    roe = sf(d.get('ROEJQ'))
    debt_ratio = sf(d.get('ZCFZL'))
    gross_margin = sf(d.get('XSMLL'))
    net_profit = sf(d.get('PARENTNETPROFIT'))
    deducted = sf(d.get('KCFJCXSYJLR'))
    revenue = sf(d.get('TOTALOPERATEREVE'))
    profit_growth = sf(d.get('PARENTNETPROFITTZ'))
    revenue_growth = sf(d.get('TOTALOPERATEREVETZ'))
    cf_per_share = sf(d.get('MGJYXJJE'))
    eps = sf(d.get('MGWFPLR'))
    ar_to_rev = sf(d.get('YSZKYYSR'))
    current_ratio = sf(d.get('LD'))
    quick_ratio = sf(d.get('SD'))

    result['financials'] = {
        'roe': roe,
        'debtRatio': debt_ratio,
        'grossMargin': gross_margin,
        'netProfit': net_profit,
        'deductedProfit': deducted,
        'revenue': revenue,
        'netProfitGrowth': profit_growth,
        'revenueGrowth': revenue_growth,
        'cfPerShare': cf_per_share,
        'eps': eps,
        'arToRevenue': ar_to_rev,
        'currentRatio': current_ratio,
        'quickRatio': quick_ratio,
    }

    # Cash flow ratio
    cf_to_profit = None
    if cf_per_share is not None and eps is not None and eps != 0:
        cf_to_profit = cf_per_share / eps
    result['financials']['cfToProfit'] = cf_to_profit

    # Non-recurring ratio
    nonrec_ratio = None
    if net_profit and deducted is not None and net_profit != 0:
        nonrec_ratio = abs(net_profit - deducted) / abs(net_profit)
    result['financials']['nonRecurringRatio'] = nonrec_ratio

    # --- Goodwill ---
    result['financials']['goodwill_wan'] = gw
    result['financials']['equity_wan'] = eq
    gw_to_eq = 0
    if gw and eq and eq > 0:
        gw_to_eq = gw / eq * 100
    result['financials']['goodwillToEquity'] = gw_to_eq

    # --- 大存大贷 check ---
    sdg_flag = False
    if bs_list:
        bs = bs_list[0]
        cash = sf(bs.get('MONETARYFUNDS'))
        total_assets = sf(bs.get('TOTAL_ASSETS'))
        short_borrow = sf(bs.get('SHORT_LOAN'))
        # Also check BORROW_FUND
        if cash and total_assets and total_assets > 0:
            cash_ratio = cash / total_assets * 100
            borrow_total = (sf(bs.get('SHORT_LOAN'), 0) or 0) + (sf(bs.get('BORROW_FUND'), 0) or 0)
            borrow_ratio = borrow_total / total_assets * 100
            result['financials']['cashToAsset'] = cash_ratio
            result['financials']['borrowToAsset'] = borrow_ratio
            if cash_ratio > 20 and borrow_ratio > 20:
                sdg_flag = True

    # --- RED FLAGS ---
    # Hard: 商誉/净资产 > 40%
    if gw_to_eq > 40:
        result['redFlags'].append({
            'flag': '商誉占净资产>40%',
            'severity': '🔴硬雷',
            'threshold': '>40%',
            'actual': f'{gw_to_eq:.1f}%',
            'action': '剔除'
        })

    # Hard: 控股股东质押 > 70%
    if pledge_ratio > 70:
        result['redFlags'].append({
            'flag': '控股股东质押>70%',
            'severity': '🔴硬雷',
            'threshold': '>70%',
            'actual': f'{pledge_ratio:.1f}%',
            'action': '剔除'
        })

    # Hard: 大存大贷
    if sdg_flag:
        result['redFlags'].append({
            'flag': '存贷双高',
            'severity': '🔴硬雷',
            'threshold': '货币资金和借款均>总资产20%',
            'actual': f'现金/总资产={result["financials"].get("cashToAsset",0):.1f}%, 借款/总资产={result["financials"].get("borrowToAsset",0):.1f}%',
            'action': '剔除'
        })

    # --- WARNINGS ---
    # Soft: 经营现金流/净利润 < 0.5
    if cf_to_profit is not None and cf_to_profit < 0.5:
        sev = '🟡软警示' if cf_to_profit >= 0 else '🟠严重'
        result['warnings'].append({
            'flag': '经营现金流/净利润<0.5' if cf_to_profit >= 0 else '经营现金流为负',
            'severity': sev,
            'threshold': '<0.5' if cf_to_profit >= 0 else '<0',
            'actual': f'{cf_to_profit:.2f}',
            'action': '降权'
        })

    # Soft: 应收账款/收入 > 40%
    if ar_to_rev is not None and ar_to_rev > 0.4:
        result['warnings'].append({
            'flag': '应收账款/收入>40%',
            'severity': '🟡软警示',
            'threshold': '>40%',
            'actual': f'{ar_to_rev*100:.1f}%',
            'action': '降权'
        })

    # Soft: 非经常性损益/利润 > 20%
    if nonrec_ratio is not None and nonrec_ratio > 0.2:
        result['warnings'].append({
            'flag': '非经常性损益/利润>20%',
            'severity': '🟡软警示',
            'threshold': '>20%',
            'actual': f'{nonrec_ratio*100:.1f}%',
            'action': '降权'
        })

    # Soft: 资产负债率 > 70%
    if debt_ratio is not None and debt_ratio > 70:
        result['warnings'].append({
            'flag': '资产负债率>70%',
            'severity': '🟡软警示',
            'threshold': '>70%',
            'actual': f'{debt_ratio:.1f}%',
            'action': '降权'
        })

    # Soft: 净利润增速为负
    if profit_growth is not None and profit_growth < -10:
        result['warnings'].append({
            'flag': '净利润大幅下滑',
            'severity': '🟡软警示',
            'threshold': '<-10%',
            'actual': f'{profit_growth:.1f}%',
            'action': '降权'
        })

    # Soft: 毛利率异常低
    if gross_margin is not None and gross_margin < 10:
        result['warnings'].append({
            'flag': '毛利率<10%',
            'severity': '🟡软警示',
            'threshold': '<10%',
            'actual': f'{gross_margin:.1f}%',
            'action': '降权'
        })

    # --- Verdict ---
    has_hard = len(result['redFlags']) > 0
    if has_hard:
        result['verdict'] = '剔除'
    elif len(result['warnings']) >= 3:
        result['verdict'] = '降权'
    elif len(result['warnings']) > 0:
        result['verdict'] = '降权'
    else:
        result['verdict'] = '通过'

    return result

# --- Main ---
# Name mapping from sector-analyst.json
NAME_MAP = {
    '600667':'太极实业','600206':'有研新材','002185':'华天科技','000021':'深科技',
    '603005':'晶方科技','001399':'惠科股份','600641':'先导基电','600460':'士兰微',
    '688371':'菲沃泰','688729':'屹唐股份','688549':'中巨芯-U','688783':'西安奕材-U',
    '688728':'格科微','603936':'博敏电子','688135':'利扬芯片','688262':'国芯科技',
    '688216':'气派科技','688711':'宏微科技','688209':'英集芯','688595':'芯海科技',
    '688259':'创耀科技','688484':'南芯科技','688106':'金宏气体','002396':'星网锐捷',
    '600330':'天通股份','600522':'中天科技','002273':'水晶光电','000938':'紫光股份',
    '002245':'蔚蓝锂芯','301282':'金禄电子','605133':'嵘泰股份','002448':'中原内配',
    '603890':'春秋电子','002669':'康达新材','002913':'奥士康','002409':'雅克科技',
    '688347':'华虹宏力','002156':'通富微电','688361':'中科飞测','688141':'杰华特',
    '688261':'东微半导','300604':'长川科技','688328':'深科达','688147':'微导纳米',
    '688809':'强一股份','688003':'天准科技','688596':'正帆科技','688409':'富创精密',
    '688525':'佰维存储','301308':'江波龙','002371':'北方华创','688012':'中微公司',
    '688072':'拓荆科技','688120':'华海清科','688037':'芯源微','688110':'东芯股份',
    '603986':'兆易创新','688627':'精智达','600584':'长电科技','301205':'联特科技',
    '002281':'光迅科技','300308':'中际旭创','688002':'睿创微纳','600183':'生益科技',
    '301583':'托伦斯',
}

results = {}
for i, code in enumerate(ALL_CODES):
    name = NAME_MAP.get(code, code)
    print(f'[{i+1}/{len(ALL_CODES)}] {code} {name}...', end=' ', flush=True)

    try:
        fin_list = get_financials(code)
        bs_list = get_balance_sheet(code)
        gw, eq = get_sina_goodwill_equity(code)
        pledge = get_pledge(code)

        result = analyze(code, name, fin_list, bs_list, gw, eq, pledge)
        results[code] = result

        rf = len(result['redFlags'])
        w = len(result['warnings'])
        v = result['verdict']
        print(f'{v} | 硬雷:{rf} 软警:{w} | 商誉/净资产:{result["financials"].get("goodwillToEquity",0):.1f}% | 质押:{pledge:.1f}%')
    except Exception as e:
        print(f'ERROR: {e}')
        results[code] = {
            'code': code, 'name': name,
            'verdict': '数据缺失',
            'redFlags': [],
            'warnings': [{'flag': '数据获取失败', 'severity': '⚠️', 'action': '人工复核'}],
            'financials': {},
            'error': str(e)
        }

    time.sleep(0.12)

# --- Summary ---
passed = [(c,r) for c,r in results.items() if r['verdict'] == '通过']
warned = [(c,r) for c,r in results.items() if r['verdict'] == '降权']
rejected = [(c,r) for c,r in results.items() if r['verdict'] == '剔除']
missing = [(c,r) for c,r in results.items() if r['verdict'] == '数据缺失']

print('\n' + '='*70)
print(f'SUMMARY: 通过={len(passed)} 降权={len(warned)} 剔除={len(rejected)} 数据缺失={len(missing)}')
print('='*70)

if rejected:
    print('\n🔴 硬雷剔除:')
    for c, r in rejected:
        flags = [f['flag'] for f in r['redFlags']]
        print(f'  {c} {r["name"]}: {", ".join(flags)}')

if warned:
    print(f'\n🟡 软警示降权 ({len(warned)}只):')
    for c, r in warned:
        warns = [f['flag'] for f in r['warnings']]
        print(f'  {c} {r["name"]}: {", ".join(warns[:3])}')

if missing:
    print(f'\n⚠️ 数据缺失 ({len(missing)}只):')
    for c, r in missing:
        print(f'  {c} {r["name"]}')

# Save
output_path = 'e:/finacial-invest/data/runs/20260721_hot-trends/fundamentals_raw.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump({'results': results, 'summary': {
        'passed': len(passed), 'warned': len(warned),
        'rejected': len(rejected), 'missing': len(missing)
    }}, f, ensure_ascii=False, indent=2)
print(f'\nSaved to {output_path}')