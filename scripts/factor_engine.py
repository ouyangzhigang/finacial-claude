#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
factor_engine.py — 综合多因子评分引擎 (Layer 1: Stock Selection)

借鉴: AQR Style Premia + Robeco Multi-Factor
保留旧版七维因子(技术/资金/情绪/催化/基本面/估值/流动性),
但用专业方法组合: z-score标准化 + IC加权 + 相关性降权 + regime调整。

用法:
  python scripts/factor_engine.py --codes 603456,002294,603369 --data-dir data/runs/20260715_short-term-picks
  python scripts/factor_engine.py --codes 603456,002294 --json '{"regime": "trending", "weights": {}}'

输出: JSON 到 stdout (供 agent/workflow 读取)
"""
import json
import sys
import os
import math
import argparse
from typing import Optional

# ── 复用 cn_fetch.py 的 kline + factors ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cn_fetch import kline as _kline, factors as _cn_factors

# ════════════════════════════════════════════
# 基础权重 (旧版七维作为起点)
# ════════════════════════════════════════════
BASE_WEIGHTS = {
    'momentum':     0.25,  # 技术动量
    'capital':      0.20,  # 资金推动
    'sentiment':    0.15,  # 情绪板块
    'catalyst':     0.20,  # 催化确定性
    'fundamentals': 0.10,  # 基本面底线
    'valuation':    0.05,  # 估值安全
    'liquidity':    0.05,  # 流动性适配
}

# ════════════════════════════════════════════
# Regime 调整系数 (Layer 0 输出)
# ════════════════════════════════════════════
REGIME_ADJUSTMENTS = {
    'trending': {
        'momentum': 1.5, 'capital': 1.2, 'sentiment': 1.0,
        'catalyst': 1.0, 'fundamentals': 0.8, 'valuation': 0.7, 'liquidity': 1.0,
    },
    'ranging': {
        'momentum': 0.7, 'capital': 1.0, 'sentiment': 0.8,
        'catalyst': 1.2, 'fundamentals': 1.2, 'valuation': 1.5, 'liquidity': 1.0,
    },
    'high_volatility': {
        'momentum': 0.5, 'capital': 0.8, 'sentiment': 0.7,
        'catalyst': 1.0, 'fundamentals': 1.5, 'valuation': 1.0, 'liquidity': 1.3,
    },
    'style_rotation': {
        'momentum': 0.5, 'capital': 0.7, 'sentiment': 0.6,
        'catalyst': 1.0, 'fundamentals': 1.2, 'valuation': 1.0, 'liquidity': 1.0,
    },
}

# ════════════════════════════════════════════
# 因子计算
# ════════════════════════════════════════════

def compute_kline_factors(symbol: str, datalen: int = 60) -> Optional[dict]:
    """从K线数据计算量化因子 (动量/量价/流动性)。
    复用 cn_fetch.kline() 获取数据。"""
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

    closes = [r['close'] for r in rows]
    highs = [r['high'] for r in rows]
    lows = [r['low'] for r in rows]
    vols = [r['vol'] for r in rows]
    last = rows[-1]

    # ── 动量因子 ──
    def mom(d):
        if len(closes) > d:
            return (closes[-1] - closes[-1 - d]) / closes[-1 - d] * 100
        return None

    m5 = mom(5)
    m10 = mom(10)
    m20 = mom(20)

    # 动量加权 (5日权重最高)
    momentum_score = 0
    if m5 is not None: momentum_score += m5 * 0.5
    if m10 is not None: momentum_score += (m10 / 2) * 0.3
    if m20 is not None: momentum_score += (m20 / 4) * 0.2

    # ── 均线 ──
    ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else closes[-1]
    ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else closes[-1]
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]

    # ── 量价因子 ──
    v5 = sum(vols[-5:]) / 5 if len(vols) >= 5 else vols[-1]
    v20 = sum(vols[-20:]) / 20 if len(vols) >= 20 else vols[-1]
    breakout = last['close'] > ma20 and last['vol'] > v5 * 1.5

    # 20日均成交额 (手*100*价格)
    amt20 = sum(rows[i]['vol'] * 100 * rows[i]['close'] for i in range(-20, 0)) / 20

    # ── 动量质量因子 (新增) ──
    # 5日每日涨跌
    daily_returns_5d = []
    for i in range(-5, 0):
        if i - 1 >= -len(closes):
            daily_returns_5d.append((closes[i] - closes[i - 1]) / closes[i - 1] * 100)

    up_days = sum(1 for r in daily_returns_5d if r > 0)
    uniformity = up_days / max(len(daily_returns_5d), 1)

    # 单日集中度: 最大单日涨幅 / 5日总涨幅
    total_5d = sum(abs(r) for r in daily_returns_5d) if daily_returns_5d else 1
    max_daily = max(abs(r) for r in daily_returns_5d) if daily_returns_5d else 0
    concentration = max_daily / total_5d if total_5d > 0 else 0

    # 量价健康度: 涨日量 / 跌日量
    up_vols = [vols[i] for i in range(-5, 0) if i - 1 >= -len(closes) and closes[i] > closes[i - 1]]
    dn_vols = [vols[i] for i in range(-5, 0) if i - 1 >= -len(closes) and closes[i] <= closes[i - 1]]
    avg_up_vol = sum(up_vols) / max(len(up_vols), 1)
    avg_dn_vol = sum(dn_vols) / max(len(dn_vols), 1)
    volume_health = avg_up_vol / max(avg_dn_vol, 1) if avg_dn_vol > 0 else 2.0

    # 动量加速度
    accel = None
    if m5 is not None and m10 is not None:
        accel = (m5 / 5) - ((m10 - m5) / 5)

    # ── 回调深度 ──
    high_20d = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    pullback_depth = (last['close'] - high_20d) / high_20d * 100

    # 回调量能 (近5日均量 / 前15日均量, <1 = 缩量回调 = 健康)
    v5_recent = sum(vols[-5:]) / 5 if len(vols) >= 5 else vols[-1]
    v15_prior = sum(vols[-20:-5]) / 15 if len(vols) >= 20 else v5_recent
    pullback_volume = v5_recent / max(v15_prior, 1) if v15_prior > 0 else 1.0

    # ── 流动性因子 ──
    turnover_approx = (v20 * 100 * last['close']) / 1e8  # 粗略估算日均成交额(亿)
    volume_ratio = v5 / max(v20, 1) if v20 > 0 else 1.0

    return {
        'symbol': symbol,
        'price': round(last['close'], 2),
        'date': last['date'],
        # 动量
        'm5': round(m5, 2) if m5 is not None else None,
        'm10': round(m10, 2) if m10 is not None else None,
        'm20': round(m20, 2) if m20 is not None else None,
        'momentum_score': round(momentum_score, 2),
        # 均线
        'ma5': round(ma5, 2), 'ma10': round(ma10, 2), 'ma20': round(ma20, 2),
        'above_ma5': last['close'] > ma5,
        'above_ma20': last['close'] > ma20,
        # 量价
        'breakout': breakout,
        'volume_ratio': round(volume_ratio, 2),
        'amt20_yi': round(amt20 / 1e8, 2),
        # 动量质量
        'uniformity': round(uniformity, 2),
        'concentration': round(concentration, 2),
        'volume_health': round(volume_health, 2),
        'acceleration': round(accel, 3) if accel is not None else None,
        # 回调
        'pullback_depth': round(pullback_depth, 2),
        'pullback_volume': round(pullback_volume, 2),
        'high_20d': round(high_20d, 2),
        # 流动性
        'turnover_yi': round(turnover_approx, 2),
        # 日K明细 (供 timing_engine 使用)
        'daily_returns_5d': [round(r, 2) for r in daily_returns_5d],
    }


def compute_composite_factors(kline_factors: dict, llm_factors: dict = None) -> dict:
    """综合七维因子计算。
    kline_factors: compute_kline_factors() 的输出
    llm_factors: LLM agent 产出的质化因子 (可选, 来自 catalyst/fundamentals json)
    """
    kf = kline_factors
    lf = llm_factors or {}

    # ── 七维原始因子值 (0-100 标准化) ──
    raw = {}

    # 1. 动量因子 (0-100)
    ms = kf.get('momentum_score', 0) or 0
    raw['momentum'] = max(0, min(100, 50 + ms * 3))  # 50为中位, 每1%动量=3分

    # 2. 资金因子 (LLM提供, 0-100)
    raw['capital'] = lf.get('capital_score', 50)

    # 3. 情绪因子 (LLM提供, 0-100)
    raw['sentiment'] = lf.get('sentiment_score', 50)

    # 4. 催化因子 (LLM提供, 0-100)
    raw['catalyst'] = lf.get('catalyst_score', 50)

    # 5. 基本面因子 (LLM提供, 0-100)
    raw['fundamentals'] = lf.get('fundamentals_score', 50)

    # 6. 估值因子 (LLM提供, 0-100)
    raw['valuation'] = lf.get('valuation_score', 50)

    # 7. 流动性因子 (从K线计算)
    amt = kf.get('amt20_yi', 0) or 0
    vr = kf.get('volume_ratio', 1) or 1
    liq_score = min(100, amt * 10)  # 1亿=10分, 10亿=100分
    if 0.8 <= vr <= 3:
        liq_score = min(100, liq_score + 20)  # 量比健康加分
    raw['liquidity'] = liq_score

    return {
        'symbol': kf['symbol'],
        'raw_factors': {k: round(v, 1) for k, v in raw.items()},
        'kline_data': kf,
        'llm_data': lf,
    }


# ════════════════════════════════════════════
# Z-Score 标准化
# ════════════════════════════════════════════

def zscore_normalize(all_stocks: list) -> list:
    """对全部候选票的七维因子做 z-score 标准化。
    输入: [{symbol, raw_factors: {dim: value}}, ...]
    输出: 同结构, 增加 z_factors 字段
    """
    if not all_stocks:
        return []

    dims = list(BASE_WEIGHTS.keys())

    # 收集每维的全部值
    dim_values = {d: [] for d in dims}
    for stock in all_stocks:
        rf = stock.get('raw_factors', {})
        for d in dims:
            dim_values[d].append(rf.get(d, 50))

    # 计算均值和标准差
    dim_stats = {}
    for d in dims:
        vals = dim_values[d]
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / max(len(vals), 1)
        std = math.sqrt(variance) if variance > 0 else 1
        dim_stats[d] = (mean, std)

    # 标准化
    for stock in all_stocks:
        rf = stock.get('raw_factors', {})
        zf = {}
        for d in dims:
            mean, std = dim_stats[d]
            raw_val = rf.get(d, 50)
            zf[d] = round((raw_val - mean) / std, 3) if std > 0 else 0
        stock['z_factors'] = zf

    return all_stocks


# ════════════════════════════════════════════
# 相关性矩阵 + 降权
# ════════════════════════════════════════════

def correlation_matrix(all_stocks: list) -> dict:
    """计算因子间相关性, 高相关因子对降权。"""
    dims = list(BASE_WEIGHTS.keys())
    n = len(all_stocks)
    if n < 3:
        return {}

    # 收集 z-score 值
    z_vals = {d: [] for d in dims}
    for stock in all_stocks:
        zf = stock.get('z_factors', {})
        for d in dims:
            z_vals[d].append(zf.get(d, 0))

    # Pearson 相关系数
    def pearson(x_list, y_list):
        n = len(x_list)
        if n < 3:
            return 0
        mx = sum(x_list) / n
        my = sum(y_list) / n
        num = sum((x - mx) * (y - my) for x, y in zip(x_list, y_list))
        dx = math.sqrt(sum((x - mx) ** 2 for x in x_list))
        dy = math.sqrt(sum((y - my) ** 2 for y in y_list))
        if dx * dy == 0:
            return 0
        return num / (dx * dy)

    corr = {}
    penalty = {}  # 每维的降权系数
    for i, d1 in enumerate(dims):
        penalty.setdefault(d1, 1.0)
        for j, d2 in enumerate(dims):
            if j <= i:
                continue
            r = pearson(z_vals[d1], z_vals[d2])
            corr[f"{d1}__{d2}"] = round(r, 3)
            # 高相关(>0.7)的两个因子互相降权
            if abs(r) > 0.7:
                # 权重较低的因子降权
                w1, w2 = BASE_WEIGHTS[d1], BASE_WEIGHTS[d2]
                if w1 < w2:
                    penalty[d1] = min(penalty[d1], 0.7)
                else:
                    penalty[d2] = min(penalty[d2], 0.7)

    return {
        'correlations': corr,
        'penalty': {k: round(v, 2) for k, v in penalty.items()},
    }


# ════════════════════════════════════════════
# 综合评分
# ════════════════════════════════════════════

def compute_scores(all_stocks: list, regime: str = 'ranging',
                   ic_weights: dict = None,
                   custom_weights: dict = None) -> list:
    """计算综合评分。
    regime: trending / ranging / high_volatility / style_rotation
    ic_weights: 每维的IC值(可选, 用于动态加权)
    custom_weights: 自定义基础权重(可选, 覆盖BASE_WEIGHTS)
    """
    weights = custom_weights or dict(BASE_WEIGHTS)
    regime_adj = REGIME_ADJUSTMENTS.get(regime, REGIME_ADJUSTMENTS['ranging'])
    ic_w = ic_weights or {}

    # 相关性降权
    corr_info = correlation_matrix(all_stocks)
    penalty = corr_info.get('penalty', {})

    for stock in all_stocks:
        zf = stock.get('z_factors', {})
        score = 0
        dim_scores = {}
        for dim in weights:
            z = zf.get(dim, 0)
            w = weights[dim]
            # IC加权 (如果有)
            ic = ic_w.get(dim, 0.5)
            ic_adj = 0.5 + ic  # IC范围[-0.5, 0.5] → 调整范围[0, 1]
            # Regime调整
            r_adj = regime_adj.get(dim, 1.0)
            # 相关性降权
            c_pen = penalty.get(dim, 1.0)

            dim_score = z * w * ic_adj * r_adj * c_pen * 100  # 乘以100使其可读
            dim_scores[dim] = round(dim_score, 2)
            score += dim_score

        stock['composite_score'] = round(score, 2)
        stock['dim_scores'] = dim_scores
        stock['regime'] = regime

    # 按总分排序
    all_stocks.sort(key=lambda x: x['composite_score'], reverse=True)
    for i, stock in enumerate(all_stocks):
        stock['rank'] = i + 1

    return all_stocks


# ════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='综合多因子评分引擎')
    parser.add_argument('--codes', required=True, help='逗号分隔的股票代码')
    parser.add_argument('--data-dir', default='', help='读取LLM agent产出json的目录')
    parser.add_argument('--json', default='{}', help='额外参数JSON (regime, weights, ic)')
    parser.add_argument('--output', default='', help='输出文件路径 (默认stdout)')
    args = parser.parse_args()

    codes = [c.strip() for c in args.codes.split(',') if c.strip()]
    params = json.loads(args.json) if args.json else {}
    regime = params.get('regime', 'ranging')

    # 1. 计算K线因子
    kline_results = []
    for code in codes:
        sym = f"sh{code}" if code.startswith(('6', '9')) else f"sz{code}"
        kf = compute_kline_factors(sym)
        if kf:
            kline_results.append(kf)

    # 2. 读取LLM agent产出 (如果有)
    llm_factors_map = {}
    if args.data_dir:
        for fname in ['catalyst.json', 'fundamentals.json', 'technical.json']:
            fpath = os.path.join(args.data_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # 从agent产出中提取因子评分
                    agent_data = data.get('data', data)
                    if isinstance(agent_data, dict):
                        for item in agent_data.get('scores', agent_data.get('results', [])):
                            code = str(item.get('code', ''))
                            if code:
                                llm_factors_map.setdefault(code, {}).update({
                                    'catalyst_score': item.get('catalyst_score', 50),
                                    'capital_score': item.get('capital_score', 50),
                                    'sentiment_score': item.get('sentiment_score', 50),
                                    'fundamentals_score': item.get('fundamentals_score', 50),
                                    'valuation_score': item.get('valuation_score', 50),
                                })
                except Exception:
                    pass

    # 3. 综合因子计算
    all_stocks = []
    for kf in kline_results:
        code = kf['symbol'].replace('sh', '').replace('sz', '')
        lf = llm_factors_map.get(code, {})
        composite = compute_composite_factors(kf, lf)
        all_stocks.append(composite)

    # 4. Z-score 标准化
    all_stocks = zscore_normalize(all_stocks)

    # 5. 综合评分
    ic_weights = params.get('ic_weights', {})
    custom_weights = params.get('weights', None)
    all_stocks = compute_scores(all_stocks, regime=regime,
                                ic_weights=ic_weights,
                                custom_weights=custom_weights)

    # 6. 输出
    result = {
        'regime': regime,
        'regime_adjustments': REGIME_ADJUSTMENTS.get(regime, {}),
        'base_weights': BASE_WEIGHTS,
        'correlation': correlation_matrix(all_stocks),
        'stocks': all_stocks,
        'summary': f'{len(all_stocks)}只股票评分完成, regime={regime}, Top1={all_stocks[0]["symbol"] if all_stocks else "N/A"}',
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
