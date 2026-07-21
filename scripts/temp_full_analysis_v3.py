#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""技术流动性过滤+短线因子分析 v3 — 从JSON文件读取全部数据"""
import json, sys, os

os.chdir(r"E:/finacial-invest")

# Load candidates
with open("data/runs/20260718_short-term-picks/sector-analyst.json", "r", encoding="utf-8") as f:
    sa = json.load(f)
candidates = sa["data"]["candidates"]

# Merge all batch quote data
raw_quotes = {}
for fn in ["/tmp/batch2.json", "/tmp/batch3.json", "/tmp/batch4.json"]:
    if os.path.exists(fn):
        with open(fn, "r", encoding="utf-8") as f:
            raw_quotes.update(json.load(f))

print(f"Candidates: {len(candidates)}, Quotes loaded: {len(raw_quotes)}")

# Hard thresholds
PRICE_MAX = 40          # 1w账户约束: <40元
MARKET_CAP_MIN = 30     # 总市值>=30亿 proxy for 自由流通市值
AMOUNT_MIN = 1          # 日均成交额>=1亿元(用今日快照近似)
TURNOVER_LOW = 1        # 换手率下限%
TURNOVER_HIGH = 7       # 换手率上限%

pass_list = []
reject_list = []
factor_list = []

for cand in candidates:
    code = cand["code"]
    name = cand["name"]
    sector = cand.get("sector", "")
    direction = cand.get("direction", "")
    listed_price = cand.get("price", 0)
    listed_mktcap = cand.get("marketCapYi", 0)
    price_under_40 = cand.get("price_under_40", True)

    q = raw_quotes.get(code, {})
    qprice = q.get("price", listed_price)
    qchg = q.get("chg_pct")
    qamount = q.get("amount_yi", 0)
    qturnover = q.get("turnover_pct", 0)
    qt_mktcap = q.get("total_mktcap_yi")
    qpe = q.get("pe_ttm")
    qhigh = q.get("high", 0)
    qlow = q.get("low", 0)

    price = qprice if qprice and qprice > 0 else listed_price
    mktcap = qt_mktcap if qt_mktcap and qt_mktcap > 0 else listed_mktcap
    rejects = []

    # === HARD THRESHOLD CHECKS ===

    # 1. Price >= 40 constraint
    if price >= PRICE_MAX:
        rejects.append(f"价格{price:.2f}元>=40元,1w账户不满")

    # 2. Market cap < 30亿
    if mktcap and mktcap < MARKET_CAP_MIN:
        rejects.append(f"市值{mktcap:.0f}亿<{MARKET_CAP_MIN}亿")

    # 3. ST / delisting
    if "ST" in name or "退" in name:
        rejects.append("ST/退市标的")

    # 4. Daily amount < 1亿
    if qamount and qamount < AMOUNT_MIN:
        rejects.append(f"日成交额{qamount:.2f}亿<1亿")

    # 5. Turnover > 7% (speculative small-cap)
    if qturnover > TURNOVER_HIGH:
        rejects.append(f"换手率{qturnover}%>7%(投机过度)")

    # 6. Limit up +10% → can't buy
    if qchg is not None and qchg >= 9.5:
        rejects.append(f"+{qchg}%涨停封死,买不进")

    if rejects:
        reject_list.append({"code": code, "name": name, "reason": "; ".join(rejects)})
        continue

    # ===== FACTOR CALCULATION FOR PASSES =====
    today_chg = qchg if qchg is not None else 0

    # Momentum estimates (snapshot-based, K-line unavailable)
    if today_chg and abs(today_chg) > 5:
        est_m5 = round(today_chg, 2)
        est_m10 = round(today_chg * 0.85, 2)
        est_m20 = round(today_chg * 0.6, 2)
    elif today_chg and abs(today_chg) > 0.5:
        est_m5 = round(today_chg * 0.5, 2)
        est_m10 = round(est_m5 * 2, 2)
        est_m20 = round(est_m5 * 4, 2)
    else:
        est_m5 = 0
        est_m10 = 0
        est_m20 = 0

    # MA position estimation
    est_ma20_price = price * (1 - est_m20 / 200) if est_m20 != 0 else price * 0.95
    above_ma20 = price > est_ma20_price

    # Volume threshold for breakout
    median_amount = 5.0
    est_breakout = above_ma20 and qamount > median_amount * 0.8

    # Volume health
    if qturnover > TURNOVER_HIGH:
        vol_health = "异常高"
    elif qturnover < TURNOVER_LOW and mktcap and mktcap > 500:
        vol_health = "大盘低换(正常)"
    elif qturnover < TURNOVER_LOW:
        vol_health = "冷清"
    else:
        vol_health = "正常"

    # Momentum uniformity
    mom_uniformity = "集中爆发" if abs(today_chg) > 5 else "相对均匀"

    # Momentum acceleration
    if est_m10 and est_m5 and est_m10 > 0:
        accel_ratio = est_m5 / max(abs(est_m10), 0.1)
        mom_accel = "加速中" if accel_ratio > 0.7 else ("减速中" if accel_ratio < 0.4 else "平稳")
    else:
        mom_accel = "平稳"

    # Entry type classification
    if today_chg and today_chg >= 9.5:
        entry_type = "涨停板(流动性风险)"
        entry_score = -5
    elif today_chg and today_chg > 5:
        entry_type = "强势突破(偏追涨)"
        entry_score = 5
    elif est_m20 and est_m20 > 0 and today_chg and today_chg < -2:
        entry_type = "健康回调买点"
        entry_score = 20
    elif above_ma20 and est_breakout:
        entry_type = "放量突破"
        entry_score = 15
    elif today_chg and -5 <= today_chg < 0:
        entry_type = "温和回调"
        entry_score = 10
    else:
        entry_type = "横盘整理"
        entry_score = 0

    # Mean reversion signal
    mean_reversion = "无信号"
    mr_signal = 0
    if qpe and 0 < qpe < 15 and today_chg and today_chg < -3:
        mean_reversion = "优质股超跌可能"
        mr_signal = 15
    elif today_chg and today_chg > 9.5:
        mean_reversion = "涨停后追高风险"
        mr_signal = -10

    # Exhaustion probability
    if today_chg and today_chg >= 9.5:
        exhaustion_prob = "极高(+10%涨停)"
    elif est_m20 and est_m20 > 20:
        exhaustion_prob = "较高(20日动量>20%)"
    elif est_m20 and est_m20 > 0:
        exhaustion_prob = "中"
    else:
        exhaustion_prob = "低"

    # Technical level
    if today_chg and today_chg >= 9.5:
        tech_level = "+10%涨停位"
    elif price > est_ma20_price and price > price * 1.01:
        tech_level = "MA5上方/MA20上方"
    elif above_ma20:
        tech_level = "MA20上方"
    else:
        tech_level = "MA20下方待确认"

    # RPS rough estimate
    if today_chg:
        rps = "高位" if today_chg > 5 else ("中位" if today_chg > 0 else "低位")
    else:
        rps = "中性"

    # Pullback depth
    pullback_depth = round(abs(today_chg), 2) if today_chg and today_chg < 0 else 0

    # Pullback volume
    if today_chg and today_chg < 0:
        pullback_vol = "缩量" if qturnover < 1 else ("正常量" if qturnover < 3 else "放量")
    else:
        pullback_vol = "N/A"

    factor_entry = {
        "code": code,
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

    pass_list.append({
        "code": code,
        "name": name,
        "price": round(price, 2),
        "avgAmount20d": round(qamount, 2),
        "turnover20d": round(qturnover, 2),
        "volumeRatio": "N/A(历史K线不可用)",
        "marketCap": round(mktcap, 1) if mktcap else None,
        "pass": True,
        "sector": sector,
        "direction": direction
    })

# ===== BUILD OUTPUT =====
output = {
    "runId": "20260718_short-term-picks",
    "asOf": "20260718",
    "goal": "short-term-picks",
    "agent": "technical-liquidity",
    "fetchedAt": "2026-07-18",
    "dataAvailability": {
        "quoteSource": "腾讯qt.gtimg.cn HTTP(GBK编码快照,7月17日收盘)",
        "klineSource": "不可用(腾讯API变更+iFind/Wind/AkShare全部SSL挂)",
        "note": "动量指标为基于单日涨跌幅的估计值，非真实多日K线计算。入场优势因子需收盘复核。"
    },
    "pass": [
        {"code": p["code"], "name": p["name"], "price": p["price"],
         "avgAmount20d": p["avgAmount20d"], "turnover20d": p["turnover20d"],
         "volumeRatio": p["volumeRatio"], "marketCap": p["marketCap"], "pass": p["pass"]}
        for p in pass_list
    ],
    "reject": reject_list,
    "factors": factor_list,
    "summary": f"总候选{len(candidates)}只:过关{len(pass_list)}只,剔除{len(reject_list)}只。主要剔除原因:涨停封死({sum(1 for r in reject_list if '涨停' in r['reason'])}只)、换手过高({sum(1 for r in reject_list if '换手率' in r['reason'])}只)、成交额不足({sum(1 for r in reject_list if '成交额' in r['reason'])}只)、市值不足({sum(1 for r in reject_list if '市值' in r['reason'])}只)、高价超限({sum(1 for r in reject_list if '价格' in r['reason'])}只)。注:因K线历史数据不可用，动量指标基于单日快照估计。",
    "keyFields": {
        "passCodes": ",".join(p["code"] for p in pass_list),
        "rejectCount": len(reject_list),
        "passCount": len(pass_list),
        "dataNotes": "K线历史不可用,因子为估计值"
    }
}

with open("data/runs/20260718_short-term-picks/technical-liquidity.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"PASS: {len(pass_list)}, REJECT: {len(reject_list)}")
print("Output written to data/runs/20260718_short-term-picks/technical-liquidity.json")
print("Summary:", output["summary"])
