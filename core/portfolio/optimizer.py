"""组合优化器(等权 + 约束: 单票/行业/催化/手数)。

迁自 portfolio_optimizer.optimize_portfolio, 用 core 数据结构。
1w 账户手数约束(100 股最小) + 行业≤40% + 催化同源≤50%(留接口)。
"""
from __future__ import annotations

from core.portfolio.sizing import equal_weight


def optimize(
    stocks: list[dict],
    account: float,
    regime: str = "ranging",
    max_single: float = 0.25,
    max_sector: float = 0.40,
    max_catalyst: float = 0.50,
    min_lot: int = 100,
) -> dict:
    """等权 + 约束组合构建。

    stocks: [{code, name, price, score, sector?, catalyst_source?}]
    返回 {positions, invested_pct, cash_pct, ...}
    """
    positions, cash_pct = equal_weight(stocks, account, regime, max_single)
    final: list[dict] = []
    invested = 0.0

    # 行业累计(约束: ≤ max_sector)
    sector_used: dict[str, float] = {}

    for p in positions:
        price = p.get("price", 0) or 0
        sector = p.get("sector", "unknown")
        # 手数约束: 买不起 1 手跳过
        if price > 0 and price * min_lot > p["amount"]:
            continue
        # 行业约束: 超限跳过
        if sector_used.get(sector, 0) + p["pct"] / 100 > max_sector:
            continue
        # 算手数(向下取整)
        shares = int(p["amount"] / (price * min_lot)) * min_lot if price > 0 else 0
        if shares <= 0:
            continue
        p["shares"] = shares
        p["amount"] = round(shares * price, 2)
        p["pct"] = round(p["amount"] / account * 100, 1)
        sector_used[sector] = sector_used.get(sector, 0) + p["pct"] / 100
        final.append(p)
        invested += p["amount"]

    return {
        "positions": final,
        "invested": round(invested, 2),
        "invested_pct": round(invested / account * 100, 1),
        "cash": round(account - invested, 2),
        "cash_pct": round((account - invested) / account * 100, 1),
        "stock_count": len(final),
        "regime": regime,
    }
