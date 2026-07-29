"""波动率因子(20 日日收益标准差)。

higher_is_better=False(低波动好, 风控视角)。
"""
from __future__ import annotations

import math
from typing import Optional

from core.factors.base import Factor
from core.providers.base import Bar, Financial, Quote


class Volatility(Factor):
    name = "volatility"
    lookback = 21
    higher_is_better = False          # 低波动好(z-score 后 engine 反向)

    def compute(self, bars, as_of, quote=None, financial=None):
        if len(bars) < 21:
            return None
        recent = bars[-21:]
        returns = [
            (recent[i].close - recent[i - 1].close) / recent[i - 1].close * 100
            for i in range(1, len(recent))
        ]
        if len(returns) < 2:
            return None
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        return round(math.sqrt(var), 2)
