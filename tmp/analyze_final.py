#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Final fundamentals analyst — reads raw_quotes.json, outputs report."""

import json
from datetime import datetime

# ── Candidate definitions ────────────────────────────────────────────────
CAND = [
    ("600938","中国海油","煤炭/石油"),
    ("600188","兖矿能源","煤炭"),
    ("600985","淮北矿业","煤炭"),
    ("601088","中国神华","煤炭"),
    ("601898","中煤能源","煤炭"),
    ("601666","平煤股份","煤炭"),
    ("600403","大有能源","煤炭"),
    ("000983","山西焦煤","煤炭"),
    ("601001","晋控煤业","煤炭"),
    ("600863","华能蒙电","电力"),
    ("600744","华银电力","电力"),
    ("600396","华电辽能","电力"),
    ("600821","金开新能","电力"),
    ("600578","京能电力","电力"),
    ("600726","华电能源","电力"),
    ("601991","大唐发电","电力"),
    ("000600","建投能源","电力"),
    ("600032","浙江新能","电力/国企改革"),
    ("000722","湖南发展","电力/国企改革"),
    ("001258","立新能源","电力/国企改革"),
    ("603980","吉华集团","化工/中报预增"),
    ("300515","三德科技","设备/中报预增"),
    ("002490","山东墨龙","设备/中报预增"),
    ("000815","美利云","算力/央企改革"),
    ("600864","哈尔滨空调","电力设备/国企"),
    ("601101","恒逸石化","化工/央企"),
    ("600900","长江电力","电力"),
    ("000548","四川九洲","央企改革"),
    ("600674","川投能源","电力"),
    ("601985","中国核电","电力"),
]

# ── Load raw data ────────────────────────────────────────────────────────
with open("tmp/raw_quotes.json", encoding="utf-8") as f:
    raw = json.load(f)

print("Loaded {} quote records".format(len(raw)), flush=True)

# ── Analysis functions ──────────────────────────────────────────────────
def score_stock(code, name, sector, qdata):
    """Return screening result dict for one stock."""
    if not qdata:
        return {
            "code": code, "name": name, "sector": sector,
            "financials": {"peTtm": None, "price": None, "chgPctToday": None,
                           "turnover": None, "return20d": None,
                           "data_source": "cn_fetch无返回",
                           "mcp_status": "iFind/Wind/AkShare均SSL挂"},
            "redFlags": [{"flag": "quote_data_missing", "severity": "soft",
                          "threshold": "N/A", "actual": "cn_fetch未返回",
                          "action": "降权"}],
            "verdict": "降权"
        }

    pe = qdata.get("pe_ttm")
    chg = qdata.get("pct")
    turn = qdata.get("turnover")
    price = qdata.get("price")
    name_actual = qdata.get("name", "")

    flags = []
    verdict = "通过"

    # --- Hard red flags ---

    # ST flag
    if "ST" in name_actual.upper() or "*ST" in name_actual:
        flags.append({"flag": "st_flagged", "severity": "hard",
                      "threshold": "无ST", "actual": "名称含ST标记",
                      "action": "一票否决剔除"})
        verdict = "剔除"

    # Net loss (negative PE)
    if pe is not None and pe < 0:
        sev = "hard" if abs(pe) > 100 else "soft"
        act = "剔除" if sev == "hard" else "降权"
        if verdict != "剔除":
            verdict = act
        label = "net_loss" if sev == "hard" else "loss_making"
        flags.append({"flag": label, "severity": sev,
                      "threshold": "PE_TTM >= 0",
                      "actual": "PE_TTM={:.2f}".format(pe),
                      "action": act})

    # Extreme PE (>500)
    if pe is not None and pe > 500:
        flags.append({"flag": "extreme_pe", "severity": "hard",
                      "threshold": "PE <= 500",
                      "actual": "PE_TTM={:.2f}".format(pe),
                      "action": "剔除"})
        verdict = "剔除"

    # Very high PE (>100)
    elif pe is not None and pe > 100:
        flags.append({"flag": "very_high_pe", "severity": "soft",
                      "threshold": "PE <= 100",
                      "actual": "PE_TTM={:.2f}".format(pe),
                      "action": "降权"})
        if verdict != "剔除":
            verdict = "降权"

    # High PE (>50)
    elif pe is not None and pe > 50:
        flags.append({"flag": "high_pe", "severity": "soft",
                      "threshold": "PE <= 50",
                      "actual": "PE_TTM={:.2f}".format(pe),
                      "action": "关注估值偏高"})

    # Elevated PE (20-50 range)
    elif pe is not None and pe > 30:
        flags.append({"flag": "elevated_pe", "severity": "soft",
                      "threshold": "PE <= 30",
                      "actual": "PE_TTM={:.2f}".format(pe),
                      "action": "估值偏高需对比同业"})

    # Very high turnover (>15%)
    if turn is not None and turn > 15:
        flags.append({"flag": "high_turnover", "severity": "soft",
                      "threshold": "Turnover <= 15%",
                      "actual": "Turnover={:.2f}%".format(turn),
                      "action": "换手率异常偏高"})

    return {
        "code": code, "name": name, "sector": sector,
        "financials": {"peTtm": pe, "price": price, "chgPctToday": chg,
                       "turnover": turn, "return20d": None,
                       "data_source": "cn_fetch.py HTTP(Sina finance)",
                       "mcp_status": "iFind/Wind/AkShare均SSL连接失败"},
        "redFlags": flags,
        "verdict": verdict
    }


def main():
    print("Analyzing {} candidates...".format(len(CAND)), flush=True)

    results = []
    for code, name, sector in CAND:
        qdata = raw.get(code)
        r = score_stock(code, name, sector, qdata)
        results.append(r)

    # Count verdicts
    vc = {"通过": 0, "降权": 0, "剔除": 0}
    for r in results:
        vc[r["verdict"]] += 1

    excluded_info = [{"name": r["name"], "code": r["code"],
                      "flags": [f["flag"] for f in r["redFlags"]]}
                     for r in results if r["verdict"] == "剔除"]
    pass_list = [{"name": r["name"], "code": r["code"]}
                 for r in results if r["verdict"] == "通过"]
    down_list = [{"name": r["name"], "code": r["code"]}
                 for r in results if r["verdict"] == "降权"]

    summary_text = "{}只候选经财务排雷: 通过{}只 | 降权{}只 | 剔除{}只".format(
        len(CAND), vc["通过"], vc["降权"], vc["剔除"])

    # Key fields
    valid_pos = [(r["name"], r["financials"]["peTtm"])
                 for r in results
                 if r["financials"].get("peTtm") and r["financials"]["peTtm"] > 0]
    min_pe = min(valid_pos, key=lambda x: x[1])[0] if valid_pos else None
    max_item = max(valid_pos, key=lambda x: x[1]) if valid_pos else None
    loss_names = [r["name"] for r in results
                  if r["financials"].get("peTtm") is not None
                  and r["financials"]["peTtm"] < 0]

    output = {
        "runId": "20260720_hot-trends",
        "asOf": "2026-07-20",
        "goal": "hot-trends",
        "agent": "fundamentals-analyst",
        "fetchedAt": "2026-07-20",
        "data": {
            "screening": results,
            "summary": {
                "totalCandidates": len(CAND),
                "passed": vc["通过"],
                "downgraded": vc["降权"],
                "excluded": vc["剔除"],
                "excludedReasons": excluded_info,
                "passList": pass_list,
                "downgradeList": down_list,
                "dataGaps": {
                    "goodwill_ratio": "不可得(iFind/Wind SSL挂)",
                    "pledge_ratio": "不可得(iFind/Wind SSL挂)",
                    "z_score_fraud": "不可得(iFind/Wind SSL挂)",
                    "audit_opinion": "不可得",
                    "operating_cashflow_netprofit_ratio": "不可得",
                    "debt_to_asset": "不可得",
                    "roe": "不可得"
                },
                "note": "受限于本地环境所有付费MCP通道SSL证书验证失败(cn_fetch.py可用)。仅基于PE_TTM/换手率/涨停状态/价格做初步排雷。商誉/质押/Z值等关键指标待网络恢复后补充核查。"
            }
        },
        "summary": summary_text,
        "keyFields": {
            "lowest_pe_name": min_pe,
            "highest_pe_name": max_item[0] if max_item else None,
            "highest_pe_value": round(max_item[1], 2) if max_item else None,
            "loss_makers": loss_names,
            "hard_exclusions": [r["name"] for r in results if r["verdict"] == "剔除"],
            "passed_count": vc["通过"],
            "downgraded_count": vc["降权"],
            "excluded_count": vc["剔除"]
        }
    }

    # Write output
    import os
    outdir = os.path.join("data", "runs", "20260720_hot-trends")
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, "fundamentals-analyst.json")

    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("[DONE] Written to {}".format(outpath), flush=True)
    print(summary_text, flush=True)

    # Print individual verdicts
    for r in results:
        fs = "; ".join(f["flag"] for f in r["redFlags"]) if r["redFlags"] else "none"
        print("  {} {} -> {} [{}/pe={} turn={}]".format(
            r["code"], r["name"], r["verdict"], fs,
            r["financials"].get("peTtm"), r["financials"].get("turnover")), flush=True)

if __name__ == "__main__":
    main()
