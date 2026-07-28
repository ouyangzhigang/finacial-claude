#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fundamentals analyst batch: financial health check + valuation anchor + red flags.
For 38 pass stocks from technical-liquidity.json (20260728).
Data: tencent_quote (PE/price/mktcap) + eastmoney MAINFINADATA (financials) + sina BS (goodwill/equity).
No MCP used.
"""
import sys, os, json, re, time, requests, urllib3
urllib3.disable_warnings()

PROXY = {'http': None, 'https': None}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

ASOF = '20260728'
OUT_DIR = f'E:/finacial-invest/data/runs/{ASOF}_short-term-picks'
OUT_FILE = os.path.join(OUT_DIR, 'fundamentals-analyst.json')

# ── Load pass stocks from technical-liquidity.json ──
TL_FILE = os.path.join(OUT_DIR, 'technical-liquidity.json')
with open(TL_FILE, 'r', encoding='utf-8') as f:
    tl = json.load(f)
PASS_STOCKS = tl['data']['pass']

# Build name map + code list
STOCKS = []
for s in PASS_STOCKS:
    STOCKS.append({'code': s['code'], 'name': s['name'], 'price': s['price'],
                    'mktcap': s.get('marketCap'), 'sector': s.get('sector', '')})

# Also get sector from factors list
factors_by_code = {f['code']: f for f in tl['data']['factors']}
for s in STOCKS:
    f = factors_by_code.get(s['code'])
    if f and not s['sector']:
        s['sector'] = f.get('sector', '')

# ── Bank codes (skip debt ratio + gross margin checks) ──
BANK_CODES = {'601398','601939','601288','601988','601328','601998'}

def tc_sym(code):
    return f'sh{code}' if code.startswith(('6','9')) else f'sz{code}'

def sh_secu(code):
    return f'{code}.SH' if code.startswith('6') else f'{code}.SZ'

def sf(v, default=None):
    if v is None or v == '': return default
    try: return float(v)
    except: return default

def tencent_quote_batch(codes):
    """Batch tencent quote for PE/price/mktcap."""
    syms = ','.join(tc_sym(c) for c in codes)
    url = f'http://qt.gtimg.cn/q={syms}'
    try:
        r = requests.get(url, timeout=15, headers=HEADERS, proxies=PROXY)
        raw = r.content.decode('gbk', errors='ignore')
        out = {}
        for m in re.finditer(r'v_(\w+)="([^"]*)"', raw):
            data = m.group(2).split('~')
            if len(data) < 50: continue
            code = data[2]
            out[code] = {
                'name': data[1],
                'price': float(data[3]) if data[3] else 0,
                'pe': float(data[39]) if len(data)>39 and data[39] else None,
                'mktcap': float(data[45]) if len(data)>45 and data[45] else None,
                'float_mktcap': float(data[44]) if len(data)>44 and data[44] else None,
            }
        return out
    except Exception as e:
        print(f'  [tencent_quote] ERR: {e}', file=sys.stderr)
        return {}

def get_fin(code):
    """Eastmoney MAINFINADATA: ROE, debt ratio, margins, growth, BPS, cash flow."""
    secu = sh_secu(code)
    url = (f'https://datacenter.eastmoney.com/securities/api/data/get'
           f'?type=RPT_F10_FINANCE_MAINFINADATA&sty=APP_F10_MAINFINADATA'
           f'&filter=(SECUCODE=%22{secu}%22)&p=1&ps=12&sr=-1&st=REPORT_DATE'
           f'&source=HSF10&client=PC')
    try:
        r = requests.get(url, verify=False, timeout=15, proxies=PROXY, headers=HEADERS)
        if r.status_code != 200: return None
        d = r.json()
        if d.get('result') and d['result'].get('data'):
            return d['result']['data']
    except Exception as e:
        pass
    return None

def get_goodwill_equity(code):
    """Sina balance sheet HTML: extract goodwill + equity (归母权益)."""
    try:
        url = f'https://money.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/{code}/ctrl/2025/displaytype/4.phtml'
        r = requests.get(url, verify=False, timeout=15, proxies=PROXY, headers=HEADERS)
        r.encoding = 'gbk'
        html = r.text
        gw = None
        pos = html.find('商誉')
        if pos > 0:
            snippet = html[pos:pos+500]
            clean = re.sub(r'<[^>]+>', ' ', snippet)
            nums = re.findall(r'[\d,]+\.?\d*', clean)
            if nums:
                try: gw = float(nums[0].replace(',', ''))
                except: pass
        eq = None
        for kw in ['归属于母公司股东权益合计', '归属于母公司所有者权益合计', '股东权益合计']:
            pos = html.find(kw)
            if pos > 0:
                snippet = html[pos:pos+500]
                clean = re.sub(r'<[^>]+>', ' ', snippet)
                nums = re.findall(r'[\d,]+\.?\d*', clean)
                if nums:
                    try: eq = float(nums[0].replace(',', ''))
                    except: pass
                if eq: break
        return gw, eq
    except:
        return None, None

def analyze(code, name, sector, tc, fin_list, gw, eq):
    """Analyze one stock: financials + valuation + red flags → verdict."""
    result = {
        'code': code, 'name': name, 'sector': sector,
        'financials': {}, 'valuation': {}, 'redFlags': [],
        'verdict': '通过', 'summary': ''
    }

    is_bank = code in BANK_CODES

    # ── Valuation from tencent ──
    pe = tc.get('pe') if tc else None
    price = tc.get('price') if tc else None
    mktcap = tc.get('mktcap') if tc else None

    # ── Financial data: prefer 年报, fall back to latest ──
    annual = None
    latest = None
    if fin_list:
        for row in fin_list:
            rt = str(row.get('REPORT_TYPE', ''))
            if '年报' in rt and annual is None:
                annual = row
            if latest is None:
                latest = row
        if not annual:
            annual = latest

    d = annual or latest or {}
    roe = sf(d.get('ROEJQ'))
    debt_ratio = sf(d.get('ZCFZL'))
    gross_margin = sf(d.get('XSMLL'))
    net_margin = sf(d.get('XSJLL'))
    bps = sf(d.get('BPS'))
    np_ = sf(d.get('PARENTNETPROFIT'))
    ded = sf(d.get('KCFJCXSYJLR'))
    pg = sf(d.get('PARENTNETPROFITTZ'))
    rg = sf(d.get('TOTALOPERATEREVETZ'))
    cfps = sf(d.get('MGJYXJJE'))
    eps = sf(d.get('EPSJB'))
    roic = sf(d.get('ROIC'))
    # Q1 single-quarter growth
    q_dnp_yoy = sf(d.get('DJD_DPNP_YOY'))

    # ROE trend (annual vs previous annual)
    roe_trend = '数据缺失(单期)'
    if len(fin_list) >= 2:
        annuals = [r for r in fin_list if '年报' in str(r.get('REPORT_TYPE', ''))]
        if len(annuals) >= 2:
            r0 = sf(annuals[0].get('ROEJQ'))
            r1 = sf(annuals[1].get('ROEJQ'))
            if r0 is not None and r1 is not None:
                if r0 > r1: roe_trend = '上升'
                elif r0 < r1: roe_trend = '下降'
                else: roe_trend = '持平'

    # Cash flow / profit ratio
    cf2p = None
    if cfps is not None and eps is not None and eps != 0:
        cf2p = round(cfps / eps, 2)

    # PB
    pb = None
    if price and bps and bps > 0:
        pb = round(price / bps, 2)

    # Non-recurring ratio
    non_recur = None
    if np_ and ded is not None and np_ != 0:
        non_recur = round(abs(np_ - ded) / abs(np_) * 100, 1)

    # Goodwill ratio
    gw2eq = 0
    if gw and eq and eq > 0:
        gw2eq = round(gw / eq * 100, 1)

    result['financials'] = {
        'roe': roe,
        'roeTrend': roe_trend,
        'cashflowRatio': cf2p,
        'netProfitGrowth': pg,
        'revenueGrowth': rg,
        'grossMargin': gross_margin,
        'netMargin': net_margin,
        'debtRatio': debt_ratio,
        'roic': roic,
        'nonRecurRatio': non_recur,
        'goodwillToEquity': gw2eq,
        'eps': eps,
        'bps': bps,
        'reportDate': str(d.get('REPORT_DATE', ''))[:10],
        'reportType': str(d.get('REPORT_TYPE', '')),
    }

    result['valuation'] = {
        'peTtm': pe,
        'pb': pb,
        'price': price,
        'mktcap': mktcap,
        'pePercentile5y': '数据缺失',
        'pbPercentile5y': '数据缺失',
        'relativeToPeers': '数据缺失',
        'verdict': '数据缺失'
    }

    # Valuation verdict
    if pe is not None:
        if pe < 0:
            result['valuation']['verdict'] = '亏损无法估值'
        elif pe <= 20:
            result['valuation']['verdict'] = '低估'
        elif pe <= 40:
            result['valuation']['verdict'] = '合理'
        elif pe <= 80:
            result['valuation']['verdict'] = '偏高'
        elif pe <= 200:
            result['valuation']['verdict'] = '高估'
        else:
            result['valuation']['verdict'] = '严重高估'

    # Financial verdict
    if roe is not None:
        if roe >= 10: fin_v = '优秀'
        elif roe >= 5: fin_v = '良好'
        elif roe >= 2: fin_v = '一般'
        elif roe >= 0: fin_v = '偏低'
        else: fin_v = '亏损'
    else:
        fin_v = '数据缺失'
    result['financials']['verdict'] = fin_v

    # ════════ RED FLAGS ════════
    flags = []

    # ── HARD RED FLAGS (一票否决) ──
    # 1. TTM亏损 (PE<0)
    if pe is not None and pe < 0:
        flags.append({'flag': 'TTM亏损', 'severity': 'hard',
                      'threshold': 'PE>0', 'actual': f'PE={pe}',
                      'action': '剔除'})

    # 2. PE>200 且无利润增速
    if pe is not None and pe > 200:
        if pg is not None and pg <= 0:
            flags.append({'flag': 'PE>200且无利润增速', 'severity': 'hard',
                          'threshold': 'PE>200需增速>0', 'actual': f'PE={pe},增速={pg}%',
                          'action': '剔除'})

    # 3. 商誉占净资产>30%
    if gw2eq > 30:
        flags.append({'flag': '商誉占净资产>30%', 'severity': 'hard',
                      'threshold': '>30%', 'actual': f'{gw2eq}%',
                      'action': '剔除'})

    # 4. 年报亏损(ROE<0或EPS<0)且PE>200 — TTM微利靠非经常性损益,盈利质量极差
    annual_loss = (roe is not None and roe < 0) or (eps is not None and eps < 0)
    if annual_loss and pe is not None and pe > 200:
        flags.append({'flag': '年报亏损且PE>200(TTM微利靠非经常性)', 'severity': 'hard',
                      'threshold': '年报盈利或PE<200', 'actual': f'ROE={roe},EPS={eps},PE={pe}',
                      'action': '剔除'})

    # 5. 经营现金流严重为负(cf2p<-2)且PE>100 — 现金流与盈利严重背离
    if cf2p is not None and cf2p < -2 and pe is not None and pe > 100:
        flags.append({'flag': '现金流严重背离盈利(cf2p<-2且PE>100)', 'severity': 'hard',
                      'threshold': 'cf2p>-2或PE<100', 'actual': f'cf2p={cf2p},PE={pe}',
                      'action': '剔除'})

    # ── SOFT WARNINGS (降权) ──
    # Debt ratio > 70% (skip banks)
    if not is_bank and debt_ratio is not None and debt_ratio > 70:
        flags.append({'flag': '资产负债率>70%', 'severity': 'soft',
                      'threshold': '<70%', 'actual': f'{debt_ratio:.1f}%',
                      'action': '降权'})

    # Cash flow / profit < 0.5
    if cf2p is not None and cf2p < 0.5:
        sev = 'soft' if cf2p >= 0 else 'hard'
        if cf2p < 0:
            flags.append({'flag': '经营现金流为负', 'severity': 'soft',
                          'threshold': '>0', 'actual': f'{cf2p}',
                          'action': '降权'})
        else:
            flags.append({'flag': '经营现金流/净利润<0.5', 'severity': 'soft',
                          'threshold': '>0.5', 'actual': f'{cf2p}',
                          'action': '降权'})

    # AR/revenue > 40% (if available)
    ar2r = sf(d.get('YSZKYYSR'))
    if ar2r is not None and ar2r > 0.4:
        flags.append({'flag': '应收账款/收入>40%', 'severity': 'soft',
                      'threshold': '<40%', 'actual': f'{ar2r*100:.1f}%',
                      'action': '降权'})

    # Non-recurring > 20%
    if non_recur is not None and non_recur > 20:
        flags.append({'flag': '非经常性损益占比>20%', 'severity': 'soft',
                      'threshold': '<20%', 'actual': f'{non_recur}%',
                      'action': '降权'})

    # Net profit decline > -10%
    if pg is not None and pg < -10:
        flags.append({'flag': '净利润大幅下滑', 'severity': 'soft',
                      'threshold': '>-10%', 'actual': f'{pg:.1f}%',
                      'action': '降权'})

    # Gross margin < 10% (skip banks — no gross margin)
    if not is_bank and gross_margin is not None and gross_margin < 10:
        flags.append({'flag': '毛利率<10%', 'severity': 'soft',
                      'threshold': '>10%', 'actual': f'{gross_margin:.1f}%',
                      'action': '降权'})

    # PE 100-200 with negative growth
    if pe is not None and 100 <= pe <= 200 and pg is not None and pg < 0:
        flags.append({'flag': 'PE偏高且利润负增长', 'severity': 'soft',
                      'threshold': 'PE<100或增速>0', 'actual': f'PE={pe},增速={pg}%',
                      'action': '降权'})

    result['redFlags'] = flags

    # Verdict
    has_hard = any(f['severity'] == 'hard' for f in flags)
    soft_count = sum(1 for f in flags if f['severity'] == 'soft')
    if has_hard:
        result['verdict'] = '剔除'
    elif soft_count >= 2:
        result['verdict'] = '降权'
    elif soft_count >= 1:
        result['verdict'] = '降权'
    else:
        result['verdict'] = '通过'

    # Summary
    flag_strs = []
    for f in flags:
        flag_strs.append(f"{f['flag']}({f['severity']})")
    flag_summary = '; '.join(flag_strs) if flag_strs else '无红旗'
    pe_str = f'PE={pe}' if pe else 'PE数据缺失'
    pb_str = f'PB={pb}' if pb else 'PB数据缺失'
    roe_str = f'ROE={roe}%' if roe is not None else 'ROE数据缺失'
    result['summary'] = f'{roe_str},{pe_str},{pb_str};{flag_summary}'

    return result


# ═══════════ MAIN ═══════════
print(f'Fundamentals analyst: {len(STOCKS)} stocks, asOf={ASOF}')

# 1. Batch tencent quote
codes = [s['code'] for s in STOCKS]
print(f'Fetching tencent quotes (batch)...')
tc_data = {}
# tencent can handle ~40 codes per request
for i in range(0, len(codes), 40):
    batch = codes[i:i+40]
    tc = tencent_quote_batch(batch)
    tc_data.update(tc)
    time.sleep(0.3)
print(f'  got {len(tc_data)} quotes')

# 2. Fetch financial data + goodwill for each
results = {}
for i, s in enumerate(STOCKS):
    code = s['code']
    name = s['name']
    sector = s.get('sector', '')
    print(f'[{i+1}/{len(STOCKS)}] {code} {name}', end=' ', flush=True)
    try:
        fin = get_fin(code)
        gw, eq = get_goodwill_equity(code)
        tc = tc_data.get(code, {})
        res = analyze(code, name, sector, tc, fin, gw, eq)
        results[code] = res
        print(f'-> {res["verdict"]} (flags:{len(res["redFlags"])})')
    except Exception as e:
        print(f'-> ERROR: {e}')
        results[code] = {
            'code': code, 'name': name, 'sector': sector,
            'financials': {}, 'valuation': {}, 'redFlags': [],
            'verdict': '数据缺失', 'summary': f'数据获取失败: {e}',
            'error': str(e)
        }
    time.sleep(0.15)

# 3. Categorize
passed = [r for r in results.values() if r['verdict'] == '通过']
warned = [r for r in results.values() if r['verdict'] == '降权']
rejected = [r for r in results.values() if r['verdict'] == '剔除']
missing = [r for r in results.values() if r['verdict'] == '数据缺失']

# Sort by verdict priority then by PE (low to high)
def sort_key(r):
    v_order = {'通过': 0, '降权': 1, '剔除': 2, '数据缺失': 3}
    pe = r.get('valuation', {}).get('peTtm')
    pe_sort = pe if (pe and pe > 0) else 9999
    return (v_order.get(r['verdict'], 9), pe_sort)

all_sorted = sorted(results.values(), key=sort_key)

summary_text = (
    f'基本面排雷完成: {len(STOCKS)}只→通过{len(passed)}/降权{len(warned)}/'
    f'剔除{len(rejected)}/数据缺失{len(missing)}。'
)
if rejected:
    rej_names = [f"{r['name']}({r['code']})" for r in rejected]
    summary_text += f'剔除: {", ".join(rej_names)}。'
if warned:
    warn_names = [f"{r['name']}({r['code']})" for r in warned]
    summary_text += f'降权: {", ".join(warn_names)}。'

# Data caveats
data_caveats = (
    '数据源: 腾讯qt.gtimg.cn(PE/价格/市值)+东财datacenter MAINFINADATA(ROE/负债率/'
    '毛利率/增速/BPS)+新浪资产负债表页(商誉/净资产)。MCP全SSL挂未用。'
    'PE/PB历史5年分位不可得(需历史估值数据)标记数据缺失。'
    '银行股(6只)跳过资产负债率/毛利率检查(行业特性)。'
    '商誉数据从新浪HTML解析,部分可能缺失。'
)

output = {
    'agent': 'fundamentals-analyst',
    'asOf': ASOF,
    'data': {
        'pass': [r for r in all_sorted if r['verdict'] == '通过'],
        'warn': [r for r in all_sorted if r['verdict'] == '降权'],
        'reject': [r for r in all_sorted if r['verdict'] == '剔除'],
        'missing': [r for r in all_sorted if r['verdict'] == '数据缺失'],
        'allSorted': all_sorted,
        'passCount': len(passed),
        'warnCount': len(warned),
        'rejectCount': len(rejected),
        'missingCount': len(missing),
        'totalCount': len(STOCKS),
        'summary': summary_text,
        'dataCaveats': data_caveats,
        'hardThresholds': {
            'pe200NoGrowth': 'PE>200且利润增速≤0 → 剔除',
            'loss': 'PE<0(TTM亏损) → 剔除',
            'goodwill': '商誉占净资产>30% → 剔除',
        },
        'softThresholds': {
            'debtRatio': '资产负债率>70% → 降权(银行除外)',
            'cashflow': '经营现金流/净利润<0.5 → 降权',
            'arRevenue': '应收账款/收入>40% → 降权',
            'nonRecurring': '非经常性损益/利润>20% → 降权',
            'profitDecline': '净利润下滑>10% → 降权',
            'grossMargin': '毛利率<10% → 降权(银行除外)',
        },
    }
}

os.makedirs(OUT_DIR, exist_ok=True)
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'\n{summary_text}')
print(f'Output: {OUT_FILE}')
print(f'通过={len(passed)} 降权={len(warned)} 剔除={len(rejected)} 数据缺失={len(missing)}')
