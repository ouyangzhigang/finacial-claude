#!/usr/bin/env python
"""Batch fundamentals for 27 short-term pick passing stocks."""
import requests, urllib3, re, json, sys, time
urllib3.disable_warnings()
PROXY = {'http': None, 'https': None}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

CODES = ['001399','300433','688729','000021','600460','688728','002203','002273',
         '600667','600206','688538','600641','688403','002396','600330','600988',
         '000426','600884','000603','002747','002245','300735','000048','603890',
         '300450','002459','688772']

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
    except: return None

def get_bs(code):
    secu = sh_secu(code)
    url = f'https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_DMSK_FN_BALANCE&sty=ALL&filter=(SECUCODE=%22{secu}%22)&p=1&ps=3&sr=-1&st=REPORT_DATE&source=HSF10&client=PC'
    try:
        r = requests.get(url, verify=False, timeout=15, proxies=PROXY, headers=HEADERS)
        if r.status_code != 200: return None
        d = r.json()
        if d.get('result') and d['result'].get('data'):
            return d['result']['data']
    except: return None

def get_gw_eq(code):
    try:
        r = requests.get(
            f'https://money.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/{code}/ctrl/2025/displaytype/4.phtml',
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

def get_pe_pb_percentile(code):
    """Get PE/PB historical percentile from 腾讯 K线."""
    market = 'sh' if code.startswith('6') else 'sz'
    url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,,,500,qfq'
    try:
        r = requests.get(url, timeout=10, proxies=PROXY, headers=HEADERS)
        if r.status_code != 200: return None, None
        d = r.json()
        data = d.get('data', {}).get(f'{market}{code}', {})
        klines = data.get('day', []) or data.get('qfqday', [])
        if not klines: return None, None
        pes = []
        for k in klines:
            if len(k) >= 7:
                try: pe = float(k[6]) if k[6] else None
                except: pe = None
                if pe is not None and pe > 0 and pe < 10000:
                    pes.append(pe)
        if len(pes) < 100: return None, None
        pes_sorted = sorted(pes)
        current_pe = pes[-1]
        rank = sum(1 for p in pes_sorted if p <= current_pe) / len(pes_sorted) * 100
        return current_pe, rank
    except: return None, None

# Run for all
results = {}
for i, code in enumerate(CODES):
    print(f'[{i+1}/{len(CODES)}] {code} ...', end=' ', flush=True)
    try:
        fin = get_fin(code)
        bs = get_bs(code)
        gw, eq = get_gw_eq(code)

        # Find annual report
        annual = None
        latest = None
        if fin:
            for row in fin:
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
        rg = sf(d.get('TOTALOPERATREVETZ'))
        cfps = sf(d.get('MGJYXJJE'))
        eps = sf(d.get('MGWFPLR'))
        ar2r = sf(d.get('YSZKYYSR'))
        nm = sf(d.get('XSJLL'))

        # Scale down large numbers (万元 to 亿元 conversion check)
        if np_ is not None and abs(np_) > 1000000: np_ = np_ / 10000
        if ded is not None and abs(ded) > 1000000: ded = ded / 10000

        cf2p = None
        if cfps is not None and eps is not None and eps != 0:
            cf2p = cfps / eps

        nr = None
        if np_ and ded is not None and np_ != 0:
            nr = abs(np_ - ded) / abs(np_)

        gw2eq = 0
        if gw and eq and eq > 0:
            gw2eq = gw / eq * 100

        sdg = False
        cr = None
        br = None
        if bs:
            b = bs[0]
            cash = sf(b.get('MONETARYFUNDS'))
            ta = sf(b.get('TOTAL_ASSETS'))
            sl = sf(b.get('SHORT_LOAN'), 0) or 0
            ll = sf(b.get('LONG_LOAN'), 0) or 0
            bf = sf(b.get('BORROW_FUND'), 0) or 0
            total_borrow = sl + ll + bf
            if cash and ta and ta > 0:
                cr = cash / ta * 100
                br = total_borrow / ta * 100
                if cr > 20 and br > 20: sdg = True

        results[code] = {
            'roe': roe, 'debtRatio': dr, 'grossMargin': gm, 'netMargin': nm,
            'netProfit': np_, 'deductedProfit': ded,
            'netProfitGrowth': pg, 'revenueGrowth': rg,
            'cfPerShare': cfps, 'eps': eps,
            'cfToProfit': cf2p, 'arToRevenue': ar2r,
            'nonRecurringRatio': nr,
            'goodwillWan': gw, 'equityWan': eq,
            'goodwillToEquity': gw2eq,
            'cashToAsset': cr, 'borrowToAsset': br,
            'sdg': sdg, 'dataSource': 'annual' if annual else 'latest',
            'reportDate': d.get('REPORT_DATE', 'N/A'),
            'reportType': d.get('REPORT_TYPE', 'N/A'),
        }
        print(f'OK ROE={roe} GM={gm} DR={dr} GW/EQ={gw2eq:.1f}%')
    except Exception as e:
        print(f'ERROR: {e}')
        results[code] = {'error': str(e)}
    time.sleep(0.15)

with open('e:/finacial-invest/data/temp_financials.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'\nSaved {len(results)} results to temp_financials.json')