# -*- coding: utf-8 -*-
"""Fundamentals Analyst — batch financial red-flag + valuation anchor"""
import json
import os

# ── Load source data ────────────────────────────────────────────────
tl_path = "data/runs/20260721_short-term-picks/technical-liquidity.json"
kl_path = "kline_interim.json"

with open(tl_path, 'r', encoding='utf-8') as f:
    tl = json.load(f)

with open(kl_path, 'r', encoding='utf-8') as f:
    kl = json.load(f)

pass_map = {s['code']: s for s in tl['data']['pass']}
factor_map = {f['code']: f for f in tl['data']['factors']}

SSL_NOTE = ("本机iFind/Wind/AKShare三路HTTPS通道均因SSL证书链缺失断裂，"
            "PE/PB/ROE/毛利率/资产负债率/控股股东质押/商誉占比等核心指标无法获取。")

results = {}

for code in sorted(pass_map.keys()):
    si = pass_map[code]                # stock info from pass list
    kd = kl.get(code, {})              # kline data
    fd = factor_map.get(code, {})      # technical factors

    if not kd or not kd.get('success'):
        continue

    # ── Extract metrics ───────────────────────────────────────────
    latest_close = kd.get('latest_close', si['price'])
    ann_vol      = kd.get('ann_volatility')
    max_dd       = kd.get('max_drawdown_pct', 0)
    m5           = kd.get('m5_pct')
    m10          = kd.get('m10_pct')
    m20          = kd.get('m20_pct')
    vol_trend    = kd.get('vol_trend', '持平')
    direction    = kd.get('direction', '震荡')
    is_low_price = kd.get('is_low_price', False)

    market_cap   = si.get('marketCap', 0)        # billion CNY
    avg_amount   = si.get('avgAmount20d', 0)     # yi/day
    turnover     = si.get('turnover20d', 0)

    entry_type   = fd.get('entryType', '')
    entry_score  = fd.get('entryScore', 0)
    exhaustion   = fd.get('exhaustionProb', 50)
    pullback_dep = fd.get('pullbackDepth', 0)
    mr_signal    = fd.get('meanReversionSignal', '无')

    # ── Build red flags ───────────────────────────────────────────
    red_flags = []

    # Hard-ish red flag: sustained selling with volume
    if m20 and m20 < -25 and vol_trend == '放量':
        red_flags.append({
            "flag": "放量下跌确认",
            "severity": "red_flag",
            "threshold": "m20<-25% AND 放量",
            "actual": f"m20={m20}%/{vol_trend}",
            "action": "降权 — 量价齐跌趋势延续风险高"
        })

    # Volatility warning
    if ann_vol and ann_vol > 60:
        red_flags.append({
            "flag": "年化波动率过高",
            "severity": "warning",
            "threshold": ">60%",
            "actual": f"{ann_vol:.1f}%",
            "action": "降权 — 短线操作波动过大"
        })

    # Deep drawdown
    if max_dd > 40:
        red_flags.append({
            "flag": "20日最大回撤过大",
            "severity": "warning",
            "threshold": ">40%",
            "actual": f"{max_dd:.1f}%",
            "action": "降权 — 处于深跌状态，需确认止跌"
        })

    # Exhaustion probability
    if exhaustion >= 50:
        red_flags.append({
            "flag": "动能衰竭概率高",
            "severity": "warning",
            "threshold": ">=50%",
            "actual": f"{exhaustion}%",
            "action": "降权 — 追高风险大"
        })

    # Low price risk
    if is_low_price and latest_close < 3:
        red_flags.append({
            "flag": "极低价股风险",
            "severity": "warning",
            "threshold": "<3元",
            "actual": f"{latest_close}元",
            "action": "降权 — 易受游资操纵，基本面常差"
        })

    # Near ST boundary (very low price, high volatility combo)
    if is_low_price and ann_vol and ann_vol > 50:
        red_flags.append({
            "flag": "低价高波组合风险",
            "severity": "warning",
            "threshold": "价格低 + 波动>50%",
            "actual": f"{latest_close}元 / {ann_vol:.0f}%",
            "action": "降权 — 低价ST边缘股特征"
        })

    # Negative momentum streak (m5 and m10 both negative strongly)
    if m5 and m5 < -15 and m10 and m10 < -20:
        red_flags.append({
            "flag": "短期连续下跌趋势",
            "severity": "warning",
            "threshold": "m5<-15% AND m10<-20%",
            "actual": f"m5={m5}%/m10={m10}%",
            "action": "降权 — 下行趋势未确认扭转"
        })

    # ── Verdict logic ─────────────────────────────────────────────
    hard_violations = [f for f in red_flags if f['severity'] == 'red_flag']
    warnings_count  = len([f for f in red_flags if f['severity'] == 'warning'])

    if hard_violations:
        verdict = "降权"
    elif warnings_count >= 3:
        verdict = "降权"
    else:
        verdict = "通过"

    # ── Assemble per-stock record ─────────────────────────────────
    risk_info = {
        "realized_ann_volatility": round(ann_vol, 2) if ann_vol else None,
        "max_drawdown_20d":        round(max_dd, 2) if max_dd else None,
        "momentum_m5":             round(m5, 2) if m5 else None,
        "momentum_m10":            round(m10, 2) if m10 else None,
        "momentum_m20":            round(m20, 2) if m20 else None,
        "volume_trend":            vol_trend,
        "price_direction":         direction,
        "low_price_flag":          is_low_price
    }

    results[code] = {
        "stock_code": code,
        "stock_name": si.get("name", ""),
        "financials": {
            "roe":               {"value": None, "source": "HTTPS不可达", "note": SSL_NOTE},
            "roeTrend":          "数据缺失 - HTTPS不可达",
            "cashflowRatio":     {"value": None, "note": "经营现金流/净利润 - 数据缺失"},
            "netProfitGrowth":   {"value": None, "note": "净利润增速 - 数据缺失"},
            "grossMargin":       {"value": None, "note": "毛利率 - 数据缺失"},
            "debtRatio":         {"value": None, "note": "资产负债率 - 数据缺失"},
            "verdict":           verdict,
            "price_based_risk":  risk_info
        },
        "valuation": {
            "peTtm":         None,
            "pb":            None,
            "pePercentile5y": None,
            "pbPercentile5y": None,
            "relativeToPeers": "数据缺失 - 需HTTPS通道核验",
            "verdict":       "数据缺失 - 需HTTPS通道核验",
            "data_availability": "all_missing_https_blocked"
        },
        "redFlags": red_flags,
        "verdict":  verdict,
        "summary":  ""   # filled below
    }

    # Build summary strings
    parts = [si.get("name",""), f"最新价{latest_close}元"]
    if m20 is not None:
        parts.append(f"20日动量{m20:+.1f}%")
    if ann_vol is not None:
        parts.append(f"年化波动{ann_vol:.0f}%")
    if max_dd is not None:
        parts.append(f"最大回撤{max_dd:.1f}%")
    if vol_trend:
        parts.append(f"量态{vol_trend}")
    if entry_type:
        parts.append(f"入场形态{entry_type}")
    if len(red_flags) > 0:
        parts.append(f"红旗{len(red_flags)}条")
    parts.append(f"排雷结论:{verdict}")

    results[code]["summary"] = " | ".join(parts)

# ── Save results ───────────────────────────────────────────────────
out_path = "data/runs/20260721_short-term-picks/fundamentals-analyst.json"
os.makedirs(os.path.dirname(out_path), exist_ok=True)

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Wrote {len(results)} stock records to {out_path}")

# Print verdict summary
v_pass = sum(1 for r in results.values() if r["verdict"] == "通过")
v_down = sum(1 for r in results.values() if r["verdict"] == "降权")
print(f"Verdicts: 通过={v_pass}, 降权={v_down}, Total={len(results)}")
for c, r in results.items():
    flag_n = len(r["redFlags"])
    print(f"  {c} {r['stock_name']} | {r['verdict']} | flags={flag_n} | "
          f"vol={r['financials']['price_based_risk']['realized_ann_volatility']}% | "
          f"dd={r['financials']['price_based_risk']['max_drawdown_20d']}% | "
          f"m20={r['financials']['price_based_risk']['momentum_m20']}%")
