"""Technical liquidity filter + short-term factor calculator for candidate pool."""
import json, urllib.request, ssl, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

candidates = [
    ("sz000703", "恒逸石化", 14.54, 552.9, "化工-炼化"),
    ("sh600746", "江苏索普", 5.74, 67.0, "化工"),
    ("sz300107", "建新股份", 6.17, 21.2, "化工"),
    ("sz300214", "日科化学", 13.07, 62.1, "化工"),
    ("sh605189", "富春染织", 14.22, 33.9, "化工-印染"),
    ("sz300164", "通源石油", 10.79, 63.2, "油服"),
    ("sh603619", "中曼石油", 20.21, 93.1, "油服"),
    ("sz000554", "泰山石油", 6.44, 23.1, "油气-炼化"),
    ("sh601101", "昊华能源", 11.61, 168.2, "煤炭"),
    ("sh600844", "金煤科技", 2.70, 22.2, "煤化工"),
    ("sz000968", "蓝焰控股", 7.04, 67.7, "煤层气"),
    ("sz000970", "中科三环", 16.16, 197.6, "稀土"),
    ("sh601969", "海南矿业", 8.34, 164.3, "有色-铁矿"),
    ("sz002141", "贤丰控股", 5.10, 52.7, "有色-锂"),
    ("sh601899", "紫金矿业", 27.88, 7350.0, "有色金属"),
    ("sz301526", "国际复材", 37.01, 517.7, "玻纤材料"),
    ("sh603806", "福斯特", 14.91, 389.0, "化工-新材料"),
    ("sh688106", "金宏气体", 40.12, 215.7, "特种气体"),
    ("sh603197", "保隆科技", 29.62, 62.5, "汽车零部件"),
    ("sz300532", "今天国际", 7.03, 42.6, "机械设备-物流"),
    ("sz002523", "天桥起重", 3.11, 44.0, "机械设备-起重"),
    ("sz300566", "激智科技", 31.88, 72.3, "消费电子-光学"),
    ("sz301362", "民爆光电", 147.14, 60.1, "LED-出口"),
    ("sz002241", "歌尔股份", 21.18, 640.0, "消费电子"),
    ("sh605028", "世茂能源", 22.03, 35.2, "家电出口"),
    ("sh603489", "八方股份", 26.44, 62.0, "电踏车出口"),
    ("sz002384", "东山精密", 250.0, 1050.0, "消费电子-FPC"),
    ("sh600488", "天药股份", 6.46, 70.5, "医药出口"),
    ("sh688488", "艾迪药业", 15.35, 64.7, "自主可控"),
    ("sh603042", "华脉科技", 12.31, 25.7, "光通信模块"),
    ("sz001388", "信通电子", 32.44, 27.4, "军工芯片"),
    ("sz000759", "中百集团", 6.75, 44.3, "内需消费"),
    ("sz001389", "广合科技", 183.63, 279.8, "PCB-信创"),
    ("sz002243", "力合科创", 6.85, 82.5, "科技服务"),
    ("sh600111", "北方稀土", 39.03, 1412.0, "稀土"),
    ("sh600309", "万华化学", 68.61, 2160.0, "化工-聚氨酯"),
]

pass_list = []
reject_list = []
factors_list = []

for code, name, ref_price, mcap, sector in candidates:
    try:
        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?param={code},day,2026-05-15,2026-07-14,40,qfq"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        raw = resp.read().decode("gbk", errors="replace")
        data = json.loads(raw)
        kdata = data.get("data", {}).get(code, {})
        days = kdata.get("qfqday", [])
        if not days or len(days) < 10:
            reject_list.append({"code": code, "name": name, "reason": f"K线数据不足(仅{len(days)}天)"})
            continue

        closes = [float(d[2]) for d in days]
        volumes = [float(d[5]) for d in days]  # in lots (手)
        dates = [d[0] for d in days]
        n = len(closes)
        latest_close = closes[-1]
        latest_date = dates[-1]

        # Momentum: (close / close_N_ago - 1) * 100
        m5 = ((latest_close / closes[-6]) - 1) * 100 if n >= 6 else None
        m10 = ((latest_close / closes[-11]) - 1) * 100 if n >= 11 else None
        m20 = ((latest_close / closes[-21]) - 1) * 100 if n >= 21 else None

        # MA20
        ma20_vals = closes[-min(20, n):]
        ma20 = sum(ma20_vals) / len(ma20_vals)
        above_ma20 = latest_close > ma20

        # Breakout: close > MA20 AND today_vol > avg_5d_vol * 1.5
        vol5_avg = sum(volumes[-5:]) / 5
        breakout = bool(above_ma20 and volumes[-1] > vol5_avg * 1.5)

        # Amount: vol(lots) * 100(shares/lot) * price / 1e8 = vol * price / 1e6 (in 亿)
        amt_vals = []
        for i in range(-min(20, n), 0):
            amt_yi = volumes[i] * closes[i] / 1e6
            amt_vals.append(amt_yi)
        amt20 = sum(amt_vals) / len(amt_vals)

        # Turnover rate: vol(lots) * 100(shares) / total_shares * 100%
        total_shares = (mcap * 1e8) / ref_price
        turnover_vals = []
        for i in range(-min(20, n), 0):
            tr = (volumes[i] * 100 / total_shares) * 100
            turnover_vals.append(tr)
        turnover_20d = sum(turnover_vals) / len(turnover_vals)

        # Volume ratio
        vol_prev5 = sum(volumes[-10:-5]) / 5 if n >= 10 else vol5_avg
        vol_ratio = vol5_avg / vol_prev5 if vol_prev5 > 0 else 1.0

        # === HARD FILTERS ===
        reject_reasons = []

        # 1. Price > 40 (1w account)
        if latest_close > 40:
            reject_reasons.append(f"股价{latest_close:.1f}>40元(1w不可配)")

        # 2. Market cap < 30亿
        if mcap < 30:
            reject_reasons.append(f"市值{mcap:.0f}亿<30亿")

        # 3. Momentum overshoot
        if m5 is not None and m5 > 30:
            reject_reasons.append(f"5日涨{m5:.1f}%>30%透支")
        if m10 is not None and m10 > 30:
            reject_reasons.append(f"10日涨{m10:.1f}%>30%透支")
        if m20 is not None and m20 > 30:
            reject_reasons.append(f"20日涨{m20:.1f}%>30%透支")

        # 4. Turnover rate 1-7%
        if turnover_20d < 1.0:
            reject_reasons.append(f"换手{turnover_20d:.1f}%<1%偏冷")
        if turnover_20d > 7.0:
            reject_reasons.append(f"换手{turnover_20d:.1f}%>7%派发警惕")

        # 5. Daily amount < 1亿
        if amt20 < 1.0:
            reject_reasons.append(f"日均成交{amt20:.2f}亿<1亿")

        # High-position pullback warning
        high_pullback = False
        if m20 is not None and m20 > 20 and m5 is not None and m5 < 0:
            high_pullback = True
            if not any("透支" in r for r in reject_reasons):
                reject_reasons.append(f"高位回调(m20+{m20:.1f}%但m5{m5:.1f}%)")

        # Technical level
        m5v = m5 if m5 else 0
        m10v = m10 if m10 else 0
        if above_ma20 and m5v > 0 and m10v > 0:
            tech_level = "上升趋势"
        elif above_ma20 and m5v < 0:
            tech_level = "高位回调"
        elif not above_ma20 and m5v > 0:
            tech_level = "超跌反弹"
        else:
            tech_level = "下行趋势"

        if reject_reasons:
            reject_list.append({
                "code": code, "name": name, "price": round(latest_close, 2),
                "reason": "; ".join(reject_reasons),
            })
        else:
            pass_list.append({
                "code": code, "name": name, "price": round(latest_close, 2),
                "avgAmount20d": round(amt20, 2),
                "turnover20d": round(turnover_20d, 2),
                "volumeRatio": round(vol_ratio, 2),
                "marketCap": mcap,
                "pass": True,
                "sector": sector,
                "techLevel": tech_level,
            })

        factors_list.append({
            "code": code, "name": name, "price": round(latest_close, 2),
            "m5": round(m5, 2) if m5 is not None else None,
            "m10": round(m10, 2) if m10 is not None else None,
            "m20": round(m20, 2) if m20 is not None else None,
            "breakout": breakout,
            "aboveMA20": above_ma20,
            "techLevel": tech_level,
            "amt20": round(amt20, 2),
            "turnover20d": round(turnover_20d, 2),
            "highPullback": high_pullback,
            "latestDate": latest_date,
            "volRatio": round(vol_ratio, 2),
        })

        time.sleep(0.12)
    except Exception as e:
        reject_list.append({"code": code, "name": name, "reason": f"数据获取失败:{str(e)[:80]}"})

output = {
    "pass": pass_list,
    "reject": reject_list,
    "factors": factors_list,
    "summary": (
        f"过关{len(pass_list)}只/剔除{len(reject_list)}只; "
        f"主要剔除原因: 换手率偏离(>7%派发或<1%偏冷)与成交额不足1亿为最主要原因, "
        f"部分高位透支(m10/m20>30%)及市值不足30亿"
    ),
}

print(json.dumps(output, ensure_ascii=False, indent=2))
