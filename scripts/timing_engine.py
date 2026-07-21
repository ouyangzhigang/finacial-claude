#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
timing_engine.py — 择时入场引擎 (Layer 2: Timing & Entry)

借鉴: Mean Reversion + Momentum Quality (学术经典)
核心: 选股(Layer 1)和择时(Layer 2)是两个独立决策。
     好股票+好价格=好入场; 好股票+坏价格=追涨套牢。

功能:
  1. 入场信号分类 (回调买入/突破回踩/均值回归/动量启动/追涨警告)
  2. 动量质量评估 (均匀度/集中度/量价健康/加速度)
  3. 透支概率模型 (非简单阈值, 考虑催化时间)
  4. 入场评分 (-30 到 +30, 叠加到 Layer 1 综合评分)

用法:
  python scripts/timing_engine.py --codes 603456,002294,603369
  python scripts/timing_engine.py --codes 603456 --json '{"catalyst_days": 5, "has_hard_catalyst": true}'

输出: JSON 到 stdout
"""
import json
import sys
import os
import math
import argparse
from typing import Optional

# ── 复用 cn_fetch.py ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cn_fetch import kline as _kline

# ════════════════════════════════════════════
# sigmoid 辅助函数
# ════════════════════════════════════════════
def sigmoid(x):
    """标准 sigmoid, 输出 0-1"""
    try:
        return 1 / (1 + math.exp(-x))
    except OverflowError:
        return 1.0 if x > 0 else 0.0


# ════════════════════════════════════════════
# K线数据获取 + 因子计算
# ════════════════════════════════════════════

def get_kline_data(symbol: str, datalen: int = 60) -> Optional[list]:
    """获取K线数据, 返回结构化列表"""
    arr = _kline(symbol, datalen)
    if not arr or len(arr) < 20:
        return None
    rows = []
    for x in arr:
        rows.append({
            'date': x[0],
            'open': float(x[1]),
            'close': float(x[2]),
            'high': float(x[3]),
            'low': float(x[4]),
            'vol': float(x[5]) if len(x) > 5 else 0,
        })
    return rows


# ════════════════════════════════════════════
# 入场信号分类
# ════════════════════════════════════════════

def classify_entry_signal(rows: list, catalyst_info: dict = None) -> dict:
    """判断入场信号类型。
    返回: {signal_type, signal_score, description, confidence}
    """
    if not rows or len(rows) < 20:
        return {'signal_type': 'unknown', 'signal_score': 0, 'description': '数据不足', 'confidence': 'low'}

    closes = [r['close'] for r in rows]
    highs = [r['high'] for r in rows]
    lows = [r['low'] for r in rows]
    vols = [r['vol'] for r in rows]
    last_close = closes[-1]

    # 均线
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20

    # 动量
    m5 = (closes[-1] - closes[-6]) / closes[-6] * 100 if len(closes) > 5 else 0
    m10 = (closes[-1] - closes[-11]) / closes[-11] * 100 if len(closes) > 10 else 0
    m20 = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) > 20 else 0

    # 20日高点
    high_20d = max(highs[-20:])
    pullback = (last_close - high_20d) / high_20d * 100

    # 量能
    v5 = sum(vols[-5:]) / 5 if len(vols) >= 5 else vols[-1]
    v15 = sum(vols[-20:-5]) / 15 if len(vols) >= 20 else v5
    vol_ratio = v5 / max(v15, 1)

    # 近5日每日涨跌
    daily_ret = []
    for i in range(-5, 0):
        if abs(i) < len(closes):
            daily_ret.append((closes[i] - closes[i - 1]) / closes[i - 1] * 100)

    # RSI (14日简化版)
    gains = [max(r, 0) for r in daily_ret]
    losses = [abs(min(r, 0)) for r in daily_ret]
    avg_gain = sum(gains) / max(len(gains), 1)
    avg_loss = sum(losses) / max(len(losses), 1)
    rsi = 100 - (100 / (1 + avg_gain / max(avg_loss, 0.01)))

    # ── 信号判断 ──
    cat = catalyst_info or {}
    has_catalyst = cat.get('has_hard_catalyst', False)
    catalyst_days = cat.get('catalyst_days', 99)

    # 1. 趋势回调买入 ✅ (最佳入场)
    if (last_close > ma20 and -8 <= pullback <= -3
            and vol_ratio < 0.9 and 35 <= rsi <= 55):
        return {
            'signal_type': 'pullback_buy',
            'signal_score': 20,
            'description': f'上升趋势回调买点: MA20上方, 回调{pullback:.1f}%, 缩量(vol_ratio={vol_ratio:.2f}), RSI={rsi:.0f}',
            'confidence': 'high',
        }

    # 2. 突破回踩确认 ✅
    if (last_close > ma20 and last_close > ma10
            and abs(pullback) < 2 and vol_ratio < 0.85
            and m20 > 5):
        return {
            'signal_type': 'breakout_pullback',
            'signal_score': 15,
            'description': f'突破回踩确认: 近高点{pullback:.1f}%, 缩量, 20日涨{m20:.1f}%',
            'confidence': 'medium',
        }

    # 3. 均值回归买入 (优质股超跌)
    if (m10 < -8 and m20 < -5 and last_close < ma20 * 0.95
            and vol_ratio < 1.2):
        return {
            'signal_type': 'mean_reversion',
            'signal_score': 12,
            'description': f'均值回归: 近10日跌{m10:.1f}%, 低于MA20 {(1-last_close/ma20)*100:.1f}%',
            'confidence': 'medium',
        }

    # 4. 动量启动买入 (有催化的初期动量)
    if (5 <= m5 <= 12 and last_close > ma20 and vol_ratio > 1.2
            and has_catalyst and catalyst_days > 3):
        return {
            'signal_type': 'momentum_start',
            'signal_score': 10,
            'description': f'动量启动: 5日涨{m5:.1f}%, 放量(vol_ratio={vol_ratio:.2f}), 有硬催化({catalyst_days}日后)',
            'confidence': 'medium',
        }

    # 5. 追涨警告 ❌ (两种情况)
    # 5a: 暴涨型 (5日涨幅>15%)
    if m5 > 15 and pullback > -2:
        return {
            'signal_type': 'chase_warning',
            'signal_score': -20,
            'description': f'追涨警告: 5日涨{m5:.1f}%已到位, 距高点仅{abs(pullback):.1f}%',
            'confidence': 'high',
        }
    # 5b: 动量减速型 (m20远大于m5, 说明主升浪已过, 在尾部追涨)
    if m20 > 20 and m5 > 8 and pullback > -3 and m5 < m20 * 0.5:
        return {
            'signal_type': 'chase_warning',
            'signal_score': -15,
            'description': f'动量减速追涨: 20日涨{m20:.1f}%但5日仅{m5:.1f}%(减速{(1-m5/m20)*100:.0f}%), 距高点{abs(pullback):.1f}%, 主升浪尾部',
            'confidence': 'medium',
        }

    # 6. 高位派发 ❌
    if m20 > 20 and m5 < -2:
        return {
            'signal_type': 'distribution',
            'signal_score': -25,
            'description': f'高位派发: 20日涨{m20:.1f}%但5日转跌{m5:.1f}%, 主升浪结束信号',
            'confidence': 'high',
        }

    # 7. 中性 (无明显信号)
    return {
        'signal_type': 'neutral',
        'signal_score': 0,
        'description': f'无明显入场信号: m5={m5:.1f}%, pullback={pullback:.1f}%, vol_ratio={vol_ratio:.2f}',
        'confidence': 'low',
    }


# ════════════════════════════════════════════
# 动量质量评估
# ════════════════════════════════════════════

def assess_momentum_quality(rows: list) -> dict:
    """评估动量质量: 是健康趋势还是虚假动量。
    返回: {quality_score(0-100), uniformity, concentration, volume_health, acceleration, verdict}
    """
    if not rows or len(rows) < 10:
        return {'quality_score': 50, 'verdict': '数据不足'}

    closes = [r['close'] for r in rows]
    vols = [r['vol'] for r in rows]

    # 近5日每日涨跌
    daily_ret = []
    for i in range(-5, 0):
        if abs(i) < len(closes):
            daily_ret.append((closes[i] - closes[i - 1]) / closes[i - 1] * 100)

    if not daily_ret:
        return {'quality_score': 50, 'verdict': '数据不足'}

    # 均匀度: 上涨天数 / 总天数
    up_days = sum(1 for r in daily_ret if r > 0)
    uniformity = up_days / len(daily_ret)

    # 集中度: 最大单日变动 / 总变动
    total_change = sum(abs(r) for r in daily_ret)
    max_daily = max(abs(r) for r in daily_ret) if daily_ret else 0
    concentration = max_daily / total_change if total_change > 0 else 0

    # 量价健康度
    up_vols = [vols[i] for i in range(-5, 0) if abs(i) < len(closes) and closes[i] > closes[i - 1]]
    dn_vols = [vols[i] for i in range(-5, 0) if abs(i) < len(closes) and closes[i] <= closes[i - 1]]
    avg_up = sum(up_vols) / max(len(up_vols), 1)
    avg_dn = sum(dn_vols) / max(len(dn_vols), 1)
    volume_health = avg_up / max(avg_dn, 1) if avg_dn > 0 else 2.0

    # 加速度
    m5 = (closes[-1] - closes[-6]) / closes[-6] * 100 if len(closes) > 5 else 0
    m10 = (closes[-1] - closes[-11]) / closes[-11] * 100 if len(closes) > 10 else 0
    acceleration = (m5 / 5) - ((m10 - m5) / 5) if m10 != m5 else 0

    # 综合质量分 (0-100)
    quality = (
        uniformity * 30           # 均匀上涨满分0.6→18分
        + (1 - min(concentration, 1)) * 25  # 低集中度满分
        + min(volume_health / 2, 1) * 25    # 量价健康满分
        + max(0, min(acceleration / 2, 1)) * 20  # 正加速度满分
    )
    quality = max(0, min(100, quality))

    # 判定
    if quality >= 70:
        verdict = '优质动量(均匀涨+量价配合)'
    elif quality >= 50:
        verdict = '一般动量'
    elif quality >= 30:
        verdict = '低质量动量(可能单日暴涨撑数据)'
    else:
        verdict = '虚假动量(高度集中+量价背离)'

    return {
        'quality_score': round(quality, 1),
        'uniformity': round(uniformity, 2),
        'concentration': round(concentration, 2),
        'volume_health': round(min(volume_health, 3), 2),
        'acceleration': round(acceleration, 3),
        'verdict': verdict,
    }


# ════════════════════════════════════════════
# 透支概率模型
# ════════════════════════════════════════════

def compute_exhaustion_prob(rows: list, catalyst_info: dict = None) -> dict:
    """计算透支概率 (非简单阈值, 考虑多因素)。
    返回: {probability(0-1), risk_level, factors}
    """
    if not rows or len(rows) < 20:
        return {'probability': 0.5, 'risk_level': 'unknown', 'factors': {}}

    closes = [r['close'] for r in rows]
    vols = [r['vol'] for r in rows]

    m5 = (closes[-1] - closes[-6]) / closes[-6] * 100 if len(closes) > 5 else 0
    m10 = (closes[-1] - closes[-11]) / closes[-11] * 100 if len(closes) > 10 else 0
    m20 = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) > 20 else 0
    max_m = max(m5, m10, m20)

    # 量能变化 (放量滞涨)
    v5 = sum(vols[-5:]) / 5
    v15 = sum(vols[-20:-5]) / 15 if len(vols) >= 20 else v5
    vol_expansion = v5 / max(v15, 1)

    cat = catalyst_info or {}
    catalyst_days = cat.get('catalyst_days', 99)
    has_hard = cat.get('has_hard_catalyst', False)

    # sigmoid 模型
    z = (
        0.08 * max_m                          # 涨幅越大越可能透支
        - 0.05 * catalyst_days                 # 催化越远越可能透支
        + 2.0 * (1 if m5 > 15 else 0)         # 5日暴涨惩罚
        + 0.5 * max(0, vol_expansion - 1.5)   # 放量滞涨
        - 1.5 * (1 if has_hard else 0)         # 有硬催化减分
        + 1.5 * (1 if m20 > 20 and m5 < m20 * 0.5 else 0)  # 动量减速信号(主升浪尾部)
    )
    prob = sigmoid(z - 1.5)  # 偏移使默认概率约30%

    # 风险等级
    if prob > 0.7:
        risk = 'high'
    elif prob > 0.4:
        risk = 'medium'
    else:
        risk = 'low'

    return {
        'probability': round(prob, 3),
        'risk_level': risk,
        'factors': {
            'max_momentum': round(max_m, 1),
            'm5': round(m5, 1),
            'vol_expansion': round(vol_expansion, 2),
            'catalyst_days': catalyst_days,
            'has_hard_catalyst': has_hard,
        },
    }


# ════════════════════════════════════════════
# 综合入场评分
# ════════════════════════════════════════════

def compute_timing_score(symbol: str, catalyst_info: dict = None) -> dict:
    """综合入场评分: 信号+动量质量+透支概率 → 入场评分(-30到+30)。
    此评分叠加到 Layer 1 综合评分上。
    """
    # Normalize: strip any sh/sz prefix (case-insensitive), re-add lowercase prefix based on stock code
    # 股票代码规范化: 从首数字判断交易所(而非取前缀,避免 "603456"→"60"错误)
    if symbol.lower().startswith(('sh', 'sz')):
        # 已有sh/sz前缀
        exchange_prefix = symbol[:2].lower()
        code_only = symbol[2:]
    else:
        # 无sh/sz前缀,从首位数字判断: 6=SH, 0/3=SZ
        first_digit = symbol[0] if symbol else ''
        exchange_prefix = 'sh' if first_digit == '6' else 'sz'
        code_only = symbol
    sym = f"{exchange_prefix}{code_only}"

    rows = get_kline_data(sym)
    if not rows:
        return {
            'symbol': symbol,
            'entry_signal': {'signal_type': 'unknown', 'signal_score': 0},
            'momentum_quality': {'quality_score': 50},
            'exhaustion_prob': {'probability': 0.5, 'risk_level': 'unknown'},
            'timing_score': 0,
            'verdict': '数据不足,无法判断入场时机',
        }

    # 1. 入场信号
    signal = classify_entry_signal(rows, catalyst_info)

    # 2. 动量质量
    quality = assess_momentum_quality(rows)

    # 3. 透支概率
    exhaustion = compute_exhaustion_prob(rows, catalyst_info)

    # 4. 综合入场评分 (-30 到 +30)
    score = signal['signal_score']  # -25 到 +20
    # 动量质量调整 (-5 到 +5)
    score += (quality['quality_score'] - 50) / 10
    # 透支概率惩罚 (0 到 -10)
    score -= exhaustion['probability'] * 10
    score = max(-30, min(30, score))

    # 判定
    if score >= 12:
        verdict = '✅ 好入场(回调买点或均值回归)'
    elif score >= 5:
        verdict = '🟡 一般入场(有动量但未透支)'
    elif score >= 0:
        verdict = '🟡 中性(无明显优势)'
    elif score >= -10:
        verdict = '🔴 差入场(动量透支或追涨风险)'
    else:
        verdict = '❌ 极差入场(应回避,等回调)'

    return {
        'symbol': symbol,
        'code': symbol,
        'entry_signal': signal,
        'momentum_quality': quality,
        'exhaustion_prob': exhaustion,
        'timing_score': round(score, 1),
        'verdict': verdict,
    }


# ════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='择时入场引擎')
    parser.add_argument('--codes', required=True, help='逗号分隔的股票代码')
    parser.add_argument('--json', default='{}', help='催化信息JSON (per-code: {code: {catalyst_days, has_hard_catalyst}})')
    parser.add_argument('--output', default='', help='输出文件路径')
    args = parser.parse_args()

    codes = [c.strip() for c in args.codes.split(',') if c.strip()]
    catalyst_map = json.loads(args.json) if args.json != '{}' else {}

    results = []
    for code in codes:
        cat_info = catalyst_map.get(code, {})
        result = compute_timing_score(code, cat_info)
        results.append(result)

    output = {
        'stocks': results,
        'summary': f'{len(results)}只股票入场评估完成',
    }

    # 添加汇总
    good_entries = [r for r in results if r['timing_score'] >= 12]
    bad_entries = [r for r in results if r['timing_score'] < -10]
    output['good_entries'] = [r['code'] for r in good_entries]
    output['bad_entries'] = [r['code'] for r in bad_entries]
    output['summary'] = (
        f'{len(results)}只评估: {len(good_entries)}只好入场, '
        f'{len(bad_entries)}只应回避'
    )

    output_json = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f'输出到 {args.output}')
    else:
        print(output_json)


if __name__ == '__main__':
    main()
