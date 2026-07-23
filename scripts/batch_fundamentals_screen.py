#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Batch fundamentals screening for 40 candidate stocks.
Uses: tencent_quote (HTTP) + mootdx Affair (TCP 7709) — both bypass Whistle proxy.

Hard rejection criteria:
  - PE > 200 (pure speculation, no growth justification)
  - ST / *ST
  - Consecutive losses (net profit < 0 for latest 2 fiscal years)
  - Goodwill > 30% of net assets

Output: data/runs/20260723_short-term-picks/fundamentals.json
"""

import json
import os
import sys
import warnings
import time
from datetime import datetime

warnings.filterwarnings('ignore')

# Add project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts'))

# ─── Candidate pool ───
CANDIDATES = [
    '000533', '000603', '000688', '000815', '001208', '001337', '001382',
    '002083', '002112', '002197', '002229', '002240', '002298', '002300',
    '002379', '002396', '002412', '002498', '002879', '002900',
    '300062', '300407', '300444', '600173', '600379', '600487', '600550',
    '600666', '600962', '600980', '601061', '601179', '601678', '601991',
    '603318', '603399', '603956', '603988', '605100', '605189'
]

# ─── Column indices in Affair data (gpcw20251231.zip) ───
# These are the column positions from the 585-column DataFrame
COL_REPORT_DATE = 0
COL_ROE = 6              # 净资产收益率
COL_GOODWILL = 35        # 商誉
COL_TOTAL_ASSETS = 40    # 资产总计
COL_TOTAL_LIAB = 63      # 负债合计
COL_TOTAL_EQUITY = 72    # 所有者权益合计
COL_REVENUE = 74         # 营业收入
COL_COST_REVENUE = 75    # 营业成本
COL_NET_PROFIT = 95      # 净利润
COL_NET_PROFIT_PARENT = 96  # 归母净利润
COL_OP_CASHFLOW = 107    # 经营活动现金流量净额
COL_REVENUE_GROWTH = 183 # 营业收入增长率
COL_PROFIT_GROWTH = 184  # 净利润增长率
COL_ROA = 200            # 总资产收益率
COL_NET_MARGIN = 199     # 销售净利率
COL_GROSS_MARGIN = 202   # 销售毛利率
COL_DEBT_RATIO = 210     # 资产负债率
COL_ACCT_RECEIVABLE = 11 # 应收账款
COL_INVENTORY = 17       # 存货
COL_CURRENT_ASSETS = 21  # 流动资产合计
COL_CURRENT_LIAB = 54    # 流动负债合计
COL_NONCURRENT_LIAB = 62 # 非流动负债合计
COL_OP_CF_DUP = 234      # 经营活动现金流量净额(dup)
COL_NET_PROFIT_DUP = 232 # 归母净利润(dup)
COL_DILUTED_EPS = 501    # 稀释每股收益
COL_REVENUE_TTM = 502    # 营业收入TTM
COL_INTEREST_DEBT = 162  # 利息保障倍数

# Column names for easier access (fallback)
COL_NAMES_MAP = {
    'report_date': 0,
    'roe': 6,
    'goodwill': 35,
    'total_assets': 40,
    'total_liabilities': 63,
    'total_equity': 72,
    'revenue': 74,
    'cost_revenue': 75,
    'net_profit': 95,
    'net_profit_parent': 96,
    'op_cashflow': 107,
    'revenue_growth': 183,
    'profit_growth': 184,
    'roa': 197,
    'net_margin': 199,
    'gross_margin': 202,
    'debt_ratio': 210,
    'acct_receivable': 11,
    'inventory': 17,
}


def safe_float(val, default=None):
    """Safely convert value to float."""
    if val is None:
        return default
    try:
        f = float(val)
        if f != f:  # NaN check
            return default
        return f
    except (ValueError, TypeError):
        return default


def get_tencent_quotes(codes):
    """Batch get PE/PB/market cap from Tencent HTTP API."""
    from scripts.astock_data import tencent_quote

    # Build comma-separated code string with proper prefixes
    code_strs = []
    for c in codes:
        if c.startswith(('60', '68')):
            code_strs.append(f'sh{c}')
        else:
            code_strs.append(f'sz{c}')

    # Batch in groups of 50 to avoid URL too long
    all_results = {}
    batch_size = 50
    for i in range(0, len(code_strs), batch_size):
        batch = ','.join(code_strs[i:i+batch_size])
        results = tencent_quote(batch)
        all_results.update(results)
        if i + batch_size < len(code_strs):
            time.sleep(0.3)

    # Also get PB from raw tencent data (field 46)
    import requests
    import re

    pb_map = {}
    for i in range(0, len(code_strs), batch_size):
        batch = ','.join(code_strs[i:i+batch_size])
        url = f'http://qt.gtimg.cn/q={batch}'
        try:
            r = requests.get(url, timeout=10,
                           headers={'User-Agent': 'Mozilla/5.0'},
                           proxies={'http': None, 'https': None})
            raw = r.content.decode('gbk', errors='ignore')
            for m in re.finditer(r'v_(\w+)="([^"]*)"', raw):
                data = m.group(2).split('~')
                if len(data) > 46:
                    code = data[2]
                    pb = safe_float(data[46]) if len(data) > 46 else None
                    if pb is not None and code not in pb_map:
                        pb_map[code] = pb
        except Exception:
            pass
        if i + batch_size < len(code_strs):
            time.sleep(0.3)

    # Merge PB into results
    for code, data in all_results.items():
        if code in pb_map:
            data['pb'] = pb_map[code]
        else:
            data['pb'] = None

    return all_results


def get_financial_data(codes):
    """Get financial data from mootdx Affair for the latest annual report."""
    from mootdx.affair import Affair

    a = Affair()
    print('  Loading gpcw20251231.zip (annual report)...')
    df = a.parse(filename='gpcw20251231.zip')
    print(f'  Loaded {df.shape[0]} stocks, {df.shape[1]} columns')

    # Also load previous year for consecutive loss check
    print('  Loading gpcw20241231.zip (previous year)...')
    df_prev = a.parse(filename='gpcw20241231.zip')
    print(f'  Loaded {df_prev.shape[0]} stocks')

    results = {}
    for code in codes:
        if code not in df.index:
            print(f'  WARNING: {code} not found in financial data')
            results[code] = None
            continue

        row = df.loc[code]
        row_prev = df_prev.loc[code] if code in df_prev.index else None

        # Extract key metrics using column indices
        fin = {
            'report_date': safe_float(row.iloc[COL_REPORT_DATE]),
            'roe': safe_float(row.iloc[COL_ROE]),
            'goodwill': safe_float(row.iloc[COL_GOODWILL], 0),
            'total_assets': safe_float(row.iloc[COL_TOTAL_ASSETS]),
            'total_liabilities': safe_float(row.iloc[COL_TOTAL_LIAB]),
            'total_equity': safe_float(row.iloc[COL_TOTAL_EQUITY]),
            'revenue': safe_float(row.iloc[COL_REVENUE]),
            'cost_revenue': safe_float(row.iloc[COL_COST_REVENUE]),
            'net_profit': safe_float(row.iloc[COL_NET_PROFIT]),
            'net_profit_parent': safe_float(row.iloc[COL_NET_PROFIT_PARENT]),
            'op_cashflow': safe_float(row.iloc[COL_OP_CASHFLOW]),
            'revenue_growth': safe_float(row.iloc[COL_REVENUE_GROWTH]),
            'profit_growth': safe_float(row.iloc[COL_PROFIT_GROWTH]),
            'roa': safe_float(row.iloc[COL_ROA]),
            'net_margin': safe_float(row.iloc[COL_NET_MARGIN]),
            'gross_margin': safe_float(row.iloc[COL_GROSS_MARGIN]),
            'debt_ratio': safe_float(row.iloc[COL_DEBT_RATIO]),
            'acct_receivable': safe_float(row.iloc[COL_ACCT_RECEIVABLE], 0),
            'inventory': safe_float(row.iloc[COL_INVENTORY], 0),
            'current_assets': safe_float(row.iloc[COL_CURRENT_ASSETS]),
            'current_liabilities': safe_float(row.iloc[COL_CURRENT_LIAB]),
            'noncurrent_liabilities': safe_float(row.iloc[COL_NONCURRENT_LIAB]),
            'diluted_eps': safe_float(row.iloc[COL_DILUTED_EPS]),
            'revenue_ttm': safe_float(row.iloc[COL_REVENUE_TTM]),
        }

        # Previous year net profit for consecutive loss check
        if row_prev is not None:
            fin['prev_net_profit'] = safe_float(row_prev.iloc[COL_NET_PROFIT])
            fin['prev_net_profit_parent'] = safe_float(row_prev.iloc[COL_NET_PROFIT_PARENT])
        else:
            fin['prev_net_profit'] = None
            fin['prev_net_profit_parent'] = None

        # Derived metrics
        if fin['total_equity'] and fin['total_equity'] > 0:
            fin['goodwill_pct_equity'] = round(fin['goodwill'] / fin['total_equity'] * 100, 2)
        else:
            fin['goodwill_pct_equity'] = None

        if fin['net_profit'] and fin['op_cashflow']:
            fin['cashflow_ratio'] = round(fin['op_cashflow'] / abs(fin['net_profit']), 2)
        else:
            fin['cashflow_ratio'] = None

        # Free cash flow (operating CF - capex proxy)
        # Capex not directly available, skip for now

        results[code] = fin

    return results


def screen_stocks(quotes, financials):
    """Screen all candidates, return pass/reject lists."""
    pass_list = []
    reject_list = []

    for code in CANDIDATES:
        q = quotes.get(code, {})
        fin = financials.get(code)

        name = q.get('name', '')
        pe = q.get('pe')
        pb = q.get('pb')
        mktcap = q.get('mktcap')

        risk_flags = []

        # ─── Hard Rejection Checks ───

        # 1. ST / *ST
        if 'ST' in name or '*ST' in name:
            reject_list.append({
                'code': code,
                'name': name,
                'reason': f'ST标记: {name}',
                'riskFlags': ['ST/*ST']
            })
            continue

        # 2. PE > 200
        if pe is not None and pe > 200:
            # Check if there's profit growth justification
            profit_growth = fin.get('profit_growth') if fin else None
            if profit_growth is None or profit_growth < 100:
                reject_list.append({
                    'code': code,
                    'name': name,
                    'pe': pe,
                    'reason': f'PE={pe:.1f}>200且无高增速支撑(利润增速={profit_growth})',
                    'riskFlags': ['PE>200']
                })
                continue
            else:
                risk_flags.append({'flag': 'PE>200但高增速', 'severity': 'warning'})

        # 3. Consecutive losses
        if fin:
            np_current = fin.get('net_profit') or fin.get('net_profit_parent')
            np_prev = fin.get('prev_net_profit') or fin.get('prev_net_profit_parent')

            if np_current is not None and np_prev is not None:
                if np_current < 0 and np_prev < 0:
                    reject_list.append({
                        'code': code,
                        'name': name,
                        'reason': f'连续亏损: 本期净利润={np_current/1e8:.2f}亿, 上期={np_prev/1e8:.2f}亿',
                        'riskFlags': ['连续亏损']
                    })
                    continue
            if np_current is not None and np_current < 0:  # Single year loss - flag as warning (separate if, not elif)
                # Single year loss - flag as warning
                risk_flags.append({
                    'flag': '单年亏损',
                    'severity': 'warning',
                    'detail': f'本期净利润={np_current/1e8:.2f}亿'
                })

        # 4. Goodwill > 30% of net assets
        if fin:
            gwp = fin.get('goodwill_pct_equity')
            if gwp is not None and gwp > 30:
                reject_list.append({
                    'code': code,
                    'name': name,
                    'reason': f'商誉占净资产{gwp:.1f}%>30%: 商誉={fin["goodwill"]/1e8:.2f}亿, 净资产={fin["total_equity"]/1e8:.2f}亿',
                    'riskFlags': ['商誉>30%净资产']
                })
                continue
            elif gwp is not None and gwp > 20:
                risk_flags.append({
                    'flag': '商誉偏高',
                    'severity': 'warning',
                    'threshold': '>20%',
                    'actual': f'{gwp:.1f}%'
                })

        # ─── Soft Warning Checks ───

        # 5. Operating cash flow / net profit < 0.5
        if fin and fin.get('cashflow_ratio') is not None:
            cf_ratio = fin['cashflow_ratio']
            if cf_ratio < 0.5 and fin.get('net_profit', 0) > 0:
                risk_flags.append({
                    'flag': '经营现金流/净利润<0.5',
                    'severity': 'warning',
                    'threshold': '<0.5',
                    'actual': f'{cf_ratio:.2f}'
                })

        # 6. Operating cash flow negative
        if fin and fin.get('op_cashflow') is not None and fin['op_cashflow'] < 0:
            risk_flags.append({
                'flag': '经营现金流为负',
                'severity': 'warning',
                'actual': f'{fin["op_cashflow"]/1e8:.2f}亿'
            })

        # 7. High debt ratio (>70%)
        if fin and fin.get('debt_ratio') is not None:
            dr = fin['debt_ratio']
            if dr > 80:
                risk_flags.append({
                    'flag': '资产负债率>80%',
                    'severity': 'warning',
                    'threshold': '>80%',
                    'actual': f'{dr:.1f}%'
                })
            elif dr > 70:
                risk_flags.append({
                    'flag': '资产负债率>70%',
                    'severity': 'caution',
                    'threshold': '>70%',
                    'actual': f'{dr:.1f}%'
                })

        # ─── Build pass entry ───
        # Financial metrics
        fin_metrics = {}
        if fin:
            fin_metrics = {
                'roe': fin.get('roe'),
                'roa': fin.get('roa'),
                'revenue_growth': fin.get('revenue_growth'),
                'profit_growth': fin.get('profit_growth'),
                'gross_margin': fin.get('gross_margin'),
                'net_margin': fin.get('net_margin'),
                'debt_ratio': fin.get('debt_ratio'),
                'cashflow_ratio': fin.get('cashflow_ratio'),
                'goodwill_pct_equity': fin.get('goodwill_pct_equity'),
                'net_profit': fin.get('net_profit'),
                'revenue': fin.get('revenue'),
                'op_cashflow': fin.get('op_cashflow'),
                'total_assets': fin.get('total_assets'),
                'total_equity': fin.get('total_equity'),
                'goodwill': fin.get('goodwill'),
                'diluted_eps': fin.get('diluted_eps'),
            }

        pass_list.append({
            'code': code,
            'name': name,
            'pe': pe,
            'pb': pb,
            'mktcap': mktcap,
            'price': q.get('price'),
            'financials': fin_metrics,
            'riskFlags': risk_flags,
            'verdict': '降权' if len([r for r in risk_flags if r.get('severity') == 'warning']) > 0 else '通过'
        })

    return pass_list, reject_list


def compute_valuation_anchors(pass_list):
    """Add valuation anchors: PE/PB percentile estimates."""
    # Since we can't easily get 5-year history, we compute relative metrics
    # Sort by PE and PB to estimate percentile within the candidate pool
    pes = [(i, s['pe']) for i, s in enumerate(pass_list) if s.get('pe') is not None and s['pe'] > 0]
    pbs = [(i, s['pb']) for i, s in enumerate(pass_list) if s.get('pb') is not None and s['pb'] > 0]

    # Sort and assign pool percentile
    pes_sorted = sorted(pes, key=lambda x: x[1])
    pbs_sorted = sorted(pbs, key=lambda x: x[1])

    n_pe = len(pes_sorted)
    n_pb = len(pbs_sorted)

    for rank, (idx, _) in enumerate(pes_sorted):
        pct = round(rank / n_pe * 100, 1)
        pass_list[idx]['pe_pool_percentile'] = pct

    for rank, (idx, _) in enumerate(pbs_sorted):
        pct = round(rank / n_pb * 100, 1)
        pass_list[idx]['pb_pool_percentile'] = pct

    # Add valuation verdict
    for s in pass_list:
        pe = s.get('pe')
        pb = s.get('pb')
        pe_pct = s.get('pe_pool_percentile')

        if pe is None or pb is None:
            s['valuation_verdict'] = '数据缺失'
        elif pe_pct is not None and pe_pct < 30:
            s['valuation_verdict'] = '低估(<30%分位)'
        elif pe_pct is not None and pe_pct > 80:
            s['valuation_verdict'] = '高位(>80%分位)'
        else:
            s['valuation_verdict'] = '合理'


def main():
    print('=' * 60)
    print('  基本面批量排雷 — 40只候选标的')
    print(f'  运行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    # Step 1: Get quotes
    print('\n[1/3] 获取行情数据 (Tencent HTTP)...')
    quotes = get_tencent_quotes(CANDIDATES)
    print(f'  获取到 {len(quotes)} 只股票行情')

    # Step 2: Get financial data
    print('\n[2/3] 获取财务数据 (mootdx TCP)...')
    financials = get_financial_data(CANDIDATES)
    found = sum(1 for v in financials.values() if v is not None)
    print(f'  获取到 {found} 只股票财务数据')

    # Step 3: Screen
    print('\n[3/3] 执行排雷筛选...')
    pass_list, reject_list = screen_stocks(quotes, financials)

    # Add valuation anchors
    compute_valuation_anchors(pass_list)

    # ─── Output ───
    output_dir = os.path.join(PROJECT_ROOT, 'data', 'runs', '20260723_short-term-picks')
    os.makedirs(output_dir, exist_ok=True)

    output = {
        'agent': 'fundamentals-analyst',
        'asOf': '20260723',
        'generatedAt': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'dataSources': {
            'quotes': 'tencent_quote (qt.gtimg.cn HTTP)',
            'financials': 'mootdx Affair (gpcw20251231.zip + gpcw20241231.zip, TCP 7709)'
        },
        'data': {
            'pass': pass_list,
            'reject': reject_list,
            'summary': f'通过{len(pass_list)}只/排除{len(reject_list)}只',
            'hardRejectReasons': {
                'ST': sum(1 for r in reject_list if 'ST' in str(r.get('riskFlags', []))),
                'PE>200': sum(1 for r in reject_list if 'PE>200' in str(r.get('riskFlags', []))),
                '连续亏损': sum(1 for r in reject_list if '连续亏损' in str(r.get('riskFlags', []))),
                '商誉>30%净资产': sum(1 for r in reject_list if '商誉' in str(r.get('riskFlags', []))),
            }
        }
    }

    output_path = os.path.join(output_dir, 'fundamentals.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    # ─── Print Summary ───
    print('\n' + '=' * 60)
    print('  筛选结果摘要')
    print('=' * 60)
    print(f'  通过: {len(pass_list)} 只')
    print(f'  剔除: {len(reject_list)} 只')
    print()

    if reject_list:
        print('  🔴 剔除标的:')
        for r in reject_list:
            print(f'    {r["code"]} {r.get("name","")} — {r["reason"]}')
        print()

    # Show warnings
    warned = [p for p in pass_list if p.get('verdict') == '降权']
    if warned:
        print(f'  🟡 软警示标的 ({len(warned)}只):')
        for p in warned:
            flags = [f.get('flag', '') for f in p.get('riskFlags', [])]
            print(f'    {p["code"]} {p.get("name","")} — {", ".join(flags)}')
        print()

    clean = [p for p in pass_list if p.get('verdict') == '通过']
    print(f'  🟢 清洁通过 ({len(clean)}只):')
    for p in clean:
        pe = p.get('pe')
        pb = p.get('pb')
        roe = p.get('financials', {}).get('roe')
        print(f'    {p["code"]} {p.get("name",""):8s} PE={pe or "N/A":>8} PB={pb or "N/A":>6} ROE={roe or "N/A"}')

    print(f'\n  数据已落盘: {output_path}')
    return output


if __name__ == '__main__':
    main()
