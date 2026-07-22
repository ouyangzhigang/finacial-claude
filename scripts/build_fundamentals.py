#!/usr/bin/env python
"""Build fundamentals analysis from mootdx+Tencent data."""
import json
import requests
import urllib3
import re
import os
from collections import Counter

urllib3.disable_warnings()

with open("data/temp_financials.json", "r", encoding="utf-8") as f:
    fin_data = json.load(f)

name_map = {
    "002185": "华天科技", "603005": "晶方科技", "600667": "太极实业",
    "000021": "深科技", "002213": "大为股份", "688729": "屹唐股份",
    "600206": "有研新材", "002167": "东方锆业", "600460": "士兰微",
    "688728": "格科微", "001399": "惠科股份", "603936": "博敏电子",
    "002273": "水晶光电", "002396": "星网锐捷", "002245": "蔚蓝锂芯",
    "301282": "金禄电子", "000815": "美利云", "002745": "木林森",
    "600884": "杉杉股份", "600522": "中天科技", "600105": "永鼎股份",
    "600330": "天通股份", "603890": "春秋电子", "603118": "共进股份",
    "300137": "先河环保", "301012": "扬电科技", "002448": "中原内配",
    "300093": "金刚光伏", "688371": "菲沃泰", "002436": "兴森科技",
}

sector_map = {
    "002185": "先进封装", "603005": "先进封装", "600667": "存储芯片/先进封装",
    "000021": "存储封测", "002213": "半导体存储", "688729": "半导体设备",
    "600206": "半导体材料", "002167": "半导体材料", "600460": "功率半导体",
    "688728": "半导体设计", "001399": "半导体显示", "603936": "PCB/存储",
    "002273": "AI光学/CPO", "002396": "数据中心/CPO", "002245": "AI电源",
    "301282": "AI算力PCB", "000815": "算力租赁", "002745": "LED封装",
    "600884": "新能源材料", "600522": "光纤光缆/AI算力", "600105": "光纤光缆/CPO",
    "600330": "光模块上游", "603890": "液冷/AIPC", "603118": "数据中心/CPO",
    "300137": "算力/环保", "301012": "算力电力", "002448": "汽车零部件",
    "300093": "算力/光伏", "688371": "液冷/纳米镀膜", "002436": "封装基板/PCB",
}


def get_price_pct(code, mkt):
    full_code = "{}{}".format(mkt, code)
    url = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={},week,,,120,qfq".format(full_code)
    try:
        r = requests.get(url, timeout=10, verify=False)
        data = r.json()
        if data.get("code") == 0:
            klines = data.get("data", {}).get(full_code, {}).get("qfqweek", [])
            if klines and len(klines) > 10:
                closes = [float(k[2]) for k in klines]
                cur = closes[-1]
                below = sum(1 for c in closes[:-1] if c < cur)
                pct = round(below / (len(closes) - 1) * 100, 1)
                return {
                    "pricePct": pct,
                    "high2y": round(max(closes), 2),
                    "low2y": round(min(closes), 2),
                    "current": cur,
                    "samples": len(closes),
                }
    except Exception:
        pass
    return None


def roe_v(roe):
    if roe is None:
        return "数据缺失"
    if roe > 10:
        return "健康(>10%)"
    if roe > 5:
        return "一般(5-10%)"
    if roe > 1:
        return "偏低(1-5%)"
    return "极低(<1%)"


def cf_v(cfnp):
    if cfnp is None:
        return "数据缺失"
    if cfnp > 1:
        return "健康(>1)"
    if cfnp > 0.5:
        return "一般(0.5-1)"
    return "现金流质量差(<0.5)"


def pe_v(pe):
    if pe is None:
        return "数据缺失"
    if pe < 0:
        return "PE为负(亏损)无估值锚"
    if pe > 200:
        return "PE极高(>200)估值风险大"
    if pe > 100:
        return "PE偏高(100-200)"
    if pe > 50:
        return "PE偏高(50-100)"
    if pe > 30:
        return "PE中等(30-50)"
    return "PE相对合理(<30)"


def pv(roe, cfnp):
    if roe is None or cfnp is None:
        return "数据缺失"
    if cfnp < 0.5 or roe < 3:
        return "盈利质量差"
    if roe < 8:
        return "盈利质量一般"
    return "盈利质量良好"


results = {}
for code, d in fin_data.items():
    if "error" in d:
        continue
    name = name_map.get(code, d.get("name", code))
    sector = sector_map.get(code, "未知")
    roe = d.get("roe")
    gm = d.get("gross_margin")
    nm = d.get("net_margin")
    dr = d.get("debt_ratio")
    cfnp = d.get("cf_to_np")
    rec_ratio = d.get("receivable_ratio")
    intan_ratio = d.get("intangible_to_na")
    pe = d.get("pe")
    pb = d.get("pb")
    mktcap = d.get("mktcap_yi")
    np = d.get("net_profit")
    rev = d.get("revenue")
    op_cf = d.get("op_cashflow")
    total_cf = d.get("total_cashflow")
    nonrecurring = d.get("nonrecurring_ratio")

    red_flags = []

    # Hard red flags
    if intan_ratio and intan_ratio > 40:
        red_flags.append({
            "flag": "商誉/无形资产占比过高",
            "severity": "hard", "threshold": ">40%",
            "actual": "{}%".format(intan_ratio), "action": "剔除",
        })
    if pe is not None and pe < 0:
        red_flags.append({
            "flag": "PE为负(净利润亏损)",
            "severity": "hard", "threshold": "PE>0",
            "actual": "PE={:.1f}".format(pe), "action": "剔除",
        })
    if rec_ratio and rec_ratio > 150:
        red_flags.append({
            "flag": "应收账款极度异常(>150%收入)",
            "severity": "hard", "threshold": ">150%",
            "actual": "{:.1f}%".format(rec_ratio), "action": "剔除",
        })
    if cfnp is not None and cfnp < -5 and np and np > 0:
        red_flags.append({
            "flag": "经营现金流极端恶化",
            "severity": "hard", "threshold": "CF/NP>-5",
            "actual": "{:.2f}".format(cfnp), "action": "剔除",
        })

    # Soft red flags
    if rec_ratio and rec_ratio > 40 and rec_ratio <= 150:
        red_flags.append({
            "flag": "应收账款占比偏高",
            "severity": "soft", "threshold": ">40%",
            "actual": "{:.1f}%".format(rec_ratio), "action": "降权",
        })
    if cfnp is not None and cfnp < 0.5 and cfnp >= -5:
        red_flags.append({
            "flag": "经营现金流/净利润不匹配",
            "severity": "soft", "threshold": ">0.5为健康",
            "actual": "{:.2f}".format(cfnp), "action": "降权",
        })
    if dr and dr > 70:
        red_flags.append({
            "flag": "资产负债率过高",
            "severity": "soft", "threshold": ">70%",
            "actual": "{:.1f}%".format(dr), "action": "降权",
        })
    if pe is not None and pe > 200:
        red_flags.append({
            "flag": "PE极度高估(>200)",
            "severity": "soft", "threshold": "PE<200",
            "actual": "PE={:.1f}".format(pe), "action": "降权",
        })
    if pe is not None and pe > 100 and pe <= 200:
        red_flags.append({
            "flag": "PE显著偏高(>100)",
            "severity": "soft", "threshold": "PE<100",
            "actual": "PE={:.1f}".format(pe), "action": "降权",
        })
    if roe is not None and roe < 1 and pe is not None and pe > 0:
        red_flags.append({
            "flag": "ROE极低(近乎零盈利)",
            "severity": "soft", "threshold": "ROE>1%",
            "actual": "ROE={:.2f}%".format(roe), "action": "降权",
        })
    if gm and gm > 100:
        red_flags.append({
            "flag": "毛利率异常(>100%数据存疑)",
            "severity": "soft", "threshold": "0-100%",
            "actual": "{:.1f}%".format(gm), "action": "降权",
        })
    if nonrecurring and abs(nonrecurring) > 20:
        red_flags.append({
            "flag": "非经常性损益占比过高",
            "severity": "soft", "threshold": ">20%",
            "actual": "{:.1f}%".format(nonrecurring), "action": "降权",
        })
    if dr and dr > 60 and dr <= 70:
        red_flags.append({
            "flag": "资产负债率偏高",
            "severity": "soft", "threshold": ">60%",
            "actual": "{:.1f}%".format(dr), "action": "降权",
        })

    hard_flags = [f for f in red_flags if f["severity"] == "hard"]
    soft_flags = [f for f in red_flags if f["severity"] == "soft"]

    if hard_flags:
        verdict = "剔除"
    elif len(soft_flags) >= 1:
        verdict = "降权"
    else:
        verdict = "通过"

    mkt = "sh" if code.startswith("6") else "sz"
    pct_data = get_price_pct(code, mkt)

    flags_summary = "; ".join([f["flag"] for f in red_flags[:3]]) if red_flags else "无显著红旗"

    results[code] = {
        "code": code,
        "name": name,
        "sector": sector,
        "financials": {
            "roe": roe,
            "roeVerdict": roe_v(roe),
            "grossMargin": gm,
            "netMargin": nm,
            "debtRatio": dr,
            "cashflowRatio": cfnp,
            "cashflowVerdict": cf_v(cfnp),
            "receivableRatio": rec_ratio,
            "nonrecurringRatio": nonrecurring,
            "netProfit_yi": round(np / 1e8, 2) if np else None,
            "revenue_yi": round(rev / 1e8, 2) if rev else None,
            "opCashflow_yi": round(op_cf / 1e8, 2) if op_cf else None,
            "intangibleToNA": intan_ratio,
            "verdict": pv(roe, cfnp),
        },
        "valuation": {
            "peTtm": pe,
            "pb": pb,
            "marketCap_yi": mktcap,
            "pricePercentile2y": pct_data.get("pricePct") if pct_data else None,
            "priceHigh2y": pct_data.get("high2y") if pct_data else None,
            "priceLow2y": pct_data.get("low2y") if pct_data else None,
            "pePercentile5y": "数据缺失(iFind SSL挂)",
            "pbPercentile5y": "数据缺失(iFind SSL挂)",
            "relativeToPeers": "数据缺失(行业均值无法获取)",
            "verdict": pe_v(pe),
        },
        "redFlags": red_flags,
        "dataGaps": [
            "商誉精确值(仅无形资产近似)",
            "控股股东质押比例(数据源不可用)",
            "PE/PB近5年历史分位(iFind-wind-akshare SSL全挂)",
            "大存大贷检查(缺货币资金明细)",
            "Z值/M值造假预警(缺完整数据)",
            "近3年ROE/毛利率趋势(仅单期数据)",
        ],
        "verdict": verdict,
        "summary": "{}: ROE={:.1f}% PE={:.1f} CF/NP={:.2f} 应收/收入={:.1f}% | {} | 判定:{}".format(
            "{}" + "({})".format(sector), roe, pe, cfnp, rec_ratio, flags_summary, verdict
        ),
    }

# Fix summary format
for code, r in results.items():
    r["summary"] = "{}: ROE={:.1f}% PE={:.1f} CF/NP={:.2f} 应收/收入={:.1f}% | {} | 判定:{}".format(
        "{}" + "({})".format(r["sector"]), r["financials"]["roe"] or 0,
        r["valuation"]["peTtm"] or 0, r["financials"]["cashflowRatio"] or 0,
        r["financials"]["receivableRatio"] or 0,
        "; ".join([f["flag"] for f in r["redFlags"][:3]]) if r["redFlags"] else "无显著红旗",
        r["verdict"],
    )

# Print summary
for code, r in sorted(results.items()):
    print("{} | {} {} | {}".format(r["verdict"], code, r["name"], r["summary"]))

v_counts = Counter(r["verdict"] for r in results.values())
print("\n=== 判定分布 ===")
for v, c in v_counts.items():
    print("  {}: {}只".format(v, c))

# Build output
output = {
    "agent": "fundamentals-analyst",
    "asOf": "20260721",
    "data": {
        "verdictSummary": {
            "pass": [{"code": r["code"], "name": r["name"], "sector": r["sector"]} for r in results.values() if r["verdict"] == "通过"],
            "downgrade": [{"code": r["code"], "name": r["name"], "sector": r["sector"]} for r in results.values() if r["verdict"] == "降权"],
            "reject": [{"code": r["code"], "name": r["name"], "sector": r["sector"]} for r in results.values() if r["verdict"] == "剔除"],
            "counts": dict(v_counts),
        },
        "stocks": results,
        "methodology": {
            "dataSources": "腾讯HTTP(PE/PB/市值/2年K线价格分位) + mootdx通达信TCP 7709(财务三表数据)",
            "missingData": ["商誉精确值", "控股股东质押比例", "PE/PB近5年历史分位", "大存大贷", "Z值/M值", "近3年财务趋势"],
            "missingReason": "iFind/wind/akshare MCP SSL全挂; 新浪/东财HTTPS也被代理拦截; 仅腾讯HTTP+通达信TCP可用",
            "notes": "无形资产/净资产作为商誉近似; 2年价格分位作为估值分位近似; 财务数据为最新一期年报口径",
        },
    },
}

os.makedirs("data/runs/20260721_short-term-picks", exist_ok=True)
with open("data/runs/20260721_short-term-picks/fundamentals-analyst.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("\nOutput written to data/runs/20260721_short-term-picks/fundamentals-analyst.json")

# Key flags
print("\n=== 关键红旗汇总 ===")
for code, r in sorted(results.items()):
    if r["redFlags"]:
        hard = [f for f in r["redFlags"] if f["severity"] == "hard"]
        soft = [f for f in r["redFlags"] if f["severity"] == "soft"]
        print("\n{} {} ({}) [{}]:".format(code, r["name"], r["sector"], r["verdict"]))
        for f in hard:
            print("  [HARD] {}: {} (阈值:{})".format(f["flag"], f["actual"], f["threshold"]))
        for f in soft:
            print("  [SOFT] {}: {} (阈值:{})".format(f["flag"], f["actual"], f["threshold"]))