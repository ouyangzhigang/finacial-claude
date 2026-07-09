#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Technical Liquidity Agent - Batch liquidity filter + short-term factors
Data sources: Sina K-line API (http) + 腾讯 qt.gtimg.cn (http)
"""
import urllib.request
import json
import ssl
import re
import sys
import os
from datetime import datetime

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

CANDIDATES = [
    {"code": "002185", "name": "华天科技", "sector": "半导体/封测"},
    {"code": "688403", "name": "汇成股份", "sector": "半导体/封测"},
    {"code": "600584", "name": "长电科技", "sector": "半导体/封测"},
    {"code": "002156", "name": "通富微电", "sector": "半导体/封测"},
    {"code": "000021", "name": "深科技", "sector": "半导体/封测存储"},
    {"code": "688362", "name": "甬矽电子", "sector": "半导体/封测"},
    {"code": "688584", "name": "上海合晶", "sector": "半导体/材料"},
    {"code": "688126", "name": "沪硅产业", "sector": "半导体/材料"},
    {"code": "002119", "name": "康强电子", "sector": "半导体/材料"},
    {"code": "688432", "name": "有研硅", "sector": "半导体/材料"},
    {"code": "600206", "name": "有研新材", "sector": "半导体/材料"},
    {"code": "002409", "name": "雅克科技", "sector": "半导体/材料"},
    {"code": "688727", "name": "恒坤新材", "sector": "半导体/材料"},
    {"code": "603991", "name": "领先股份", "sector": "半导体/设计"},
    {"code": "688328", "name": "深科达", "sector": "半导体/设备"},
    {"code": "688206", "name": "概伦电子", "sector": "半导体/EDA"},
    {"code": "301348", "name": "蓝箭电子", "sector": "半导体/封测"},
    {"code": "688048", "name": "长光华芯", "sector": "半导体/激光芯片"},
    {"code": "688795", "name": "摩尔线程", "sector": "半导体/GPU"},
    {"code": "688802", "name": "沐曦股份", "sector": "半导体/GPU"},
    {"code": "688008", "name": "澜起科技", "sector": "半导体/内存接口"},
    {"code": "688103", "name": "国力电子", "sector": "半导体/元器件"},
    {"code": "002845", "name": "同兴达", "sector": "光学光电"},
    {"code": "002632", "name": "道明光学", "sector": "光学光电"},
    {"code": "002745", "name": "木林森", "sector": "光学光电"},
    {"code": "301379", "name": "天山电子", "sector": "光学光电"},
    {"code": "688610", "name": "埃科光电", "sector": "光学光电"},
    {"code": "600353", "name": "旭光电子", "sector": "光学光电"},
    {"code": "000977", "name": "浪潮信息", "sector": "IT国产化"},
    {"code": "300469", "name": "信息发展", "sector": "IT国产化"},
    {"code": "600228", "name": "返利科技", "sector": "IT国产化"},
    {"code": "688207", "name": "格灵深瞳", "sector": "IT国产化/AI"},
    {"code": "300270", "name": "中威电子", "sector": "IT国产化"},
    {"code": "300626", "name": "华瑞股份", "sector": "IT国产化"},
    {"code": "603928", "name": "兴业股份", "sector": "半导体/光刻胶"},
    {"code": "002815", "name": "崇达技术", "sector": "半导体/PCB"},
    {"code": "600667", "name": "太极实业", "sector": "半导体/工程"},
    {"code": "603137", "name": "恒尚节能", "sector": "城市更新"},
    {"code": "603898", "name": "好莱客", "sector": "城市更新"},
    {"code": "002208", "name": "合肥城建", "sector": "城市更新"},
    {"code": "002677", "name": "浙江美大", "sector": "城市更新"},
    {"code": "603726", "name": "朗迪集团", "sector": "城市更新"},
    {"code": "000417", "name": "合百集团", "sector": "城市更新"},
    {"code": "002414", "name": "高德红外", "sector": "军工"},
    {"code": "002829", "name": "星网宇达", "sector": "军工/航天"},
    {"code": "605319", "name": "无锡振华", "sector": "军工"},
    {"code": "688333", "name": "铂力特", "sector": "军工"},
    {"code": "600992", "name": "贵绳股份", "sector": "军工"},
    {"code": "603666", "name": "亿嘉和", "sector": "军工"},
    {"code": "600879", "name": "航天电子", "sector": "军工/航天"},
    {"code": "688818", "name": "电科蓝天", "sector": "军工/航天"},
    {"code": "601698", "name": "中国卫通", "sector": "军工/卫星"},
    {"code": "600118", "name": "中国卫星", "sector": "军工/卫星"},
]

def sina_prefix(code):
    return ('sh' if code.startswith('6') else 'sz') + code

def fetch_sina_kline(code, datalen=65):
    prefix = sina_prefix(code)
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={prefix}&scale=240&ma=no&datalen={datalen}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode('utf-8', errors='replace')
            if data and data.strip():
                return json.loads(data)
    except Exception as e:
        return None
    return None

def fetch_tencent_batch(codes):
    results = {}
    batch_size = 40
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        tcodes = [sina_prefix(c) for c in batch]
        url = f"http://qt.gtimg.cn/q={','.join(tcodes)}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode('gbk', errors='replace')
                for line in data.strip().split(';'):
                    line = line.strip()
                    if not line or '=' not in line:
                        continue
                    m = re.match(r'v_(\w+)="(.+)"', line)
                    if not m:
                        continue
                    tc = m.group(1)
                    fields = m.group(2).split('~')
                    if len(fields) > 45:
                        results[tc] = fields
        except Exception as e:
            pass
    return results

def compute_factors(kl):
    if not kl or len(kl) < 20:
        return None
    closes, volumes, amounts_proxy = [], [], []
    for bar in kl:
        try:
            o = float(bar['open']); h = float(bar['high'])
            l = float(bar['low']); c = float(bar['close'])
            v = float(bar['volume'])
            closes.append(c); volumes.append(v)
            avg_price = (o + h + l + c) / 4
            amounts_proxy.append(avg_price * v)
        except:
            closes.append(0); volumes.append(0); amounts_proxy.append(0)
    n = len(closes)
    if n < 20:
        return None
    close_now = closes[-1]
    m5 = round((close_now / closes[-6] - 1) * 100, 2) if n >= 6 and closes[-6] > 0 else None
    m10 = round((close_now / closes[-11] - 1) * 100, 2) if n >= 11 and closes[-11] > 0 else None
    m20 = round((close_now / closes[-21] - 1) * 100, 2) if n >= 21 and closes[-21] > 0 else None
    ma20 = round(sum(closes[-20:]) / 20, 2) if n >= 20 else None
    above_ma20 = close_now > ma20 if ma20 else None
    vol_today = volumes[-1]
    vol5_avg = sum(volumes[-6:-1]) / 5 if n >= 6 else None
    breakout = bool(vol_today > vol5_avg * 1.5) if vol5_avg and vol5_avg > 0 else False
    amt20 = sum(amounts_proxy[-20:]) / 20 if n >= 20 else None
    amt20_yi = round(amt20 / 1e8, 2) if amt20 else None
    vol_ratio = round(vol_today / vol5_avg, 2) if vol5_avg and vol5_avg > 0 else None
    return {
        'close': round(close_now, 2), 'm5': m5, 'm10': m10, 'm20': m20,
        'ma20': ma20, 'aboveMA20': above_ma20, 'breakout': breakout,
        'amt20Yi': amt20_yi, 'volRatio': vol_ratio, 'barsCount': n,
    }

def parse_tencent(fields):
    try:
        return {
            'name': fields[1] if len(fields) > 1 else '',
            'price': float(fields[3]) if len(fields) > 3 and fields[3] else 0,
            'prevClose': float(fields[4]) if len(fields) > 4 and fields[4] else 0,
            'changePct': float(fields[32]) if len(fields) > 32 and fields[32] else 0,
            'amountWan': float(fields[37]) if len(fields) > 37 and fields[37] else 0,
            'turnoverPct': float(fields[38]) if len(fields) > 38 and fields[38] else 0,
            'pe': float(fields[39]) if len(fields) > 39 and fields[39] else 0,
            'circMvYi': float(fields[44]) if len(fields) > 44 and fields[44] else 0,
            'totalMvYi': float(fields[45]) if len(fields) > 45 and fields[45] else 0,
        }
    except:
        return None

def main():
    codes = [c['code'] for c in CANDIDATES]
    print(f"Processing {len(CANDIDATES)} candidates...", file=sys.stderr)

    # Fetch Sina K-line
    kline_data = {}
    for i, cand in enumerate(CANDIDATES):
        code = cand['code']
        print(f"  [{i+1}/{len(CANDIDATES)}] K-line: {code} {cand['name']}", file=sys.stderr)
        kl = fetch_sina_kline(code, datalen=65)
        if kl:
            kline_data[code] = kl
        else:
            print(f"    WARN: K-line failed for {code}", file=sys.stderr)
    print(f"K-line fetched: {len(kline_data)}/{len(CANDIDATES)}", file=sys.stderr)

    # Fetch 腾讯 snapshot
    print("Fetching 腾讯 batch snapshot...", file=sys.stderr)
    tencent_data = fetch_tencent_batch(codes)
    print(f"腾讯 snapshot fetched: {len(tencent_data)}/{len(CANDIDATES)}", file=sys.stderr)

    pass_list, reject_list, factors_list = [], [], []

    for cand in CANDIDATES:
        code = cand['code']; name = cand['name']; sector = cand['sector']
        kl = kline_data.get(code)
        factors = compute_factors(kl)
        tc_prefix = sina_prefix(code)
        ts = tencent_data.get(tc_prefix)
        ts_data = parse_tencent(ts) if ts else None

        price = ts_data['price'] if ts_data and ts_data['price'] > 0 else (factors['close'] if factors else 0)
        change_pct = ts_data['changePct'] if ts_data else 0
        amount_today_yi = (ts_data['amountWan'] / 10000) if ts_data else 0
        turnover_today = ts_data['turnoverPct'] if ts_data else 0
        circ_mv = ts_data['circMvYi'] if ts_data else 0
        total_mv = ts_data['totalMvYi'] if ts_data else 0
        pe = ts_data['pe'] if ts_data else 0
        amt20_yi = factors['amt20Yi'] if factors else None
        bars_count = factors['barsCount'] if factors else 0

        reject_reasons = []

        # K-line data
        if not factors:
            reject_reasons.append("K线数据缺失")
        # 20日均成交额 >= 1亿
        if amt20_yi is not None and amt20_yi < 1.0:
            reject_reasons.append(f"20日均成交额{amt20_yi:.2f}亿<1亿")
        # 流通市值 >= 30亿
        if circ_mv > 0 and circ_mv < 30:
            reject_reasons.append(f"流通市值{circ_mv:.1f}亿<30亿")
        # 次新 (上市<60交易日)
        if bars_count > 0 and bars_count < 60:
            reject_reasons.append(f"次新(仅{bars_count}日K线)")
        # 透支: 近5/10/20日任一>30%
        m5 = factors['m5'] if factors else None
        m10 = factors['m10'] if factors else None
        m20 = factors['m20'] if factors else None
        if m5 is not None and m5 > 30:
            reject_reasons.append(f"近5日涨{m5:.1f}%透支")
        if m10 is not None and m10 > 30:
            reject_reasons.append(f"近10日涨{m10:.1f}%透支")
        if m20 is not None and m20 > 30:
            reject_reasons.append(f"近20日涨{m20:.1f}%透支")
        # 高位回调审查 (20日涨>20%但5日跌>2%)
        high_pullback = False
        if m20 is not None and m5 is not None:
            if m20 > 20 and m5 < -2:
                high_pullback = True
                reject_reasons.append(f"高位回调(20日+{m20:.1f}%但5日{m5:.1f}%)")
        # ST
        is_st = 'ST' in name or '*ST' in name
        if is_st:
            reject_reasons.append("ST")
        # 换手率极端
        if turnover_today > 15:
            reject_reasons.append(f"换手率{turnover_today:.1f}%过高(>15%)")

        passed = len(reject_reasons) == 0

        # Technical level
        tech_level = "数据缺失"
        if factors:
            if factors['aboveMA20'] and m5 and m5 > 0 and m10 and m10 > 0 and m20 and m20 > 0:
                tech_level = "上升趋势(5/10/20日动量全正,站上MA20)"
            elif high_pullback:
                tech_level = "高位回调(20日涨>20%但5日转负)"
            elif m5 and m5 > 0 and m20 and m20 < 0:
                tech_level = "超跌反弹(20日跌但5日转正)"
            elif factors['aboveMA20']:
                tech_level = "站上MA20但动量不全正"
            else:
                tech_level = "跌破MA20"

        factor_entry = {
            'code': code, 'name': name, 'sector': sector,
            'price': round(price, 2), 'changePct': round(change_pct, 2),
            'm5': m5, 'm10': m10, 'm20': m20,
            'ma20': factors['ma20'] if factors else None,
            'aboveMA20': factors['aboveMA20'] if factors else None,
            'breakout': factors['breakout'] if factors else None,
            'volRatio': factors['volRatio'] if factors else None,
            'amt20Yi': amt20_yi,
            'turnoverToday': round(turnover_today, 2),
            'circMvYi': round(circ_mv, 1),
            'totalMvYi': round(total_mv, 1),
            'pe': round(pe, 1) if pe > 0 else None,
            'barsCount': bars_count,
            'highPullback': high_pullback,
            'amountTodayYi': round(amount_today_yi, 2),
            'technicalLevel': tech_level,
        }
        factors_list.append(factor_entry)

        if passed:
            pass_list.append({
                'code': code, 'name': name, 'price': round(price, 2),
                'avgAmount20d': amt20_yi,
                'turnoverToday': round(turnover_today, 2),
                'volRatio': factors['volRatio'] if factors else None,
                'circMvYi': round(circ_mv, 1),
                'pass': True, 'sector': sector,
            })
        else:
            reject_list.append({
                'code': code, 'name': name,
                'reason': '; '.join(reject_reasons),
                'sector': sector,
            })

    output = {
        'pass': pass_list,
        'reject': reject_list,
        'factors': factors_list,
        'summary': f"过关{len(pass_list)}只/剔除{len(reject_list)}只;主要剔除:透支(5/10/20日>30%)+高位回调+流动性不足(成交额<1亿/市值<30亿)+次新",
        'meta': {
            'totalCandidates': len(CANDIDATES),
            'passed': len(pass_list),
            'rejected': len(reject_list),
            'klineFetched': len(kline_data),
            'tencentFetched': len(tencent_data),
            'dataSource': 'Sina K-line(http)+腾讯qt.gtimg.cn(http)',
            'asOf': '20260709',
        }
    }
    return output

if __name__ == '__main__':
    output = main()
    # Write to output file
    out_dir = "e:/finacial-invest/data/runs/20260709_short-term-picks"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "technical-liquidity.json")
    envelope = {
        "runId": "20260709_short-term-picks",
        "asOf": "20260709",
        "goal": "short-term-picks",
        "agent": "technical-liquidity",
        "fetchedAt": "20260709",
        "data": output,
        "summary": output['summary'],
        "keyFields": {
            "passed": len(output['pass']),
            "rejected": len(output['reject']),
            "passCodes": [p['code'] for p in output['pass']],
            "rejectCodes": [r['code'] for r in output['reject']],
            "mainRejectReasons": list(set(r['reason'].split(';')[0] for r in output['reject'])),
        }
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)
    print(f"Output written to {out_path}", file=sys.stderr)
    print(json.dumps(envelope['keyFields'], ensure_ascii=False, indent=2))
