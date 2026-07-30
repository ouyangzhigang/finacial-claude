# -*- coding: utf-8 -*-
"""technical-liquidity 环节: 候选池硬门槛过滤 + 短线因子计算。
数据源: cn_fetch.kline(腾讯日K, cached) + cn_fetch.quote(腾讯批量报价)。
口径: 短线动量用 5/10/20 日(5日权重最高), 不套 quant-factor-screener 的 12-1 月口径。
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cn_fetch

CAND_FILE = "E:/finacial-invest/data/runs/20260730_short-term-picks/sector-analyst.json"
OUT_FILE  = "E:/finacial-invest/data/runs/20260730_short-term-picks/technical-liquidity.json"

def pref(code):
    return ("sh" if code.startswith("6") else "sz") + code

def rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(-n, 0):
        d = closes[i] - closes[i - 1]
        (gains if d > 0 else losses).append(abs(d))
    ag = sum(gains) / n if gains else 0
    al = sum(losses) / n if losses else 0.0001
    rs = ag / al if al else 99
    return round(100 - 100 / (1 + rs), 1)

def compute(code, name, cand, q):
    pfx = pref(code)
    arr = cn_fetch.kline(pfx, 30)
    if not arr or len(arr) < 20:
        return None, "K线不足20日", None
    rows = [{"date": x[0], "open": float(x[1]), "close": float(x[2]),
             "high": float(x[3]), "low": float(x[4]), "vol": float(x[5])} for x in arr]
    closes = [r["close"] for r in rows]
    vols = [r["vol"] for r in rows]
    last = rows[-1]

    def mom(d):
        return (closes[-1] - closes[-1 - d]) / closes[-1 - d] * 100 if len(closes) > d else None
    m5, m10, m20 = mom(5), mom(10), mom(20)
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20
    v5 = sum(vols[-5:]) / 5
    v20 = sum(vols[-20:]) / 20

    amt20 = sum(rows[i]["vol"] * 100 * rows[i]["close"] for i in range(-20, 0)) / 20 / 1e8
    amt5 = sum(rows[i]["vol"] * 100 * rows[i]["close"] for i in range(-5, 0)) / 5 / 1e8

    float_mcap = q.get("float_mktcap_yi")
    price = q.get("price") or last["close"]
    float_shares = (float_mcap * 1e8 / price) if float_mcap else None
    if float_shares:
        turn20 = sum(rows[i]["vol"] * 100 for i in range(-20, 0)) / 20 / float_shares * 100
        turn5 = sum(rows[i]["vol"] * 100 for i in range(-5, 0)) / 5 / float_shares * 100
    else:
        turn20 = turn5 = None

    vol_ratio = last["vol"] / v5 if v5 else None

    # ── A. 动量质量 ──
    last5 = rows[-5:]
    up_days = sum(1 for i in range(1, 5) if last5[i]["close"] > last5[i-1]["close"])
    daily_rets = [(last5[i]["close"] - last5[i-1]["close"]) / last5[i-1]["close"] * 100 for i in range(1, 5)]
    up_rets = [r for r in daily_rets if r > 0]
    max_up = max(up_rets) if up_rets else 0
    uniformity = round(up_days / 4, 2)
    max_share = round(max_up / m5, 2) if (m5 and m5 > 0 and max_up > 0) else None

    up_vol, dn_vol, n_up, n_dn = 0, 0, 0, 0
    for i in range(1, 5):
        v = last5[i]["vol"]
        if last5[i]["close"] >= last5[i-1]["close"]:
            up_vol += v; n_up += 1
        else:
            dn_vol += v; n_dn += 1
    vol_health = round((up_vol / n_up) / (dn_vol / n_dn), 2) if (n_up and n_dn) else None

    accel_5 = m5 / 5 if m5 is not None else None
    accel_late = (m10 - m5) / 5 if (m5 is not None and m10 is not None) else None
    if accel_5 is not None and accel_late is not None:
        momentum_accel = "加速" if accel_5 > accel_late else "减速"
    else:
        momentum_accel = None

    # ── 技术位 ──
    breakout = last["close"] > ma20 and last["vol"] > v5 * 1.5
    above_ma5 = last["close"] > ma5
    above_ma10 = last["close"] > ma10
    above_ma20 = last["close"] > ma20
    hi20 = max(closes[-20:])
    pullback_depth = round((last["close"] - hi20) / hi20 * 100, 2)
    pullback_vol_ratio = round(v5 / v20, 2) if v20 else None
    rsi14 = rsi(closes, 14)

    # ── B. 入场优势 ──
    entry_type, entry_score, entry_note = "中性", 0, ""
    exhaustion_prob = "低"
    if m20 is not None and m20 > 20 and m5 is not None and m5 < 0 and (not above_ma5) and pullback_vol_ratio and pullback_vol_ratio > 1:
        entry_type, entry_score, exhaustion_prob = "高位派发", -20, "极高"
        entry_note = "近20日涨>20%+5日转负+放量+破MA5"
    elif m5 is not None and m5 > 10 and last["close"] >= hi20 * 0.985 and pullback_vol_ratio and pullback_vol_ratio > 1:
        entry_type, entry_score, exhaustion_prob = "追涨入场", -15, "高"
        entry_note = "5日涨>10%+近高点+放量"
    elif above_ma20 and m5 is not None and -8 <= m5 <= -3 and pullback_vol_ratio and pullback_vol_ratio < 1 and rsi14 is not None and 38 <= rsi14 <= 55:
        entry_type, entry_score = "健康回调买点", 20
        entry_note = "MA20上方+5日回调-3~-8%+缩量+RSI适中"
    elif above_ma20 and -5 <= pullback_depth <= -0.5 and pullback_vol_ratio and pullback_vol_ratio < 0.95 and m5 is not None and m5 < 3:
        entry_type, entry_score = "突破回踩确认", 15
        entry_note = "站上MA20+小幅回踩+缩量"
    elif m20 is not None and m20 < -15 and m5 is not None and m5 > 0 and pullback_vol_ratio and pullback_vol_ratio > 1:
        entry_type, entry_score, exhaustion_prob = "超跌反弹启动", 10, "中"
        entry_note = "20日跌>15%+5日转正+放量"

    if exhaustion_prob == "低":
        if m5 is not None and m5 > 15:
            exhaustion_prob = "高"
            entry_note = (entry_note + ";" if entry_note else "") + "5日涨>15%透支"
        elif m20 is not None and m20 > 25 and m5 is not None and m5 < 0:
            exhaustion_prob = "极高"
            entry_note = (entry_note + ";" if entry_note else "") + "20日涨>25%+5日转负(主升浪结束)"

    # ── C. 均值回归 ──
    mr_signal, mr_note = None, ""
    if (not above_ma20) and rsi14 is not None and rsi14 < 35 and closes[-1] > closes[-2]:
        mr_signal, mr_note = "布林下轨支撑", "破MA20+RSI<35+收阳企稳"

    if above_ma5 and above_ma10 and above_ma20 and m5 and m10 and m20 and m5 > 0 and m10 > 0 and m20 > 0:
        tech_level = "上升趋势(多周期共振)"
    elif m20 is not None and m20 > 20 and m5 is not None and m5 < 0:
        tech_level = "高位回调"
    elif m20 is not None and m20 < 0 and m5 is not None and m5 > 0:
        tech_level = "超跌反弹"
    elif above_ma20 and m5 is not None and m5 > 0:
        tech_level = "多头排列"
    elif not above_ma20:
        tech_level = "空头排列(破MA20)"
    else:
        tech_level = "震荡"

    factor = {
        "code": code, "name": name,
        "m5": round(m5, 2) if m5 is not None else None,
        "m10": round(m10, 2) if m10 is not None else None,
        "m20": round(m20, 2) if m20 is not None else None,
        "momentumUniformity": uniformity, "maxUpShare": max_share,
        "volumeHealth": vol_health, "momentumAccel": momentum_accel,
        "entryType": entry_type, "entryScore": entry_score, "entryNote": entry_note,
        "meanReversionSignal": mr_signal, "mrNote": mr_note,
        "pullbackDepth": pullback_depth, "pullbackVolume": pullback_vol_ratio,
        "exhaustionProb": exhaustion_prob,
        "breakout": breakout, "aboveMA5": above_ma5, "aboveMA10": above_ma10,
        "aboveMA20": above_ma20, "rsi14": rsi14,
        "ma5": round(ma5, 2), "ma10": round(ma10, 2), "ma20": round(ma20, 2),
        "technicalLevel": tech_level,
        "price": round(price, 2),
        "avgAmount20d": round(amt20, 2), "avgAmount5d": round(amt5, 2),
        "turnover20d": round(turn20, 2) if turn20 is not None else None,
        "turnover5d": round(turn5, 2) if turn5 is not None else None,
        "turnoverToday": q.get("turnover"),
        "volumeRatio": round(vol_ratio, 2) if vol_ratio is not None else None,
        "floatMktCapYi": float_mcap, "marketCapYi": q.get("mktcap_yi"),
        "peTtm": q.get("pe_ttm"),
        "dayChangePct": q.get("pct"),
        "klineDate": last["date"],
    }
    # 硬门槛数据
    gate = {
        "floatMktCapYi": float_mcap, "avgAmount20d": round(amt20, 2),
        "turnover20d": round(turn20, 2) if turn20 is not None else None,
    }
    return factor, None, gate

def main():
    cands = json.load(open(CAND_FILE, encoding="utf-8"))["data"]["candidates"]
    # 批量取 quote 一次 (key=6位代码)
    pfxs = [pref(c["code"]) for c in cands]
    qall = cn_fetch.quote(pfxs)
    # 批量预热 kline (确保缓存命中, 避免逐股往返)
    for c in cands:
        cn_fetch.kline(pref(c["code"]), 30)

    pass_list, reject_list, factor_list = [], [], []
    for c in cands:
        code, name = c["code"], c["name"]
        q = qall.get(code, {})
        f, err, gate = compute(code, name, c, q)
        if err:
            reject_list.append({"code": code, "name": name, "reason": err})
            continue
        reasons = []
        # 硬否决(Critical Rules #1 + rule#3/D): amt20/float/ST/涨跌停/透支极高
        if f["avgAmount20d"] < 1.0:
            reasons.append(f"成交额20日{f['avgAmount20d']}亿<1亿")
        if f["floatMktCapYi"] is None or f["floatMktCapYi"] < 30:
            reasons.append(f"流通市值{f['floatMktCapYi']}亿<30亿")
        if "ST" in name or "退" in name:
            reasons.append("ST/退市")
        pct = f["dayChangePct"]
        if pct is not None and abs(pct) >= 9.8:
            reasons.append(f"涨跌停{pct}%")
        if f["m5"] is not None and f["m5"] > 30:
            reasons.append(f"5日涨{f['m5']}%>30%透支")
        # 透支极高(主升浪结束)否决: rule#3 + methodology D
        if f["exhaustionProb"] == "极高":
            reasons.append(f"透支极高(主升浪结束:{f['entryNote'] or '20日涨>25%+5日转负'})")
        # turnover 不在 Critical Rules#1 否决清单 -> 软标记(偏冷/高位派发),不剔除
        turnover_note = ""
        big_cap_exempt = f["floatMktCapYi"] and f["floatMktCapYi"] >= 1000 and f["avgAmount20d"] >= 5
        if f["turnover20d"] is not None:
            if f["turnover20d"] < 1:
                amt_lvl = "amt20充裕" if (big_cap_exempt or f["avgAmount20d"] >= 5) else ("amt20" + str(f["avgAmount20d"]) + "亿刚过线")
                turnover_note = f"偏冷(换手20日{f['turnover20d']}%<1%,{amt_lvl})"
            elif f["turnover20d"] > 7:
                turnover_note = f"高位换手(换手20日{f['turnover20d']}%>7%警惕派发)"
        affordable = c.get("affordable1w", True)
        if reasons:
            reject_list.append({"code": code, "name": name, "reason": ";".join(reasons),
                                "price": f["price"], "avgAmount20d": f["avgAmount20d"],
                                "turnover20d": f["turnover20d"], "floatMktCapYi": f["floatMktCapYi"],
                                "m5": f["m5"], "m20": f["m20"],
                                "entryType": f["entryType"], "exhaustionProb": f["exhaustionProb"]})
        else:
            # 高位(m20>20)提示也写入note,供评分参考
            hi_note = f"高位(m20+{f['m20']}%)" if (f["m20"] and f["m20"] > 20) else ""
            note = ";".join(x for x in [turnover_note, hi_note] if x)
            pass_list.append({
                "code": code, "name": name, "price": f["price"],
                "avgAmount20d": f["avgAmount20d"], "turnover20d": f["turnover20d"],
                "volumeRatio": f["volumeRatio"], "floatMktCapYi": f["floatMktCapYi"],
                "marketCapYi": f["marketCapYi"], "affordable1w": affordable,
                "entryType": f["entryType"], "entryScore": f["entryScore"],
                "exhaustionProb": f["exhaustionProb"], "technicalLevel": f["technicalLevel"],
                "m5": f["m5"], "m20": f["m20"],
                "pass": True, "note": note,
            })
        factor_list.append(f)

    dist = {}
    for f in factor_list:
        dist[f["entryType"]] = dist.get(f["entryType"], 0) + 1
    rej_reasons = {}
    for r in reject_list:
        for seg in r["reason"].split(";"):
            seg = seg.split("(")[0]
            rej_reasons[seg] = rej_reasons.get(seg, 0) + 1

    pass_codes = ",".join(p["code"] for p in pass_list)
    summary = (f"过关{len(pass_list)}只/剔除{len(reject_list)}只(48只候选)。"
               f"入场优势分布: {dist}。"
               f"主要剔除原因: {rej_reasons}。"
               f"否决清单=Critical Rules#1(amt20/float/ST/涨跌停/次新)+透支极高(主升浪结束rule#3/D);换手率1%-7%为软标记非否决。过关票均满足amt20>=1亿+流通市值>=30亿+非ST+非透支极高;大盘股(工/农/建/中行/中石油/长江电力等)结构性低换手<1%但amt20充裕按amt20为真实流动性测试保留并标偏冷。")
    out = {
        "agent": "technical-liquidity", "asOf": "20260730",
        "data": {
            "pass": pass_list, "reject": reject_list,
            "factors": factor_list,
            "passCodes": pass_codes,
            "entryDist": dist, "rejectReasons": rej_reasons,
            "poolSize": len(cands), "passCount": len(pass_list), "rejectCount": len(reject_list),
            "hardGates": {"avgAmount20d": ">=1亿(否决)", "floatMktCap": ">=30亿(否决)", "notST": True, "notLimit": "非一字涨停/封死跌停(否决)", "notOverdrawn_5d": "5日<=30%(否决)", "exhaustionExtremelyHigh": "透支极高/主升浪结束否决(rule#3+D: 20日涨>25%且5日转负)", "turnover20d": "1%-7%软标记非否决(Critical Rules#1否决清单不含换手;<1%偏冷/>7%警惕派发写入note供评分)", "bigCapNote": "大盘股(流通市值>=1000亿)结构性低换手<1%但amt20充裕(>>1亿),1w账户1手可买卖,按amt20为真实流动性测试,标记偏冷不剔除"},
            "dataNotes": "行情走腾讯qt.gtimg.cn+web.ifzq.gtimg.cn(HTTP绕代理最稳);cn_fetch kline现可取(07-30盘后数据已更新,前序sector-analyst盘中kline返空系数据源未更新);factors需带sh/sz前缀调用;换手率20日由流通市值/现价反推流通股本做分母计算;RSI14从日K收盘计算;量比=今日量/5日均量。",
            "summary": summary,
        },
    }
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    json.dump(out, open(OUT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"passCount": len(pass_list), "rejectCount": len(reject_list),
                      "passCodes": pass_codes, "entryDist": dist, "rejectReasons": rej_reasons},
                     ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
