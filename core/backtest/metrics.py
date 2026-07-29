"""回测指标(胜率/夏普/回撤/置信区间)。

迁自 portfolio_optimizer 的统计逻辑, 独立模块化。
"""
from __future__ import annotations

import math


def win_rate(returns: list[float]) -> float:
    """胜率 %。"""
    if not returns:
        return 0.0
    return sum(1 for r in returns if r > 0) / len(returns) * 100


def avg_return(returns: list[float]) -> float:
    """平均收益 %。"""
    return sum(returns) / len(returns) if returns else 0.0


def max_drawdown(equity_curve: list[float]) -> float:
    """最大回撤 %(负值)。equity_curve: 累计净值序列。"""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    mdd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        mdd = min(mdd, (v - peak) / peak * 100 if peak > 0 else 0)
    return round(mdd, 2)


def sharpe(returns: list[float]) -> float:
    """简化夏普(收益/波动, 5 日窗口)。"""
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var) if var > 0 else 0.0
    return round(mean / std, 2) if std > 0 else 0.0


def confidence_interval(wins: int, n: int) -> list[float]:
    """二项分布 95% 置信区间 %(胜率)。样本<12 标记不足(与改造1一致)。"""
    if n == 0:
        return [0.0, 0.0]
    p = wins / n
    se = math.sqrt(p * (1 - p) / n)
    return [round(max(0, (p - 1.96 * se)) * 100, 1), round(min(100, (p + 1.96 * se)) * 100, 1)]
