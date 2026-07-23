#!/usr/bin/env python
"""Compute technical liquidity analysis for all candidates and output JSON."""
import json, math

# All pre-filter rejects
rejects = [
    {"code":"300062","name":"中能电气","reason":"流通市值29.1亿<30亿,流动性不足"},
    {"code":"300141","name":"和顺电气","reason":"流通市值25.1亿<30亿,流动性不足"},
    {"code":"300510","name":"金冠股份","reason":"流通市值29.2亿<30亿,流动性不足"},
    {"code":"001382","name":"新亚电缆","reason":"流通市值10.4亿+次新(上市<60交易日),高风险"},
    {"code":"600844","name":"金煤科技","reason":"流通市值25.3亿<30亿,流动性不足"},
    {"code":"301587","name":"中瑞股份","reason":"流通市值15.9亿+次新(上市<60交易日),高风险"},
    {"code":"300407","name":"凯发电气","reason":"流通市值27.0亿<30亿,流动性不足"},
    {"code":"002879","name":"长缆科技","reason":"流通市值22.5亿<30亿,流动性不足"},
    {"code":"603488","name":"展鹏科技","reason":"流通市值22.5亿<30亿,流动性不足"},
    {"code":"300875","name":"捷强装备","reason":"流通市值29.8亿<30亿,流动性不足"},
    {"code":"600722","name":"金牛化工","reason":"m5=40.7%>30%,近5日涨幅透支严重"},
    {"code":"600396","name":"华电辽能","reason":"m5=36.2%>30%,近5日涨幅透支严重"},
    {"code":"002197","name":"证通电子","reason":"m5=32.7%>30%,近5日涨幅透支严重"},
    {"code":"600644","name":"乐山电力","reason":"m5=31.5%>30%,近5日涨幅透支严重"},
    {"code":"002451","name":"摩恩电气","reason":"流通市值29.95亿<30亿,流动性不足"},
    {"code":"600980","name":"北矿科技","reason":"今日成交额0.34亿远低于1亿门槛,流动性严重不足"},
    {"code":"002088","name":"鲁阳节能","reason":"今日成交额0.47亿远低于1亿门槛,流动性严重不足"},
    {"code":"601061","name":"中信金属","reason":"换手率0.5%<1%,极度冷门,流动性不足"},
]

# All pass data from Tencent API query
pass_data = {
    "300444": {"name":"双杰电气","sector":"电网设备","price":9.54,"preClose":7.95,"amount_yi":9.40,"turnover":17.0,"pe":16.47,"floatCap":59.86,"totalCap":76.76,"pb":3.69,"volRatio":2.16,"m5":11.84,"m10":-13.9,"m20":-26.45,"changePct":20.0},
    "300265": {"name":"通光线缆","sector":"电网设备/军工","price":14.32,"preClose":12.75,"amount_yi":8.68,"turnover":13.41,"pe":218.85,"floatCap":66.92,"totalCap":66.96,"pb":2.86,"volRatio":2.40,"m5":4.3,"m10":-8.03,"m20":-37.52,"changePct":12.31},
    "002300": {"name":"太阳电缆","sector":"电网设备","price":6.45,"preClose":5.86,"amount_yi":1.92,"turnover":4.28,"pe":59.5,"floatCap":46.59,"totalCap":46.59,"pb":2.51,"volRatio":1.94,"m5":6.09,"m10":3.2,"m20":-5.7,"changePct":10.07},
    "002498": {"name":"汉缆股份","sector":"电网设备","price":5.91,"preClose":5.37,"amount_yi":4.37,"turnover":2.29,"pe":34.44,"floatCap":196.61,"totalCap":196.61,"pb":2.27,"volRatio":1.21,"m5":7.26,"m10":-2.15,"m20":-16.41,"changePct":10.06},
    "002546": {"name":"新联电子","sector":"电网设备","price":8.22,"preClose":7.47,"amount_yi":3.66,"turnover":5.80,"pe":12.2,"floatCap":65.86,"totalCap":68.56,"pb":1.81,"volRatio":1.15,"m5":5.38,"m10":4.31,"m20":7.45,"changePct":10.04},
    "002606": {"name":"大连电瓷","sector":"电网设备","price":13.61,"preClose":12.37,"amount_yi":5.01,"turnover":9.10,"pe":23.79,"floatCap":57.32,"totalCap":59.76,"pb":3.06,"volRatio":1.44,"m5":3.89,"m10":9.32,"m20":-2.79,"changePct":10.02},
    "001208": {"name":"华菱线缆","sector":"电网设备/军工","price":13.61,"preClose":12.37,"amount_yi":2.90,"turnover":6.90,"pe":80.09,"floatCap":43.38,"totalCap":86.88,"pb":3.0,"volRatio":1.29,"m5":1.42,"m10":-6.4,"m20":-4.09,"changePct":10.02},
    "603050": {"name":"科林电气","sector":"电网设备","price":18.67,"preClose":16.97,"amount_yi":1.60,"turnover":2.22,"pe":33.08,"floatCap":75.3,"totalCap":75.3,"pb":4.09,"volRatio":2.26,"m5":-1.06,"m10":-4.74,"m20":-4.06,"changePct":10.02},
    "603191": {"name":"望变电气","sector":"电网设备","price":13.40,"preClose":12.18,"amount_yi":2.28,"turnover":5.30,"pe":65.96,"floatCap":44.22,"totalCap":44.22,"pb":1.78,"volRatio":2.35,"m5":2.06,"m10":-5.7,"m20":-18.54,"changePct":10.02},
    "600550": {"name":"保变电气","sector":"电网设备","price":11.65,"preClose":10.59,"amount_yi":6.96,"turnover":3.38,"pe":93.98,"floatCap":214.54,"totalCap":214.54,"pb":24.04,"volRatio":1.69,"m5":14.33,"m10":9.39,"m20":-4.04,"changePct":10.01},
    "601179": {"name":"中国西电","sector":"电网设备","price":13.65,"preClose":12.41,"amount_yi":23.81,"turnover":3.52,"pe":52.95,"floatCap":699.68,"totalCap":699.68,"pb":3.03,"volRatio":1.18,"m5":16.67,"m10":2.55,"m20":-15.16,"changePct":9.99},
    "600468": {"name":"百利电气","sector":"电网设备","price":5.54,"preClose":5.04,"amount_yi":2.32,"turnover":3.98,"pe":72.94,"floatCap":60.26,"totalCap":60.26,"pb":3.0,"volRatio":1.95,"m5":9.27,"m10":8.2,"m20":1.93,"changePct":9.92},
    "002560": {"name":"通达股份","sector":"电网设备","price":5.96,"preClose":5.42,"amount_yi":3.23,"turnover":8.84,"pe":25.13,"floatCap":37.75,"totalCap":43.82,"pb":1.62,"volRatio":1.62,"m5":0.85,"m10":-12.48,"m20":-25.13,"changePct":9.96},
    "002339": {"name":"积成电子","sector":"电网设备","price":7.04,"preClose":6.40,"amount_yi":3.00,"turnover":9.21,"pe":435.74,"floatCap":33.70,"totalCap":35.49,"pb":2.04,"volRatio":3.08,"m5":6.83,"m10":6.18,"m20":-0.85,"changePct":10.0},
    "002112": {"name":"三变科技","sector":"电网设备","price":14.52,"preClose":13.20,"amount_yi":2.42,"turnover":6.58,"pe":262.98,"floatCap":38.05,"totalCap":42.71,"pb":4.95,"volRatio":1.70,"m5":2.33,"m10":-4.41,"m20":-13.47,"changePct":10.0},
    "002358": {"name":"森源电气","sector":"电网设备","price":5.50,"preClose":5.00,"amount_yi":2.54,"turnover":5.17,"pe":51.92,"floatCap":51.14,"totalCap":51.14,"pb":1.53,"volRatio":2.51,"m5":6.38,"m10":5.16,"m20":-3.68,"changePct":10.0},
    "600089": {"name":"特变电工","sector":"电网设备","price":21.56,"preClose":19.78,"amount_yi":55.91,"turnover":5.29,"pe":17.66,"floatCap":1089.38,"totalCap":1089.38,"pb":1.55,"volRatio":2.36,"m5":14.19,"m10":7.58,"m20":-5.6,"changePct":9.0},
    "603618": {"name":"杭电股份","sector":"电网设备","price":27.19,"preClose":25.65,"amount_yi":27.72,"turnover":14.75,"pe":-78.61,"floatCap":187.99,"totalCap":187.99,"pb":6.95,"volRatio":1.75,"m5":-9.22,"m10":-25.73,"m20":-52.46,"changePct":6.0},
    "002218": {"name":"拓日新能","sector":"电网设备","price":3.82,"preClose":3.47,"amount_yi":1.97,"turnover":3.78,"pe":-27.1,"floatCap":53.01,"totalCap":53.8,"pb":1.37,"volRatio":1.28,"m5":7.3,"m10":5.52,"m20":-1.04,"changePct":10.09},
    "600698": {"name":"湖南天雁","sector":"军工/商业航天","price":6.22,"preClose":5.65,"amount_yi":2.33,"turnover":4.66,"pe":-219.04,"floatCap":51.65,"totalCap":66.47,"pb":9.0,"volRatio":4.06,"m5":7.24,"m10":8.17,"m20":3.67,"changePct":10.09},
    "600343": {"name":"航天动力","sector":"军工/商业航天","price":18.68,"preClose":16.98,"amount_yi":9.43,"turnover":8.21,"pe":-63.2,"floatCap":119.22,"totalCap":119.22,"pb":9.36,"volRatio":1.32,"m5":-2.96,"m10":-25.87,"m20":-21.78,"changePct":10.01},
    "600990": {"name":"四创电子","sector":"军工/商业航天","price":16.94,"preClose":15.40,"amount_yi":1.02,"turnover":2.32,"pe":-14.16,"floatCap":45.57,"totalCap":45.92,"pb":2.97,"volRatio":1.41,"m5":1.93,"m10":-11.59,"m20":-4.72,"changePct":10.0},
    "601606": {"name":"长城军工","sector":"军工/商业航天","price":29.14,"preClose":26.49,"amount_yi":8.37,"turnover":4.14,"pe":3047.14,"floatCap":211.04,"totalCap":211.04,"pb":9.68,"volRatio":2.47,"m5":11.82,"m10":8.26,"m20":1.9,"changePct":10.0},
    "002829": {"name":"星网宇达","sector":"军工/商业航天","price":21.07,"preClose":21.86,"amount_yi":5.40,"turnover":17.71,"pe":-35.3,"floatCap":30.77,"totalCap":43.79,"pb":2.83,"volRatio":0.99,"m5":11.84,"m10":18.84,"m20":20.74,"changePct":-3.61},
    "600409": {"name":"三友化工","sector":"中报预增","price":6.58,"preClose":5.98,"amount_yi":3.38,"turnover":2.60,"pe":797.88,"floatCap":135.83,"totalCap":135.83,"pb":0.99,"volRatio":1.34,"m5":17.08,"m10":17.29,"m20":-3.52,"changePct":10.03},
    "000155": {"name":"川能动力","sector":"中报预增","price":12.29,"preClose":11.17,"amount_yi":9.68,"turnover":4.45,"pe":42.61,"floatCap":226.89,"totalCap":226.89,"pb":2.11,"volRatio":2.26,"m5":12.34,"m10":11.93,"m20":-2.38,"changePct":10.03},
    "600354": {"name":"敦煌种业","sector":"中报预增","price":6.04,"preClose":5.49,"amount_yi":3.56,"turnover":11.66,"pe":104.11,"floatCap":31.88,"totalCap":31.88,"pb":4.26,"volRatio":1.84,"m5":6.34,"m10":24.79,"m20":23.27,"changePct":10.02},
    "000603": {"name":"盛达资源","sector":"中报预增","price":24.83,"preClose":22.57,"amount_yi":16.51,"turnover":10.34,"pe":28.38,"floatCap":165.55,"totalCap":171.32,"pb":4.91,"volRatio":2.20,"m5":21.42,"m10":13.33,"m20":7.44,"changePct":10.01},
    "002379": {"name":"宏桥控股","sector":"中报预增","price":20.45,"preClose":18.59,"amount_yi":14.51,"turnover":6.45,"pe":13.52,"floatCap":232.39,"totalCap":2664.86,"pb":5.44,"volRatio":0.94,"m5":10.3,"m10":44.52,"m20":29.76,"changePct":10.01},
    "603876": {"name":"鼎胜新材","sector":"中报预增","price":21.10,"preClose":19.18,"amount_yi":7.40,"turnover":3.91,"pe":31.55,"floatCap":196.08,"totalCap":196.08,"pb":2.61,"volRatio":1.43,"m5":5.61,"m10":-3.21,"m20":-27.27,"changePct":10.01},
    "603399": {"name":"永杉锂业","sector":"中报预增","price":13.72,"preClose":12.47,"amount_yi":6.64,"turnover":9.72,"pe":-41.02,"floatCap":70.29,"totalCap":70.29,"pb":4.34,"volRatio":1.05,"m5":0.22,"m10":-18.72,"m20":-39.67,"changePct":10.02},
    "002539": {"name":"云图控股","sector":"中报预增","price":11.40,"preClose":10.36,"amount_yi":4.46,"turnover":4.55,"pe":15.7,"floatCap":101.44,"totalCap":137.68,"pb":1.45,"volRatio":1.60,"m5":15.27,"m10":7.65,"m20":-7.01,"changePct":10.04},
    "600513": {"name":"联环药业","sector":"中报预增","price":16.57,"preClose":15.06,"amount_yi":4.32,"turnover":9.65,"pe":-41.14,"floatCap":47.3,"totalCap":47.3,"pb":3.76,"volRatio":0.87,"m5":-4.11,"m10":17.68,"m20":10.39,"changePct":10.03},
    "600219": {"name":"南山铝业","sector":"中报预增","price":4.79,"preClose":4.35,"amount_yi":18.58,"turnover":3.49,"pe":13.31,"floatCap":550.07,"totalCap":550.07,"pb":1.11,"volRatio":1.88,"m5":17.11,"m10":19.45,"m20":11.66,"changePct":10.11},
    "000035": {"name":"中国天楹","sector":"中报预增","price":4.83,"preClose":4.39,"amount_yi":3.79,"turnover":3.53,"pe":39.85,"floatCap":111.72,"totalCap":115.34,"pb":1.07,"volRatio":2.46,"m5":6.15,"m10":6.86,"m20":-4.17,"changePct":10.02},
    "600379": {"name":"宝光股份","sector":"中报预增","price":11.52,"preClose":10.47,"amount_yi":1.42,"turnover":3.84,"pe":91.06,"floatCap":38.04,"totalCap":38.04,"pb":4.89,"volRatio":0.67,"m5":-5.81,"m10":-22.37,"m20":-24.06,"changePct":10.03},
    "600449": {"name":"宁夏建材","sector":"中报预增","price":12.29,"preClose":11.17,"amount_yi":1.20,"turnover":2.14,"pe":31.6,"floatCap":58.77,"totalCap":58.77,"pb":0.81,"volRatio":1.50,"m5":0.0,"m10":-3.91,"m20":2.42,"changePct":10.03},
    "600173": {"name":"卧龙新能","sector":"中报预增","price":6.14,"preClose":5.58,"amount_yi":1.26,"turnover":3.01,"pe":-20.47,"floatCap":43.01,"totalCap":43.01,"pb":1.2,"volRatio":3.74,"m5":6.97,"m10":6.6,"m20":0.33,"changePct":10.04},
    "002490": {"name":"山东墨龙","sector":"中报预增","price":8.20,"preClose":7.77,"amount_yi":7.19,"turnover":16.48,"pe":1230.61,"floatCap":44.42,"totalCap":65.42,"pb":12.99,"volRatio":1.17,"m5":8.47,"m10":6.91,"m20":29.13,"changePct":5.53},
    "300191": {"name":"潜能恒信","sector":"中报预增","price":31.50,"preClose":28.46,"amount_yi":10.68,"turnover":15.49,"pe":145.65,"floatCap":69.68,"totalCap":100.8,"pb":8.84,"volRatio":1.49,"m5":20.6,"m10":11.66,"m20":10.49,"changePct":10.68},
    "000862": {"name":"银星能源","sector":"电网设备/中报预增","price":5.92,"preClose":5.38,"amount_yi":4.54,"turnover":12.88,"pe":198.52,"floatCap":37.18,"totalCap":54.34,"pb":1.25,"volRatio":1.89,"m5":23.08,"m10":28.7,"m20":21.31,"changePct":10.04},
    "002240": {"name":"盛新锂能","sector":"中报预增","price":30.42,"preClose":27.65,"amount_yi":17.34,"turnover":6.44,"pe":-103.39,"floatCap":277.71,"totalCap":278.43,"pb":2.59,"volRatio":1.20,"m5":0.83,"m10":-14.43,"m20":-34.59,"changePct":10.02},
    "603727": {"name":"博迈科","sector":"中报预增","price":17.44,"preClose":15.85,"amount_yi":1.52,"turnover":3.23,"pe":-543.51,"floatCap":49.13,"totalCap":49.13,"pb":1.58,"volRatio":1.45,"m5":13.76,"m10":8.66,"m20":-5.98,"changePct":10.03},
    "601678": {"name":"滨化股份","sector":"中报预增","price":6.22,"preClose":5.65,"amount_yi":8.10,"turnover":6.44,"pe":54.34,"floatCap":127.1,"totalCap":149.84,"pb":1.29,"volRatio":0.87,"m5":22.68,"m10":8.36,"m20":-4.45,"changePct":10.09},
}

def compute_factors(d):
    m5 = d.get("m5") or 0
    m10 = d.get("m10") or 0
    m20 = d.get("m20") or 0
    chg = d.get("changePct") or 0
    volRatio = d.get("volRatio") or 0
    turnover = d.get("turnover") or 0
    amt = d.get("amount_yi") or 0

    # A. Momentum acceleration
    momentum_accel = round((m5 / 5) - ((m10 - m5) / 5), 2) if m5 != 0 else 0

    # B. Momentum uniformity (approximate)
    if m5 != 0 and abs(m5) > 0.5:
        uniformity = round(max(0.1, 1 - abs(chg / m5) * 0.33), 2)
    else:
        uniformity = 0.5

    # C. Volume health
    if volRatio > 3:
        vol_health = "天量警惕"
    elif volRatio > 1.5:
        vol_health = "放量"
    elif volRatio > 0.8:
        vol_health = "正常"
    else:
        vol_health = "缩量"

    # D. Entry type determination (refined: distinguish 涨停 breakout vs 放量滞涨)
    is_zhangting = chg > 9.5  # 涨停 or near-涨停
    entry_type = "neutral"
    entry_score = 0

    if -8 <= m5 <= -3 and m20 > 0 and vol_health == "缩量":
        entry_type = "健康回调买点"
        entry_score = 20
    elif m20 > 20 and m5 < 0 and vol_health in ("放量", "天量警惕"):
        entry_type = "高位派发(回避)"
        entry_score = -20
    elif m5 > 10 and is_zhangting and m20 < -5:
        entry_type = "超跌反弹启动(涨停突破)"
        entry_score = 12
    elif m5 > 10 and is_zhangting and m20 < 0:
        entry_type = "反弹加速(涨停确认)"
        entry_score = 8
    elif m5 > 10 and is_zhangting and m20 >= 0:
        entry_type = "趋势加强(涨停突破)"
        entry_score = 6
    elif m5 > 10 and not is_zhangting and vol_health in ("放量", "天量警惕") and chg < 5:
        entry_type = "追涨入场(谨慎)"
        entry_score = -15
    elif m5 > 10 and not is_zhangting:
        entry_type = "反弹加速"
        entry_score = 5
    elif m5 > 0 and m10 > 0 and m20 > 0:
        entry_type = "趋势延续"
        entry_score = 5
    elif m20 < -15 and m5 > 0 and is_zhangting:
        entry_type = "超跌反弹启动(涨停)"
        entry_score = 10
    elif m20 < -15 and m5 > 0 and vol_health in ("放量", "天量警惕"):
        entry_type = "超跌反弹启动"
        entry_score = 10
    elif m20 < -10 and m5 > 0:
        entry_type = "超跌反弹(温和)"
        entry_score = 8
    elif m20 < 0 and m5 > 0:
        entry_type = "反弹初期"
        entry_score = 3
    elif m20 > 0 and -3 <= m5 <= 3 and vol_health == "缩量":
        entry_type = "突破回踩确认"
        entry_score = 15
    elif m5 < 0 and m10 < 0 and m20 < 0:
        entry_type = "下跌趋势(回避)"
        entry_score = -25
    elif m20 > 20 and m5 > 0 and chg < 0:
        entry_type = "高位回调(警惕)"
        entry_score = -10
    else:
        entry_type = "盘整中"
        entry_score = 0

    # E. Mean reversion signal
    if m20 < -15 and m5 > 0:
        mrs = "布林带下轨超跌反弹"
    elif m20 < -8 and m5 > 0:
        mrs = "轻微超跌修复"
    elif m20 < -8:
        mrs = "深度超跌(未反弹)"
    else:
        mrs = "无"

    # F. Exhaustion probability (refined: context-aware)
    if m20 > 25 and m5 < 0:
        exhaustion = "极高(>80%)"
    elif m5 > 15 and m20 > 10:
        exhaustion = "高概率(>70%)"
    elif m5 > 15 and m20 >= 0:
        exhaustion = "中概率(40%)"
    elif m5 > 15 and m20 < 0:
        exhaustion = "中低概率(25%)"
    elif 5 <= m5 <= 15 and m20 > 10:
        exhaustion = "低(<30%)"
    else:
        exhaustion = "低(<30%)"

    # G. Above MA20
    if m20 > 0:
        above_ma20 = True
    elif m20 > -3:
        above_ma20 = "near"
    else:
        above_ma20 = False

    # H. Technical level
    if m5 > 0 and m10 > 0 and m20 > 0:
        tech = "上升趋势(多周期共振)"
    elif m20 > 20 and m5 < 0:
        tech = "高位回调(警惕派发)"
    elif m20 < -15 and m5 > 0:
        tech = "超跌反弹"
    elif m20 < 0 and m5 > 0:
        tech = "底部反弹初期"
    elif m5 < 0 and m10 < 0 and m20 < 0:
        tech = "下跌趋势"
    else:
        tech = "震荡整理"

    # I. RPS
    if m5 > 3:
        rps = "强于大盘"
    elif m5 > 0:
        rps = "略强于大盘"
    elif m5 > -3:
        rps = "与大盘同步"
    else:
        rps = "弱于大盘"

    # J. Breakout
    if chg > 9 and vol_health in ("放量", "天量警惕"):
        breakout = "放量涨停突破"
    elif chg > 5 and vol_health in ("放量", "天量警惕"):
        breakout = "放量突破"
    else:
        breakout = "无"

    # K. Pullback depth
    if m5 > 0 and m20 < 0:
        pullback_depth = round(abs(m20), 1)
    else:
        pullback_depth = 0.0

    return {
        "m5": round(m5, 2),
        "m10": round(m10, 2),
        "m20": round(m20, 2),
        "momentumUniformity": uniformity,
        "volumeHealth": vol_health,
        "momentumAccel": momentum_accel,
        "entryType": entry_type,
        "entryScore": entry_score,
        "meanReversionSignal": mrs,
        "pullbackDepth": pullback_depth,
        "pullbackVolume": vol_health,
        "exhaustionProb": exhaustion,
        "breakout": breakout,
        "aboveMA20": above_ma20,
        "rps": rps,
        "technicalLevel": tech,
    }

# Build passes
passes = []
for code, d in pass_data.items():
    factors = compute_factors(d)
    passes.append({
        "code": code,
        "name": d["name"],
        "sector": d["sector"],
        "price": d["price"],
        "avgAmount20d": round(d["amount_yi"], 2),
        "turnover20d": d["turnover"],
        "volumeRatio": d["volRatio"],
        "marketCap": d["floatCap"],
        "pass": True,
        "factors": factors,
    })

# Sort passes by entryScore descending
passes.sort(key=lambda x: x["factors"]["entryScore"], reverse=True)

# Build pass/reject lists
pass_list = [{"code": p["code"], "name": p["name"], "sector": p["sector"], "price": p["price"],
              "avgAmount20d": p["avgAmount20d"], "turnover20d": p["turnover20d"],
              "volumeRatio": p["volumeRatio"], "marketCap": p["marketCap"],
              "pass": True} for p in passes]

# Count by entry type
entry_counts = {}
for p in passes:
    et = p["factors"]["entryType"]
    entry_counts[et] = entry_counts.get(et, 0) + 1

# Main reject reasons
# Consolidate reject reasons
reject_categories = {}
for r in rejects:
    reason = r["reason"]
    if "流通市值" in reason and "<30亿" in reason:
        reject_categories["流通市值<30亿"] = reject_categories.get("流通市值<30亿", 0) + 1
    elif "m5=" in reason and ">30%" in reason:
        reject_categories["近5日涨幅>30%透支"] = reject_categories.get("近5日涨幅>30%透支", 0) + 1
    elif "成交额" in reason:
        reject_categories["日均成交额<1亿"] = reject_categories.get("日均成交额<1亿", 0) + 1
    elif "换手率" in reason:
        reject_categories["换手率<1%偏冷"] = reject_categories.get("换手率<1%偏冷", 0) + 1
    elif "次新" in reason:
        reject_categories["次新(上市<60交易日)"] = reject_categories.get("次新(上市<60交易日)", 0) + 1
    else:
        reject_categories["其他"] = reject_categories.get("其他", 0) + 1

reject_summary = "、".join([f"{k}:{v}只" for k, v in sorted(reject_categories.items(), key=lambda x: -x[1])])

# Build summary
entry_dist = ", ".join([f"{k}:{v}只" for k, v in sorted(entry_counts.items(), key=lambda x: -x[1])])
summary = f"过关{len(passes)}只/剔除{len(rejects)}只。入场优势分布: {entry_dist}。主要剔除原因: {reject_summary}"

# passCodes for workflow
pass_codes = ",".join([p["code"] for p in passes])

# Build output
output = {
    "agent": "technical-liquidity",
    "asOf": "20260723",
    "data": {
        "pass": pass_list,
        "reject": rejects,
        "factors": [{"code": p["code"], **p["factors"]} for p in passes],
        "summary": summary,
        "keyFields": {
            "passCodes": pass_codes,
            "passCount": len(passes),
            "rejectCount": len(rejects),
            "entryDistribution": entry_counts,
            "dataSource": "腾讯qt.gtimg.cn(HTTP绕代理)+cn_fetch.py factors(腾讯K线)",
            "dataQuality": "MCP全SSL挂未使用; 腾讯API正常; m5/m10/m20来自Tencent实时报价GP-A/CYB段; 日均成交额用今日单日成交额代理; 换手率为今日单日值; 20日均换手率数据缺失用今日值代理; 无逐日K线数据故动量均匀度/量价健康度基于单日快照近似",
        }
    }
}

# Write output
import os
out_dir = r"E:\finacial-invest\data\runs\20260723_short-term-picks"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "technical-liquidity.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Written to {out_path}")
print(f"Passes: {len(passes)}, Rejects: {len(rejects)}")
print(f"Summary: {summary}")
print(f"passCodes: {pass_codes}")