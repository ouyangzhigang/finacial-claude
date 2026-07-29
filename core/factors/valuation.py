"""估值因子(用 quote.pe_ttm)。

higher_is_better=False(低 PE 好)。亏损(PE<=0)返回 None(不参与排序, 不误判)。
历史分位待 storage/parquet 层建后补(当前用绝对值, engine z-score 横截面标准化)。
"""
from __future__ import annotations

from typing import Optional

from core.factors.base import Factor
from core.providers.base import Bar, Financial, Quote


class Valuation(Factor):
    name = "valuation"
    lookback = 0                      # 不依赖 K 线, 用快照
    higher_is_better = False          # 低 PE 好(z-score 后 engine 反向)

    def compute(self, bars, as_of, quote=None, financial=None):
        if quote is None or quote.pe_ttm is None:
            return None
        pe = quote.pe_ttm
        if pe <= 0:                   # 亏损/负 PE, 不参与排序
            return None
        return round(pe, 2)
