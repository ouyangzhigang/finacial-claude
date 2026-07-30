#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fundamentals analyst batch (20260729, 28-stock pass list):
financial health + valuation anchor + red flags.
Input: technical-liquidity.json data.pass (28 stocks) + sector-analyst.json (sector/source).
Data: tencent_quote (PE/price/mktcap) + eastmoney MAINFINADATA (financials) + sina BS (goodwill/equity).
No MCP used (本机 SSL 全挂). Output flat schema: passed/downgraded/vetoed/all arrays.
"""
import sys, os, json, re, time, requests, urllib3
urllib3.disable_warnings()

PROXY = {'http': None, 'https': None}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Shared session: trust_env=False to bypass Whistle proxy (Windows env HTTP_PROXY)
SESSION = requests.Session()
SESSION.trust_env = False
SESSION.headers.update(HEADERS)

ASOF = '20260729'
OUT_DIR = f'E:/finacial-invest/data/runs/{ASOF}_short-term-picks'
OUT_FILE = os.path.join(OUT_DIR, 'fundamentals-analyst.json')
TL_FILE = os.path.join(OUT_DIR, 'technical-liquidity.json')
SA_FILE = os.path.join(OUT_DIR, 'sector-analyst.json')

with open(TL_FILE, 'r', encoding='utf-8') as f:
    tl = json.load(f)
PASS_STOCKS = tl['data']['pass']
FACTORS_BY_CODE = {f['code']: f for f in tl['data'].get('factors', [])}

# sector / source from sector-analyst
SECTOR_BY_CODE = {}
try:
    with open(SA_FILE, 'r', encoding='utf-8') as f:
        sa = json.load(f)
    for c in sa['data'].get('candidates', []):
        SECTOR_BY_CODE[c['code']] = {'sector': c.get('sector', ''), 'source': c.get('source', '')}
except Exception as e:
    print(f'[WARN] sector-analyst load: {e}', file=sys.stderr)

STOCKS = []
for s in PASS_STOCKS:
    sec_info = SECTOR_BY_CODE.get(s['code'], {})
    STOCKS.append({'code': s['code'], 'name': s['name'], 'price': s['price'],
                   'mktcap': s.get('marketCap'), 'sector': sec_info.get('sector', ''),
                   'source': sec_info.get('source', '')})

BANK_CODES = set()

def derive_role(sector, source):
    s = (sector or '')
    if '上游资源' in s or '资源' in s:
        return '上游资源/周期'
    if '国企改革' in s or '央国企' in s:
        return '央国企价值重估'
    if '半年报预增' in s or '业绩' in s:
        return '业绩驱动/半年报预增'
    if any(k in s for k in ['锂', '盐湖', '能源金属', '金属']):
        return '上游资源/周期'
    return '其他'

def tc_sym(code):
    # pass list codes already carry sh/sz prefix (e.g. 'sh600028') — pass through
    if code.startswith(('sh', 'sz', 'bj')):
        return code
    return f'sh{code}' if code.startswith(('6', '9')) else f'sz{code}'

def bare_code(code):
    return code[2:] if code.startswith(('sh', 'sz', 'bj')) else code


def sh_secu(code):
    c = bare_code(code)
    return f'{c}.SH' if c.startswith('6') else f'{c}.SZ'

def sf(v, default=None):
    if v is None or v == '':
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default

def tencent_quote_batch(codes):
    # map bare numeric code (from tencent response field 2) -> original prefixed code
    bare_to_code = {}
    syms = []
    for c in codes:
        bare = c[2:] if c.startswith(('sh', 'sz', 'bj')) else c
        bare_to_code.setdefault(bare, c)
        syms.append(tc_sym(c))
    url = f'http://qt.gtimg.cn/q={",".join(syms)}'
    out = {}
    try:
        r = SESSION.get(url, timeout=20)
        raw = r.content.decode('gbk', errors='ignore')
        for m in re.finditer(r'v_(\w+)="([^"]*)"', raw):
            data = m.group(2).split('~')
            if len(data) < 50:
                continue
            bare = data[2]
            key = bare_to_code.get(bare, bare)
            out[key] = {
                'name': data[1],
                'price': float(data[3]) if data[3] else 0,
                'pe': float(data[39]) if len(data) > 39 and data[39] else None,
                'mktcap': float(data[45]) if len(data) > 45 and data[45] else None,
                'float_mktcap': float(data[44]) if len(data) > 44 and data[44] else None,
            }
    except Exception as e:
        print(f'  [tencent_quote] ERR: {e}', file=sys.stderr)
    return out

def get_fin(code):
    secu = sh_secu(code)
    url = (f'https://datacenter.eastmoney.com/securities/api/data/get'
           f'?type=RPT_F10_FINANCE_MAINFINADATA&sty=APP_F10_MAINFINADATA'
           f'&filter=(SECUCODE=%22{secu}%22)&p=1&ps=12&sr=-1&st=REPORT_DATE'
           f'&source=HSF10&client=PC')
    try:
        r = SESSION.get(url, verify=False, timeout=15)
        if r.status_code != 200:
            return None
        d = r.json()
        if d.get('result') and d['result'].get('data'):
            return d['result']['data']
    except Exception:
        pass
    return None

def get_goodwill_equity(code):
    try:
        url = f'https://money.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/{bare_code(code)}/ctrl/2025/displaytype/4.phtml'
        r = SESSION.get(url, verify=False, timeout=15)
        r.encoding = 'gbk'
        html = r.text
        gw = None
        pos = html.find('商誉')
        if pos > 0:
            snippet = html[pos:pos + 500]
            clean = re.sub(r'<[^>]+>', ' ', snippet)
            nums = re.findall(r'[\d,]+\.?\d*', clean)
            if nums:
                try:
                    gw = float(nums[0].replace(',', ''))
                except Exception:
                    pass
        eq = None
        for kw in ['归属于母公司股东权益合计', '归属于母公司所有者权益合计', '股东权益合计']:
            pos = html.find(kw)
            if pos > 0:
                snippet = html[pos:pos + 500]
                clean = re.sub(r'<[^>]+>', ' ', snippet)
                nums = re.findall(r'[\d,]+\.?\d*', clean)
                if nums:
                    try:
                        eq = float(nums[0].replace(',', ''))
                    except Exception:
                        pass
                if eq:
                    break
        return gw, eq
    except Exception:
        return None, None


def analyze(code, name, sector, source, tc, fin_list, gw_wan, eq_wan):
    is_bank = code in BANK_CODES

    pe = tc.get('pe') if tc else None
    price = tc.get('price') if tc else None
    total_mcap_yi = tc.get('mktcap') if tc else None
    circ_mcap_yi = tc.get('float_mktcap') if tc else None

    annual = None
    latest = None
    if fin_list:
        for row in fin_list:
            rd = str(row.get('REPORT_DATE', ''))[:10]
            if rd.endswith('-12-31') and annual is None:
                annual = row
            if latest is None:
                latest = row
        if not annual:
            annual = latest

    d = annual or latest or {}
    report_date = str(d.get('REPORT_DATE', ''))[:10]
    report_type = '年报' if report_date.endswith('-12-31') else ('一季报' if report_date.endswith('-03-31') else ('半年报' if report_date.endswith('-06-30') else ('三季报' if report_date.endswith('-09-30') else '其他')))

    roe = sf(d.get('ROEJQ'))
    debt_ratio = sf(d.get('ZCFZL'))
    gross_margin = sf(d.get('XSMLL'))
    net_margin = sf(d.get('XSJLL'))
    bps = sf(d.get('BPS'))
    np_yuan = sf(d.get('PARENTNETPROFIT'))
    ded = sf(d.get('KCFJCXSYJLR'))
    pg = sf(d.get('PARENTNETPROFITTZ'))
    rg = sf(d.get('TOTALOPERATEREVETZ'))
    cfps = sf(d.get('MGJYXJJE'))
    eps = sf(d.get('EPSJB'))
    roic = sf(d.get('ROIC'))

    roe_trend = '数据缺失(单期)'
    if fin_list:
        annuals = [r for r in fin_list if str(r.get('REPORT_DATE', ''))[:10].endswith('-12-31')]
        if len(annuals) >= 2:
            r0 = sf(annuals[0].get('ROEJQ'))
            r1 = sf(annuals[1].get('ROEJQ'))
            if r0 is not None and r1 is not None:
                roe_trend = '上升' if r0 > r1 else ('下降' if r0 < r1 else '持平')

    cf2p = None
    if cfps is not None and eps is not None and eps != 0:
        cf2p = round(cfps / eps, 2)

    pb = None
    if price and bps and bps > 0:
        pb = round(price / bps, 2)

    non_recur = None
    if np_yuan is not None and ded is not None and np_yuan != 0:
        non_recur = round(abs(np_yuan - ded) / abs(np_yuan) * 100, 1)

    gw_yi = round(gw_wan / 10000.0, 4) if gw_wan is not None else None
    gw2eq = None
    if gw_wan is not None and eq_wan is not None and eq_wan > 0:
        gw2eq = round(gw_wan / eq_wan * 100, 2)

    flags = []

    # HARD (一票否决)
    if pe is not None and pe < 0:
        flags.append({'flag': 'TTM亏损', 'severity': 'hard',
                      'threshold': 'PE>0', 'actual': f'PE={pe}',
                      'action': '剔除'})
    if pe is not None and pe > 200:
        if pg is None or pg <= 0:
            flags.append({'flag': 'PE>200且无利润增速', 'severity': 'hard',
                          'threshold': 'PE>200需增速>0', 'actual': f'PE={pe},增速={pg}%',
                          'action': '剔除'})
    if gw2eq is not None and gw2eq > 30:
        flags.append({'flag': '商誉占净资产>30%', 'severity': 'hard',
                      'threshold': '<30%(>40%直接剔除)', 'actual': f'{gw2eq}%',
                      'action': '剔除'})
    annual_loss = (roe is not None and roe < 0) or (eps is not None and eps < 0)
    if annual_loss and pe is not None and pe > 200:
        flags.append({'flag': '年报亏损且PE>200(TTM微利靠非经常性)', 'severity': 'hard',
                      'threshold': '年报盈利或PE<200', 'actual': f'ROE={roe},EPS={eps},PE={pe}',
                      'action': '剔除'})
    if cf2p is not None and cf2p < -2 and pe is not None and pe > 100:
        flags.append({'flag': '现金流严重背离盈利(cf2p<-2且PE>100)', 'severity': 'hard',
                      'threshold': 'cf2p>-2或PE<100', 'actual': f'cf2p={cf2p},PE={pe}',
                      'action': '剔除'})

    # SOFT (降权)
    if not is_bank and debt_ratio is not None and debt_ratio > 70:
        flags.append({'flag': '资产负债率>70%', 'severity': 'soft',
                      'threshold': '<70%', 'actual': f'{debt_ratio:.1f}%', 'action': '降权'})
    if cf2p is not None:
        if cf2p < 0:
            flags.append({'flag': '经营现金流为负', 'severity': 'soft',
                          'threshold': '>0', 'actual': f'{cf2p}', 'action': '降权'})
        elif cf2p < 0.5:
            flags.append({'flag': '经营现金流/净利润<0.5', 'severity': 'soft',
                          'threshold': '>0.5', 'actual': f'{cf2p}', 'action': '降权'})
    ar2r = sf(d.get('YSZKYYSR'))
    if ar2r is not None and ar2r > 0.4:
        flags.append({'flag': '应收账款/收入>40%', 'severity': 'soft',
                      'threshold': '<40%', 'actual': f'{ar2r * 100:.1f}%', 'action': '降权'})
    if non_recur is not None and non_recur > 20:
        flags.append({'flag': '非经常性损益占比>20%', 'severity': 'soft',
                      'threshold': '<20%', 'actual': f'{non_recur}%', 'action': '降权'})
    if pg is not None and pg < -10:
        flags.append({'flag': '净利润大幅下滑', 'severity': 'soft',
                      'threshold': '>-10%', 'actual': f'{pg:.1f}%', 'action': '降权'})
    if not is_bank and gross_margin is not None and gross_margin < 10:
        flags.append({'flag': '毛利率<10%', 'severity': 'soft',
                      'threshold': '>10%', 'actual': f'{gross_margin:.1f}%', 'action': '降权'})
    if pe is not None and 100 <= pe <= 200 and pg is not None and pg < 0:
        flags.append({'flag': 'PE偏高且利润负增长', 'severity': 'soft',
                      'threshold': 'PE<100或增速>0', 'actual': f'PE={pe},增速={pg}%',
                      'action': '降权'})

    has_hard = any(f['severity'] == 'hard' for f in flags)
    soft_count = sum(1 for f in flags if f['severity'] == 'soft')
    if has_hard:
        verdict = '剔除'
    elif soft_count >= 1:
        verdict = '降权'
    else:
        verdict = '通过'

    if pe is None:
        val_v = '数据缺失'
    elif pe < 0:
        val_v = '亏损无法估值'
    elif pe <= 20:
        val_v = '低估'
    elif pe <= 40:
        val_v = '合理'
    elif pe <= 80:
        val_v = '偏高'
    elif pe <= 200:
        val_v = '高估'
    else:
        val_v = '严重高估'

    f_ = FACTORS_BY_CODE.get(code, {})
    m5 = f_.get('m5')
    m20 = f_.get('m20')
    entry_type = f_.get('entryType')
    exh = f_.get('exhaustionProb')
    tech_level = f_.get('technicalLevel')
    ctx_parts = []
    if entry_type:
        ctx_parts.append(f'入场类型:{entry_type}')
    if exh is not None:
        ctx_parts.append(f'透支概率{exh}%')
    if tech_level:
        ctx_parts.append(f'技术位:{tech_level}')
    if m5 is not None:
        ctx_parts.append(f'm5={m5}%')
    if m20 is not None:
        ctx_parts.append(f'm20={m20}%')
    val_adj = 0
    if m20 is not None and m5 is not None and m20 > 20 and m5 < 0:
        ctx_parts.append('高位回调票(近20日涨>20%且近5日转负):估值维再-5')
        val_adj = -5
    m10 = f_.get('m10')
    if any(v is not None and v > 30 for v in (m5, m10, m20)):
        ctx_parts.append('短期透支(近5/10/20日任一>30%):估值维不再加分')
    override_context = '; '.join(ctx_parts) if ctx_parts else '无'

    item = {
        'code': code, 'name': name, 'sector': sector, 'source': source,
        'role': derive_role(sector, source),
        'price': price,
        'roe': roe,
        'roeTrend': roe_trend,
        'peTtm': pe,
        'pb': pb,
        'totalMcapYi': total_mcap_yi,
        'circMcapYi': circ_mcap_yi,
        'reportDate': report_date,
        'reportType': report_type,
        'netProfitYi': round(np_yuan / 1e8, 2) if np_yuan is not None else None,
        'revenueGrowthPct': rg,
        'netProfitGrowthPct': pg,
        'netMarginPct': net_margin,
        'grossMarginPct': gross_margin,
        'debtRatioPct': debt_ratio,
        'roic': roic,
        'eps': eps,
        'bps': bps,
        'cashflowPerShare': cfps,
        'cashflowRatio': cf2p,
        'nonRecurRatio': non_recur,
        'goodwillYi': gw_yi,
        'goodwillRatioPct': gw2eq,
        'redFlags': flags,
        'overrideContext': override_context,
        'valuationAdj': val_adj,
        'verdict': verdict,
        'valuationVerdict': val_v,
    }
    flag_strs = '; '.join(f"{f['flag']}({f['severity']})" for f in flags) or '无红旗'
    pe_s = f'PE={pe}' if pe is not None else 'PE数据缺失'
    pb_s = f'PB={pb}' if pb is not None else 'PB数据缺失'
    roe_s = f'ROE={roe}%' if roe is not None else 'ROE数据缺失'
    item['summary'] = f'{name}({code}): {roe_s},{pe_s},{pb_s};{flag_strs}'
    return item


# MAIN
print(f'Fundamentals analyst: {len(STOCKS)} stocks, asOf={ASOF}', flush=True)

codes = [s['code'] for s in STOCKS]
print('Fetching tencent quotes (batch)...', flush=True)
tc_data = {}
for i in range(0, len(codes), 40):
    batch = codes[i:i + 40]
    tc_data.update(tencent_quote_batch(batch))
    time.sleep(0.3)
print(f'  got {len(tc_data)} quotes', flush=True)

results = []
for i, s in enumerate(STOCKS):
    code = s['code']
    name = s['name']
    sector = s.get('sector', '')
    source = s.get('source', '')
    print(f'[{i + 1}/{len(STOCKS)}] {code} {name}', end=' ', flush=True)
    try:
        fin = get_fin(code)
        gw, eq = get_goodwill_equity(code)
        tc = tc_data.get(code, {})
        res = analyze(code, name, sector, source, tc, fin, gw, eq)
        results.append(res)
        print(f'-> {res["verdict"]} (flags:{len(res["redFlags"])})', flush=True)
    except Exception as e:
        print(f'-> ERROR: {e}', flush=True)
        results.append({
            'code': code, 'name': name, 'sector': sector, 'source': source,
            'role': derive_role(sector, source),
            'price': s.get('price'), 'roe': None, 'roeTrend': '数据缺失(获取失败)',
            'peTtm': None, 'pb': None, 'totalMcapYi': s.get('mktcap'), 'circMcapYi': None,
            'reportDate': '', 'reportType': '', 'netProfitYi': None,
            'revenueGrowthPct': None, 'netProfitGrowthPct': None, 'netMarginPct': None,
            'grossMarginPct': None, 'debtRatioPct': None, 'roic': None, 'eps': None, 'bps': None,
            'cashflowPerShare': None, 'cashflowRatio': None, 'nonRecurRatio': None,
            'goodwillYi': None, 'goodwillRatioPct': None, 'redFlags': [],
            'overrideContext': '数据获取失败', 'valuationAdj': 0,
            'verdict': '数据缺失', 'valuationVerdict': '数据缺失',
            'summary': f'{name}({code}): 数据获取失败:{e}',
        })
    time.sleep(0.15)

passed = [r for r in results if r['verdict'] == '通过']
downgraded = [r for r in results if r['verdict'] == '降权']
vetoed = [r for r in results if r['verdict'] == '剔除']
missing = [r for r in results if r['verdict'] == '数据缺失']

def sort_key(r):
    v_order = {'通过': 0, '降权': 1, '剔除': 2, '数据缺失': 3}
    pe = r.get('peTtm')
    pe_sort = pe if (pe and pe > 0) else 9999
    return (v_order.get(r['verdict'], 9), pe_sort)

all_sorted = sorted(results, key=sort_key)

summary_text = (
    f'基本面排雷完成: {len(STOCKS)}只→通过{len(passed)}/降权{len(downgraded)}/'
    f'剔除{len(vetoed)}/数据缺失{len(missing)}。'
)
if vetoed:
    summary_text += '硬雷剔除: ' + ', '.join(f"{r['name']}({r['code']})" for r in vetoed) + '。'
if downgraded:
    summary_text += '软警示降权: ' + ', '.join(f"{r['name']}({r['code']})" for r in downgraded) + '。'
if missing:
    summary_text += '数据缺失: ' + ', '.join(f"{r['name']}({r['code']})" for r in missing) + '。'

data_caveats = (
    '数据源: 腾讯qt.gtimg.cn(PE/价格/市值)+东财datacenter MAINFINADATA(ROE/负债率/'
    '毛利率/增速/BPS/每股现金流)+新浪资产负债表页(商誉/净资产)。MCP全SSL挂未用。'
    'PE/PB历史5年分位不可得(需历史估值时序)标记数据缺失,估值锚以绝对PE分层代替。'
    '商誉数据从新浪HTML解析(单位万元,转亿元),部分个股可能缺失。'
    '年报口径优先(REPORT_DATE以-12-31结尾,2025年报),无则取最新一期。'
    '行情为2026-07-30盘中,盘中价不作买入依据;基本面为底线排雷,硬雷点一票否决不作调和。'
)

output = {
    'agent': 'fundamentals-analyst',
    'asOf': ASOF,
    'data': {
        'summary': summary_text,
        'passed': passed,
        'downgraded': downgraded,
        'vetoed': vetoed,
        'all': all_sorted,
        'passCount': len(passed),
        'downgradeCount': len(downgraded),
        'vetoCount': len(vetoed),
        'missingCount': len(missing),
        'totalCount': len(STOCKS),
        'dataCaveats': data_caveats,
        'hardThresholds': {
            'pe200NoGrowth': 'PE>200且利润增速≤0 → 剔除',
            'loss': 'PE<0(TTM亏损) → 剔除',
            'goodwill': '商誉占净资产>30% → 剔除(>40%直接剔除)',
            'annualLossHighPE': '年报亏损(ROE/EPS<0)且PE>200 → 剔除',
            'cashflowDivergence': '经营现金流/净利润<-2且PE>100 → 剔除',
        },
        'softThresholds': {
            'debtRatio': '资产负债率>70% → 降权(银行除外)',
            'cashflow': '经营现金流/净利润<0.5 或 <0 → 降权',
            'arRevenue': '应收账款/收入>40% → 降权',
            'nonRecurring': '非经常性损益/利润>20% → 降权',
            'profitDecline': '净利润下滑>10% → 降权',
            'grossMargin': '毛利率<10% → 降权(银行除外)',
            'pe100to200Neg': 'PE 100-200且利润负增长 → 降权',
        },
    }
}

os.makedirs(OUT_DIR, exist_ok=True)
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'\n{summary_text}', flush=True)
print(f'Output: {OUT_FILE}', flush=True)
print(f'通过={len(passed)} 降权={len(downgraded)} 剔除={len(vetoed)} 数据缺失={len(missing)}', flush=True)
