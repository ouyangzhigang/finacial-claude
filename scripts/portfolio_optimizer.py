#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
portfolio_optimizer.py — 回测引擎+组合优化 (Layer 3: Portfolio Construction)

借鉴: Bridgewater Risk Parity + Two Sigma Risk Management

功能:
  1. 回测引擎: 3个月非重叠5日窗口 + 环境分层(顺风/震荡/逆风)
  2. 组合优化: 约束条件下的仓位分配
  3. 风险指标: 胜率+均收+回撤+夏普比率+置信区间

用法:
  python scripts/portfolio_optimizer.py --codes 603456,002294,603369 --index-code sh000001
  python scripts/portfolio_optimizer.py --codes 603456 --account 10000 --risk-budget 0.65

输出: JSON 到 stdout
"""
import json
import sys
import os
import math
import argparse
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cn_fetch import kline as _kline


# ════════════════════════════════════════════
# 回测引擎 (环境分层)
# ════════════════════════════════════════════

def get_3month_kline(symbol: str) -> Optional[list]:
    """获取3个月日K线 (~60交易日)"""
    sym = symbol if symbol.startswith(('sh', 'sz')) else (
        f"sh{symbol}" if symbol.startswith(('6', '9')) else f"sz{symbol}"
    )
    arr = _kline(sym, 90)  # 取90天确保60交易日
    if not arr or len(arr) < 25:
        return None
    rows = []
    for x in arr:
        rows.append({
            'date': x[0],
            'close': float(x[2]),
            'high': float(x[3]),
            'low': float(x[4]),
            'vol': float(x[5]) if len(x) > 5 else 0,
        })
    return rows


def get_index_3month(index_sym: str = 'sh000001') -> list:
    """获取指数3个月K线 (用于环境分层)"""
    import urllib.request, ssl
    ctx = ssl._create_unverified_context()
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={index_sym},day,,,90,qfq"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            j = json.loads(r.read().decode('utf-8', 'ignore'))
        data_node = j.get('data', {}).get(index_sym, {})
        arr = data_node.get('qfqday') or data_node.get('day') or []
        return [{'date': x[0], 'close': float(x[2])} for x in arr]
    except Exception:
        return []


def classify_market_env(index_closes: list, start_idx: int, window: int = 5) -> str:
    """判断某5日窗口的市场环境: tailwind / neutral / headwind"""
    if start_idx < window or start_idx + window >= len(index_closes):
        return 'neutral'
    # 5日涨幅
    start_price = index_closes[start_idx]
    end_price = index_closes[min(start_idx + window, len(index_closes) - 1)]
    ret = (end_price - start_price) / start_price * 100
    if ret > 1.5:
        return 'tailwind'
    elif ret < -1.5:
        return 'headwind'
    else:
        return 'neutral'


def run_backtest(stock_rows: list, index_rows: list = None, window: int = 5) -> dict:
    """非重叠5日窗口回测 + 环境分层"""
    if not stock_rows or len(stock_rows) < 25:
        return {'sample_count': 0, 'verdict': '数据不足'}

    closes = [r['close'] for r in stock_rows]
    dates = [r['date'] for r in stock_rows]
    highs = [r['high'] for r in stock_rows]
    lows = [r['low'] for r in stock_rows]
    n = len(closes)

    # 指数收盘 (用于环境分层)
    index_closes = [r['close'] for r in index_rows] if index_rows else []

    # 非重叠窗口: 从最近往前, 每5天一个窗口
    windows = []
    i = n - 1
    while i - window >= 0:
        entry_price = closes[i - window]
        exit_price = closes[i]
        ret = (exit_price - entry_price) / entry_price * 100

        # 窗口内最大回撤
        window_highs = highs[i - window:i + 1]
        window_lows = lows[i - window:i + 1]
        max_dd = 0
        for j in range(len(window_lows)):
            peak = max(window_highs[:j + 1])
            dd = (window_lows[j] - peak) / peak * 100
            max_dd = min(max_dd, dd)

        # 市场环境
        env = 'neutral'
        if index_closes and len(index_closes) >= i + 1:
            # 对齐日期 (简化: 用索引对齐)
            idx_offset = len(index_closes) - n
            idx_start = max(0, i - window + idx_offset)
            idx_end = min(len(index_closes) - 1, i + idx_offset)
            env = classify_market_env(index_closes, idx_start, idx_end - idx_start)

        windows.append({
            'entry_date': dates[i - window],
            'exit_date': dates[i],
            'entry_price': round(entry_price, 2),
            'exit_price': round(exit_price, 2),
            'return_pct': round(ret, 2),
            'max_drawdown': round(max_dd, 2),
            'profit': ret > 0,
            'env': env,
        })
        i -= window

    if not windows:
        return {'sample_count': 0, 'verdict': '数据不足'}

    # 总体统计
    returns = [w['return_pct'] for w in windows]
    wins = sum(1 for w in windows if w['profit'])
    win_rate = wins / len(windows) * 100
    avg_return = sum(returns) / len(returns)
    max_dd_overall = min(w['max_drawdown'] for w in windows)

    # 95% 置信区间 (二项分布)
    p = wins / len(windows)
    se = math.sqrt(p * (1 - p) / len(windows))
    ci_low = max(0, (p - 1.96 * se) * 100)
    ci_high = min(100, (p + 1.96 * se) * 100)

    # 环境分层统计
    env_stats = {}
    for env in ['tailwind', 'neutral', 'headwind']:
        env_windows = [w for w in windows if w['env'] == env]
        if env_windows:
            env_wins = sum(1 for w in env_windows if w['profit'])
            env_stats[env] = {
                'count': len(env_windows),
                'win_rate': round(env_wins / len(env_windows) * 100, 1),
                'avg_return': round(sum(w['return_pct'] for w in env_windows) / len(env_windows), 2),
            }
        else:
            env_stats[env] = {'count': 0, 'win_rate': 0, 'avg_return': 0}

    # 加权综合胜率 (顺风30% + 震荡40% + 逆风30%)
    weighted_wr = (
        env_stats['tailwind']['win_rate'] * 0.3
        + env_stats['neutral']['win_rate'] * 0.4
        + env_stats['headwind']['win_rate'] * 0.3
    )

    # 简化夏普 (5日窗口收益/波动)
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1))
        sharpe = mean_r / std_r if std_r > 0 else 0
    else:
        sharpe = 0

    # 达标判断
    pass_count = 0
    if win_rate >= 55:
        pass_count += 1
    if avg_return >= 2:
        pass_count += 1
    if max_dd_overall >= -8:
        pass_count += 1

    if pass_count == 0:
        verdict = 'rejected'
    elif pass_count == 1:
        verdict = 'observation'
    elif pass_count == 2:
        verdict = 'cautious'
    else:
        verdict = 'approved'

    return {
        'sample_count': len(windows),
        'win_rate': round(win_rate, 1),
        'weighted_win_rate': round(weighted_wr, 1),
        'avg_return': round(avg_return, 2),
        'max_drawdown': round(max_dd_overall, 2),
        'sharpe_5d': round(sharpe, 2),
        'confidence_interval': [round(ci_low, 1), round(ci_high, 1)],
        'pass_count': pass_count,
        'verdict': verdict,
        'env_stats': env_stats,
        'windows': windows,
    }


# ════════════════════════════════════════════
# 组合优化
# ════════════════════════════════════════════

def optimize_portfolio(stocks: list, account: int = 10000,
                       risk_budget: float = 0.65, cash_min: float = 0.25) -> dict:
    """基于约束条件的仓位分配。
    stocks: [{code, name, price, composite_score, timing_score, backtest, ...}]
    """
    total_budget = account * risk_budget
    cash_reserve = account * cash_min

    # 过滤: timing_score < -10 的票不入组合
    eligible = [s for s in stocks if s.get('timing_score', 0) > -10]
    if not eligible:
        return {'positions': [], 'cash': account, 'cash_pct': 100, 'reason': '无合格标的'}

    # 按综合评分+入场评分排序
    eligible.sort(key=lambda x: x.get('composite_score', 0) + x.get('timing_score', 0), reverse=True)

    # 1w 账户手数约束: 100股最小手数
    positions = []
    remaining = total_budget
    for stock in eligible:
        price = stock.get('price', 0)
        if price <= 0 or price > 40:  # 1w账户 >40元不可配
            continue
        lot_cost = price * 100
        if lot_cost > remaining or lot_cost > account * 0.30:  # 单票≤30%
            continue
        positions.append({
            'code': stock.get('code', ''),
            'name': stock.get('name', ''),
            'price': price,
            'lots': 1,
            'shares': 100,
            'amount': round(lot_cost, 2),
            'pct': round(lot_cost / account * 100, 1),
            'score': round(stock.get('composite_score', 0) + stock.get('timing_score', 0), 1),
            'timing': stock.get('timing_verdict', ''),
            'backtest': stock.get('backtest_verdict', ''),
        })
        remaining -= lot_cost
        if remaining < 1000:  # 至少留1000现金
            break

    invested = sum(p['amount'] for p in positions)
    cash = account - invested

    return {
        'positions': positions,
        'invested': round(invested, 2),
        'invested_pct': round(invested / account * 100, 1),
        'cash': round(cash, 2),
        'cash_pct': round(cash / account * 100, 1),
        'risk_budget': risk_budget,
        'stock_count': len(positions),
    }


# ════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='回测引擎+组合优化')
    parser.add_argument('--codes', required=True, help='逗号分隔的股票代码')
    parser.add_argument('--index-code', default='sh000001', help='基准指数代码')
    parser.add_argument('--account', type=int, default=10000, help='账户金额')
    parser.add_argument('--risk-budget', type=float, default=0.65, help='风险预算(仓位上限)')
    parser.add_argument('--cash-min', type=float, default=0.25, help='最低现金比例')
    parser.add_argument('--output', default='', help='输出文件路径')
    parser.add_argument('--backtest-only', action='store_true', help='只做回测,不做组合优化')
    args = parser.parse_args()

    codes = [c.strip() for c in args.codes.split(',') if c.strip()]

    # 获取指数数据 (所有股票共用)
    index_rows = get_index_3month(args.index_code)

    # 逐票回测
    backtest_results = []
    for code in codes:
        rows = get_3month_kline(code)
        if rows:
            bt = run_backtest(rows, index_rows)
            bt['code'] = code
            bt['price'] = rows[-1]['close']
            backtest_results.append(bt)
        else:
            backtest_results.append({
                'code': code, 'sample_count': 0, 'verdict': 'data_missing',
                'win_rate': 0, 'weighted_win_rate': 0, 'avg_return': 0,
                'max_drawdown': 0, 'pass_count': 0, 'price': 0,
            })

    output = {
        'backtest': backtest_results,
        'summary': f'{len(backtest_results)}只回测完成',
    }

    # 组合优化 (可选)
    if not args.backtest_only:
        stocks_for_opt = []
        for bt in backtest_results:
            stocks_for_opt.append({
                'code': bt['code'],
                'price': bt.get('price', 0),
                'composite_score': 50,  # 需要从 factor_engine 传入
                'timing_score': 0,       # 需要从 timing_engine 传入
                'backtest_verdict': bt.get('verdict', 'unknown'),
            })
        portfolio = optimize_portfolio(
            stocks_for_opt, account=args.account,
            risk_budget=args.risk_budget, cash_min=args.cash_min,
        )
        output['portfolio'] = portfolio

    # 汇总
    approved = [b for b in backtest_results if b.get('verdict') == 'approved']
    rejected = [b for b in backtest_results if b.get('verdict') == 'rejected']
    output['summary'] = (
        f'{len(backtest_results)}只回测: '
        f'{len(approved)}只approved, {len(rejected)}只rejected'
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
