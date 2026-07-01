# -*- coding: utf-8 -*-
"""宏观 + 市场情绪数据采集 - akshare 免密钥源"""
import sys, json, os
os.environ.setdefault('TQDM_DISABLE', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import warnings; warnings.filterwarnings('ignore')
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests
_orig_req = requests.Session.request
def _patched_req(self, *a, **k):
    k.setdefault('verify', False)
    return _orig_req(self, *a, **k)
requests.Session.request = _patched_req

import akshare as ak
import pandas as pd
import numpy as np

OUT = r"E:\project\toolkit\output\_data_market.json"
data = {}

def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k,v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, (pd.Timestamp,)): return o.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, float):
        return None if o != o else o
    if isinstance(o, np.bool_): return bool(o)
    if isinstance(o, str): return o
    try:
        if pd.isna(o): return None
    except Exception:
        pass
    return o

def dump():
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean(data), f, ensure_ascii=False, default=str, indent=1)
    os.replace(tmp, OUT)

def safe(key, fn, *a, **kw):
    try:
        df = fn(*a, **kw)
        if df is None:
            data[key]=None; print(f"[FAIL] {key}: None"); dump(); return None
        recs = df.to_dict('records')
        data[key] = recs
        print(f"[OK]   {key}: {len(recs)} rows x {len(df.columns)} cols")
        dump(); return df
    except Exception as e:
        data[key] = {"_error": repr(e)[:300]}
        print(f"[FAIL] {key}: {repr(e)[:120]}"); dump(); return None

def safe_tail(key, fn, n=18, *a, **kw):
    """取最近 n 期"""
    try:
        df = fn(*a, **kw)
        if df is None:
            data[key]=None; print(f"[FAIL] {key}: None"); dump(); return None
        df2 = df.tail(n)
        data[key] = df2.to_dict('records')
        print(f"[OK]   {key}: tail{n} of {len(df)} -> {len(df2)} rows")
        dump(); return df
    except Exception as e:
        data[key] = {"_error": repr(e)[:300]}
        print(f"[FAIL] {key}: {repr(e)[:120]}"); dump(); return None

print("=== macro & market | akshare", ak.__version__, "===")

# ===== 宏观 =====
safe_tail("gdp", ak.macro_china_gdp, n=12)
safe_tail("pmi", ak.macro_china_pmi, n=18)
_pmi_non = getattr(ak, "macro_china_non_pmi", None)
if _pmi_non is not None:
    safe_tail("pmi_non", _pmi_non, n=18)
else:
    data["pmi_non"] = {"_error": "attr missing in this akshare version"}
    print("[SKIP] pmi_non: attr missing"); dump()
safe_tail("cpi", ak.macro_china_cpi, n=18)
safe_tail("ppi", ak.macro_china_ppi, n=18)
safe_tail("money_supply", ak.macro_china_money_supply, n=18)
safe_tail("shrzgm", ak.macro_china_shrzgm, n=18)  # 社融
safe_tail("lpr", ak.macro_china_lpr, n=18)
safe_tail("bond_yield10y", ak.bond_china_yield, n=120, start_date="20250101", end_date="20260701")
safe_tail("usd_cny", ak.currency_boc_sina, n=60, symbol="美元", start_date="20250101", end_date="20260701")

# ===== 市场情绪 / 涨跌停 / 资金 =====
for d in ["20260630","20260701","20260629","20260626"]:
    try:
        zt = ak.stock_zt_pool_em(date=d)
        if zt is not None and not zt.empty:
            data["zt_pool"] = zt.to_dict('records'); data["zt_pool_date"]=d
            print(f"[OK]   zt_pool@{d}: {len(zt)} rows"); dump(); break
        else:
            print(f"[INFO] zt_pool@{d}: empty, try next")
    except Exception as e:
        print(f"[FAIL] zt_pool@{d}: {repr(e)[:80]}")

for d in ["20260630","20260701","20260629","20260626"]:
    try:
        dt = ak.stock_zt_pool_dt_em(date=d)
        if dt is not None and not dt.empty:
            data["dt_pool"] = dt.to_dict('records'); data["dt_pool_date"]=d
            print(f"[OK]   dt_pool@{d}: {len(dt)} rows"); dump(); break
    except Exception as e:
        print(f"[FAIL] dt_pool@{d}: {repr(e)[:80]}")

safe("market_fund_flow", ak.stock_market_fund_flow)
try:
    safe("market_activity", ak.stock_market_activity_legu)
except Exception as e:
    data["market_activity"]={"_error":repr(e)[:200]}; dump()

# 概念板块涨幅榜(若 fetch_stock 未跑,此处兜底)
safe("concept_list", ak.stock_board_concept_name_em)

print("=== fetch_market done ===")
