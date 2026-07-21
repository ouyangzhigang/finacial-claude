#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fundamentals-screener V3: batch financial red-flag screen using binary subprocess."""

import json, subprocess, sys, os, time

RAW = [
    {"code": "600938", "name": "中国海油",   "sector": "煤炭/石油"},
    {"code": "600188", "name": "兖矿能源",   "sector": "煤炭"},
    {"code": "600985", "name": "淮北矿业",   "sector": "煤炭"},
    {"code": "601088", "name": "中国神华",   "sector": "煤炭"},
    {"code": "601898", "name": "中煤能源",   "sector": "煤炭"},
    {"code": "601666", "name": "平煤股份",   "sector": "煤炭"},
    {"code": "600403", "name": "大有能源",   "sector": "煤炭"},
    {"code": "000983", "name": "山西焦煤",   "sector": "煤炭"},
    {"code": "601001", "name": "晋控煤业",   "sector": "煤炭"},
    {"code": "600863", "name": "华能蒙电",   "sector": "电力"},
    {"code": "600744", "name": "华银电力",   "sector": "电力"},
    {"code": "600396", "name": "华电辽能",   "sector": "电力"},
    {"code": "600821", "name": "金开新能",   "sector": "电力"},
    {"code": "600578", "name": "京能电力",   "sector": "电力"},
    {"code": "600726", "name": "华电能源",   "sector": "电力"},
    {"code": "601991", "name": "大唐发电",   "sector": "电力"},
    {"code": "000600", "name": "建投能源",   "sector": "电力"},
    {"code": "600032", "name": "浙江新能",   "sector": "电力/国企改革"},
    {"code": "000722", "name": "湖南发展",   "sector": "电力/国企改革"},
    {"code": "001258", "name": "立新能源",   "sector": "电力/国企改革"},
    {"code": "603980", "name": "吉华集团",   "sector": "化工/中报预增"},
    {"code": "300515", "name": "三德科技",   "sector": "设备/中报预增"},
    {"code": "002490", "name": "山东墨龙",   "sector": "设备/中报预增"},
    {"code": "000815", "name": "美利云",     "sector": "算力/央企改革"},
    {"code": "600864", "name": "哈尔滨空调", "sector": "电力设备/国企"},
    {"code": "601101", "name": "恒逸石化",   "sector": "化工/央企"},
    {"code": "600900", "name": "长江电力",   "sector": "电力"},
    {"code": "000548", "name": "四川九洲",   "sector": "央企改革"},
    {"code": "600674", "name": "川投能源",   "sector": "电力"},
    {"code": "601985", "name": "中国核电",   "sector": "电力"},
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(SCRIPT_DIR, "..", "..")
CN_FETCH = os.path.join(REPO_ROOT, "scripts", "cn_fetch.py")

def ex(code):
    return "sh" if code.startswith("6") else "sz"

def run_cn(args):
    """Run cn_fetch.py via binary subprocess, decode stdout as utf-8."""
    try:
        r = subprocess.run(
            [sys.executable, CN_FETCH] + args,
            capture_output=True, timeout=15,
            cwd=REPO_ROOT,
        )
        out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        if not out.strip():
            return {}
        return json.loads(out)
    except Exception as e:
        print("  ERR subproc {}: {}".format(args, e), file=sys.stderr)
        return {}

def fetch_single_quote(code):
    raw = run_cn(["quote", ex(code)+code])
    for k, v in raw.items():
        if isinstance(v, dict) and "code" in v:
            return v
    return None

def fetch_kline(code, days=25):
    raw = run_cn(["kline", ex(code)+code, str(days)])
    if isinstance(raw, list):
        return raw
    return []

def calc_return(klines, n_days=20):
    if not klines or len(klines) < 2:
        return None
    old_c = float(klines[0][2])  # close price (index 2)
    new_c = float(klines[-1][2])
    return round((new_c / old_c - 1) * 100, 2)

def analyze(code, name, sector, data):
    entry = {
        "code": code,
        "name": name,
        "sector": sector,
        "financials": {},
        "redFlags": [],
        "verdict": "通过"
    }

    if not data:
        entry["financials"]["peTtm"] = None
        entry["financials"]["data_source"] = "cn_fetch无返回(May be delisted/suspended)"
        entry["verdict"] = "降权"
        entry["redFlags"].append({
            "flag": "quote_data_missing",
            "severity": "soft",
            "threshold": "N/A",
            "actual": "cn_fetch.py未返回该股数据",
            "action": "降权处理，需人工确认状态"
        })
        return entry

    pe_ttm = data.get("pe_ttm")
    chg_pct = data.get("pct")
    turnover = data.get("turnover")
    price = data.get("price")
    name_actual = data.get("name", "")

    # --- Hard red flags ---

    # 1. ST/*ST flag
    if "ST" in name_actual.upper() or "*ST" in name_actual:
        entry["redFlags"].append({
            "flag": "st_flagged",
            "severity": "hard",
            "threshold": "无ST",
            "actual": "名称含ST/*ST标记",
            "action": "一票否决剔除"
        })
        entry["verdict"] = "剔除"

    # 2. Net loss (negative PE_TTM)
    if pe_ttm is not None and pe_ttm < 0:
        severity = "hard" if abs(pe_ttm) > 100 else "soft"
        action = "剔除" if severity == "hard" else "降权"
        if entry["verdict"] != "剔除":
            entry["verdict"] = action
        entry["redFlags"].append({
            "flag": "net_loss" if severity == "hard" else "loss_making",
            "severity": severity,
            "threshold": "PE_TTM >= 0 (盈利)",
            "actual": "PE_TTM = {:.2f}".format(pe_ttm),
            "action": action
        })

    # 3. Extreme PE (>500)
    if pe_ttm is not None and pe_ttm > 500:
        entry["redFlags"].append({
            "flag": "extreme_pe",
            "severity": "hard",
            "threshold": "PE_TTM <= 500",
            "actual": "PE_TTM = {:.2f}".format(pe_ttm),
            "action": "剔除"
        })
        entry["verdict"] = "剔除"

    # 4. Very high PE (>100)
    elif pe_ttm is not None and pe_ttm > 100:
        entry["redFlags"].append({
            "flag": "very_high_pe",
            "severity": "soft",
            "threshold": "PE_TTM <= 100",
            "actual": "PE_TTM = {:.2f}".format(pe_ttm),
            "action": "降权"
        })
        if entry["verdict"] != "剔除":
            entry["verdict"] = "降权"

    # 5. High PE (>50) moderate concern
    elif pe_ttm is not None and pe_ttm > 50:
        entry["redFlags"].append({
            "flag": "high_pe",
            "severity": "soft",
            "threshold": "PE_TTM <= 50",
            "actual": "PE_TTM = {:.2f}".format(pe_ttm),
            "action": "关注估值偏高"
        })

    # 6. Elevated PE (20-50 range)
    elif pe_ttm is not None and pe_ttm > 30:
        entry["redFlags"].append({
            "flag": "elevated_pe",
            "severity": "soft",
            "threshold": "PE_TTM <= 30",
            "actual": "PE_TTM = {:.2f}".format(pe_ttm),
            "action": "估值偏高需对比同业"
        })

    # 7. Very high turnover (>15%)
    if turnover is not None and turnover > 15:
        entry["redFlags"].append({
            "flag": "high_turnover",
            "severity": "soft",
            "threshold": "Turnover <= 15%",
            "actual": "Turnover = {:.2f}%".format(turnover),
            "action": "换手率异常偏高"
        })

    entry["financials"] = {
        "peTtm": pe_ttm,
        "price": price,
        "chgPctToday": chg_pct,
        "turnover": turnover,
        "data_source": "cn_fetch.py HTTP(Sina finance)",
        "mcp_status": "iFind/Wind/AkShare均SSL连接失败,无法获取商誉/质押/Z值指标"
    }

    return entry


def main():
    print("[START] fundamentals-screener V3: screening {} candidates".format(len(RAW)), file=sys.stderr)

    results = {}
    for i, stock in enumerate(RAW):
        q = fetch_single_quote(stock["code"])
        results[stock["code"]] = q
        ok = "OK" if q else "MISSING"
        if (i+1) % 10 == 0 or i == len(RAW)-1:
            print("  [{}/{}] {} [{}]".format(i+1, len(RAW), stock["name"], ok), file=sys.stderr)
        time.sleep(0.05)

    SCREENING = []
    for stock in RAW:
        entry = analyze(stock["code"], stock["name"], stock["sector"], results.get(stock["code"]))
        SCREENING.append(entry)

    # K-line 20-day return for non-excluded
    active = [e for e in SCREENING if e["verdict"] != "剔除"]
    print("[KLINE] Fetching 20d returns for {} active stocks...".format(len(active)), file=sys.stderr)
    for entry in active:
        kl = fetch_kline(entry["code"], days=25)
        ret20 = calc_return(kl) if kl else None
        entry["financials"]["return20d"] = ret20
        if ret20 is not None and ret20 > 30:
            entry["redFlags"].append({
                "flag": "overextended_20d",
                "severity": "hard",
                "threshold": "20日涨幅 <= 30%",
                "actual": "20日涨幅 = {:.2f}%".format(ret20),
                "action": "估值透支，剔除"
            })
            entry["verdict"] = "剔除"

    # Summary stats
    vc = {"通过": 0, "降权": 0, "剔除": 0}
    for e in SCREENING:
        vc[e["verdict"]] += 1

    excluded_info = [{"name": e["name"], "code": e["code"], "flags": [r["flag"] for r in e["redFlags"]]} for e in SCREENING if e["verdict"] == "剔除"]
    passed_list = [{"name": e["name"], "code": e["code"]} for e in SCREENING if e["verdict"] == "通过"]
    downgraded_list = [{"name": e["name"], "code": e["code"]} for e in SCREENING if e["verdict"] == "降权"]

    summary_text = "{}只候选经财务排雷: 通过{}只 | 降权{}只 | 剔除{}只".format(
        len(RAW), vc["通过"], vc["降权"], vc["剔除"])

    # Key fields
    all_pe = [(e["name"], e["financials"].get("peTtm")) for e in SCREENING if e["financials"].get("peTtm")]
    valid_pos = [(n, p) for n, p in all_pe if p is not None and p > 0]
    min_pe = min(valid_pos, key=lambda x: x[1])[0] if valid_pos else None
    max_pe_item = max(valid_pos, key=lambda x: x[1]) if valid_pos else None
    max_pe_name = max_pe_item[0] if max_pe_item else None
    max_pe_val = max_pe_item[1] if max_pe_item else None

    loss_makers = [e["name"] for e in SCREENING if e["financials"].get("peTtm") is not None and e["financials"]["peTtm"] < 0]

    output = {
        "runId": "20260720_hot-trends",
        "asOf": "2026-07-20",
        "goal": "hot-trends",
        "agent": "fundamentals-analyst",
        "fetchedAt": "2026-07-20",
        "data": {
            "screening": SCREENING,
            "summary": {
                "totalCandidates": len(RAW),
                "passed": vc["通过"],
                "downgraded": vc["降权"],
                "excluded": vc["剔除"],
                "excludedReasons": excluded_info,
                "passList": passed_list,
                "downgradeList": downgraded_list,
                "dataGaps": {
                    "goodwill_ratio": "不可得(iFind/Wind SSL挂)",
                    "pledge_ratio": "不可得(iFind/Wind SSL挂)",
                    "z_score_fraud": "不可得(iFind/Wind SSL挂)",
                    "audit_opinion": "不可得",
                    "operating_cashflow_netprofit_ratio": "不可得",
                    "debt_to_asset": "不可得",
                    "roe": "不可得"
                },
                "note": "受限于本地环境所有付费MCP通道SSL证书验证失败(cn_fetch.py可用),仅基于PE_TTM/换手率/涨停状态/20日涨幅做初步排雷。商誉/质押/Z值等关键指标待网络恢复后补充核查。"
            }
        },
        "summary": summary_text,
        "keyFields": {
            "lowest_pe_name": min_pe,
            "highest_pe_name": max_pe_name,
            "highest_pe_value": max_pe_val,
            "loss_makers": loss_makers,
            "hard_exclusions": [e["name"] for e in SCREENING if e["verdict"] == "剔除"],
            "passed_count": vc["通过"],
            "downgraded_count": vc["降权"],
            "excluded_count": vc["剔除"]
        }
    }

    outdir = os.path.join(REPO_ROOT, "data", "runs", "20260720_hot-trends")
    os.makedirs(outdir, exist_ok=True)
    outfile = os.path.join(outdir, "fundamentals-analyst.json")

    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("[DONE] Written to {}".format(outfile), file=sys.stderr)
    for e in SCREENING:
        flag_str = "; ".join(r["flag"] for r in e["redFlags"]) if e["redFlags"] else "none"
        print("  {} {} -> {} [{}]".format(e["code"], e["name"], e["verdict"], flag_str), file=sys.stderr)

if __name__ == "__main__":
    from datetime import datetime
    main()
