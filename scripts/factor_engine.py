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
    'momentum':     0.22,  # 技术动量
    'capital':      0.18,  # 资金推动
    'sentiment':    0.05,  # 市场情绪(封板率等, market_radar)
    'social':       0.10,  # 社交舆情热度(sentiment_engine)
    'catalyst':     0.20,  # 催化确定性
    'fundamentals': 0.12,  # 基本面底线
    'valuation':    0.08,  # 估值安全
    'liquidity':    0.05,  # 流动性适配
}

# ════════════════════════════════════════════
# Regime 调整系数 (Layer 0 输出)
# ════════════════════════════════════════════
REGIME_ADJUSTMENTS = {
    'trending': {
        'momentum': 1.5, 'capital': 1.2, 'sentiment': 1.0, 'social': 1.3,
        'catalyst': 1.0, 'fundamentals': 0.8, 'valuation': 0.7, 'liquidity': 1.0,
    },
    'ranging': {
        'momentum': 0.7, 'capital': 1.0, 'sentiment': 0.8, 'social': 0.8,
        'catalyst': 1.2, 'fundamentals': 1.2, 'valuation': 1.5, 'liquidity': 1.0,
    },
    'high_volatility': {
        'momentum': 0.5, 'capital': 0.8, 'sentiment': 0.7, 'social': 0.6,
        'catalyst': 1.0, 'fundamentals': 1.5, 'valuation': 1.0, 'liquidity': 1.3,
    },
    'style_rotation': {
        'momentum': 0.5, 'capital': 0.7, 'sentiment': 0.6, 'social': 0.7,
        'catalyst': 1.0, 'fundamentals': 1.2, 'valuation': 1.0, 'liquidity': 1.0,
    },
    'shock': {
        'momentum': 0.3, 'capital': 0.5, 'sentiment': 0.4, 'social': 0.5,
        'catalyst': 0.8, 'fundamentals': 1.8, 'valuation': 1.5, 'liquidity': 1.5,
    },
}

# ════════════════════════════════════════════
# 因子计算
# ════════════════════════════════════════════

def compute_kline_factors(symbol: str, datalen: int = 60, factors_cache: Optional[dict] = None) -> Optional[dict]:
    """从K线数据计算量化因子 (动量/量价/流动性)。
    复用 cn_fetch.kline() 获取数据。

    Args:
        symbol: 股票代码 (sh/sz前缀)
        datalen: K线数据长度
        factors_cache: 可选的 cn_fetch.factors() 预计算缓存 (含 avgAmount20d)
    """
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

    # ── 20日均成交额（优先使用cn_fetch.factors()预计算值） ────────────
    # 原始k线重算可能因数据长度不足产生偏差，优先取cn_fetch.quote接口的amt20字段（腾讯行情直出，单位亿）
    amt20_cn = factors_cache.get('avgAmount20d') if factors_cache else None  # cn_fetch返回单位已是亿元

    if amt20_cn is not None and amt20_cn > 0:
        # 使用cn_fetch预计算的金额（已转亿元），更可靠
        amt20 = float(amt20_cn)
        amt20_source = 'cn_factors'
    else:
        # Fallback: 从k线重新计算（注意vol单位为手×100股）
        amt20 = sum(rows[i]['vol'] * 100 * rows[i]['close'] for i in range(-20, 0)) / 20
        amt20 = amt20 / 1e8  # 转为亿元
        amt20_source = 'kline_recalc'
        # 记录警告以便调试
        if len(rows) < 20:
            print(f"⚠️ factor_engine: {symbol} k线数据仅{len(rows)}日(<20), avgAmount20d fallback为K线重算值", file=sys.stderr)

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

    # 4. 社交舆情因子 (sentiment_engine提供, 0-100)
    raw['social'] = lf.get('social_heat', 50)

    # 5. 催化因子 (LLM提供, 0-100)
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

    # ── 基本面硬扣分(垃圾公司过滤器) ──
    # ROE<5% 且 PE>50 → 说明盈利能力弱但估值高, 扣30分
    # 此扣分在 z-score 之前执行, 确保"垃圾公司"在因子层面就被压低
    roe = lf.get('roe')
    pe = lf.get('pe')
    fundamentals_penalty = 0
    if roe is not None and pe is not None:
        try:
            roe_val = float(roe)
            pe_val = float(pe)
            if roe_val < 5 and pe_val > 50:
                fundamentals_penalty = 30
                raw['fundamentals'] = max(0, raw['fundamentals'] - fundamentals_penalty)
        except (ValueError, TypeError):
            pass  # 非数值型 ROE/PE, 跳过扣分

    # ── 数据可用性检测(改造3): 区分"有真实数据"和"默认50" ──
    # K线维度: 有有效K线数据视为可用
    data_availability = {}
    data_availability['momentum'] = kf.get('m5') is not None or (kf.get('momentum_score', 0) or 0) != 0
    data_availability['liquidity'] = (kf.get('amt20_yi') or 0) > 0
    # 外部JSON维度: 键存在且非None视为有真实数据(默认50返回不算)
    for dim, key in [('capital', 'capital_score'), ('sentiment', 'sentiment_score'),
                     ('social', 'social_heat'), ('catalyst', 'catalyst_score'),
                     ('fundamentals', 'fundamentals_score'), ('valuation', 'valuation_score')]:
        data_availability[dim] = key in lf and lf[key] is not None

    return {
        'symbol': kf['symbol'],
        'raw_factors': {k: round(v, 1) for k, v in raw.items()},
        'kline_data': kf,
        'llm_data': lf,
        'fundamentals_penalty': fundamentals_penalty,  # 记录扣分, 供调试
        'data_availability': data_availability,  # 改造3: 每维数据可用性
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
    for dim in dims:
        penalty.setdefault(dim, 1.0)
    for i, d1 in enumerate(dims):
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

    # ── 数据可用率检测(改造3): 动态权重再分配 ──
    # 可用率<50%的维度权重×0.3, 砍掉的份额转移给momentum(最可靠)
    # 全部非K线维度<50% → data_link_broken=True, 置信度强制低
    dim_available_count = {d: 0 for d in weights}
    for stock in all_stocks:
        da = stock.get('data_availability', {})
        for d in weights:
            if da.get(d, False):
                dim_available_count[d] += 1
    total_stocks = max(1, len(all_stocks))
    dim_availability_rate = {d: dim_available_count[d] / total_stocks for d in weights}

    adjusted_weights = dict(weights)
    transfer_pool = 0.0
    for d in list(weights.keys()):
        if d != 'momentum' and dim_availability_rate.get(d, 1) < 0.5:
            reduction = adjusted_weights[d] * 0.7  # 砍70%
            transfer_pool += reduction
            adjusted_weights[d] = adjusted_weights[d] * 0.3
    if transfer_pool > 0 and 'momentum' in adjusted_weights:
        adjusted_weights['momentum'] += transfer_pool

    # 数据链断模式: 非K线维度全<50%可用率(≠动量优先,是数据缺失)
    non_kline_dims = [d for d in weights if d not in ('momentum', 'liquidity')]
    data_link_broken = len(non_kline_dims) > 0 and all(dim_availability_rate.get(d, 0) < 0.5 for d in non_kline_dims)
    weights = adjusted_weights

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

    # 改造3: 把数据可用性元数据写入每只票(供governor/hard_gate读取)
    for stock in all_stocks:
        stock['data_link_broken'] = data_link_broken
        stock['dim_availability_rate'] = {k: round(v, 2) for k, v in dim_availability_rate.items()}
        stock['adjusted_weights'] = {k: round(v, 3) for k, v in adjusted_weights.items()}

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

    # 1. 计算K线因子 (传入 cn_fetch.factors() 预计算缓存, 消除重复HTTP)
    kline_results = []
    for code in codes:
        sym = code if code.startswith(('sh', 'sz')) else (f"sh{code}" if code.startswith(('6', '9')) else f"sz{code}")
        # 预取 cn_fetch.factors() 缓存 (含 avgAmount20d, 避免 compute_kline_factors 内重算)
        try:
            fc = _cn_factors(sym)
            factors_cache = fc if isinstance(fc, dict) else None
        except Exception:
            factors_cache = None  # 获取失败时降级为 None, 函数内走 kline 重算 fallback
        kf = compute_kline_factors(sym, factors_cache=factors_cache)
        if kf:
            kline_results.append(kf)

    # 2. 读取LLM agent产出 + 量化引擎产出 (自给自足模式)
    llm_factors_map = {}
    if args.data_dir:
        # ── 2a. 读取 technical-liquidity.json (流动性+技术因子) ──
        tech_path = os.path.join(args.data_dir, 'technical-liquidity.json')
        if os.path.exists(tech_path):
            try:
                with open(tech_path, 'r', encoding='utf-8') as f:
                    tdata = json.load(f)
                td = tdata.get('data', tdata)
                for item in td.get('pass', []):
                    code = str(item.get('code', ''))
                    if code:
                        llm_factors_map.setdefault(code, {}).update({
                            'turnover20d': item.get('turnover20d'),
                            'avgAmount20d': item.get('avgAmount20d'),
                            'marketCap': item.get('marketCap'),
                            'entryType': item.get('entryType'),
                            'entryScore': item.get('entryScore'),
                        })
            except Exception:
                pass

        # ── 2b. 读取 fundamentals-analyst.json (基本面+估值因子) ──
        fund_path = os.path.join(args.data_dir, 'fundamentals-analyst.json')
        if os.path.exists(fund_path):
            try:
                with open(fund_path, 'r', encoding='utf-8') as f:
                    fdata = json.load(f)
                fd = fdata.get('data', fdata)
                stocks_dict = fd.get('stocks', {})
                if isinstance(stocks_dict, dict):
                    for code, info in stocks_dict.items():
                        code = str(code)
                        if not isinstance(info, dict):
                            continue
                        financials = info.get('financials', {})
                        valuation = info.get('valuation', {})
                        roe = financials.get('roe')
                        pe = valuation.get('peTtm')
                        verdict = info.get('verdict', '')
                        red_flags = info.get('redFlags', [])

                        # 基本面评分: 从 verdict 和 redFlags 推导
                        fund_score = 50  # 中性起点
                        if verdict == '剔除':
                            fund_score = 10
                        elif verdict == '降权':
                            fund_score = 30
                        elif any(f.get('severity') == 'red' for f in red_flags):
                            fund_score = 15
                        elif verdict in ('通过', '清洁通过'):
                            fund_score = 70
                        elif '最优' in str(verdict):
                            fund_score = 85

                        # 估值评分: 从 PE 推导
                        val_score = 50
                        if pe is not None:
                            try:
                                pe_val = float(pe)
                                if pe_val < 0:
                                    val_score = 20  # 亏损
                                elif pe_val <= 15:
                                    val_score = 80  # 低估
                                elif pe_val <= 30:
                                    val_score = 60  # 合理
                                elif pe_val <= 60:
                                    val_score = 40  # 偏高
                                elif pe_val <= 200:
                                    val_score = 25  # 高估
                                else:
                                    val_score = 10  # 极高
                            except (ValueError, TypeError):
                                pass

                        llm_factors_map.setdefault(code, {}).update({
                            'roe': roe,
                            'pe': pe,
                            'fundamentals_score': fund_score,
                            'valuation_score': val_score,
                            'verdict': verdict,
                        })
            except Exception:
                pass

        # ── 2c. 读取 sentiment_engine 产出 (社交舆情量化因子) ──
        sentiment_path = os.path.join(args.data_dir, 'sentiment_scores.json')
        if os.path.exists(sentiment_path):
            try:
                with open(sentiment_path, 'r', encoding='utf-8') as f:
                    sdata = json.load(f)
                for item in sdata.get('stocks', []):
                    code = str(item.get('code', ''))
                    if code:
                        llm_factors_map.setdefault(code, {}).update({
                            'social_heat': item.get('social_heat', 50),
                            'hype_risk': item.get('hype_risk', 0),
                            # 催化评分: 从社交热度+概念命中推导 (catalyst-scanner.json 可能不存在)
                            'catalyst_score': min(90, item.get('social_heat', 50) * 0.7 + 20),
                            'sentiment_score': item.get('market_sentiment', 50),
                        })
            except Exception:
                pass

        # ── 2d. 读取 capital_scores.json (资金流评分, 优先读文件) ──
        capital_path = os.path.join(args.data_dir, 'capital_scores.json')
        if os.path.exists(capital_path):
            try:
                with open(capital_path, 'r', encoding='utf-8') as f:
                    cdata = json.load(f)
                for code, score in cdata.items():
                    if isinstance(score, (int, float)):
                        llm_factors_map.setdefault(str(code), {})['capital_score'] = score
            except Exception:
                pass
        else:
            # 文件不存在时降级为实时计算
            try:
                from astock_data import compute_capital_score
                for code in codes:
                    cap_score = compute_capital_score(code)
                    llm_factors_map.setdefault(code, {})['capital_score'] = cap_score
            except ImportError:
                pass

        # ── 2e. 读取 supply_risk.json (供给端风险) ──
        supply_path = os.path.join(args.data_dir, 'supply_risk.json')
        if os.path.exists(supply_path):
            try:
                with open(supply_path, 'r', encoding='utf-8') as f:
                    supdata = json.load(f)
                for code, info in supdata.items():
                    if isinstance(info, dict):
                        risk_score = info.get('risk_score', 0)
                        llm_factors_map.setdefault(str(code), {})['supply_risk'] = risk_score
            except Exception:
                pass

        # ── 2f. mootdx 财务数据兜底 (当 ROE 大面积缺失时) ──
        roe_missing = sum(1 for v in llm_factors_map.values() if v.get('roe') is None)
        if roe_missing > len(codes) * 0.5:  # 超过50%的股票缺ROE → 启动mootdx兜底
            try:
                from mootdx.affair import Affair
                a = Affair()
                df = a.parse(filename='gpcw20251231.zip')
                # 列索引 (参考 batch_fundamentals_screen.py)
                COL_ROE, COL_GOODWILL = 6, 35
                COL_TOTAL_EQUITY = 72
                COL_REVENUE_GROWTH, COL_PROFIT_GROWTH = 183, 184
                COL_GROSS_MARGIN, COL_DEBT_RATIO = 202, 210
                COL_NET_PROFIT = 95
                for code in codes:
                    if code in df.index:
                        row = df.loc[code]
                        try:
                            mootdx_roe = float(row.iloc[COL_ROE]) if row.iloc[COL_ROE] is not None and float(row.iloc[COL_ROE]) == float(row.iloc[COL_ROE]) else None
                            goodwill = float(row.iloc[COL_GOODWILL]) if row.iloc[COL_GOODWILL] is not None else 0
                            equity = float(row.iloc[COL_TOTAL_EQUITY]) if row.iloc[COL_TOTAL_EQUITY] is not None else 1
                            goodwill_ratio = (goodwill / equity * 100) if equity > 0 else 0
                            net_profit = float(row.iloc[COL_NET_PROFIT]) if row.iloc[COL_NET_PROFIT] is not None else None
                            revenue_growth = float(row.iloc[COL_REVENUE_GROWTH]) if row.iloc[COL_REVENUE_GROWTH] is not None else None
                            profit_growth = float(row.iloc[COL_PROFIT_GROWTH]) if row.iloc[COL_PROFIT_GROWTH] is not None else None
                            gross_margin = float(row.iloc[COL_GROSS_MARGIN]) if row.iloc[COL_GROSS_MARGIN] is not None else None
                            debt_ratio = float(row.iloc[COL_DEBT_RATIO]) if row.iloc[COL_DEBT_RATIO] is not None else None

                            existing = llm_factors_map.setdefault(code, {})
                            if existing.get('roe') is None and mootdx_roe is not None:
                                existing['roe'] = mootdx_roe
                            existing['goodwill_ratio'] = goodwill_ratio
                            existing['net_profit'] = net_profit
                            existing['revenue_growth'] = revenue_growth
                            existing['profit_growth'] = profit_growth
                            existing['gross_margin'] = gross_margin
                            existing['debt_ratio'] = debt_ratio

                            # 用 mootdx 数据修正 fundamentals_score（如果之前是默认50）
                            if existing.get('fundamentals_score', 50) == 50:
                                fund_score = 50
                                if mootdx_roe is not None:
                                    if mootdx_roe < 0:
                                        fund_score = 15  # 亏损
                                    elif mootdx_roe < 5:
                                        fund_score = 30  # 盈利弱
                                    elif mootdx_roe < 10:
                                        fund_score = 55  # 一般
                                    elif mootdx_roe < 20:
                                        fund_score = 70  # 良好
                                    else:
                                        fund_score = 85  # 优秀
                                if goodwill_ratio > 30:
                                    fund_score = min(fund_score, 20)  # 商誉炸弹
                                if net_profit is not None and net_profit < 0:
                                    fund_score = min(fund_score, 15)  # 亏损
                                existing['fundamentals_score'] = fund_score
                        except (ValueError, TypeError, IndexError):
                            pass
            except ImportError:
                pass  # mootdx 不可用, 静默降级
            except Exception:
                pass  # 其他错误(网络等), 静默降级

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
    # 改造3: 顶层加数据链状态(供hard_gate/governor读取)
    _data_link_broken = all_stocks[0].get('data_link_broken', False) if all_stocks else False
    _dim_avail = all_stocks[0].get('dim_availability_rate', {}) if all_stocks else {}
    _adj_w = all_stocks[0].get('adjusted_weights', BASE_WEIGHTS) if all_stocks else dict(BASE_WEIGHTS)
    result = {
        'regime': regime,
        'regime_adjustments': REGIME_ADJUSTMENTS.get(regime, {}),
        'base_weights': BASE_WEIGHTS,
        'adjusted_weights': _adj_w,  # 改造3: 数据缺失再分配后的实际权重
        'dim_availability_rate': _dim_avail,  # 改造3: 每维数据可用率
        'data_link_broken': _data_link_broken,  # 改造3: 数据链断模式(全非K线维<50%)
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
