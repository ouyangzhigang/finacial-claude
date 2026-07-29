"""质量因子(用 financial.roe 为主)。

higher_is_better=True(高 ROE 好)。ROE 缺失返回 None。
毛利率/负债率/商誉由 fundamentals agent 雷(hard_gate G1), 因子库取 ROE 为主质量指标。
"""
from __future__ import annotations

from typing import Optional

from core.factors.base import Factor
from core.providers.base import Bar, Financial, Quote


class Quality(Factor):
    name = "quality"
    lookback = 0                      # 用财务, 不依赖 K 线
    higher_is_better = True

    def compute(self, bars, as_of, quote=None, financial=None):
        if financial is None or financial.roe is None:
            return None
        return round(financial.roe, 2)
