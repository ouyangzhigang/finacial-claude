#!/usr/bin/env python3
"""
Technical Liquidity Agent v2: batch liquidity filtering + momentum factor computation.
Uses Tencent HTTP API (bypasses proxy) for kline + quote data.
Fixes: proper 20d avg turnover rate, 688 volume units, circulating cap.
"""
import urllib.request
import urllib.error
import ssl
import json
import sys
import re

# Bypass proxy for Tencent
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
proxy_handler = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=ctx))
urllib.request.install_opener(opener)

CANDIDATES = [
    {"code":"603118","name":"共进股份","sector":"超节点/AI算力","price":16.42,"mktcapYi":129.27,"pe":161.72,"dayChangePct":9.98,"turnoverPct":14.11,"note":"超节点联动+CPO+机器人"},
    {"code":"000063","name":"中兴通讯","sector":"超节点/AI算力","price":37.50,"mktcapYi":1793.83,"pe":40.09,"dayChangePct":7.51,"turnoverPct":11.98,"note":"超节点受益+通信设备龙头+成交额第九"},
    {"code":"002396","name":"星网锐捷","sector":"超节点/AI算力","price":34.59,"mktcapYi":263.08,"pe":65.12,"dayChangePct":9.43,"turnoverPct":28.90,"note":"通信设备+算力+高换手"},
    {"code":"603803","name":"瑞斯康达","sector":"超节点/AI算力","price":10.07,"mktcapYi":42.79,"pe":-232.46,"dayChangePct":10.05,"turnoverPct":5.39,"note":"算力交换机+光网络+半年报大幅减亏-市值略低于50亿"},
    {"code":"000815","name":"美利云","sector":"算力租赁","price":16.13,"mktcapYi":112.15,"pe":144.02,"dayChangePct":10.03,"turnoverPct":12.97,"note":"算力租赁+央企-涨停"},
    {"code":"000938","name":"紫光股份","sector":"算力租赁","price":44.90,"mktcapYi":1284.18,"pe":60.44,"dayChangePct":8.30,"turnoverPct":18.80,"note":"算力基础设施-成交额第五-略超40元"},
    {"code":"603162","name":"海通发展","sector":"中报预增","price":11.28,"mktcapYi":155.17,"pe":17.21,"dayChangePct":10.05,"turnoverPct":7.18,"note":"航运+中报预增+低PE"},
    {"code":"002545","name":"东方铁塔","sector":"中报预增","price":18.13,"mktcapYi":225.55,"pe":16.08,"dayChangePct":10.01,"turnoverPct":2.76,"note":"钾肥+钢结构+中报预增+低PE"},
    {"code":"002412","name":"汉森制药","sector":"中报预增","price":6.71,"mktcapYi":33.76,"pe":14.99,"dayChangePct":10.00,"turnoverPct":7.69,"note":"中药+独家品种+中报预增-市值低于50亿"},
    {"code":"000506","name":"招金黄金","sector":"黄金/贵金属","price":13.02,"mktcapYi":120.96,"pe":34.62,"dayChangePct":9.97,"turnoverPct":9.29,"note":"黄金+半年报预增+国企+龙虎榜"},
    {"code":"000975","name":"山金国际","sector":"黄金/贵金属","price":22.52,"mktcapYi":624.37,"pe":17.01,"dayChangePct":10.02,"turnoverPct":3.71,"note":"黄金+半年报预增+山东国资+低PE"},
    {"code":"000603","name":"盛达资源","sector":"黄金/贵金属","price":22.57,"mktcapYi":155.73,"pe":25.80,"dayChangePct":10.00,"turnoverPct":6.27,"note":"黄金+白银+龙虎榜涨停"},
    {"code":"601899","name":"紫金矿业","sector":"黄金/贵金属","price":32.20,"mktcapYi":8562.21,"pe":13.88,"dayChangePct":6.59,"turnoverPct":2.55,"note":"黄金龙头+极低PE+成交额第十三"},
    {"code":"603993","name":"洛阳钼业","sector":"黄金/贵金属","price":19.61,"mktcapYi":4195.42,"pe":17.37,"dayChangePct":4.98,"turnoverPct":2.67,"note":"钼铜黄金+低PE+大市值"},
    {"code":"300139","name":"晓程科技","sector":"黄金/贵金属","price":39.54,"mktcapYi":108.34,"pe":58.46,"dayChangePct":8.51,"turnoverPct":26.24,"note":"黄金+半导体+高换手"},
    {"code":"600396","name":"华电辽能","sector":"央企改革","price":14.92,"mktcapYi":219.73,"pe":541.87,"dayChangePct":10.03,"turnoverPct":16.79,"note":"绿色电力+央企+涨停"},
    {"code":"600403","name":"大有能源","sector":"央企改革","price":5.70,"mktcapYi":136.28,"pe":-6.56,"dayChangePct":10.04,"turnoverPct":6.21,"note":"煤炭+中报减亏+河南国资+涨停"},
    {"code":"600744","name":"华银电力","sector":"央企改革","price":7.94,"mktcapYi":161.27,"pe":111.74,"dayChangePct":9.97,"turnoverPct":18.97,"note":"火电+新能源+定增获批+央企"},
    {"code":"600726","name":"华电能源","sector":"央企改革","price":6.60,"mktcapYi":521.88,"pe":160.73,"dayChangePct":10.00,"turnoverPct":5.14,"note":"热电联产+新能源转型+央企"},
    {"code":"000539","name":"粤电力A","sector":"央企改革","price":6.46,"mktcapYi":339.17,"pe":40.81,"dayChangePct":6.78,"turnoverPct":9.28,"note":"电力+央企+龙虎榜上榜"},
    {"code":"600644","name":"乐山电力","sector":"央企改革","price":10.60,"mktcapYi":61.30,"pe":274.92,"dayChangePct":9.96,"turnoverPct":16.76,"note":"电力+天然气+新型储能"},
    {"code":"300105","name":"龙源技术","sector":"央企改革","price":10.20,"mktcapYi":52.61,"pe":-81.18,"dayChangePct":17.51,"turnoverPct":17.63,"note":"火电节能+央企+涨幅榜第六"},
    {"code":"600722","name":"金牛化工","sector":"央企改革","price":9.91,"mktcapYi":67.42,"pe":141.74,"dayChangePct":9.99,"turnoverPct":20.36,"note":"甲醇+风电+河北国资+高换手"},
    {"code":"002185","name":"华天科技","sector":"端侧AI/半导体","price":18.42,"mktcapYi":612.17,"pe":75.04,"dayChangePct":0.38,"turnoverPct":20.13,"note":"封测龙头+高换手-涨幅滞后有补涨潜力"},
    {"code":"002436","name":"兴森科技","sector":"端侧AI/半导体","price":35.01,"mktcapYi":595.06,"pe":412.32,"dayChangePct":7.13,"turnoverPct":15.34,"note":"PCB+封装基板+放量"},
    {"code":"688620","name":"安凯微","sector":"端侧AI/半导体","price":15.40,"mktcapYi":60.37,"pe":-43.78,"dayChangePct":11.51,"turnoverPct":9.22,"note":"AIoT芯片+涨幅榜"},
    {"code":"000021","name":"深科技","sector":"端侧AI/半导体","price":40.22,"mktcapYi":633.21,"pe":52.81,"dayChangePct":4.06,"turnoverPct":14.03,"note":"存储+封测+略超40元"},
    {"code":"688049","name":"炬芯科技","sector":"端侧AI/半导体","price":42.70,"mktcapYi":74.80,"pe":35.31,"dayChangePct":15.09,"turnoverPct":13.09,"note":"端侧AI芯片+中报预增+低PE-略超40元"},
    {"code":"300458","name":"全志科技","sector":"端侧AI/半导体","price":41.71,"mktcapYi":414.45,"pe":110.93,"dayChangePct":11.14,"turnoverPct":19.64,"note":"端侧AI+SoC芯片-略超40元"},
    {"code":"688166","name":"博瑞医药","sector":"创新药","price":39.70,"mktcapYi":173.01,"pe":340.25,"dayChangePct":13.14,"turnoverPct":7.22,"note":"创新药+中报预增+领涨"},
    {"code":"688046","name":"药康生物","sector":"创新药","price":27.00,"mktcapYi":110.70,"pe":69.29,"dayChangePct":10.66,"turnoverPct":5.47,"note":"CRO+创新药"},
    {"code":"603538","name":"美诺华","sector":"创新药","price":29.23,"mktcapYi":99.36,"pe":88.58,"dayChangePct":4.54,"turnoverPct":24.63,"note":"原料药+CDMO+高换手"},
    {"code":"300006","name":"莱美药业","sector":"创新药","price":5.27,"mktcapYi":55.65,"pe":-40.93,"dayChangePct":16.59,"turnoverPct":10.36,"note":"创新药+中报预增+涨幅榜第七"},
    {"code":"300164","name":"通源石油","sector":"事件驱动","price":12.12,"mktcapYi":71.32,"pe":310.96,"dayChangePct":8.89,"turnoverPct":38.04,"note":"油气服务+中东局势催化+极高换手"},
    {"code":"002167","name":"东方锆业","sector":"事件驱动","price":17.10,"mktcapYi":132.47,"pe":244.50,"dayChangePct":1.48,"turnoverPct":24.34,"note":"锆制品+核电+高换手"},
    {"code":"000676","name":"智度股份","sector":"事件驱动","price":6.92,"mktcapYi":87.18,"pe":60.85,"dayChangePct":0.00,"turnoverPct":21.24,"note":"数字营销+龙虎榜+振幅15.87%"},
    {"code":"300834","name":"星辉环材","sector":"事件驱动","price":38.08,"mktcapYi":73.77,"pe":139.73,"dayChangePct":20.01,"turnoverPct":3.23,"note":"回购+聚苯乙烯+涨幅榜第一"},
    {"code":"002213","name":"大为股份","sector":"事件驱动","price":27.49,"mktcapYi":65.31,"pe":3448.07,"dayChangePct":10.00,"turnoverPct":4.29,"note":"汽车电子+涨停"},
    {"code":"000839","name":"国安股份","sector":"央企改革","price":2.64,"mktcapYi":103.48,"pe":118.23,"dayChangePct":10.00,"turnoverPct":4.39,"note":"AI应用+内容审核+数据标注+央企+低价"},
    {"code":"000595","name":"新能股份","sector":"事件驱动","price":5.02,"mktcapYi":57.16,"pe":60.12,"dayChangePct":10.09,"turnoverPct":1.30,"note":"新能源+涨停+低价"},
]

def market_prefix(code):
    return 'sh' if code.startswith(('6', '9')) else 'sz'

def is_kcb(code):
    return code.startswith('688')

def fetch_quote(codes):
    """Fetch snapshot quotes for circulating market cap."""
    parts = []
    for c in codes:
        pfx = market_prefix(c)
        parts.append(f"{pfx}{c}")
    url = f"http://qt.gtimg.cn/q={','.join(parts)}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode('gbk', errors='replace')
            results = {}
            for line in raw.strip().split('\n'):
                if '="' not in line:
                    continue
                fields = line.split('~')
                if len(fields) < 46:
                    continue
                code = fields[2]
                circ_mcap = float(fields[45]) if fields[45] else 0  # 流通市值(亿)
                total_mcap = float(fields[44]) if fields[44] else 0
                results[code] = {'circMcapYi': circ_mcap, 'totalMcapYi': total_mcap}
            return results
    except Exception as e:
        print(f"ERROR quote: {e}", file=sys.stderr)
        return {}

def fetch_kline(code, days=30):
    prefix = market_prefix(code)
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,{days},qfq"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            klines = data.get('data', {}).get(f'{prefix}{code}', {}).get('qfqday', [])
            if not klines:
                klines = data.get('data', {}).get(f'{prefix}{code}', {}).get('day', [])
            return klines
    except Exception as e:
        return []

def compute_factors(c, klines, circ_mcap_yi):
    if not klines or len(klines) < 20:
        return None

    closes, volumes, highs, lows = [], [], [], []
    for k in klines:
        try:
            closes.append(float(k[2]))
            volumes.append(float(k[5]))
            highs.append(float(k[3]))
            lows.append(float(k[4]))
        except (ValueError, IndexError):
            continue

    if len(closes) < 20:
        return None

    n = len(closes)
    cur = closes[-1]
    is_kcb_stock = is_kcb(c['code'])

    # --- 20-day avg turnover amount ---
    # 科创板 volume in shares, others in 手 (lots)
    rvols = volumes[-20:]
    rcloses = closes[-20:]
    if is_kcb_stock:
        amounts = [v * c for v, c in zip(rvols, rcloses)]
    else:
        amounts = [v * 100 * c for v, c in zip(rvols, rcloses)]
    avg_amount20d = round(sum(amounts) / 20 / 1e8, 2)

    # --- 20-day avg turnover rate ---
    if circ_mcap_yi > 0:
        avg_turnover_20d = round(avg_amount20d / circ_mcap_yi * 100, 2)
    else:
        avg_turnover_20d = c.get('turnoverPct', 0)

    # --- Momentum ---
    m5 = round((cur / closes[-6] - 1) * 100, 2) if n >= 6 else None
    m10 = round((cur / closes[-11] - 1) * 100, 2) if n >= 11 else None
    m20 = round((cur / closes[-21] - 1) * 100, 2) if n >= 21 else None

    ma5 = round(sum(closes[-5:]) / 5, 2) if n >= 5 else None
    ma10 = round(sum(closes[-10:]) / 10, 2) if n >= 10 else None
    ma20 = round(sum(closes[-20:]) / 20, 2) if n >= 20 else None

    # --- Momentum uniformity ---
    up_days = 0
    max_single = 0
    if n >= 6:
        for i in range(-5, 0):
            dc = (closes[i] / closes[i-1] - 1) * 100
            if dc > 0:
                up_days += 1
            if dc > max_single:
                max_single = dc

    # --- Volume health ---
    up_vol = 0.0; down_vol = 0.0
    if n >= 6:
        for i in range(-5, 0):
            dc = (closes[i] / closes[i-1] - 1) * 100
            if dc > 0:
                up_vol += volumes[i]
            else:
                down_vol += volumes[i]
    vol_health = round(up_vol / down_vol, 2) if down_vol > 0 else (2.0 if up_vol > 0 else 1.0)

    # --- Momentum acceleration ---
    accel = round((m5 / 5) - ((m10 - m5) / 5), 2) if m5 and m10 else None

    # --- Pullback ---
    high_20 = max(highs[-20:])
    pullback = round((cur - high_20) / high_20 * 100, 2)

    avg_vol_5 = sum(volumes[-5:]) / 5 if n >= 5 else 0
    avg_vol_20 = sum(volumes[-20:]) / 20
    pullback_vol_ratio = round(avg_vol_5 / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0

    # --- RSI-14 ---
    rsi = None
    if n >= 15:
        gains = 0.0; losses = 0.0
        for i in range(-14, 0):
            chg = closes[i] - closes[i-1]
            if chg > 0: gains += chg
            else: losses += abs(chg)
        rsi = round(100 - (100 / (1 + gains / losses)), 1) if losses > 0 else (100.0 if gains > 0 else 0.0)

    breakout = cur >= high_20 * 0.98
    high_5 = max(highs[-5:])
    near_5d_high = round(cur / high_5, 4) if high_5 > 0 else 1.0

    # Volume ratio (5d / 20d avg volume)
    vol_ratio = round(avg_vol_5 / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0

    return {
        'm5': m5, 'm10': m10, 'm20': m20,
        'ma5': ma5, 'ma10': ma10, 'ma20': ma20,
        'aboveMA5': cur > ma5 if ma5 else None,
        'aboveMA10': cur > ma10 if ma10 else None,
        'aboveMA20': cur > ma20 if ma20 else None,
        'avgAmount20d': avg_amount20d,
        'avgTurnover20d': avg_turnover_20d,
        'momentumUniformity': f"{up_days}/5",
        'maxSingleDayPct': round(max_single, 2),
        'volumeHealth': vol_health,
        'momentumAccel': accel,
        'pullbackDepth': pullback,
        'pullbackVolumeRatio': pullback_vol_ratio,
        'rsi14': rsi,
        'breakout': breakout,
        'near5dHigh': near_5d_high,
        'volumeRatio': vol_ratio,
    }

def apply_filters(c, f):
    reasons = []

    # 1. 日均成交额 >= 1亿
    if f['avgAmount20d'] < 1.0:
        reasons.append(f"日均成交额20日={f['avgAmount20d']}亿<1亿")

    # 2. 20日平均换手率 1%-7%
    to20 = f['avgTurnover20d']
    if to20 < 1.0:
        reasons.append(f"20日均换手={to20}%<1%(偏冷)")
    elif to20 > 7.0:
        reasons.append(f"20日均换手={to20}%>7%(高位警惕派发)")

    # 3. 自由流通市值 >= 30亿
    if c['mktcapYi'] < 30:
        reasons.append(f"市值={c['mktcapYi']}亿<30亿")

    # 4. 量比极端 (use volumeRatio)
    if f['volumeRatio'] > 3.0:
        reasons.append(f"量比(5日/20日均)={f['volumeRatio']}>3(天量恐见顶)")

    # 5. 透支判断: 近5日涨>30%
    if f['m5'] is not None and f['m5'] > 30:
        reasons.append(f"近5日涨幅={f['m5']}%>30%(透支剔除)")

    # 6. 透支判断: 近20日涨>25% 且近5日转负
    if f['m20'] is not None and f['m5'] is not None:
        if f['m20'] > 25 and f['m5'] < 0:
            reasons.append(f"近20日涨={f['m20']}%>25%且近5日转负(主升浪结束)")

    # 7. 一字涨停检查: 涨停+换手极低
    if c['dayChangePct'] >= 9.9 and c['turnoverPct'] < 1.0:
        reasons.append(f"涨停换手={c['turnoverPct']}%<1%(疑似一字板)")

    # 8. 1w账户: 股价<40元
    if c['price'] > 40:
        reasons.append(f"股价={c['price']}元>40元(1w账户不可配)")

    if reasons:
        return False, "; ".join(reasons)
    return True, None

def compute_entry_signal(c, f):
    m5 = f['m5']; m20 = f['m20']
    pullback = f['pullbackDepth']; pullback_vol = f['pullbackVolumeRatio']
    rsi = f['rsi14']; above_ma20 = f['aboveMA20']

    # A. 健康回调买点
    if above_ma20 and m5 is not None and -8 <= m5 <= -3 and pullback_vol < 0.8 and rsi is not None and 40 <= rsi <= 50:
        return "健康回调买点", 20

    # B. 突破回踩确认
    if f['breakout'] and pullback < 0 and pullback > -3 and pullback_vol < 0.8:
        return "突破回踩确认", 15

    # C. 超跌反弹启动
    if m20 is not None and m20 < -15 and m5 is not None and m5 > 0 and pullback_vol > 1.2:
        return "超跌反弹启动", 10

    # D. 追涨入场(负分)
    if m5 is not None and m5 > 10 and f['near5dHigh'] > 0.98 and pullback_vol > 1.5:
        return "追涨入场(警惕)", -15

    # E. 高位派发(负分)
    if m20 is not None and m20 > 20 and m5 is not None and m5 < 0 and pullback_vol > 1.5 and not f.get('aboveMA5', True):
        return "高位派发(危险)", -20

    # F. 趋势延续
    if above_ma20 and f['momentumUniformity'] in ['4/5', '5/5'] and m5 is not None and 0 < m5 < 15:
        return "趋势延续", 5

    # G. 突破启动
    if f['breakout'] and pullback_vol > 1.2 and m5 is not None and m5 > 0:
        return "突破启动", 12

    # H. 弱势反弹(偏负)
    if not above_ma20 and m5 is not None and m5 < 0:
        return "弱势(下跌趋势)", -5

    return "无明确信号", 0

def compute_exhaustion(c, f):
    m5 = f['m5']; m20 = f['m20']
    if m5 is None or m20 is None:
        return "低(<30%)", "数据不足"

    if m5 > 15:
        return "高概率(>70%)", "近5日涨>15%且催化在7日内"
    elif m20 > 25 and m5 < 0:
        return "极高(>80%)", "近20日涨>25%且近5日转负(主升浪结束)"
    elif 5 < m5 <= 15:
        return "低(<30%)", "近5日涨5-15%启动期"
    elif m20 > 20 and m5 > 0:
        return "中概率(40%)", "近20日涨>20%需观察是否减速"
    else:
        return "低(<30%)", "动量正常范围"

def compute_mean_reversion(c, f):
    m10 = f['m10']; m5 = f['m5']; rsi = f['rsi14']
    if m10 is not None and m10 < -8 and m5 is not None and m5 > 0:
        return "超跌反弹", 8
    if f['pullbackDepth'] < -15 and rsi is not None and rsi < 30:
        return "布林下轨", 8
    if rsi is not None and rsi < 25:
        return "超卖极端", 5
    return None, 0

def main():
    # Step 1: Fetch all quotes for circulating market cap
    all_codes = [c['code'] for c in CANDIDATES]
    quotes = fetch_quote(all_codes)
    print(f"Fetched quotes for {len(quotes)} stocks", file=sys.stderr)

    results = {'pass': [], 'reject': [], 'factors': []}
    pass_codes = []

    for c in CANDIDATES:
        code = c['code']; name = c['name']
        q = quotes.get(code, {})
        circ_mcap = q.get('circMcapYi', c['mktcapYi'])

        klines = fetch_kline(code, days=30)
        if not klines or len(klines) < 20:
            results['reject'].append({'code': code, 'name': name, 'reason': 'K线数据缺失(不足20日)'})
            continue

        f = compute_factors(c, klines, circ_mcap)
        if f is None:
            results['reject'].append({'code': code, 'name': name, 'reason': '因子计算失败'})
            continue

        ok, reason = apply_filters(c, f)
        if not ok:
            results['reject'].append({
                'code': code, 'name': name, 'reason': reason,
                'avgAmount20d': f['avgAmount20d'],
                'avgTurnover20d': f['avgTurnover20d'],
                'm5': f['m5'], 'm20': f['m20'],
                'mktcapYi': c['mktcapYi'],
                'price': c['price'],
            })
            continue

        # Passed
        entry_type, entry_score = compute_entry_signal(c, f)
        exhaustion_prob, exhaust_reason = compute_exhaustion(c, f)
        mr_signal, mr_score = compute_mean_reversion(c, f)

        # Technical level
        if f['aboveMA5'] and f['aboveMA10'] and f['aboveMA20']:
            tech = "多头排列"
        elif f['aboveMA20']:
            tech = "MA20上方"
        elif not f['aboveMA20'] and f['m5'] is not None and f['m5'] > 0:
            tech = "MA20下方但5日反弹"
        else:
            tech = "空头排列"

        rps = f['m5'] if f['m5'] is not None else 0

        results['pass'].append({
            'code': code, 'name': name,
            'price': c['price'],
            'avgAmount20d': f['avgAmount20d'],
            'turnover20d': f['avgTurnover20d'],
            'volumeRatio': f['volumeRatio'],
            'marketCap': c['mktcapYi'],
            'pass': True,
        })

        results['factors'].append({
            'code': code, 'name': name,
            'm5': f['m5'], 'm10': f['m10'], 'm20': f['m20'],
            'momentumUniformity': f['momentumUniformity'],
            'volumeHealth': f['volumeHealth'],
            'momentumAccel': f['momentumAccel'],
            'entryType': entry_type, 'entryScore': entry_score,
            'meanReversionSignal': mr_signal, 'meanReversionScore': mr_score,
            'pullbackDepth': f['pullbackDepth'],
            'pullbackVolume': f['pullbackVolumeRatio'],
            'exhaustionProb': exhaustion_prob,
            'breakout': f['breakout'],
            'aboveMA20': f['aboveMA20'],
            'rsi14': f['rsi14'],
            'rps': round(rps, 2),
            'technicalLevel': tech,
            'sector': c['sector'],
            'note': c['note'],
        })
        pass_codes.append(code)

    # Summary
    entry_dist = {}
    for ft in results['factors']:
        et = ft['entryType']
        entry_dist[et] = entry_dist.get(et, 0) + 1

    reject_reasons = {}
    for r in results['reject']:
        first = r['reason'].split(';')[0]
        reject_reasons[first] = reject_reasons.get(first, 0) + 1

    top_reason = max(reject_reasons, key=reject_reasons.get) if reject_reasons else "无"

    summary = (f"过关{len(results['pass'])}只/剔除{len(results['reject'])}只"
               f" | 入场分布:{entry_dist}"
               f" | 主要剔除原因:{top_reason}")

    output = {
        'agent': 'technical-liquidity',
        'asOf': '20260722',
        'data': {
            'pass': results['pass'],
            'reject': results['reject'],
            'factors': results['factors'],
            'passCodes': ','.join(pass_codes),
            'summary': summary,
        }
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()