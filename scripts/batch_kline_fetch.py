#!/usr/bin/env python3
"""Batch fetch kline data for all 40 candidates using Tencent HTTP API (bypasses proxy)."""
import urllib.request
import urllib.error
import ssl
import json
import sys
import os

# Bypass proxy for Tencent
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Proxy bypass handler
proxy_handler = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=ctx))
urllib.request.install_opener(opener)

# All 40 candidates from sector-analyst.json
CANDIDATES = [
    ("603118", "共进股份"), ("000063", "中兴通讯"), ("002396", "星网锐捷"),
    ("603803", "瑞斯康达"), ("000815", "美利云"), ("000938", "紫光股份"),
    ("603162", "海通发展"), ("002545", "东方铁塔"), ("002412", "汉森制药"),
    ("000506", "招金黄金"), ("000975", "山金国际"), ("000603", "盛达资源"),
    ("601899", "紫金矿业"), ("603993", "洛阳钼业"), ("300139", "晓程科技"),
    ("600396", "华电辽能"), ("600403", "大有能源"), ("600744", "华银电力"),
    ("600726", "华电能源"), ("000539", "粤电力A"), ("600644", "乐山电力"),
    ("300105", "龙源技术"), ("600722", "金牛化工"), ("002185", "华天科技"),
    ("002436", "兴森科技"), ("688620", "安凯微"), ("000021", "深科技"),
    ("688049", "炬芯科技"), ("300458", "全志科技"), ("688166", "博瑞医药"),
    ("688046", "药康生物"), ("603538", "美诺华"), ("300006", "莱美药业"),
    ("300164", "通源石油"), ("002167", "东方锆业"), ("000676", "智度股份"),
    ("300834", "星辉环材"), ("002213", "大为股份"), ("000839", "国安股份"),
    ("000595", "新能股份"),
]

def market_prefix(code):
    """Return sh or sz prefix for Tencent API."""
    if code.startswith(('6', '9')):
        return 'sh'
    return 'sz'

def fetch_kline(code, days=30):
    """Fetch daily kline data from Tencent."""
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
        print(f"ERROR fetching kline for {code}: {e}", file=sys.stderr)
        return []

def compute_momentum(klines):
    """Compute momentum factors from kline data."""
    if not klines or len(klines) < 20:
        return None

    # Parse klines: [date, open, close, high, low, volume]
    closes = []
    volumes = []
    highs = []
    lows = []
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

    # 5-day momentum
    m5 = (closes[-1] / closes[-6] - 1) * 100 if n >= 6 else None
    # 10-day momentum
    m10 = (closes[-1] / closes[-11] - 1) * 100 if n >= 11 else None
    # 20-day momentum
    m20 = (closes[-1] / closes[-21] - 1) * 100 if n >= 21 else None

    # MA5, MA10, MA20
    ma5 = sum(closes[-5:]) / 5 if n >= 5 else None
    ma10 = sum(closes[-10:]) / 10 if n >= 10 else None
    ma20 = sum(closes[-20:]) / 20 if n >= 20 else None

    current = closes[-1]
    above_ma5 = current > ma5 if ma5 else None
    above_ma10 = current > ma10 if ma10 else None
    above_ma20 = current > ma20 if ma20 else None

    # 20-day average turnover amount
    avg_amount20 = None
    if n >= 20 and len(volumes) >= 20:
        # Estimate turnover from volume * typical price
        recent_volumes = volumes[-20:]
        recent_closes = closes[-20:]
        avg_amount20 = sum(v * c for v, c in zip(recent_volumes, recent_closes)) / 20 / 1e8  # in 亿元

    # Momentum uniformity: how many of last 5 days were up
    up_days_5 = 0
    max_single_day = 0
    if n >= 6:
        for i in range(-5, 0):
            daily_chg = (closes[i] / closes[i-1] - 1) * 100
            if daily_chg > 0:
                up_days_5 += 1
            if daily_chg > max_single_day:
                max_single_day = daily_chg

    # Volume health: up-day volume / down-day volume in last 5 days
    up_vol = 0
    down_vol = 0
    if n >= 6:
        for i in range(-5, 0):
            daily_chg = (closes[i] / closes[i-1] - 1) * 100
            if daily_chg > 0:
                up_vol += volumes[i]
            else:
                down_vol += volumes[i]

    vol_health = (up_vol / down_vol) if down_vol > 0 else (2.0 if up_vol > 0 else 1.0)

    # Momentum acceleration: (m5/5) vs (m10-m5)/5
    accel = None
    if m5 is not None and m10 is not None:
        accel = (m5 / 5) - ((m10 - m5) / 5) if m5 != 0 else 0

    # Pullback from recent high
    high_20 = max(highs[-20:]) if n >= 20 else max(highs)
    pullback = (current - high_20) / high_20 * 100

    # Pullback volume: last 5 days avg volume vs 20-day avg
    avg_vol_5 = sum(volumes[-5:]) / 5 if n >= 5 else 0
    avg_vol_20 = sum(volumes[-20:]) / 20 if n >= 20 else 0
    pullback_vol_ratio = avg_vol_5 / avg_vol_20 if avg_vol_20 > 0 else 1.0

    # RSI-14 (approximate)
    rsi = None
    if n >= 15:
        gains = 0
        losses = 0
        for i in range(-14, 0):
            chg = closes[i] - closes[i-1]
            if chg > 0:
                gains += chg
            else:
                losses += abs(chg)
        if losses > 0:
            rs = gains / losses
            rsi = 100 - (100 / (1 + rs))
        elif gains > 0:
            rsi = 100
        else:
            rsi = 0

    # Breakout detection: current close vs 20-day high
    breakout = current >= high_20 * 0.98 if n >= 20 else False

    # Near 5-day high ratio
    high_5 = max(highs[-5:]) if n >= 5 else current
    near_5d_high = current / high_5 if high_5 > 0 else 1.0

    return {
        'm5': round(m5, 2) if m5 is not None else None,
        'm10': round(m10, 2) if m10 is not None else None,
        'm20': round(m20, 2) if m20 is not None else None,
        'ma5': round(ma5, 2) if ma5 else None,
        'ma10': round(ma10, 2) if ma10 else None,
        'ma20': round(ma20, 2) if ma20 else None,
        'aboveMA5': above_ma5,
        'aboveMA10': above_ma10,
        'aboveMA20': above_ma20,
        'avgAmount20d': round(avg_amount20, 2) if avg_amount20 else None,
        'momentumUniformity': f"{up_days_5}/5",
        'maxSingleDayPct': round(max_single_day, 2),
        'volumeHealth': round(vol_health, 2),
        'momentumAccel': round(accel, 2) if accel is not None else None,
        'pullbackDepth': round(pullback, 2),
        'pullbackVolumeRatio': round(pullback_vol_ratio, 2),
        'rsi14': round(rsi, 1) if rsi is not None else None,
        'breakout': breakout,
        'near5dHigh': round(near_5d_high, 4),
        'rawCloses': closes[-21:] if n >= 21 else closes,
        'rawVolumes': volumes[-21:] if n >= 21 else volumes,
    }

def main():
    results = {}
    for code, name in CANDIDATES:
        klines = fetch_kline(code, days=30)
        if not klines:
            print(f"{code} {name}: KLINE_FETCH_FAILED", file=sys.stderr)
            results[f"{code}_{name}"] = None
            continue
        factors = compute_momentum(klines)
        if factors:
            # Remove raw data for output
            factors.pop('rawCloses', None)
            factors.pop('rawVolumes', None)
            results[f"{code}_{name}"] = factors
        else:
            results[f"{code}_{name}"] = None
        print(f"{code} {name}: OK, klines={len(klines)}", file=sys.stderr)

    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()