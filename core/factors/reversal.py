"""反转因子(短期反转, 5 日)。

higher_is_better=False(近 5 日跌的票反弹概率高, 反转分高)。
与 momentum_5d 方向相反, IC 加权会选哪个在当前市场有效。
"""
from __future__ import annotations

from typing import Optional

from core.factors.base import Factor
from core.providers.base import Bar, Financial, Quote


class Reversal(Factor):
    name = "reversal"
    lookback = 6
    higher_is_better = False          # 跌的票反转分高(z-score 后 engine 反向)

    def compute(self, bars, as_of, quote=None, financial=None):
        if len(bars) < 6:
            return None
        return round((bars[-1].close - bars[-6].close) / bars[-6].close * 100, 2)
