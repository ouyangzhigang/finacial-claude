"""A股交易成本(当前完全缺失, v2 补)。

旧 portfolio_optimizer 零成本算收益, 高估。现补全:
  佣金: 万 2.5 双向(券商最低)
  印花税: 卖出千 1
  沪股过户费: 万 0.1
  滑点: 10 bp(固定, 保守)
"""
from __future__ import annotations

COMMISSION_RATE = 0.00025   # 万 2.5, 双向
STAMP_DUTY_RATE = 0.001    # 卖出, 千 1
TRANSFER_FEE_SH = 0.00001  # 沪, 万 0.1
SLIPPAGE_BP = 10           # 滑点, 基点


def trade_cost(buy_amount: float, sell_amount: float, is_sh: bool = False) -> float:
    """一轮买卖的总成本(元)。"""
    comm = (buy_amount + sell_amount) * COMMISSION_RATE
    stamp = sell_amount * STAMP_DUTY_RATE
    transfer = (buy_amount + sell_amount) * TRANSFER_FEE_SH if is_sh else 0.0
    slip = (buy_amount + sell_amount) * SLIPPAGE_BP / 10000
    return round(comm + stamp + transfer + slip, 4)


def net_return_pct(gross_ret_pct: float, is_sh: bool = False) -> float:
    """毛收益%→扣成本净收益%(一轮买卖, 买入 amount=1, 卖出 1*(1+ret))。"""
    buy = 1.0
    sell = 1.0 * (1 + gross_ret_pct / 100)
    cost = trade_cost(buy, sell, is_sh)
    return round((sell - buy - cost) / buy * 100, 2)
