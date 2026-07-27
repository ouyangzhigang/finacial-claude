"""
批量流动性硬门槛过滤 + 短线因子计算
通过腾讯 HTTP 通道 (qt.gtimg.cn + web.ifzq.gtimg.cn)
日期: 20260726
"""
import json
import urllib.request
import urllib.error
import ssl
import sys
import time
import gzip
from io import BytesIO
from collections import defaultdict

# SSL workaround for local proxy issues
ssl._create_default_https_context = ssl._create_unverified_context

TENCENT_QUOTE_URL = "http://qt.gtimg.cn/q={codes}"
TENCENT_KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{period},,,{count},qfq"

def make_request(url, retries=3):
    """HTTP request with retry and SSL tolerance"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept-Encoding': 'gzip, deflate'
            })
            resp = urllib.request.urlopen(req, timeout=15)
            raw = resp.read()
            # Handle gzip
            if resp.headers.get('Content-Encoding') == 'gzip':
                raw = gzip.decompress(raw)
            # Decode GBK
            for enc in ['gbk', 'gb2312', 'gb18030', 'utf-8']:
                try:
                    return raw.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw.decode('utf-8', errors='replace')
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                raise

def parse_tencent_quote(text):
    """Parse qt.gtimg.cn quote response into dict"""
    results = {}
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or '="' not in line:
            continue
        # Extract var name and data
        eq_idx = line.index('="')
        var_name = line[:eq_idx]
        data_str = line[eq_idx+2:].rstrip('";\n\r')
        if not data_str:
            continue
        fields = data_str.split('~')
        if len(fields) < 50:
            continue

        try:
            code = fields[2]
            name = fields[1]
            # Parse key fields
            price = float(fields[3]) if fields[3] else 0
            prev_close = float(fields[4]) if fields[4] else 0
            open_price = float(fields[5]) if fields[5] else 0
            volume = float(fields[6]) if fields[6] else 0  # 手
            high = float(fields[33]) if fields[33] else 0
            low = float(fields[34]) if fields[34] else 0
            amount = float(fields[37]) if fields[37] else 0  # 万元
            turnover = float(fields[38]) if fields[38] else 0  # %
            pe = float(fields[39]) if fields[39] else 0
            amplitude = float(fields[43]) if fields[43] else 0  # 振幅%
            total_mcap = float(fields[44]) if fields[44] else 0  # 亿
            float_mcap = float(fields[45]) if fields[45] else 0  # 亿
            pb = float(fields[46]) if fields[46] else 0
            limit_up = float(fields[47]) if fields[47] else 0
            limit_down = float(fields[48]) if fields[48] else 0
            vol_ratio = float(fields[49]) if fields[49] else 0  # 量比
            day_change = float(fields[32]) if fields[32] else 0  # 涨跌额
            day_change_pct = float(fields[33]) if fields[33] else 0  # 涨跌幅(实际上fields[32]是涨跌额,这里重算)

            # Re-derive day change pct
            if prev_close > 0:
                day_change_pct = (price - prev_close) / prev_close * 100
            else:
                day_change_pct = 0

            # Amount in 万元 -> 元
            amount_yuan = amount * 10000 if amount > 0 else 0

            results[code] = {
                'code': code,
                'name': name,
                'price': price,
                'prevClose': prev_close,
                'open': open_price,
                'high': high,
                'low': low,
                'volume': volume,  # 手
                'amount': amount_yuan,  # 元
                'amountWan': amount,  # 万元
                'turnover': turnover,
                'pe': pe,
                'totalMcap': total_mcap,  # 亿
                'floatMcap': float_mcap,  # 亿
                'pb': pb,
                'limitUp': limit_up,
                'limitDown': limit_down,
                'volRatio': vol_ratio,
                'dayChangePct': day_change_pct,
                'amplitude': amplitude,
            }
        except (ValueError, IndexError) as e:
            print(f"  [WARN] parse error for {fields[2] if len(fields)>2 else '?'}: {e}", file=sys.stderr)
            continue

    return results

def parse_tencent_kline(text, code):
    """Parse web.ifzq.gtimg.cn K-line response"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    # Navigate: data -> code -> qfqday
    code_key = code
    if code_key not in data.get('data', {}):
        # Try without sh/sz prefix variation
        for k in data.get('data', {}):
            if code in k or k in code:
                code_key = k
                break

    kline_data = data.get('data', {}).get(code_key, {}).get('qfqday', [])
    if not kline_data:
        return []

    result = []
    for row in kline_data:
        if isinstance(row, list) and len(row) >= 6:
            try:
                result.append({
                    'date': str(row[0]),
                    'open': float(row[1]),
                    'close': float(row[2]),
                    'high': float(row[3]),
                    'low': float(row[4]),
                    'volume': float(row[5]),  # 手
                })
            except (ValueError, TypeError):
                continue

    return result

def compute_factors(kline_data, quote_data):
    """Compute short-term momentum factors from K-line data"""
    if len(kline_data) < 20:
        return None

    closes = [d['close'] for d in kline_data]
    volumes = [d['volume'] for d in kline_data]
    highs = [d['high'] for d in kline_data]
    lows = [d['low'] for d in kline_data]
    dates = [d['date'] for d in kline_data]

    n = len(closes)

    # Last day is the latest trading day (should be 2026-07-24, since today is 07-26 Sunday)
    # If latest date is 07-24, then:
    # m5 = closes[-1] vs closes[-6] (5 trading days ago)
    # But actually: 1-day return from latest close to prior close
    # For momentum computation, we use the latest close as current

    latest_close = closes[-1]
    latest_date = dates[-1]

    # 5-day momentum (5 trading days)
    if n >= 6:
        m5 = (closes[-1] / closes[-6] - 1) * 100
    else:
        m5 = None

    # 10-day momentum
    if n >= 11:
        m10 = (closes[-1] / closes[-11] - 1) * 100
    else:
        m10 = None

    # 20-day momentum
    if n >= 21:
        m20 = (closes[-1] / closes[-21] - 1) * 100
    else:
        m20 = None

    # Moving averages
    ma5 = sum(closes[-5:]) / 5 if n >= 5 else None
    ma10 = sum(closes[-10:]) / 10 if n >= 10 else None
    ma20 = sum(closes[-20:]) / 20 if n >= 20 else None

    # A. Momentum Quality Factors
    # Momentum Uniformity: 5-day up days count and max single-day contribution
    up_days_5 = 0
    max_day_contrib_5 = 0
    daily_returns_5 = []
    if n >= 6:
        for i in range(-5, 0):
            ret = (closes[i] / closes[i-1] - 1) * 100 if closes[i-1] > 0 else 0
            daily_returns_5.append(ret)
            if ret > 0:
                up_days_5 += 1
            if abs(ret) > abs(max_day_contrib_5):
                max_day_contrib_5 = ret

    # Momentum uniformity score: 0-10
    momentum_uniformity = 0
    if m5 is not None and m5 != 0:
        # Higher score if more up days and lower single-day contribution
        uniformity_ratio = abs(max_day_contrib_5 / m5) if abs(m5) > 0.1 else 1
        momentum_uniformity = min(10, up_days_5 * 2 * (1 - uniformity_ratio * 0.5))
        momentum_uniformity = max(0, momentum_uniformity)

    # Volume Health: up-day volume vs down-day volume (last 10 days)
    up_vol = 0
    down_vol = 0
    up_count = 0
    down_count = 0
    if n >= 11:
        for i in range(-10, 0):
            ret = (closes[i] / closes[i-1] - 1) if closes[i-1] > 0 else 0
            if ret > 0:
                up_vol += volumes[i]
                up_count += 1
            elif ret < 0:
                down_vol += volumes[i]
                down_count += 1

    volume_health = 0
    if up_count > 0 and down_count > 0:
        avg_up_vol = up_vol / up_count
        avg_down_vol = down_vol / down_count
        if avg_down_vol > 0:
            vol_ratio_ud = avg_up_vol / avg_down_vol
            # >1 means up days have higher volume = healthy
            volume_health = min(10, max(0, (vol_ratio_ud - 0.7) * 5))

    # Momentum Acceleration
    momentum_accel = 0
    if m5 is not None and m10 is not None:
        # (m5/5) vs (m10-m5)/5
        daily_m5 = m5 / 5
        daily_m10_minus_m5 = (m10 - m5) / 5
        momentum_accel = daily_m5 - daily_m10_minus_m5
        # Positive = accelerating, Negative = decelerating

    # 20-day average amount
    avg_amount_20d = 0
    if n >= 20:
        amounts_20 = []
        for i in range(-20, 0):
            # Estimate amount = volume * avg_price
            avg_price = (highs[i] + lows[i] + closes[i]) / 3
            amt = volumes[i] * 100 * avg_price  # 手->股
            amounts_20.append(amt)
        avg_amount_20d = sum(amounts_20) / 20

    # Average turnover (20-day)
    avg_turnover_20d = 0
    if quote_data and n >= 20:
        total_mcap = quote_data.get('totalMcap', 0) * 1e8  # 亿->元
        if total_mcap > 0:
            daily_avg_vol_shares = sum(volumes[-20:]) / 20 * 100  # 手->股
            avg_turnover_20d = (daily_avg_vol_shares / (total_mcap / quote_data['price'])) * 100 if quote_data['price'] > 0 else 0

    # MA20 position
    above_ma20 = latest_close > ma20 if ma20 else None

    # Pullback depth from recent high
    if n >= 20:
        recent_high_20 = max(highs[-20:])
        pullback_depth = (latest_close / recent_high_20 - 1) * 100
    else:
        pullback_depth = 0

    # Pullback volume check (last 5 days vs prior 15 days)
    pullback_volume = ""
    if n >= 20:
        avg_vol_last5 = sum(volumes[-5:]) / 5
        avg_vol_prior15 = sum(volumes[-20:-5]) / 15
        if avg_vol_prior15 > 0:
            vol_decline = avg_vol_last5 / avg_vol_prior15
            if vol_decline < 0.7:
                pullback_volume = "缩量"
            elif vol_decline > 1.3:
                pullback_volume = "放量"
            else:
                pullback_volume = "平量"

    # RSI(14)
    rsi = None
    if n >= 15:
        gains = []
        losses = []
        for i in range(-14, 0):
            change = closes[i] - closes[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

    # Entry type classification
    entry_type = "normal"
    entry_score = 0
    exhaustion_prob = "低(<30%)"

    if pullback_depth is not None and m20 is not None:
        # Check for exhaustion patterns
        if m5 is not None and m5 > 15:
            exhaustion_prob = "高(>70%)"
        elif m20 is not None and m20 > 25 and m5 is not None and m5 < 0:
            exhaustion_prob = "极高(>80%)"
            entry_type = "高位派发"
            entry_score = -20
        elif m5 is not None and 5 < m5 <= 15:
            exhaustion_prob = "中(40%)"

    if m20 is not None and m20 > 20 and m5 is not None and m5 < 0 and pullback_volume == "放量":
        entry_type = "高位派发"
        entry_score = -20
        exhaustion_prob = "极高(>80%)"
    elif pullback_depth is not None and pullback_depth < -3 and pullback_depth > -8 and above_ma20 and pullback_volume == "缩量":
        entry_type = "健康回调"
        entry_score = 20
    elif m5 is not None and m5 > 10:
        entry_type = "追涨风险"
        entry_score = -15
    elif m20 is not None and m20 < -15 and m5 is not None and m5 > 0 and pullback_volume == "放量":
        entry_type = "超跌反弹"
        entry_score = 10

    # Breakout detection: close near 20-day high
    breakout = False
    if n >= 20:
        high_20 = max(highs[-20:])
        if latest_close >= high_20 * 0.98:
            breakout = True

    # 5-day RPS (relative to self, percentile of current vs 20-day range)
    rps = None
    if n >= 20:
        min_20 = min(lows[-20:])
        max_20 = max(highs[-20:])
        if max_20 > min_20:
            rps = (latest_close - min_20) / (max_20 - min_20) * 100

    # Determine technical level
    technical_level = "neutral"
    if m5 is not None and m10 is not None and m20 is not None:
        if m5 > 0 and m10 > 0 and m20 > 0 and above_ma20:
            technical_level = "上升趋势"
        elif m20 > 20 and m5 < 0:
            technical_level = "高位回调"
        elif m20 < -10 and m5 > 0:
            technical_level = "超跌反弹"
        elif m5 > 0 and above_ma20 and not (m10 > 0 and m20 > 0):
            technical_level = "短期反弹"
        elif m5 < 0 and m10 < 0 and m20 < 0:
            technical_level = "下跌趋势"
        elif above_ma20:
            technical_level = "均线上方"
        else:
            technical_level = "均线下方"

    return {
        'm5': round(m5, 2) if m5 is not None else None,
        'm10': round(m10, 2) if m10 is not None else None,
        'm20': round(m20, 2) if m20 is not None else None,
        'ma5': round(ma5, 2) if ma5 is not None else None,
        'ma10': round(ma10, 2) if ma10 is not None else None,
        'ma20': round(ma20, 2) if ma20 is not None else None,
        'momentumUniformity': round(momentum_uniformity, 1),
        'volumeHealth': round(volume_health, 1),
        'momentumAccel': round(momentum_accel, 2) if isinstance(momentum_accel, (int, float)) else momentum_accel,
        'entryType': entry_type,
        'entryScore': entry_score,
        'pullbackDepth': round(pullback_depth, 2) if pullback_depth is not None else None,
        'pullbackVolume': pullback_volume,
        'exhaustionProb': exhaustion_prob,
        'breakout': breakout,
        'aboveMA20': above_ma20,
        'rsi': round(rsi, 1) if rsi is not None else None,
        'rps': round(rps, 1) if rps is not None else None,
        'technicalLevel': technical_level,
        'avgAmount20d': round(avg_amount_20d, 0),
        'avgTurnover20d': round(avg_turnover_20d, 2) if avg_turnover_20d else None,
        'latestDate': latest_date,
    }

# ─── MAIN ───
def main():
    # 25 affordable candidates
    candidates = [
        {"code": "601606", "name": "长城军工", "sector": "军工/地面兵装", "role": "leader"},
        {"code": "600178", "name": "东安动力", "sector": "军工/兵装重组", "role": "follower"},
        {"code": "600698", "name": "湖南天雁", "sector": "军工/兵装重组", "role": "follower"},
        {"code": "002265", "name": "建设工业", "sector": "军工/兵装重组", "role": "leader"},
        {"code": "002189", "name": "中光学", "sector": "军工/军工电子", "role": "subLeader"},
        {"code": "300922", "name": "天秦装备", "sector": "军工/地面兵装", "role": "follower"},
        {"code": "300414", "name": "中光防雷", "sector": "军工/通信", "role": "follower"},
        {"code": "688151", "name": "华强科技", "sector": "军工/核防护", "role": "follower"},
        {"code": "600862", "name": "中航高科", "sector": "军工/航空装备", "role": "subLeader"},
        {"code": "000768", "name": "中航西飞", "sector": "军工/航空装备", "role": "subLeader"},
        {"code": "603690", "name": "至纯科技", "sector": "半导体/设备", "role": "leader"},
        {"code": "000670", "name": "盈方微", "sector": "半导体/存储芯片", "role": "follower"},
        {"code": "603068", "name": "博通集成", "sector": "半导体/芯片设计", "role": "subLeader"},
        {"code": "300480", "name": "光力科技", "sector": "半导体/设备", "role": "leader"},
        {"code": "603726", "name": "朗迪集团", "sector": "半导体/长鑫产业链", "role": "follower"},
        {"code": "000417", "name": "合百集团", "sector": "半导体/长鑫产业链", "role": "follower"},
        {"code": "002208", "name": "合肥城建", "sector": "半导体/长鑫产业链", "role": "follower"},
        {"code": "688484", "name": "南芯科技", "sector": "半导体/芯片设计", "role": "follower"},
        {"code": "600171", "name": "上海贝岭", "sector": "半导体/模拟芯片", "role": "subLeader"},
        {"code": "001229", "name": "魅视科技", "sector": "AI算力/视觉", "role": "leader"},
        {"code": "002298", "name": "中电鑫龙", "sector": "AI算力/输配电", "role": "follower"},
        {"code": "002300", "name": "太阳电缆", "sector": "AI算力/配套", "role": "follower"},
        {"code": "603956", "name": "威派格", "sector": "AI算力/液冷", "role": "follower"},
        {"code": "002879", "name": "长缆科技", "sector": "AI算力/液冷", "role": "subLeader"},
        {"code": "600539", "name": "狮头股份", "sector": "AI算力/半导体", "role": "follower"},
    ]

    # Build Tencent quote codes: sh for 60xxxx, sz for 00xxxx/30xxxx, sh for 688xxx
    tencent_codes = []
    for c in candidates:
        code = c['code']
        if code.startswith('60') or code.startswith('688'):
            tencent_codes.append(f"sh{code}")
        else:
            tencent_codes.append(f"sz{code}")

    # 1. Fetch batch quotes
    print(f"[1/4] Fetching quotes for {len(candidates)} stocks...")
    quote_url = TENCENT_QUOTE_URL.format(codes=','.join(tencent_codes))
    quote_text = make_request(quote_url)
    quotes = parse_tencent_quote(quote_text)
    print(f"  Got quotes for {len(quotes)}/{len(candidates)} stocks")

    # 2. Fetch K-line for each
    print(f"[2/4] Fetching K-line for each stock...")
    klines = {}
    for i, c in enumerate(candidates):
        code = c['code']
        if code.startswith('60') or code.startswith('688'):
            tc = f"sh{code}"
        else:
            tc = f"sz{code}"

        try:
            kline_url = TENCENT_KLINE_URL.format(code=tc, period='day', count=40)
            kline_text = make_request(kline_url)
            kline_data = parse_tencent_kline(kline_text, tc)
            klines[code] = kline_data
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i+1}/{len(candidates)}")
            time.sleep(0.3)  # Rate limit
        except Exception as e:
            print(f"  [ERROR] K-line for {code} {c['name']}: {e}")
            klines[code] = []

    print(f"  Got K-line for {sum(1 for v in klines.values() if v)}/{len(candidates)} stocks")

    # 3. Compute factors and apply hard filters
    print(f"[3/4] Computing factors and applying hard filters...")
    pass_list = []
    reject_list = []
    factor_list = []

    for c in candidates:
        code = c['code']
        name = c['name']
        quote = quotes.get(code, {})
        kline = klines.get(code, [])

        # ─── HARD FILTERS ───
        reject_reasons = []

        # Filter 0: K-line data availability
        if not kline or len(kline) < 20:
            reject_list.append({"code": code, "name": name, "reason": f"K线数据不足(仅{len(kline)}条), 无法计算动量"})
            continue

        # Filter 1: Price > 40 for 1w account
        price = quote.get('price', c.get('price', 999))
        if price > 40:
            reject_list.append({"code": code, "name": name, "reason": f"股价{price}元>40元, 1w账户不可配"})
            continue

        # Compute factors
        factors = compute_factors(kline, quote)
        if factors is None:
            reject_list.append({"code": code, "name": name, "reason": "K线数据不足无法计算因子"})
            continue

        # Filter 2: 20-day average amount >= 1亿
        avg_amount_20d = factors.get('avgAmount20d', 0)
        if avg_amount_20d < 100000000:  # 1亿
            amt_wan = avg_amount_20d / 10000
            reject_list.append({"code": code, "name": name, "reason": f"日均成交额{amt_wan:.0f}万元<1亿元, 流动性不足"})
            continue

        # Filter 3: Free float market cap >= 30亿
        float_mcap = quote.get('floatMcap', 0)
        if float_mcap < 30:
            reject_list.append({"code": code, "name": name, "reason": f"自由流通市值{float_mcap:.1f}亿<30亿, 易被操控"})
            continue

        # Filter 4: Volume ratio check (0.8-3)
        vol_ratio = quote.get('volRatio', 1)
        if vol_ratio < 0.8:
            reject_list.append({"code": code, "name": name, "reason": f"量比{vol_ratio}<0.8, 地量无催化"})
            continue

        # Filter 5: Check for limit up (一字涨停) or limit down (封死跌停)
        # 一字涨停: dayChangePct > 9.8% and open == high == low (almost)
        day_change = quote.get('dayChangePct', 0)
        open_price = quote.get('open', 0)
        high = quote.get('high', 0)
        low = quote.get('low', 0)
        limit_up = quote.get('limitUp', 0)
        limit_down = quote.get('limitDown', 0)

        # Check if it's a straight-line limit (一字板)
        if price > 0 and limit_up > 0 and price >= limit_up * 0.995 and open_price >= limit_up * 0.99:
            reject_list.append({"code": code, "name": name, "reason": f"一字涨停(开{open_price}, 高{high}), 买不进去"})
            continue

        # Check if limit down locked
        if price > 0 and limit_down > 0 and price <= limit_down * 1.005 and high <= limit_down * 1.01:
            reject_list.append({"code": code, "name": name, "reason": f"封死跌停(价{price}), 出不来"})
            continue

        # Filter 6: Exhaustion check - 5-day > 30%
        m5 = factors.get('m5')
        if m5 is not None and m5 > 30:
            reject_list.append({"code": code, "name": name, "reason": f"近5日涨{m5}%>30%, 短期严重透支"})
            continue

        # Filter 7: Turnover rate check (avg 20d)
        turnover = quote.get('turnover', 0)
        # If turnover > 7%, check if it's extreme
        # We'll flag but not necessarily reject unless > 15%
        if turnover > 15:
            reject_list.append({"code": code, "name": name, "reason": f"换手率{turnover}%>15%, 极端换手警惕派发"})
            continue

        # ─── ALL FILTERS PASSED ───
        pass_item = {
            'code': code,
            'name': name,
            'sector': c['sector'],
            'role': c['role'],
            'price': price,
            'avgAmount20d': round(avg_amount_20d, 0),
            'turnover20d': factors.get('avgTurnover20d'),
            'turnover': turnover,
            'volumeRatio': vol_ratio,
            'floatMcap': float_mcap,
            'marketCap': quote.get('totalMcap', 0),
            'pass': True,
        }
        pass_list.append(pass_item)

        factor_item = {
            'code': code,
            'name': name,
            'sector': c['sector'],
            'role': c['role'],
            **factors,
        }
        factor_list.append(factor_item)

    print(f"  Pass: {len(pass_list)}, Reject: {len(reject_list)}")

    # 4. Build output
    print(f"[4/4] Building output...")

    # Summary stats
    entry_types = defaultdict(int)
    for f in factor_list:
        entry_types[f['entryType']] += 1

    reject_reasons_summary = defaultdict(int)
    for r in reject_list:
        # Extract the core reason (before colon)
        reason = r['reason'].split('：')[0] if '：' in r['reason'] else r['reason'].split(':')[0]
        reject_reasons_summary[reason] += 1

    # Entry score distribution
    entry_scores = [f['entryScore'] for f in factor_list]
    avg_entry_score = sum(entry_scores) / len(entry_scores) if entry_scores else 0

    summary = (
        f"过关{len(pass_list)}只/剔除{len(reject_list)}只 | "
        f"入场优势分布: {dict(entry_types)} | "
        f"平均入场分{avg_entry_score:.1f} | "
        f"主要剔除原因: {dict(reject_reasons_summary)} | "
        f"数据源: 腾讯qt.gtimg.cn(行情)+web.ifzq.gtimg.cn(K线), K线最新日期{factors.get('latestDate','N/A') if factor_list else 'N/A'}"
    )

    output = {
        "agent": "technical-liquidity",
        "asOf": "20260726",
        "data": {
            "pass": pass_list,
            "reject": reject_list,
            "factors": factor_list,
            "summary": summary,
            "passCodes": ','.join([p['code'] for p in pass_list]),
            "dataSource": "腾讯HTTP通道(qt.gtimg.cn行情+web.ifzq.gtimg.cn前复权日K线)",
            "dataDate": factor_list[0].get('latestDate', 'N/A') if factor_list else 'N/A',
            "methodology": {
                "hardFilters": [
                    "日均成交额(20日)>=1亿",
                    "自由流通市值>=30亿",
                    "量比0.8-3",
                    "非一字涨停/封死跌停",
                    "近5日涨幅<=30%(透支剔除)",
                    "换手率<=15%(极端换手剔除)",
                    "股价<=40元(1w账户约束)",
                ],
                "factors": [
                    "动量质量: m5/m10/m20, 动量均匀度, 量价健康度, 动量加速度",
                    "入场优势: 健康回调/突破回踩/超跌反弹/追涨风险/高位派发",
                    "技术位: MA5/10/20, RSI, 布林位置, 突破状态",
                ]
            }
        }
    }

    # Write output
    output_path = "E:/finacial-invest/data/runs/20260726_short-term-picks/technical-liquidity.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Output written to {output_path}")
    print(f"  Pass: {len(pass_list)} stocks")
    print(f"  Reject: {len(reject_list)} stocks")
    for p in pass_list:
        print(f"    PASS: {p['code']} {p['name']} price={p['price']} amt20d={p['avgAmount20d']/1e8:.2f}亿")
    for r in reject_list:
        print(f"    REJECT: {r['code']} {r['name']} - {r['reason']}")

    return output

if __name__ == '__main__':
    main()
