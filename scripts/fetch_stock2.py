# -*- coding: utf-8 -*-
"""全志科技 300458 第二轮:新浪/同花顺源取数(绕开东财push2 502)"""
import sys, json, os
os.environ.setdefault('TQDM_DISABLE', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import warnings; warnings.filterwarnings('ignore')
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests
_o = requests.Session.request
def _p(self, *a, **k):
    k.setdefault('verify', False); return _o(self, *a, **k)
requests.Session.request = _p
import akshare as ak
import pandas as pd, numpy as np

OUT = r"E:\project\toolkit\output\_data_300458_v2.json"
CODE = "300458"; SZC = "sz300458"
data = {"code": CODE, "name": "全志科技"}

def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k,v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, (pd.Timestamp,)): return o.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if np.isnan(o) else float(o)
    if isinstance(o, float): return None if o != o else o
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

def safe(key, fn, *a, **k):
    try:
        df = fn(*a, **k)
        if df is None: data[key]=None; print(f"[FAIL] {key}: None"); dump(); return None
        recs = df.to_dict('records'); data[key] = recs
        print(f"[OK]   {key}: {len(recs)} rows x {len(df.columns)} cols"); dump(); return df
    except Exception as e:
        data[key] = {"_error": repr(e)[:300]}; print(f"[FAIL] {key}: {repr(e)[:120]}"); dump(); return None

print("=== fetch_stock2 sina/ths | ak", ak.__version__, "===")

# 1. 新浪日K(近2年,前复权) - 技术分析核心
safe("kline_daily", ak.stock_zh_a_daily, symbol=SZC, start_date="2024-07-01", end_date="2026-07-01", adjust="qfq")
# 1b. 长期日K(5年,估值分位/年线/月聚合源)
safe("kline_daily_5y", ak.stock_zh_a_daily, symbol=SZC, start_date="2021-07-01", end_date="2026-07-01", adjust="qfq")

# 2. 新浪全市场实时行情(过滤300458 -> PE/PB/市值/换手/实时价)
def get_spot():
    df = ak.stock_zh_a_spot()
    if df is None or df.empty: return df
    code_col = None
    for c in df.columns:
        if '代码' in str(c) or str(c).lower() in ('code','symbol'):
            code_col = c; break
    if code_col is None: code_col = df.columns[0]
    hits = df[df[code_col].astype(str).str.contains(CODE, na=False)]
    return hits
safe("spot", get_spot)

# 3. 北向(深股通)持股 - 多接口尝试
nb = None
for fn_name in ['stock_hsgt_hold_stock', 'stock_hk_hold']:
    fn = getattr(ak, fn_name, None)
    if not fn: continue
    try:
        if fn_name == 'stock_hsgt_hold_stock':
            df = fn(market="深股通")
            if df is not None and not df.empty:
                cc = [c for c in df.columns if '代码' in str(c) or str(c).lower() in ('code','symbol','股票代码')]
                if cc:
                    hits = df[df[cc[0]].astype(str).str.contains(CODE, na=False)]
                    if not hits.empty: nb = hits.to_dict('records')
        else:
            df = fn(symbol=SZC)
            if df is not None and not df.empty: nb = df.to_dict('records')
        if nb: data["northbound"] = nb; print(f"[OK]   northbound via {fn_name}: {len(nb)}"); break
    except Exception as e:
        print(f"[FAIL] northbound {fn_name}: {repr(e)[:80]}")
if not nb: data["northbound"] = {"_error": "all northbound attrs failed"}; print("[FAIL] northbound: all")
dump()

# 4. 概念板块(同花顺优先,东财兜底)
for fn_name in ['stock_board_concept_name_ths', 'stock_board_concept_name_em']:
    fn = getattr(ak, fn_name, None)
    if not fn: continue
    try:
        df = fn()
        if df is not None and not df.empty:
            data["concept_list"] = {"_via": fn_name, "rows": df.to_dict('records')}
            print(f"[OK]   concept_list via {fn_name}: {len(df)} rows"); break
    except Exception as e:
        print(f"[FAIL] concept_list {fn_name}: {repr(e)[:80]}")
dump()

# 5. 资金流(东财,重试,可能仍502)
try:
    safe("fund_flow", ak.stock_individual_fund_flow, stock=CODE, market="sz")
except Exception as e:
    data["fund_flow"] = {"_error": repr(e)[:200]}; dump()

# 6. 股东户数(东财datacenter,重试)
try:
    safe("gdhs", ak.stock_zh_a_gdhs, symbol=CODE)
except Exception as e:
    data["gdhs"] = {"_error": repr(e)[:200]}; dump()

# 7. 个股信息(东财,重试,可能仍空)
try:
    safe("info_em", ak.stock_individual_info_em, symbol=CODE)
except Exception as e:
    data["info_em"] = {"_error": repr(e)[:200]}; dump()

print("=== fetch_stock2 done ===")
