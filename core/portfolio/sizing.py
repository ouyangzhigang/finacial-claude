"""仓位分配(等权起步 + regime 仓位上限 + 约束)。

迁自 portfolio_optimizer 的约束逻辑, 简化为等权(决策3: 等权起步简单可复现)。
"""
from __future__ import annotations

REGIME_CAP = {
    "trending": 0.8,
    "ranging": 0.6,
    "shock": 0.4,
    "style_rotation": 0.6,
    "high_volatility": 0.5,
}


def equal_weight(
    stocks: list[dict],
    account: float,
    regime: str = "ranging",
    max_single: float = 0.25,
    min_cash: float = 0.25,
) -> tuple[list[dict], float]:
    """等权 + 仓位上限(regime)+ 单票 ≤ max_single + 留 min_cash 现金。

    stocks: [{code, name, price, score, ...}]
    返回 (positions, cash_pct)
    """
    cap = REGIME_CAP.get(regime, 0.6)
    budget = account * cap
    n = len(stocks)
    if n == 0:
        return [], 100.0
    per = min(budget / n, account * max_single)
    positions, invested = [], 0.0
    for s in stocks:
        if invested + per > account * (1 - min_cash):
            break
        positions.append(
            {**s, "amount": round(per, 2), "pct": round(per / account * 100, 1)}
        )
        invested += per
    return positions, round((account - invested) / account * 100, 1)
