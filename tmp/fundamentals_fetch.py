#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fundamentals analyst data fetcher - local HTTP fallback when MCPs are all SSL-down"""

import json
import ssl
import re
import time
from urllib.request import Request, urlopen

ssl._create_default_https_context = ssl._create_unverified_context

STOCKS = [
    {"code": "000725", "name": "京东方A"},
    {"code": "002891", "name": "中宠股份"},
    {"code": "002294", "name": "信立泰"},
    {"code": "000543", "name": "皖能电力"},
    {"code": "000899", "name": "赣能股份"},
    {"code": "601369", "name": "陕鼓动力"},
]


def http_get(url, timeout=15):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        resp = urlopen(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return "ERROR:" + str(e)


def parse_tencent_quote(code, field_str):
    fields = field_str.strip().split("~")
    if len(fields) < 32:
        return {}

    def safe_float(idx):
        try:
            v = fields[idx]
            return float(v) if v and v != "-" else None
        except Exception:
            return None

    return {
        "name": fields[1] if len(fields) > 1 else "",
        "price": safe_float(3),
        "change_pct": safe_float(32),
        "volume": safe_float(6),
        "turnover_rate": safe_float(37),
        "pe_ttm": safe_float(39),
        "pb_mf": safe_float(41),
        "total_mv": safe_float(34),
    }


def main():
    print("[INFO] Starting fundamentals data collection...")

    # Step 1: Tencent batch quotes for all stocks
    code_list = []
    for s in STOCKS:
        c = s["code"]
        p = "sz" if c.startswith(("0", "3")) else "sh"
        code_list.append(f"{p}{c}")

    qs = ",".join(code_list)
    url_qt = f"https://qt.gtimg.cn/q={qs}"
    print("[INFO] Fetching Tencent quotes...")
    qt_html = http_get(url_qt)

    quotes = {}
    for line in qt_html.split("\n"):
        if "=" not in line:
            continue
        parts = line.strip().split("=")
        if len(parts) < 2:
            continue
        name_key = parts[0].strip()
        m = re.search(r"v_(?:sz|sh)(\d{6})", name_key)
        if not m:
            continue
        stk_code = m.group(1)
        quotes[stk_code] = parse_tencent_quote(stk_code, parts[1])

    for c in STOCKS:
        q = quotes.get(c["code"], {})
        print(f"  {c['code']} ({c['name']}): price={q.get('price')} PE={q.get('pe_ttm')} PB={q.get('pb_mf')}")

    # Step 2: East Money F10 financial snapshot
    print("\n[INFO] Fetching East Money F10 fundamental snapshots...")
    fund_snapshots = {}
    for stk in STOCKS:
        code = stk["code"]

        url_fin = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPT_F10_FINANCE_MAINFINADATA&"
            "columns=SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,BASIC_EPS,"
            "TOTAL_OPERATE_INCOME,PARENT_NETPROFIT,GROSS_PROFIT_RATIO,"
            "NETPROFIT_MARGIN,DILUTED_ROE,TOTAL_ASSETS,TOTAL_LIABITIES,"
            "ASSETLIABILITYRATIO,ONLINECASHFLOWAMOUNT,FLOWOPS,CAPITAL_EXPENDITURE,"
            "MARKETCAPITATION&"
            f"filter=(SECURITY_CODE=%22{code}%22)&pageSize=4&sortBy=REPORT_DATE&sortType=-1"
        )
        html = http_get(url_fin)

        snapshot = {"raw": ""}
        if html and not html.startswith("ERROR") and "[" in html:
            try:
                data = json.loads(html)
                result_list = data.get("result", {}).get("data", [])
                if result_list:
                    r = result_list[0]
                    snapshot.update(
                        {
                            "report_date": r.get("REPORT_DATE"),
                            "basic_eps": r.get("BASIC_EPS"),
                            "revenue": r.get("TOTAL_OPERATE_INCOME"),
                            "net_profit": r.get("PARENT_NETPROFIT"),
                            "gross_margin": r.get("GROSS_PROFIT_RATIO"),
                            "net_margin": r.get("NETPROFIT_MARGIN"),
                            "roe": r.get("DILUTED_ROE"),
                            "debt_ratio": r.get("ASSETLIABILITYRATIO"),
                            "op_cashflow": r.get("ONLINECASHFLOWAMOUNT"),
                            "free_cashflow": r.get("FLOWOPS"),
                        }
                    )
                    cf = r.get("ONLINECASHFLOWAMOUNT")
                    np_ = r.get("PARENT_NETPROFIT")
                    if cf and np_:
                        try:
                            snapshot["cashflow_to_profit_ratio"] = float(cf) / float(np_) if float(np_) != 0 else None
                        except Exception:
                            pass
                    if len(result_list) >= 2:
                        r_prev = result_list[1]
                        np_curr = r.get("PARENT_NETPROFIT")
                        np_prev = r_prev.get("PARENT_NETPROFIT")
                        if np_curr and np_prev:
                            try:
                                curr = float(np_curr)
                                prev_val = float(np_prev)
                                snapshot["net_profit_yoy"] = ((curr - prev_val) / abs(prev_val) * 100) if prev_val else None
                            except Exception:
                                pass
                snapshot["raw"] = json.dumps(data, ensure_ascii=False)[:500]
            except Exception as e:
                snapshot["parse_error"] = str(e)
                snapshot["raw"] = html[:500]

        fund_snapshots[code] = snapshot
        sn = snapshot.get
        print(
            f"  {code} ({stk['name']}): ROE={sn('roe','N/A')} GM={sn('gross_margin','N/A')} "
            f"DR={sn('debt_ratio','N/A')} CF/P={sn('cashflow_to_profit_ratio','N/A')} YoY={sn('net_profit_yoy','N/A')}"
        )
        time.sleep(0.5)

    # Step 3: Pledge check
    print("\n[INFO] Checking pledge data...")
    pledge_data = {}
    for stk in STOCKS:
        code = stk["code"]
        url_pledge = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "reportName=RPT_DEF_A_STOCK_PLEDGE_STATISTICS&"
            "columns=SECURITY_CODE,REPORT_DATE,PLEDGE_TOTAL_SHARES,UNPLEDGE_SHARES,"
            "PLEDGE_RATIOL,PLEDGE_SHARES_RATIO&"
            f"filter=(SECURITY_CODE=%22{code}%22)&pageSize=1&sortBy=REPORT_DATE&sortType=-1"
        )
        html = http_get(url_pledge)
        result = {"raw": ""}
        if html and not html.startswith("ERROR") and "[" in html:
            try:
                data = json.loads(html)
                rd = data.get("result", {}).get("data", [])
                if rd:
                    result["pledge_ratio"] = rd[0].get("PLEDGE_RATIOL")
                    result["pledge_shares_ratio"] = rd[0].get("PLEDGE_SHARES_RATIO")
                    result["report_date"] = rd[0].get("REPORT_DATE")
                    result["parsed_ok"] = True
            except Exception as e:
                result["parse_error"] = str(e)
        result["raw"] = html[:300] if html else ""
        pledge_data[code] = result
        print(f"  {code} ({stk['name']}): pledge_raw={html[:200] if html else 'None'}")
        time.sleep(0.5)

    # Compile final output
    output = {
        "fetchedAt": "20260720",
        "asOf": "20260720",
        "method": "local-http-fallback-tencent-em",
        "stocks": {},
        "_meta": {"notes": "All MCPs SSL-down. Using Tencent quotes + EastMoney HTTP APIs."},
    }

    for stk in STOCKS:
        code = stk["code"]
        entry = {
            "tencent_quote": quotes.get(code, {}),
            "fundamental_snapshot": fund_snapshots.get(code, {}),
            "pledge_check": pledge_data.get(code, {}),
        }
        output["stocks"][code] = entry

    with open("E:/finacial-invest/tmp/fundamentals_raw.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n[DONE] Raw data saved -> tmp/fundamentals_raw.json")


if __name__ == "__main__":
    main()
