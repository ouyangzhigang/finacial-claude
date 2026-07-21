#!/usr/bin/env python
"""Batch query financial red-flag data for all 65 candidates via 东方财富 datacenter API."""
import json, subprocess, time, sys, re

CODES = [
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
    """Convert 600xxx -> 600xxx.SH, 000xxx -> 000xxx.SZ, 688xxx -> 688xxx.SH"""
    if code.startswith('6'):
        return f'{code}.SH'
    elif code.startswith('0') or code.startswith('3'):
        return f'{code}.SZ'
    else:
        return f'{code}.SH'

def curl_financials(secucode, report_date=''):
    """Query 东方财富 main financial indicators."""
    url = f'https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_FINANCE_MAINFINADATA&sty=APP_F10_MAINFINADATA&filter=(SECUCODE=%22{secucode}%22)&p=1&ps=10&sr=-1&st=REPORT_DATE&source=HSF10&client=PC'
    try:
        result = subprocess.run(['curl', '-k', '-s', url], capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f'  curl_financials error for {secucode}: {e}', file=sys.stderr)
        return None

def curl_balance_sheet(secucode):
    """Query 东方财富 balance sheet for 商誉."""
    url = f'https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_DMSK_FN_BALANCE&sty=ALL&filter=(SECUCODE=%22{secucode}%22)(REPORT_TYPE=%22年报%22)&p=1&ps=2&sr=-1&st=REPORT_DATE&source=HSF10&client=PC'
    try:
        result = subprocess.run(['curl', '-k', '-s', url], capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f'  curl_bs error for {secucode}: {e}', file=sys.stderr)
        return None

def curl_pledge(secucode):
    """Query 东方财富 shareholders/pledge data."""
    url = f'https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_EQUITY_PLEDGE&sty=ALL&filter=(SECUCODE=%22{secucode}%22)&p=1&ps=5&sr=-1&st=NOTICE_DATE&source=HSF10&client=PC'
    try:
        result = subprocess.run(['curl', '-k', '-s', url], capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f'  curl_pledge error for {secucode}: {e}', file=sys.stderr)
        return None

def safe_float(v, default=None):
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default

def analyze_stock(code, fin_data, bs_data, pledge_data):
    """Extract key red-flag indicators."""
    result = {'code': code, 'redFlags': [], 'warnings': []}

    # Parse financial data - find latest annual report
    latest_annual = None
    latest_q = None
    if fin_data and fin_data.get('result') and fin_data['result'].get('data'):
        for row in fin_data['result']['data']:
            rtype = row.get('REPORT_TYPE', '')
            if '年报' in rtype and latest_annual is None:
                latest_annual = row
            if '一季报' in rtype and latest_q is None:
                latest_q = row

    # Use annual data for most indicators
    d = latest_annual if latest_annual else (latest_q or {})
    dq = latest_q if latest_q else {}

    # Core financials
    result['roe'] = safe_float(d.get('ROEJQ'))
    result['debtRatio'] = safe_float(d.get('ZCFZL'))
    result['grossMargin'] = safe_float(d.get('XSMLL'))
    result['netProfit'] = safe_float(d.get('PARENTNETPROFIT'))
    result['deductedProfit'] = safe_float(d.get('KCFJCXSYJLR'))
    result['revenue'] = safe_float(d.get('TOTALOPERATEREVE'))
    result['netProfitGrowth'] = safe_float(d.get('PARENTNETPROFITTZ'))
    result['revenueGrowth'] = safe_float(d.get('TOTALOPERATEREVETZ'))

    # Cash flow indicators
    result['cfPerShare'] = safe_float(d.get('MGJYXJJE'))
    result['eps'] = safe_float(d.get('MGWFPLR'))
    result['bps'] = safe_float(d.get('BPS'))

    # Cash flow ratio
    if result['cfPerShare'] is not None and result['eps'] is not None and result['eps'] != 0:
        result['cfToProfit'] = result['cfPerShare'] / result['eps']
    else:
        result['cfToProfit'] = None

    # AR/revenue ratio
    result['arToRevenue'] = safe_float(d.get('YSZKYYSR'))

    # Non-recurring ratio
    if result['netProfit'] and result['deductedProfit'] is not None and result['netProfit'] != 0:
        result['nonRecurringRatio'] = abs(result['netProfit'] - result['deductedProfit']) / abs(result['netProfit'])
    else:
        result['nonRecurringRatio'] = None

    # --- Balance sheet: 商誉 ---
    if bs_data and bs_data.get('result') and bs_data['result'].get('data'):
        bs_row = bs_data['result']['data'][0]
        result['goodwill'] = safe_float(bs_row.get('GOODWILL'))
        result['totalEquity'] = safe_float(bs_row.get('TOTAL_EQUITY'))
        result['totalAssets'] = safe_float(bs_row.get('TOTAL_ASSETS'))
        result['cashEquivalents'] = safe_float(bs_row.get('MONETARY_CAPITAL'))
        result['shortBorrow'] = safe_float(bs_row.get('SHORT_BORROW'))
        result['longBorrow'] = safe_float(bs_row.get('LONG_BORROW'))

        if result['goodwill'] and result['totalEquity'] and result['totalEquity'] > 0:
            result['goodwillToEquity'] = result['goodwill'] / result['totalEquity'] * 100
        else:
            result['goodwillToEquity'] = 0

        # 大存大贷 check
        if result['cashEquivalents'] and result['totalAssets'] and result['shortBorrow'] is not None:
            cashRatio = result['cashEquivalents'] / result['totalAssets'] * 100
            borrowRatio = (safe_float(result.get('shortBorrow',0) or 0) + safe_float(result.get('longBorrow',0) or 0)) / result['totalAssets'] * 100
            result['cashToAsset'] = cashRatio
            result['borrowToAsset'] = borrowRatio
            if cashRatio > 20 and borrowRatio > 20:
                result['sdgFlag'] = True
            else:
                result['sdgFlag'] = False
        else:
            result['sdgFlag'] = False
    else:
        result['goodwill'] = None
        result['totalEquity'] = None
        result['goodwillToEquity'] = 0
        result['sdgFlag'] = False

    # --- Pledge data ---
    if pledge_data and pledge_data.get('result') and pledge_data['result'].get('data'):
        max_pledge = 0
        for row in pledge_data['result']['data']:
            ratio = safe_float(row.get('PLEDGE_RATIO'), 0)
            if ratio > max_pledge:
                max_pledge = ratio
        result['maxPledgeRatio'] = max_pledge
    else:
        result['maxPledgeRatio'] = 0

    # --- Red flag checks ---
    # Hard red flags
    if result.get('goodwillToEquity', 0) > 40:
        result['redFlags'].append({
            'flag': '商誉占净资产>40%',
            'severity': '🔴硬雷',
            'threshold': '>40%',
            'actual': f'{result["goodwillToEquity"]:.1f}%',
            'action': '剔除'
        })

    if result.get('maxPledgeRatio', 0) > 70:
        result['redFlags'].append({
            'flag': '控股股东质押>70%',
            'severity': '🔴硬雷',
            'threshold': '>70%',
            'actual': f'{result["maxPledgeRatio"]:.1f}%',
            'action': '剔除'
        })

    if result.get('sdgFlag'):
        result['redFlags'].append({
            'flag': '存贷双高',
            'severity': '🔴硬雷',
            'threshold': '货币资金和借款均>总资产20%',
            'actual': f'现金/总资产={result.get("cashToAsset",0):.1f}%, 借款/总资产={result.get("borrowToAsset",0):.1f}%',
            'action': '剔除'
        })

    # Soft warnings
    if result.get('cfToProfit') is not None and result['cfToProfit'] < 0.5:
        result['warnings'].append({
            'flag': '经营现金流/净利润<0.5',
            'severity': '🟡软警示',
            'threshold': '<0.5',
            'actual': f'{result["cfToProfit"]:.2f}',
            'action': '降权'
        })

    if result.get('cfToProfit') is not None and result['cfToProfit'] < 0:
        result['warnings'].append({
            'flag': '经营现金流为负',
            'severity': '🟡软警示',
            'threshold': '<0',
            'actual': f'{result["cfToProfit"]:.2f}',
            'action': '降权'
        })

    if result.get('arToRevenue') is not None and result['arToRevenue'] > 0.4:
        result['warnings'].append({
            'flag': '应收账款/收入>40%',
            'severity': '🟡软警示',
            'threshold': '>40%',
            'actual': f'{result["arToRevenue"]*100:.1f}%',
            'action': '降权'
        })

    if result.get('nonRecurringRatio') is not None and result['nonRecurringRatio'] > 0.2:
        result['warnings'].append({
            'flag': '非经常性损益/利润>20%',
            'severity': '🟡软警示',
            'threshold': '>20%',
            'actual': f'{result["nonRecurringRatio"]*100:.1f}%',
            'action': '降权'
        })

    if result.get('debtRatio') is not None and result['debtRatio'] > 70:
        result['warnings'].append({
            'flag': '资产负债率>70%',
            'severity': '🟡软警示',
            'threshold': '>70%',
            'actual': f'{result["debtRatio"]:.1f}%',
            'action': '降权'
        })

    # Verdict
    has_hard = any('🔴硬雷' in r.get('severity','') for r in result['redFlags'])
    if has_hard:
        result['verdict'] = '剔除'
    elif len(result['warnings']) >= 3:
        result['verdict'] = '降权'
    elif len(result['warnings']) > 0:
        result['verdict'] = '降权'
    else:
        result['verdict'] = '通过'

    return result

# Main
results = {}
for i, code in enumerate(CODES):
    secu = sh_secucode(code)
    print(f'[{i+1}/{len(CODES)}] {code} ({secu})...', end=' ', flush=True)

    fin_data = curl_financials(secu)
    bs_data = curl_balance_sheet(secu)
    pledge_data = curl_pledge(secu)

    result = analyze_stock(code, fin_data, bs_data, pledge_data)
    results[code] = result

    v = result['verdict']
    rf_count = len(result['redFlags'])
    w_count = len(result['warnings'])
    print(f'{v} (硬雷:{rf_count}, 软警:{w_count})')

    time.sleep(0.15)  # Rate limit

# Output summary
print('\n' + '='*60)
print('SUMMARY')
print('='*60)
hard_rejects = [c for c, r in results.items() if r['verdict'] == '剔除']
warnings_list = [c for c, r in results.items() if r['verdict'] == '降权']
passed = [c for c, r in results.items() if r['verdict'] == '通过']

print(f'通过: {len(passed)}')
print(f'降权: {len(warnings_list)}')
print(f'剔除: {len(hard_rejects)}')

if hard_rejects:
    print('\n硬雷剔除:')
    for c in hard_rejects:
        r = results[c]
        flag_names = [f['flag'] for f in r['redFlags']]
        print(f'  {c}: {", ".join(flag_names)}')

print('\n降权:')
for c in warnings_list:
    r = results[c]
    warn_names = [f['flag'] for f in r['warnings']]
    print(f'  {c}: {", ".join(warn_names[:3])}')

# Save results
output = {'results': results, 'summary': {'passed': len(passed), 'warned': len(warnings_list), 'rejected': len(hard_rejects)}}
print(json.dumps(output, ensure_ascii=False, indent=2))