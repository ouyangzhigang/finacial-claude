#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json, sys, warnings, os
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import astock_data as A

CANDS = ['603986','002049','300223','002126','002747',
         '600027','600886','600025','601985','600089',
         '002471','601611','002879','601799','300496','600406','601968','600550']

out = {}
for c in CANDS:
    r = A.eastmoney_datacenter('RPT_LICO_FN_CPD',
        filter_str=f'(SECURITY_CODE="{c}")', page_size=8,
        sort_columns='REPORTDATE', sort_types='-1')
    rows = []
    for x in r:
        rows.append({
            'date': x.get('REPORTDATE'),
            'rev_yi': round(float(x.get('TOTAL_OPERATE_INCOME') or 0)/1e8,2),
            'rev_yoy': x.get('YSTZ'),
            'np_yi': round(float(x.get('PARENT_NETPROFIT') or 0)/1e8,2),
            'np_yoy': x.get('SJLTZ'),
            'roe': x.get('WEIGHTAVG_ROE'),
            'ocf_ps': x.get('MGJYXJJE'),
            'gm': x.get('XSMLL'),
        })
    out[c] = rows
print(json.dumps(out, ensure_ascii=False, default=str))
