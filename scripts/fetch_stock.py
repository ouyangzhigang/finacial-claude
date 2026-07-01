# -*- coding: utf-8 -*-
"""全志科技 300458 全维度数据采集 - akshare 免密钥源"""
import sys, json, os, traceback
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

OUT = r"E:\project\toolkit\output\_data_300458.json"
CODE = "300458"
SZ = "sz"  # 深圳创业板

data = {"code": CODE, "name": "全志科技"}

def clean(o):
    """递归清洗 NaN/Timestamp/Decimal 为 JSON 安全类型"""
    if isinstance(o, dict): return {k: clean(v) for k,v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, (pd.Timestamp,)): return o.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)):
        if np.isnan(o): return None
        return float(o)
    if isinstance(o, float):
        if o != o: return None  # NaN
        return o
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
            data[key] = None; print(f"[FAIL] {key}: None returned"); dump(); return None
        recs = df.to_dict('records')
        data[key] = recs
        print(f"[OK]   {key}: {len(recs)} rows x {len(df.columns)} cols")
        dump()
        return df
    except Exception as e:
        data[key] = {"_error": repr(e)[:300]}
        print(f"[FAIL] {key}: {repr(e)[:120]}")
        dump()
        return None

print("=== akshare", ak.__version__, "|", CODE, "===")

# ===== Section A: 公司信息 + 实时盘口 =====
safe("info_em", ak.stock_individual_info_em, symbol=CODE)
safe("bid_ask", ak.stock_bid_ask_em, symbol=CODE)

# ===== Section B: 历史K线 日/周/月 (前复权) =====
safe("kline_daily", ak.stock_zh_a_hist, symbol=CODE, period="daily",
     start_date="20240701", end_date="20260701", adjust="qfq")
safe("kline_weekly", ak.stock_zh_a_hist, symbol=CODE, period="weekly",
     start_date="20240101", end_date="20260701", adjust="qfq")
safe("kline_monthly", ak.stock_zh_a_hist, symbol=CODE, period="monthly",
     start_date="20200101", end_date="20260701", adjust="qfq")
# 长期日线(用于5年估值分位/年线) - 不复权看真实除权,用前复权算收益
safe("kline_daily_5y", ak.stock_zh_a_hist, symbol=CODE, period="daily",
     start_date="20210701", end_date="20260701", adjust="qfq")

# ===== Section C: 财务 =====
safe("fin_indicator", ak.stock_financial_analysis_indicator, symbol=CODE, start_year="2020")
safe("fin_abstract", ak.stock_financial_abstract, symbol=CODE)
try:
    safe("fin_abstract_ths", ak.stock_financial_abstract_ths, symbol=CODE, indicator="按报告期")
except Exception as e:
    data["fin_abstract_ths"] = {"_error": repr(e)[:200]}; dump()

# ===== Section D: 资金 / 筹码 / 北向 =====
safe("fund_flow", ak.stock_individual_fund_flow, stock=CODE, market=SZ)
try:
    safe("hsgt_individual", ak.stock_hsgt_individual_em, symbol=CODE)
except Exception as e:
    data["hsgt_individual"] = {"_error": repr(e)[:200]}; dump()
safe("gdhs", ak.stock_zh_a_gdhs, symbol=CODE)  # 股东户数
try:
    safe("gdhs_detail", ak.stock_zh_a_gdhs_detail_em, symbol=CODE)
except Exception as e:
    data["gdhs_detail"] = {"_error": repr(e)[:200]}; dump()

# ===== Section E: 龙虎榜(近60日过滤) + 限售解禁 =====
try:
    lhb = ak.stock_lhb_detail_em(start_date="20250501", end_date="20260701")
    if lhb is not None and not lhb.empty:
        lhb_q = lhb[lhb.astype(str).apply(lambda r: r.str.contains(CODE, na=False).any(), axis=1)]
        data["lhb"] = lhb_q.to_dict('records')
        print(f"[OK]   lhb: {len(lhb_q)} rows (filtered from {len(lhb)})")
    else:
        data["lhb"] = []; print("[OK]   lhb: 0 rows")
    dump()
except Exception as e:
    data["lhb"] = {"_error": repr(e)[:200]}; print(f"[FAIL] lhb: {repr(e)[:100]}"); dump()

try:
    safe("restricted", ak.stock_restricted_release_detail_em, symbol=CODE)
except Exception as e:
    try:
        safe("restricted", ak.stock_restricted_release_detail_em, stock=CODE)
    except Exception as e2:
        data["restricted"] = {"_error": repr(e2)[:200]}; dump()

# ===== Section F: 概念板块(涨跌榜 + 个股所属) =====
safe("concept_list", ak.stock_board_concept_name_em)
# 反查个股所属概念:遍历候选科技板块
candidate_boards = ["AI芯片","汽车芯片","智能音箱","MCU芯片","中芯国际概念",
                    "存储芯片","国产芯片","消费电子","机器人执行器","智能穿戴",
                    "VRAR","液冷服务器","算力"]
owned = []
for b in candidate_boards:
    try:
        cons = ak.stock_board_concept_cons_em(symbol=b)
        if cons is not None and not cons.empty:
            # 列名可能为"代码"
            code_col = [c for c in cons.columns if "代码" in c or c=="code"]
            if code_col:
                hits = cons[cons[code_col[0]].astype(str).str.contains(CODE, na=False)]
                if not hits.empty:
                    owned.append(b)
    except Exception:
        pass
data["owned_concepts"] = owned
print(f"[INFO] owned_concepts: {owned}")
dump()

print("=== fetch_stock done ===")
