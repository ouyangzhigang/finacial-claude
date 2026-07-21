#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

with open('data/temp_analysis.json', 'r', encoding='utf-8') as f:
    analysis = json.load(f)

sectors = {
    "688728": "半导体/CMOS传感器", "688729": "半导体/设备(去胶)", "688371": "半导体/纳米镀膜",
    "301282": "半导体/PCB", "002156": "先进封装", "600584": "先进封装",
    "002185": "先进封装", "603005": "先进封装/TSV", "600460": "功率半导体/IGBT",
    "600171": "模拟芯片/电源管理", "002079": "半导体分立器件", "300236": "半导体材料/电镀液",
    "002747": "人形机器人/工业机器人", "300024": "人形机器人/工业机器人", "300607": "人形机器人/注塑机+机器人",
    "300068": "储能/储能电池", "002518": "储能/PCS", "002236": "中报预增/AI安防",
    "002415": "中报预增/AI安防",
}

entry_types = {
    "688728": "超跌反弹启动", "688729": "超跌反弹启动", "688371": "超跌反弹启动",
    "301282": "超跌反弹启动", "002156": "趋势延续", "600584": "趋势延续",
    "002185": "趋势延续", "603005": "趋势延续", "600460": "趋势延续",
    "600171": "趋势延续", "002079": "趋势延续", "300236": "趋势延续",
    "002747": "趋势延续", "300024": "趋势延续", "300607": "趋势延续",
    "300068": "趋势延续", "002518": "趋势延续", "002236": "趋势延续",
    "002415": "趋势延续",
}

results = []

for sym, d in sorted(analysis.items()):
    if 'error' in d:
        continue

    name = d['name']
    price = d['price']
    sector = sectors.get(sym, '')
    entry = entry_types.get(sym, '')
    net_profit_yi = d.get('net_profit_yi', 0)

    # Financials
    financials = {
        "roe": d['roe'],
        "roeTrend": f"FY2025年报ROE={d['roe']}%",
        "grossMargin": d['gross_margin'],
        "netMargin": d['net_margin'],
        "revenueGrowth": d['revenue_growth'],
        "netProfitGrowth": d['profit_growth'],
        "cashflowRatio": d.get('cf_ratio'),
        "debtRatio": d['debt_ratio'],
        "interestCoverage": d.get('interest_coverage'),
        "nonRecurringRatio": d.get('non_recurring_ratio'),
        "ocfPerShare": d['ocf_per_share'],
        "netAssetsYi": d['net_assets_yi'],
        "reportDate": d['report_date'],
        "verdict": ""
    }

    # Valuation
    pe = d.get('pe')
    pb = d.get('pb')
    valuation = {
        "price": price,
        "peTtm": pe,
        "pb": pb,
        "pePercentile5y": "数据缺失(East Money datacenter无历史分位端点)",
        "pbPercentile5y": "数据缺失",
        "relativeToPeers": "数据缺失(无同业对比端点)",
        "verdict": ""
    }

    # Red Flags
    redFlags = []

    # Hard red flags
    if d['roe'] < -20:
        redFlags.append({"flag": "ROE巨亏", "severity": "hard", "threshold": "ROE<-20%", "actual": f"{d['roe']}%", "action": "剔除"})
    elif d['roe'] < 0:
        redFlags.append({"flag": "ROE亏损", "severity": "hard", "threshold": "ROE<0%", "actual": f"{d['roe']}%", "action": "剔除"})

    if d['debt_ratio'] > 90:
        redFlags.append({"flag": "资产负债率极高(>90%)", "severity": "hard", "threshold": ">90%", "actual": f"{d['debt_ratio']}%", "action": "剔除"})

    # Negative interest coverage only hard flag if also losing money
    if d.get('interest_coverage') is not None and d['interest_coverage'] < 0 and net_profit_yi <= 0:
        redFlags.append({"flag": "利息保障倍数为负(亏损企业无法偿息)", "severity": "hard", "threshold": ">0", "actual": str(round(d['interest_coverage'], 2)), "action": "剔除"})

    if d['price'] > 40:
        redFlags.append({"flag": "股价超1w账户上限(>40元)", "severity": "hard", "threshold": "<=40元", "actual": f"{price}元", "action": "剔除"})

    # Soft warnings
    if d.get('non_recurring_ratio') is not None and d['non_recurring_ratio'] > 80:
        redFlags.append({"flag": "非经常性损益占比极高(扣非接近亏损)", "severity": "soft", "threshold": "<80%", "actual": f"{d['non_recurring_ratio']}%", "action": "降权"})
    elif d.get('non_recurring_ratio') is not None and d['non_recurring_ratio'] > 50:
        redFlags.append({"flag": "非经常性损益占比偏高(>50%)", "severity": "soft", "threshold": "<50%", "actual": f"{d['non_recurring_ratio']}%", "action": "降权"})

    if d.get('cf_ratio') is not None and d['cf_ratio'] < 0:
        redFlags.append({"flag": "经营现金流为负", "severity": "soft", "threshold": ">0", "actual": str(round(d['cf_ratio'], 2)), "action": "降权"})

    if pe and pe > 200:
        redFlags.append({"flag": "PE极高(>200x)", "severity": "soft", "threshold": "<200", "actual": f"{pe}x", "action": "降权"})
    elif pe and pe > 80:
        redFlags.append({"flag": "PE偏高(>80x)", "severity": "soft", "threshold": "<80", "actual": f"{pe}x", "action": "降权"})

    if d['roe'] < 5 and d['roe'] > 0:
        redFlags.append({"flag": "ROE偏低(<5%)", "severity": "soft", "threshold": ">5%", "actual": f"{d['roe']}%", "action": "降权"})

    if d['revenue_growth'] < -15:
        redFlags.append({"flag": "营收大幅下滑(<-15%)", "severity": "soft", "threshold": ">-15%", "actual": f"{d['revenue_growth']}%", "action": "降权"})

    if d['profit_growth'] < -50:
        redFlags.append({"flag": "净利大幅下滑(<-50%)", "severity": "soft", "threshold": ">-50%", "actual": f"{d['profit_growth']}%", "action": "降权"})

    if d['debt_ratio'] > 65:
        redFlags.append({"flag": "资产负债率偏高(>65%)", "severity": "soft", "threshold": "<65%", "actual": f"{d['debt_ratio']}%", "action": "降权"})

    # Determine verdict
    hard_flags = [f for f in redFlags if f['severity'] == 'hard']
    soft_flags = [f for f in redFlags if f['severity'] == 'soft']

    if hard_flags:
        verdict = "剔除"
        reason = "; ".join([f['flag'] for f in hard_flags])
    elif soft_flags:
        verdict = "降权"
        reason = "; ".join([f['flag'] for f in soft_flags[:3]])
    else:
        verdict = "通过"
        reason = "财务指标健康,无明显红旗"

    financials['verdict'] = verdict
    valuation['verdict'] = verdict

    summary = f"{name}({sector}): {verdict} | PE={pe}x PB={pb} ROE={d['roe']}% | {reason}"

    results.append({
        "code": sym,
        "name": name,
        "price": price,
        "sector": sector,
        "entryType": entry,
        "financials": financials,
        "valuation": valuation,
        "redFlags": redFlags,
        "verdict": verdict,
        "summary": summary,
    })

# Sort
verdict_order = {"剔除": 0, "降权": 1, "通过": 2}
results.sort(key=lambda x: verdict_order.get(x['verdict'], 3))

reject = sum(1 for r in results if r['verdict'] == '剔除')
downgrade = sum(1 for r in results if r['verdict'] == '降权')
pass_ = sum(1 for r in results if r['verdict'] == '通过')

for r in results:
    print(f"[{r['verdict']}] {r['name']}({r['code']}): {r['summary']}")

print(f"\n剔除: {reject}, 降权: {downgrade}, 通过: {pass_}, 总计: {len(results)}")

output = {
    "runId": "20260721_short-term-picks",
    "asOf": "20260721",
    "goal": "short-term-picks",
    "agent": "fundamentals-analyst",
    "fetchedAt": "20260721",
    "dataSource": {
        "primary": "East Money datacenter (RPT_F10_FINANCE_MAINFINADATA) via HTTPS verify=False",
        "priceSource": "cn_fetch.py (Tencent HTTP qt.gtimg.cn)",
        "pePbSource": "计算值: price / (net_profit/total_shares) 和 price / BPS",
        "mcpStatus": "iFind/Wind/AkShare MCP三路SSL全挂",
        "missingData": ["PE/PB 5年历史分位", "商誉/净资产", "控股股东质押比例", "同业对比估值"],
        "dataQuality": "FY2025年报数据(部分为Q1 2026年化); 价格已通过cn_fetch.py Tencent HTTP验证"
    },
    "priceVerification": {
        "note": "技术流动性层价格估算存在显著偏差,cn_fetch.py实际价格验证如下",
        "over40yuan": [
            {"code": "002156", "name": "通富微电", "estimated": 32.50, "actual": 69.30, "deviation": "+113.2%"},
            {"code": "600584", "name": "长电科技", "estimated": 38.00, "actual": 84.69, "deviation": "+122.9%"},
            {"code": "300236", "name": "上海新阳", "estimated": 39.00, "actual": 93.51, "deviation": "+139.8%"},
        ],
        "significantDeviation": [
            {"code": "300068", "name": "南都电源", "estimated": 15.00, "actual": 4.03, "deviation": "-73.1%"},
            {"code": "002079", "name": "苏州固锝", "estimated": 18.00, "actual": 9.08, "deviation": "-49.6%"},
            {"code": "300607", "name": "拓斯达", "estimated": 17.00, "actual": 30.50, "deviation": "+79.4%"},
            {"code": "002747", "name": "埃斯顿", "estimated": 19.50, "actual": 33.43, "deviation": "+71.4%"},
        ]
    },
    "data": {
        "stocks": results,
        "summary": {
            "total": len(results),
            "reject": reject,
            "downgrade": downgrade,
            "pass": pass_,
        }
    },
    "summary": f"财务排雷完成: 剔除{reject}只(硬红旗+价格超限), 降权{downgrade}只(软警示), 通过{pass_}只(财务健康). iFind/Wind/AkShare MCP全挂SSL,数据源为East Money datacenter+cn_fetch.py价格验证. PE/PB历史分位/商誉/质押数据缺失.",
    "keyFields": {
        "rejectCodes": ",".join([r['code'] for r in results if r['verdict'] == '剔除']),
        "downgradeCodes": ",".join([r['code'] for r in results if r['verdict'] == '降权']),
        "passCodes": ",".join([r['code'] for r in results if r['verdict'] == '通过']),
        "hardRedFlags": "南都电源(ROE-97%+负债92%+利息保障-7.1); 机器人(ROE-9.3%+利息保障-5.6); 通富微电/长电科技/上海新阳(价格>40元1w账户不可配); 格科微(扣非亏损+利息保障1.03); 屹唐股份(经营现金流为负)",
        "dataQuality": "iFind/Wind/AkShare三路SSL全挂; 财务数据=East Money datacenter HTTPS verify=False; 价格=cn_fetch.py Tencent HTTP; PE/PB=计算值; 商誉/质押/历史分位=数据缺失",
        "priceVerification": "3只价格超40元(通富微电69.30/长电科技84.69/上海新阳93.51)需重新评估1w账户可配性; 技术流动性层价格估算存在显著偏差"
    }
}

with open('data/runs/20260721_short-term-picks/fundamentals-analyst.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\nOutput written to data/runs/20260721_short-term-picks/fundamentals-analyst.json")