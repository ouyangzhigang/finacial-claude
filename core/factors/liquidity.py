"""流动性因子(迁自 cn_fetch.factors 的 amt20)。

20 日均成交额(亿), higher_is_better=True(流动好)。
从 K 线 vol(手)×100×close 估算成交额(与 cn_fetch line 75 一致)。
"""
from __future__ import annotations

from typing import Optional

from core.factors.base import Factor
from core.providers.base import Bar, Financial, Quote


class Liquidity(Factor):
    name = "liquidity"
    lookback = 21
    higher_is_better = True

    def compute(self, bars, as_of, quote=None, financial=None):
        if len(bars) < 20:
            return None
        recent = bars[-20:]
        # vol(手)×100=股 × close=元, 取 20 日均, 转亿
        amt_yi = sum(b.vol * 100 * b.close for b in recent) / 20 / 1e8
        return round(amt_yi, 2)
