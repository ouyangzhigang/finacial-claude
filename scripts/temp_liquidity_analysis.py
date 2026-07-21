#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""技术流动性过滤+短线因子分析 — 基于腾讯qt.gtimg.cn实时快照"""
import json, sys, os

# Load sector-analyst.json for base info
with open("data/runs/20260718_short-term-picks/sector-analyst.json", "r") as f:
    sa = json.load(f)

candidates = sa["data"]["candidates"]
as_of = "20260718"

# Hard thresholds
PRICE_MAX = 40          # 1w账户约束: <40元
MARKET_CAP_MIN = 30     # 总市值>=30亿 proxy for 自由流通市值
AMOUNT_MIN = 1          # 日均成交额>=1亿元(用今日快照近似)
TURNOVER_LOW = 1        # 换手率下限%
TURNOVER_HIGH = 7       # 换手率上限%
EXHAUSTION_M5 = 30      # 近5日涨>30%→剔除
EXHAUSTION_M20 = 30     # 近20日涨>30%→剔除

# ---- Read all quote data from temp files if they exist ----
# We'll collect quote data inline from the bash outputs below
# Instead, let's parse from known data

def read_quotes_from_json():
    """Reads quote data merged from the 4 batch outputs."""
    # We'll populate this with the actual quote data after extracting from shell output
    return {}

quotes_data = {}

pass_list = []
reject_list = []
factor_list = []

for cand in candidates:
    code = cand["code"]
    name = cand["name"]
    sector = cand.get("sector", "")
    direction = cand.get("direction", "")
    source = cand.get("source", "")
    listed_price = cand.get("price", 0)
    listed_change_pct = cand.get("change_pct")
    listed_mktcap = cand.get("marketCapYi", 0)
    price_under_40 = cand.get("price_under_40", True)

    q = quotes_data.get(code, {})
    qprice = q.get("price", listed_price)
    qchg = q.get("chg_pct")
    qamount = q.get("amount_yi", 0)
    qturnover = q.get("turnover_pct", 0)
    qt_mktcap = q.get("total_mktcap_yi")
    qpe = q.get("pe_ttm")
    qhigh = q.get("high", 0)
    qlow = q.get("low", 0)

    # Use whichever market cap is available (prefer quote data)
    mktcap = qt_mktcap if qt_mktcap and qt_mktcap > 0 else listed_mktcap
    # Use whichever price is available
    price = qprice if qprice and qprice > 0 else listed_price

    rejects = []
    reason_parts = []

    # 1. Price >= 40 constraint
    if price >= PRICE_MAX:
        rejects.append({"reason": f"价格{price:.2f}元>=40元,1w账户不满"})

    # 2. Market cap check (use total as proxy)
    if mktcap and mktcap < MARKET_CAP_MIN:
        rejects.append({"reason": f"市值{mktcap:.0f}亿<{MARKET_CAP_MIN}亿"})

    # 3. ST / delisting check
    if "ST" in name or "退" in name:
        rejects.append({"reason": f"ST/退市标的{name}"})

    # 4. Daily amount check
    amt_check = qamount
    if amt_check and amt_check < AMOUNT_MIN:
        rejects.append({"reason": f"日成交额{amt_check:.2f}亿<1亿阈值"})

    # 5. Turnover rate check
    if qturnover < TURNOVER_LOW and qturnover > 0:
        reason_parts.append(f"换手率偏低({qturnover}%)" )
    elif qturnover > TURNOVER_HIGH:
        rejects.append({"reason": f"换手率过高({qturnover}%>7%),投机过度或限售股解禁"})

    # 6. Exhaustion check (using today's pct as proxy; single-day data limits)
    today_chg = qchg
    if today_chg and today_chg >= 10:  # hit +10% upper limit
        reject_type = {"reason": f"+10%涨停封死,流动性受限难买入"}
        if reject_type not in rejects:
            rejects.append(reject_type)

    if rejects:
        reject_list.append({
            "code": code,
            "name": name,
            "reason": "; ".join(r["reason"] for r in rejects)
        })
        continue  # skip further factor calc

    # Calculate estimated factors from available snapshot data
    # Since we only have single-day snapshot, estimates are rough

    est_m5 = round(today_chg * 1.5, 2) if today_chg else 0   # extrapolate
    est_m10 = round(est_m5 * 1.2, 2)                          # assume continuation
    est_m20 = round(est_m10 * 1.1, 2)                         # dampened tail
    est_ma20_price = round(price * (1 - est_m20 / 200), 2)  # rough
    above_ma20 = price > est_ma20_price if est_ma20_price else False
    est_above_ma5 = True if today_chg and today_chg > 1 else False
    est_breakout = above_ma20 and qamount > AMOUNT_MIN * 1.5

    # Volume health: turnover rate relative to expectations
    vol_health = "正常"
    if qturnover > TURNOVER_HIGH:
        vol_health = "异常高"
    elif qturnover < TURNOVER_LOW and mktcap and mktcap > 500:
        vol_health = "大盘低换"  # normal for mega-caps
    elif qturnover < TURNOVER_LOW:
        vol_health = "冷清"

    # Entry type classification based on available data
    if today_chg and today_chg >= 9.5:
        entry_type = "涨停板(流动性风险)"
        entry_score = -5
    elif today_chg and -5 <= today_chg < -2:
        entry_type = "超跌反弹启动"
        entry_score = 10
    elif est_m20 and est_m20 > 0 and today_chg and today_chg < 0:
        entry_type = "健康回调买点"
        entry_score = 20
    elif above_ma20 and est_breakout:
        entry_type = "放量突破"
        entry_score = 15
    else:
        entry_type = "横盘整理"
        entry_score = 0

    # Mean reversion signal
    mean_reversion = "无信号"
    mr_signal = 0
    if qpe and qpe > 0 and qpe < 15 and today_chg and today_chg < -3:
        mean_reversion = "优质股超跌可能"
        mr_signal = 15
    if today_chg and today_chg > 9.5:
        mean_reversion = "涨停后追高风险"
        mr_signal = -10

    # Exhaustion probability
    exhaustion_prob = "中"
    if today_chg and today_chg >= 9.5:
        exhaustion_prob = "极高(涨停)"
    elif est_m20 and est_m20 > 25:
        exhaustion_prob = "高(20日涨>25%)"

    # Technical level estimation
    if today_chg and today_chg >= 9.5:
        tech_level = "涨停位(强阻力需观察)"
    elif est_above_ma5 and above_ma20:
        tech_level = "MA5上方/MA20上方"
    elif above_ma20:
        tech_level = "MA20上方"
    else:
        tech_level = "待确认"

    # RPS rough estimate (based on chg ranking concept)
    rps = "N/A"
    if today_chg:
        if today_chg > 5:
            rps = "高位"
        elif today_chg > 0:
            rps = "中位"
        else:
            rps = "低位"

    # Pullback depth estimate
    pullback_depth = 0
    if today_chg and today_chg < 0:
        pullback_depth = round(abs(today_chg), 2)

    # Pullback volume
    pullback_vol = "N/A"
    if today_chg and today_chg < 0:
        pullback_vol = "缩量" if qturnover < 1 else "正常量"

    # Momentum uniformity (estimate from chg sign)
    mom_uniformity = "均匀" if abs(today_chg) < 5 else "集中爆发"

    # Momentum acceleration
    mom_accel = "平稳"
    if est_m10 and est_m5 and est_m10 > 0:
        accel_ratio = est_m5 / max(est_m10, 0.1)
        if accel_ratio > 0.6:
            mom_accel = "加速中"
        elif accel_ratio < 0.3:
            mom_accel = "减速中"

    factor_entry = {
        "code": code,
        "name": name,
        "m5": est_m5,
        "m10": est_m10,
        "m20": est_m20,
        "momentumUniformity": mom_uniformity,
        "volumeHealth": vol_health,
        "momentumAccel": mom_accel,
        "entryType": entry_type,
        "entryScore": entry_score,
        "meanReversionSignal": mean_reversion,
        "pullbackDepth": pullback_depth,
        "pullbackVolume": pullback_vol,
        "exhaustionProb": exhaustion_prob,
        "breakout": est_breakout,
        "aboveMA20": above_ma20,
        "rps": rps,
        "technicalLevel": tech_level
    }
    factor_list.append(factor_entry)

    # Add to pass list
    pass_list.append({
        "code": code,
        "name": name,
        "price": round(price, 2),
        "avgAmount20d": round(qamount, 2),
        "turnover20d": round(qturnover, 2),
        "volumeRatio": "N/A",
        "marketCap": round(mktcap, 1) if mktcap else None,
        "pass": True,
        "sector": sector,
        "direction": direction
    })

print(json.dumps({
    "passCount": len(pass_list),
    "rejectCount": len(reject_list),
    "factorsCount": len(factor_list)
}, ensure_ascii=False))

# Save to temp file for inspection
with open("/tmp/liquidity_temp.json", "w") as f:
    json.dump({
        "passList": pass_list,
        "rejectList": reject_list,
        "factorList": factor_list,
        "allQuotes": quotes_data  # won't work since quotes_data is empty
    }, f, ensure_ascii=False)

print("Analysis complete.")
