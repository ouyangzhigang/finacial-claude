#!/usr/bin/env python
"""Minimal batch re-run: just save results, no fancy display."""
import requests, urllib3, re, json, sys, time, io
urllib3.disable_warnings()

PROXY = {'http': None, 'https': None}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

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

def sh_secu(code):
    return f'{code}.SH' if code.startswith('6') else f'{code}.SZ'

def sf(v, default=None):
    if v is None: return default
    try: return float(v)
    except: return default

def get_fin(code):
    secu = sh_secu(code)
    url = f'https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_FINANCE_MAINFINADATA&sty=APP_F10_MAINFINADATA&filter=(SECUCODE=%22{secu}%22)&p=1&ps=10&sr=-1&st=REPORT_DATE&source=HSF10&client=PC'
    try:
        r = requests.get(url, verify=False, timeout=15, proxies=PROXY, headers=HEADERS)
        if r.status_code != 200: return None
        d = r.json()
        if d.get('result') and d['result'].get('data'):
            return d['result']['data']
    except: pass
    return None

def get_bs(code):
    secu = sh_secu(code)
    url = f'https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_DMSK_FN_BALANCE&sty=ALL&filter=(SECUCODE=%22{secu}%22)&p=1&ps=3&sr=-1&st=REPORT_DATE&source=HSF10&client=PC'
    try:
        r = requests.get(url, verify=False, timeout=15, proxies=PROXY, headers=HEADERS)
        if r.status_code != 200: return None
        d = r.json()
        if d.get('result') and d['result'].get('data'):
            return d['result']['data']
    except: pass
    return None

def get_gw_eq(code):
    try:
        r = requests.get(f'https://money.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/{code}/ctrl/2025/displaytype/4.phtml',
                        verify=False, timeout=15, proxies=PROXY, headers=HEADERS)
        r.encoding = 'gbk'
        html = r.text
        gw = None
        pos = html.find('商誉')
        if pos > 0:
            snippet = html[pos:pos+500]
            clean = re.sub(r'<[^>]+>', ' ', snippet)
            nums = re.findall(r'[\d,]+\.?\d*', clean)
            if nums: gw = float(nums[0].replace(',', ''))
        eq = None
        for kw in ['归属于母公司股东权益合计', '归属于母公司所有者权益合计', '股东权益合计']:
            pos = html.find(kw)
            if pos > 0:
                snippet = html[pos:pos+500]
                clean = re.sub(r'<[^>]+>', ' ', snippet)
                nums = re.findall(r'[\d,]+\.?\d*', clean)
                if nums: eq = float(nums[0].replace(',', ''))
                break
        return gw, eq
    except: return None, None

def analyze(code, name, fin_list, bs_list, gw, eq):
    r = {'code': code, 'name': name, 'redFlags': [], 'warnings': [], 'financials': {}, 'verdict': '通过'}

    annual = None
    latest = None
    if fin_list:
        for row in fin_list:
            rt = row.get('REPORT_TYPE', '')
            if '年报' in rt and annual is None: annual = row
            if latest is None: latest = row
    d = annual if annual else (latest or {})

    roe = sf(d.get('ROEJQ'))
    dr = sf(d.get('ZCFZL'))
    gm = sf(d.get('XSMLL'))
    np_ = sf(d.get('PARENTNETPROFIT'))
    ded = sf(d.get('KCFJCXSYJLR'))
    pg = sf(d.get('PARENTNETPROFITTZ'))
    rg = sf(d.get('TOTALOPERATEREVETZ'))
    cfps = sf(d.get('MGJYXJJE'))
    eps = sf(d.get('MGWFPLR'))
    ar2r = sf(d.get('YSZKYYSR'))

    r['financials'] = {
        'roe': roe, 'debtRatio': dr, 'grossMargin': gm,
        'netProfit': np_, 'deductedProfit': ded,
        'netProfitGrowth': pg, 'revenueGrowth': rg,
        'cfPerShare': cfps, 'eps': eps, 'arToRevenue': ar2r,
        'goodwillWan': gw, 'equityWan': eq,
    }

    # CF/profit
    cf2p = None
    if cfps is not None and eps is not None and eps != 0:
        cf2p = cfps / eps
    r['financials']['cfToProfit'] = cf2p

    # Non-recurring
    nr = None
    if np_ and ded is not None and np_ != 0:
        nr = abs(np_ - ded) / abs(np_)
    r['financials']['nonRecurringRatio'] = nr

    # Goodwill ratio
    gw2eq = 0
    if gw and eq and eq > 0: gw2eq = gw / eq * 100
    r['financials']['goodwillToEquity'] = gw2eq

    # 大存大贷
    sdg = False
    if bs_list:
        bs = bs_list[0]
        cash = sf(bs.get('MONETARYFUNDS'))
        ta = sf(bs.get('TOTAL_ASSETS'))
        sl = sf(bs.get('SHORT_LOAN'), 0) or 0
        bf = sf(bs.get('BORROW_FUND'), 0) or 0
        if cash and ta and ta > 0:
            cr = cash / ta * 100
            br = (sl + bf) / ta * 100
            r['financials']['cashToAsset'] = cr
            r['financials']['borrowToAsset'] = br
            if cr > 20 and br > 20: sdg = True

    # Hard red flags
    if gw2eq > 40:
        r['redFlags'].append({'flag': '商誉占净资产>40%', 'severity': 'hard', 'threshold': '>40%', 'actual': f'{gw2eq:.1f}%', 'action': '剔除'})
    if sdg:
        r['redFlags'].append({'flag': '存贷双高', 'severity': 'hard', 'threshold': '货币资金和借款均>总资产20%', 'actual': f'现金/总资产={r["financials"].get("cashToAsset",0):.1f}%', 'action': '剔除'})

    # Soft warnings
    if cf2p is not None and cf2p < 0.5:
        sev = 'soft' if cf2p >= 0 else 'severe'
        r['warnings'].append({'flag': '经营现金流/净利润<0.5' if cf2p >= 0 else '经营现金流为负', 'severity': sev, 'threshold': '<0.5' if cf2p >= 0 else '<0', 'actual': f'{cf2p:.2f}', 'action': '降权'})
    if ar2r is not None and ar2r > 0.4:
        r['warnings'].append({'flag': '应收账款/收入>40%', 'severity': 'soft', 'threshold': '>40%', 'actual': f'{ar2r*100:.1f}%', 'action': '降权'})
    if nr is not None and nr > 0.2:
        r['warnings'].append({'flag': '非经常性损益/利润>20%', 'severity': 'soft', 'threshold': '>20%', 'actual': f'{nr*100:.1f}%', 'action': '降权'})
    if dr is not None and dr > 70:
        r['warnings'].append({'flag': '资产负债率>70%', 'severity': 'soft', 'threshold': '>70%', 'actual': f'{dr:.1f}%', 'action': '降权'})
    if pg is not None and pg < -10:
        r['warnings'].append({'flag': '净利润大幅下滑', 'severity': 'soft', 'threshold': '<-10%', 'actual': f'{pg:.1f}%', 'action': '降权'})
    if gm is not None and gm < 10:
        r['warnings'].append({'flag': '毛利率<10%', 'severity': 'soft', 'threshold': '<10%', 'actual': f'{gm:.1f}%', 'action': '降权'})

    if r['redFlags']: r['verdict'] = '剔除'
    elif len(r['warnings']) >= 3: r['verdict'] = '降权'
    elif r['warnings']: r['verdict'] = '降权'
    else: r['verdict'] = '通过'

    return r

# Main
results = {}
for i, code in enumerate(ALL_CODES):
    name = NAME_MAP.get(code, code)
    print(f'[{i+1}/{len(ALL_CODES)}] {code} {name}', end=' ', flush=True)
    try:
        fin = get_fin(code)
        bs = get_bs(code)
        gw, eq = get_gw_eq(code)
        res = analyze(code, name, fin, bs, gw, eq)
        results[code] = res
        print(f'-> {res["verdict"]} (hard:{len(res["redFlags"])} soft:{len(res["warnings"])})')
    except Exception as e:
        print(f'-> ERROR: {e}')
        results[code] = {'code': code, 'name': name, 'verdict': '数据缺失', 'redFlags': [], 'warnings': [], 'financials': {}, 'error': str(e)}
    time.sleep(0.1)

# Save
with open('e:/finacial-invest/data/runs/20260721_hot-trends/fundamentals_raw.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# Summary
passed = sum(1 for r in results.values() if r['verdict'] == '通过')
warned = sum(1 for r in results.values() if r['verdict'] == '降权')
rejected = sum(1 for r in results.values() if r['verdict'] == '剔除')
missing = sum(1 for r in results.values() if r['verdict'] == '数据缺失')
print(f'\nDone: passed={passed} warned={warned} rejected={rejected} missing={missing}')
print('Saved to fundamentals_raw.json')
