#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
regime_detector.py — 市场环境识别引擎 (Layer 0: Regime Detection)

借鉴: Bridgewater All-Weather + AQR Regime-Aware Factor Timing
识别四种市场环境, 输出因子权重调整系数和风险预算。

Regime 类型:
  - trending: 趋势市(大盘单边涨/跌) → 动量因子加权
  - ranging: 震荡市(大盘横盘) → 反转/价值因子加权
  - high_volatility: 高波动市 → 质量/流动性因子加权
  - style_rotation: 风格切换期 → 全因子降权, 提升现金

用法:
  python scripts/regime_detector.py
  python scripts/regime_detector.py --output data/runs/xxx/regime.json

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
# 指数K线获取
# ════════════════════════════════════════════

INDEX_SYMBOLS = {
    'sh000001': '上证综指',
    'sz399001': '深证成指',
    'sz399006': '创业板指',
    'sh000688': '科创50',
}


def _kline_index(symbol: str, datalen: int = 30) -> list:
    """获取指数K线 (用腾讯 web.ifzq.gtimg.cn, 指数格式同股票)"""
    import urllib.request, ssl
    ctx = ssl._create_unverified_context()
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{datalen},qfq"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            j = json.loads(r.read().decode('utf-8', 'ignore'))
        # 指数数据可能在 'day' 或 'qfqday' 键
        data_node = j.get('data', {}).get(symbol, {})
        arr = data_node.get('qfqday') or data_node.get('day') or []
        return arr
    except Exception:
        return []


def get_index_klines(datalen: int = 30) -> dict:
    """获取主要指数K线数据"""
    result = {}
    for sym, name in INDEX_SYMBOLS.items():
        arr = _kline_index(sym, datalen)
        if arr and len(arr) >= 10:
            rows = []
            for x in arr:
                rows.append({
                    'date': x[0],
                    'close': float(x[2]),
                    'high': float(x[3]),
                    'low': float(x[4]),
                    'vol': float(x[5]) if len(x) > 5 else 0,
                })
            result[sym] = {'name': name, 'data': rows}
    return result


# ════════════════════════════════════════════
# Regime 计算
# ════════════════════════════════════════════

def compute_index_stats(data: list) -> dict:
    """计算单个指数的统计指标"""
    if not data or len(data) < 20:
        return {}

    closes = [r['close'] for r in data]

    # 日收益率
    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]

    # 20日动量
    m20 = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) > 20 else 0
    m5 = (closes[-1] - closes[-6]) / closes[-6] * 100 if len(closes) > 5 else 0

    # 20日波动率 (年化)
    recent_returns = returns[-20:]
    if len(recent_returns) >= 5:
        mean_r = sum(recent_returns) / len(recent_returns)
        var_r = sum((r - mean_r) ** 2 for r in recent_returns) / (len(recent_returns) - 1)
        daily_vol = math.sqrt(var_r) * 100
        annual_vol = daily_vol * math.sqrt(252)
    else:
        daily_vol = 0
        annual_vol = 0

    # 5日成交额变化
    vols = [r['vol'] for r in data[-10:]]
    v5 = sum(vols[-5:]) / 5 if len(vols) >= 5 else 1
    v5_prior = sum(vols[:5]) / 5 if len(vols) >= 10 else v5
    vol_change = (v5 - v5_prior) / max(v5_prior, 1) * 100

    # 趋势强度 (ADX简化版: |m20| / volatility)
    trend_strength = abs(m20) / max(annual_vol / 100, 1)

    return {
        'm5': round(m5, 2),
        'm20': round(m20, 2),
        'daily_vol': round(daily_vol, 2),
        'annual_vol': round(annual_vol, 1),
        'trend_strength': round(trend_strength, 2),
        'vol_change': round(vol_change, 1),
    }


def detect_regime(index_data: dict) -> dict:
    """综合判断市场环境"""
    # 以上证综指为主
    sh_data = index_data.get('sh000001', {})
    if not sh_data:
        return {'regime': 'ranging', 'confidence': 'low', 'reasons': ['上证指数数据缺失']}

    stats = compute_index_stats(sh_data.get('data', []))
    if not stats:
        return {'regime': 'ranging', 'confidence': 'low', 'reasons': ['数据不足']}

    m20 = stats['m20']
    m5 = stats['m5']
    annual_vol = stats['annual_vol']
    trend_strength = stats['trend_strength']
    vol_change = stats['vol_change']

    # 板块轮动检测 (通过科创50 vs 上证的分化判断)
    kc_data = index_data.get('sh000688', {})
    kc_stats = compute_index_stats(kc_data.get('data', [])) if kc_data else {}
    style_divergence = abs(stats['m5'] - kc_stats.get('m5', stats['m5'])) > 5

    # ── Regime 判断 ──
    regime = 'ranging'
    confidence = 'medium'
    reasons = []

    # 1. 高波动市
    if annual_vol > 25:
        regime = 'high_volatility'
        confidence = 'high'
        reasons.append(f'年化波动率{annual_vol:.1f}%>25%')

    # 2. 风格切换期
    elif style_divergence and abs(m5) > 2:
        regime = 'style_rotation'
        confidence = 'medium'
        reasons.append(f'上证与科创50分化>{abs(stats["m5"] - kc_stats.get("m5", 0)):.1f}%')
        reasons.append(f'5日动量{m5:.1f}%')

    # 3. 趋势市
    elif abs(m20) > 5 and trend_strength > 0.5:
        regime = 'trending'
        confidence = 'high' if abs(m20) > 8 else 'medium'
        reasons.append(f'20日动量{m20:.1f}%, 趋势强度{trend_strength:.2f}')

    # 4. 震荡市 (默认)
    else:
        regime = 'ranging'
        confidence = 'medium'
        reasons.append(f'20日动量{m20:.1f}%在±5%内, 波动率{annual_vol:.1f}%')

    return {
        'regime': regime,
        'confidence': confidence,
        'reasons': reasons,
    }


# ════════════════════════════════════════════
# 因子权重调整 + 风险预算
# ════════════════════════════════════════════

REGIME_CONFIG = {
    'trending': {
        'description': '趋势市(大盘单边运动)',
        'strategy': '顺势而为,动量因子加权',
        'weight_adjustments': {
            'momentum': 1.5, 'capital': 1.2, 'sentiment': 1.0,
            'catalyst': 1.0, 'fundamentals': 0.8, 'valuation': 0.7, 'liquidity': 1.0,
        },
        'risk_budget': 0.80,  # 最大仓位
        'cash_min': 0.15,     # 最低现金
        'entry_preference': 'pullback_buy',  # 偏好回调买入
    },
    'ranging': {
        'description': '震荡市(大盘横盘)',
        'strategy': '反转+价值,找好价格',
        'weight_adjustments': {
            'momentum': 0.7, 'capital': 1.0, 'sentiment': 0.8,
            'catalyst': 1.2, 'fundamentals': 1.2, 'valuation': 1.5, 'liquidity': 1.0,
        },
        'risk_budget': 0.65,
        'cash_min': 0.25,
        'entry_preference': 'mean_reversion',
    },
    'high_volatility': {
        'description': '高波动市(剧烈波动)',
        'strategy': '防守为主,质量+流动性优先',
        'weight_adjustments': {
            'momentum': 0.5, 'capital': 0.8, 'sentiment': 0.7,
            'catalyst': 1.0, 'fundamentals': 1.5, 'valuation': 1.0, 'liquidity': 1.3,
        },
        'risk_budget': 0.50,
        'cash_min': 0.35,
        'entry_preference': 'mean_reversion',
    },
    'style_rotation': {
        'description': '风格切换期(急转)',
        'strategy': '保守观望,全因子降权',
        'weight_adjustments': {
            'momentum': 0.5, 'capital': 0.7, 'sentiment': 0.6,
            'catalyst': 1.0, 'fundamentals': 1.2, 'valuation': 1.0, 'liquidity': 1.0,
        },
        'risk_budget': 0.45,
        'cash_min': 0.40,
        'entry_preference': 'wait',
    },
}


# ════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='市场环境识别引擎')
    parser.add_argument('--output', default='', help='输出文件路径')
    args = parser.parse_args()

    # 1. 获取指数数据
    index_data = get_index_klines(30)

    # 2. 计算各指数统计
    index_stats = {}
    for sym, info in index_data.items():
        index_stats[sym] = {
            'name': info['name'],
            **compute_index_stats(info['data']),
        }

    # 3. 识别 regime
    regime_info = detect_regime(index_data)
    regime = regime_info['regime']

    # 4. 获取 regime 配置
    config = REGIME_CONFIG[regime]

    # 5. 组合输出
    result = {
        'regime': regime,
        'regime_description': config['description'],
        'regime_strategy': config['strategy'],
        'confidence': regime_info['confidence'],
        'reasons': regime_info['reasons'],
        'index_stats': index_stats,
        'weight_adjustments': config['weight_adjustments'],
        'risk_budget': config['risk_budget'],
        'cash_min': config['cash_min'],
        'entry_preference': config['entry_preference'],
        'summary': f'当前环境: {config["description"]}({regime_info["confidence"]}), 建议仓位≤{config["risk_budget"]*100:.0f}%, 偏好{config["entry_preference"]}入场',
    }

    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f'输出到 {args.output}')
    else:
        print(output_json)


if __name__ == '__main__':
    main()
