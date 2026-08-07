# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, r'E:\finacial-invest\scripts')
import astock_data as A

CODES = ["600378","300943","300131","688512","300420","688328","688593","300363"]
out = {}
for code in CODES:
    try:
        lrb = A.sina_financial_report(code, "lrb")
        if not lrb:
            out[code] = {"err": "no lrb"}
            continue
        # Extract revenue & net profit + growth from latest 2 periods
        periods = []
        for row in lrb[:4]:
            r = {}
            # sina keys vary; collect keys containing 营业/净利润/归属
            for k, v in row.items():
                kl = k.lower() if isinstance(k, str) else str(k)
                if any(t in str(k) for t in ['营业收入','营业总收入','净利润','归属','股东']):
                    r[k] = v
            periods.append(r)
        out[code] = {"periods_raw": periods, "report_dates": [row.get('报告期') or row.get('date') for row in lrb[:4]]}
    except Exception as e:
        out[code] = {"err": str(e)}

print(json.dumps(out, ensure_ascii=False, indent=2))
