#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json, sys, warnings, os, re
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import astock_data as A

CANDS = ['603986','002049','300223','002126','002747',
         '600027','600886','600025','601985','600089',
         '002471','601611','002879','601799','300496']

out = {}
for c in CANDS:
    rows = A.sina_financial_report(c, 'lrb')
    out[c] = rows[:4] if rows else []
print(json.dumps(out, ensure_ascii=False, default=str))
