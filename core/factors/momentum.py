"""动量因子族(迁自 cn_fetch.factors 的 m5/m10/m20)。

5/10/20 日动量, higher_is_better=True(涨好)。
"""
from __future__ import annotations

from typing import Optional

from core.factors.base import Factor
from core.providers.base import Bar, Financial, Quote


class Momentum5D(Factor):
    name = "momentum_5d"
    lookback = 6
    higher_is_better = True

    def compute(self, bars, as_of, quote=None, financial=None):
        if len(bars) < 6:
            return None
        return round((bars[-1].close - bars[-6].close) / bars[-6].close * 100, 2)


class Momentum10D(Factor):
    name = "momentum_10d"
    lookback = 11
    higher_is_better = True

    def compute(self, bars, as_of, quote=None, financial=None):
        if len(bars) < 11:
            return None
        return round((bars[-1].close - bars[-11].close) / bars[-11].close * 100, 2)


class Momentum20D(Factor):
    name = "momentum_20d"
    lookback = 21
    higher_is_better = True

    def compute(self, bars, as_of, quote=None, financial=None):
        if len(bars) < 21:
            return None
        return round((bars[-1].close - bars[-21].close) / bars[-21].close * 100, 2)
