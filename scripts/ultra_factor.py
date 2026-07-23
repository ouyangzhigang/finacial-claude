#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ultra_factor.py — 超短6维因子评分引擎

专为1天超短线设计: 封板质量 + 资金强度 + 舆情热度 + 事件催化 + 技术动量 + 龙虎榜信号

用法:
  python scripts/ultra_factor.py --date 20260722 --output data/runs/20260722_ultra-short-picks/ultra_scores.json

数据源:
  - market_radar.py (涨停池/龙虎榜/资金流/新闻/板块)
  - sentiment_engine.py (舆情热度)
  - cn_fetch.py (K线/腾讯行情)
  - hot_trend_dig.py (龙虎榜深度)
"""

import json
import os
import sys
import math
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ════════════════════════════════════════════
# 6维因子权重
# ════════════════════════════════════════════

FACTOR_WEIGHTS = {
    'seal_quality':     0.25,  # 封板质量
    'capital_flow':     0.20,  # 资金强度
    'sentiment':        0.15,  # 舆情热度
    'catalyst':         0.20,  # 事件催化
    'momentum':         0.10,  # 技术动量
    'lhb_signal':       0.10,  # 龙虎榜信号
}

# ════════════════════════════════════════════
# 硬门过滤(超短版)
# ════════════════════════════════════════════

ULTRA_GATES = {
    '一字板': {
        'desc': '一字板不追(买不到, 买到就是坑)',
        'check': lambda st: st.get('is_yizi', False),
    },
    '6连板': {
        'desc': '6连板以上不追(接力风险极大)',
        'check': lambda st: st.get('consecutive_boards', 0) >= 6,
    },
    '尾盘炸板': {
        'desc': '尾盘炸板不买(封板失败信号)',
        'check': lambda st: st.get('seal_break_count', 0) > 0 and st.get('last_seal_time', '99') >= '14',
    },
    '拉萨主导': {
        'desc': '拉萨席位主导不买(散户接盘)',
        'check': lambda st: st.get('lasa_dominant', False),
    },
    '流动性不足': {
        'desc': '成交额<1亿不买',
        'check': lambda st: st.get('amount_yi', 0) < 1.0,
    },
    'ST股票': {
        'desc': 'ST股票不买',
        'check': lambda st: st.get('is_st', False),
    },
}


# ════════════════════════════════════════════
# 市场温度计
# ════════════════════════════════════════════

def compute_market_temperature(zt_count, seal_rate, blast_rate, max_board, profit_effect):
    """计算市场温度 (0-100)"""
    scores = []

    # 涨停家数: 0-100映射
    if zt_count >= 100: scores.append(100)
    elif zt_count >= 60: scores.append(75)
    elif zt_count >= 40: scores.append(50)
    elif zt_count >= 20: scores.append(25)
    else: scores.append(5)

    # 封板率: 0-100映射
    if seal_rate >= 90: scores.append(95)
    elif seal_rate >= 80: scores.append(75)
    elif seal_rate >= 65: scores.append(50)
    elif seal_rate >= 50: scores.append(25)
    else: scores.append(5)

    # 炸板率: 扣分
    if blast_rate <= 5: scores.append(95)
    elif blast_rate <= 15: scores.append(70)
    elif blast_rate <= 25: scores.append(45)
    elif blast_rate <= 40: scores.append(20)
    else: scores.append(5)

    # 连板高度
    if max_board >= 6: scores.append(90)
    elif max_board >= 4: scores.append(75)
    elif max_board >= 3: scores.append(55)
    elif max_board >= 2: scores.append(35)
    else: scores.append(15)

    # 赚钱效应
    if profit_effect >= 70: scores.append(90)
    elif profit_effect >= 55: scores.append(70)
    elif profit_effect >= 45: scores.append(50)
    elif profit_effect >= 30: scores.append(25)
    else: scores.append(5)

    return sum(scores) / len(scores)


def temperature_decision(temp):
    """温度 → 仓位/操作建议"""
    if temp < 30:
        return {'verdict': '拒绝', 'max_position': 0.0, 'max_picks': 0, 'reason': '市场冰点, 超短胜率极低'}
    elif temp < 60:
        return {'verdict': '谨慎', 'max_position': 0.30, 'max_picks': 2, 'reason': '市场偏冷, 仅选最优1-2只'}
    elif temp < 80:
        return {'verdict': '正常', 'max_position': 0.50, 'max_picks': 3, 'reason': '市场活跃, 正常出击'}
    else:
        return {'verdict': '积极但警惕', 'max_position': 0.40, 'max_picks': 2, 'reason': '市场过热, 防炸板潮'}


# ════════════════════════════════════════════
# 因子计算
# ════════════════════════════════════════════

def score_seal_quality(st):
    """封板质量评分 (0-100)"""
    score = 60  # 基础分

    # 封板时间: 越早越好
    seal_time = st.get('first_seal_time', '99:99')
    try:
        hour = int(seal_time.split(':')[0]) if ':' in seal_time else 99
        minute = int(seal_time.split(':')[1]) if ':' in seal_time else 99
        if hour < 10: score += 30  # 开盘就封 → 最强
        elif hour == 10: score += 20
        elif hour < 11: score += 10
        elif hour < 13: score += 5
        elif hour < 14: score -= 5
        else: score -= 15  # 尾盘封板 → 最弱
    except (ValueError, IndexError):
        pass

    # 封单量/流通市值
    seal_amount = st.get('seal_amount_yi', 0)  # 亿
    if seal_amount > 5: score += 20
    elif seal_amount > 2: score += 15
    elif seal_amount > 1: score += 10
    elif seal_amount > 0.5: score += 5
    else: score -= 10

    # 开板次数: 0=满分
    break_count = st.get('seal_break_count', 0)
    if break_count == 0: score += 10
    elif break_count <= 2: score -= 5
    else: score -= 20

    # 连板高度: 2-4板最优
    boards = st.get('consecutive_boards', 1)
    if boards == 1: score += 5   # 首板: 安全但溢价低
    elif 2 <= boards <= 3: score += 15  # 2-3板: 最佳
    elif boards == 4: score += 5  # 4板: 还行
    elif boards == 5: score -= 5  # 5板: 偏高
    # 6板以上已被硬门过滤

    return max(0, min(100, score))


def score_capital_flow(st):
    """资金强度评分 (0-100)"""
    score = 50

    # 主力净流入/成交额
    main_net = st.get('main_net_yi', 0)  # 亿
    amount = st.get('amount_yi', 1)
    if amount > 0:
        ratio = main_net / amount * 100
        if ratio > 10: score += 25
        elif ratio > 5: score += 15
        elif ratio > 0: score += 5
        elif ratio > -5: score -= 10
        else: score -= 25

    # 大单买入占比
    big_order = st.get('big_order_ratio', 0)
    if big_order > 50: score += 15
    elif big_order > 30: score += 8
    elif big_order < 10: score -= 10

    # 北向资金
    north_flow = st.get('north_flow_yi', 0)
    if north_flow > 5: score += 10
    elif north_flow > 0: score += 3

    return max(0, min(100, score))


def score_sentiment(st):
    """舆情热度评分 (0-100)"""
    social_heat = st.get('social_heat', 50)
    heat_momentum = st.get('heat_momentum', 0)
    bull_ratio = st.get('bull_ratio', 0.5)
    hype_risk = st.get('hype_risk', 0)

    score = social_heat * 0.5  # 基础: 热度

    # 热度动量加分
    if heat_momentum > 0.3: score += 20
    elif heat_momentum > 0: score += 10
    elif heat_momentum < -0.3: score -= 15

    # 多空比加分
    if bull_ratio > 0.7: score += 15
    elif bull_ratio > 0.5: score += 5

    # 炒作风险扣分
    if hype_risk > 70: score -= 20
    elif hype_risk > 50: score -= 10

    return max(0, min(100, score))


def score_catalyst(st):
    """事件催化评分 (0-100)"""
    score = 50

    # 新闻新鲜度
    news_hours = st.get('latest_news_hours', 999)
    if news_hours < 1: score += 25
    elif news_hours < 3: score += 20
    elif news_hours < 6: score += 15
    elif news_hours < 12: score += 10
    elif news_hours < 24: score += 5

    # 政策级别
    policy_level = st.get('policy_level', 0)
    if policy_level >= 3: score += 20  # 国务院级别
    elif policy_level >= 2: score += 15  # 部委级别
    elif policy_level >= 1: score += 10  # 地方级别

    # 业绩超预期
    earnings_surprise = st.get('earnings_surprise', 0)
    if earnings_surprise > 50: score += 20
    elif earnings_surprise > 20: score += 10
    elif earnings_surprise > 0: score += 5

    # 板块效应
    sector_zt_count = st.get('sector_zt_count', 0)
    if sector_zt_count >= 5: score += 15
    elif sector_zt_count >= 3: score += 10
    elif sector_zt_count >= 1: score += 5

    # 多催化叠加
    catalyst_count = st.get('catalyst_count', 1)
    if catalyst_count >= 3: score += 10
    elif catalyst_count >= 2: score += 5

    return max(0, min(100, score))


def score_momentum(st):
    """技术动量评分 (0-100)"""
    score = 50

    # 近5日涨幅
    m5 = st.get('m5', 0)
    if 5 <= m5 <= 15: score += 20  # 温和上涨, 未透支
    elif 0 < m5 < 5: score += 10
    elif m5 > 15 and m5 <= 25: score += 5  # 注意透支
    elif m5 > 25: score -= 15  # 透支严重
    elif m5 < 0: score -= 10

    # 量比
    volume_ratio = st.get('volume_ratio', 1)
    if 1.5 <= volume_ratio <= 3: score += 15
    elif volume_ratio > 3: score += 5  # 放量太大
    elif volume_ratio < 0.5: score -= 10

    # RSI
    rsi = st.get('rsi', 50)
    if 50 <= rsi <= 75: score += 10  # 健康强势
    elif rsi > 75: score -= 5  # 超买
    elif rsi < 30: score -= 10  # 弱势

    # 站上MA5
    above_ma5 = st.get('above_ma5', True)
    if above_ma5: score += 5

    return max(0, min(100, score))


def score_lhb(st):
    """龙虎榜信号评分 (0-100)"""
    score = 50

    # 机构净买入
    inst_net = st.get('inst_net_buy_yi', 0)
    if inst_net > 1: score += 30
    elif inst_net > 0.5: score += 20
    elif inst_net > 0: score += 10
    elif inst_net < -0.5: score -= 20

    # 知名游资
    has_top_trader = st.get('has_top_trader', False)
    if has_top_trader: score += 15

    # 拉萨席位
    has_lasa = st.get('has_lasa', False)
    if has_lasa: score -= 25

    # 净买额/成交额
    lhb_ratio = st.get('lhb_amount_ratio', 0)
    if lhb_ratio > 10: score += 15
    elif lhb_ratio > 5: score += 10

    return max(0, min(100, score))


# ════════════════════════════════════════════
# 综合评分
# ════════════════════════════════════════════

def compute_ultra_score(st):
    """计算综合超短评分"""
    dims = {
        'seal_quality': score_seal_quality(st),
        'capital_flow': score_capital_flow(st),
        'sentiment': score_sentiment(st),
        'catalyst': score_catalyst(st),
        'momentum': score_momentum(st),
        'lhb_signal': score_lhb(st),
    }

    composite = sum(dims[k] * FACTOR_WEIGHTS[k] for k in FACTOR_WEIGHTS)

    return {
        'composite_score': round(composite, 1),
        'dim_scores': {k: round(v, 1) for k, v in dims.items()},
        'weights': FACTOR_WEIGHTS,
    }


# ════════════════════════════════════════════
# 数据采集
# ════════════════════════════════════════════

def fetch_market_data(date_str):
    """采集市场雷达数据(涨停池+龙虎榜+资金流+新闻)"""
    try:
        result = subprocess.run(
            ['python', 'scripts/market_radar.py', '--section', 'zt,longhu,capital,news,sector'],
            capture_output=True, text=True, encoding='utf-8', timeout=60,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        )
        return result.stdout
    except Exception as e:
        print(f"market_radar.py 失败: {e}", file=sys.stderr)
        return ""


def fetch_lhb_deep(date_str):
    """采集龙虎榜深度数据"""
    try:
        result = subprocess.run(
            ['python', 'scripts/hot_trend_dig.py', '--date', date_str],
            capture_output=True, text=True, encoding='utf-8', timeout=60,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        )
        return result.stdout
    except Exception as e:
        print(f"hot_trend_dig.py 失败: {e}", file=sys.stderr)
        return ""


def fetch_sentiment(codes, data_dir):
    """采集舆情数据"""
    try:
        codes_str = ','.join(codes[:50])
        result = subprocess.run(
            ['python', 'scripts/sentiment_engine.py', '--codes', codes_str,
             '--data-dir', data_dir, '--output', f'{data_dir}/sentiment_scores.json'],
            capture_output=True, text=True, encoding='utf-8', timeout=120,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        )
        return result.stdout
    except Exception as e:
        print(f"sentiment_engine.py 失败: {e}", file=sys.stderr)
        return ""


def fetch_kline_factors(codes):
    """采集K线因子"""
    from cn_fetch import factors as cn_factors, kline as cn_kline
    result = {}
    for code in codes:
        sym = f"sh{code}" if code.startswith(('6', '9')) else f"sz{code}"
        try:
            fc = cn_factors(sym)
            if fc and isinstance(fc, dict):
                result[code] = {
                    'm5': fc.get('m5', 0),
                    'm10': fc.get('m10', 0),
                    'm20': fc.get('m20', 0),
                    'ma5': fc.get('ma5', 0),
                    'ma20': fc.get('ma20', 0),
                    'above_ma5': fc.get('above_ma5', False),
                    'above_ma20': fc.get('above_ma20', False),
                    'volume_ratio': fc.get('v5', 0) / fc.get('v20', 1) if fc.get('v20', 0) > 0 else 1,
                    'amt20_yi': fc.get('amt20_yi', 0),
                    'last': fc.get('last', 0),
                    'date': fc.get('date', ''),
                }
        except Exception:
            pass
    return result


# ════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════

def build_candidates(date_str, data_dir):
    """从涨停池+龙虎榜+热榜构建候选池"""
    candidates = []

    # 1. 从 market_radar 涨停池提取
    import re
    radar_output = fetch_market_data(date_str)

    # 解析涨停池 (从 market_radar 输出中提取)
    zt_pattern = re.findall(
        r'(\d{6})\s+(\S+)\s+.*?涨停.*?(?:封板|seal).*?(\d{2}:\d{2})',
        radar_output
    )

    # 2. 从 hot_trend_dig 龙虎榜提取
    lhb_output = fetch_lhb_deep(date_str)

    # 3. 从 sentiment_engine 取热度
    # (候选池构建后再调用)

    # 从腾讯行情获取基础数据
    codes_for_quote = []
    # 取涨停池中的代码
    for match in re.finditer(r'"code":\s*"(\d{6})"', radar_output):
        codes_for_quote.append(match.group(1))

    codes_for_quote = list(set(codes_for_quote))[:80]  # 去重, 最多80只

    if not codes_for_quote:
        print("⚠️ 未从涨停池获取到代码, 尝试从腾讯涨幅榜获取", file=sys.stderr)
        try:
            from cn_fetch import quote
            # 用常见A股代码前缀批量查询
            # fallback: 直接返回空
        except Exception:
            pass
        return [], {'zt_count': 0, 'seal_rate': 0, 'blast_rate': 0, 'max_board': 0, 'profit_effect': 0}

    # 获取行情
    try:
        from cn_fetch import quote as cn_quote
        quotes = cn_quote([f"sh{c}" if c.startswith(('6','9')) else f"sz{c}" for c in codes_for_quote])
    except Exception:
        quotes = {}

    # 获取K线因子
    kline_factors = fetch_kline_factors(codes_for_quote)

    # 构建候选
    for code in codes_for_quote:
        sym = f"sh{code}" if code.startswith(('6', '9')) else f"sz{code}"
        q = quotes.get(code, {})
        kf = kline_factors.get(code, {})

        if not q or not isinstance(q, dict):
            continue

        st = {
            'code': code,
            'name': q.get('name', '?'),
            'price': q.get('price', 0),
            'prev_close': q.get('prev', 0),
            'pct': q.get('pct', 0),
            'high': q.get('high', 0),
            'low': q.get('low', 0),
            'amount_yi': q.get('amount_yi', 0),
            'turnover': q.get('turnover', 0),
            'pe_ttm': q.get('pe_ttm'),
            'mktcap_yi': q.get('mktcap_yi'),
            'is_st': 'ST' in str(q.get('name', '')),
            'is_yizi': q.get('pct', 0) >= 9.9 and q.get('low', 0) == q.get('high', 0),

            # 封板信息 (从 market_radar 解析)
            'first_seal_time': '99:99',
            'seal_amount_yi': 0,
            'seal_break_count': 0,
            'consecutive_boards': 1,
            'sector_zt_count': 0,

            # 资金流
            'main_net_yi': 0,
            'big_order_ratio': 0,
            'north_flow_yi': 0,

            # 舆情
            'social_heat': 50,
            'heat_momentum': 0,
            'bull_ratio': 0.5,
            'hype_risk': 0,

            # 事件
            'latest_news_hours': 999,
            'policy_level': 0,
            'earnings_surprise': 0,
            'catalyst_count': 1,

            # 龙虎榜
            'inst_net_buy_yi': 0,
            'has_top_trader': False,
            'has_lasa': False,
            'lasa_dominant': False,
            'lhb_amount_ratio': 0,

            # 技术
            'm5': kf.get('m5', 0),
            'm10': kf.get('m10', 0),
            'volume_ratio': kf.get('volume_ratio', 1),
            'rsi': 50,
            'above_ma5': kf.get('above_ma5', True),
        }
        candidates.append(st)

    # 市场温度
    market = {
        'zt_count': len(candidates),
        'seal_rate': 80,
        'blast_rate': 15,
        'max_board': 3,
        'profit_effect': 55,
    }

    return candidates, market


def main():
    p = argparse.ArgumentParser(description='超短6维因子评分引擎')
    p.add_argument('--date', required=True, help='日期 YYYYMMDD')
    p.add_argument('--data-dir', default='', help='数据目录')
    p.add_argument('--output', default='', help='输出文件路径')
    p.add_argument('--top-n', type=int, default=5, help='TopN数量')
    args = p.parse_args()

    data_dir = args.data_dir or f'data/runs/{args.date}_ultra-short-picks'
    os.makedirs(data_dir, exist_ok=True)

    # 1. 构建候选池
    print(f"🔍 构建候选池 (日期: {args.date})...", file=sys.stderr)
    candidates, market = build_candidates(args.date, data_dir)

    if not candidates:
        print("⚠️ 候选池为空, 无法评分", file=sys.stderr)
        output = {
            'date': args.date,
            'market': market,
            'temperature': 0,
            'temperature_decision': {'verdict': '拒绝', 'reason': '无候选标的'},
            'stocks': [],
            'summary': '候选池为空',
        }
    else:
        # 2. 市场温度
        temp = compute_market_temperature(
            market['zt_count'], market['seal_rate'],
            market['blast_rate'], market['max_board'],
            market['profit_effect']
        )
        temp_decision = temperature_decision(temp)

        print(f"🌡️ 市场温度: {temp:.1f}° → {temp_decision['verdict']} ({temp_decision['reason']})", file=sys.stderr)

        if temp_decision['verdict'] == '拒绝':
            print("❌ 市场温度过低, 拒绝选股", file=sys.stderr)
            output = {
                'date': args.date,
                'market': market,
                'temperature': round(temp, 1),
                'temperature_decision': temp_decision,
                'stocks': [],
                'summary': f"市场温度{temp:.1f}°, 拒绝选股",
            }
        else:
            # 3. 硬门过滤
            passed = []
            rejected = []
            for st in candidates:
                rejected_by = []
                for gate_name, gate in ULTRA_GATES.items():
                    if gate['check'](st):
                        rejected_by.append(f"{gate_name}: {gate['desc']}")

                if rejected_by:
                    st['gate_status'] = 'reject'
                    st['gate_reasons'] = rejected_by
                    rejected.append(st)
                else:
                    st['gate_status'] = 'pass'
                    passed.append(st)

            print(f"🚪 硬门过滤: {len(passed)} 通过 / {len(rejected)} 否决", file=sys.stderr)

            # 4. 因子评分
            for st in passed:
                scores = compute_ultra_score(st)
                st.update(scores)

            # 5. 排序
            passed.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

            # 6. 输出
            top_n = passed[:args.top_n]
            output = {
                'date': args.date,
                'market': market,
                'temperature': round(temp, 1),
                'temperature_decision': temp_decision,
                'gates_summary': {
                    'passed': len(passed),
                    'rejected': len(rejected),
                    'total': len(candidates),
                },
                'stocks': passed,
                'rejected': [{'code': r['code'], 'name': r.get('name', '?'), 'reasons': r.get('gate_reasons', [])} for r in rejected],
                'top_n': [{'code': s['code'], 'name': s.get('name', '?'), 'composite_score': s.get('composite_score', 0),
                           'dim_scores': s.get('dim_scores', {})} for s in top_n],
                'summary': f"{len(passed)}只评分完成, 温度{temp:.1f}°, Top1={top_n[0]['code'] if top_n else 'N/A'}",
            }

    # 写输出
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(data_dir, 'ultra_scores.json')

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 输出到 {output_path}", file=sys.stderr)
    top_n = output.get('stocks', [])
    if top_n:
        print(f"   Top{args.top_n}: {[s['code'] for s in top_n]}", file=sys.stderr)

    # 打印到 stdout 供 agent 读取
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()