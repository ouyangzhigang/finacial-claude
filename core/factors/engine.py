"""因子组合引擎(z-score + IC/IR 加权 + regime 调整)。

流程(防穿越):
1. 按 as_of 切片 + filter_closed(因子拿不到未来)
2. 并行算各因子(纯函数, 注入 quote/financial)
3. z-score 横截面标准化
4. higher_is_better=False 的因子 z 反向(统一高分=好)
5. IC/IR 加权(registry.weights())
6. regime 调整(trending 加权动量, ranging 加权估值/质量)
"""
from __future__ import annotations

import math
from typing import Optional

from core.factors.base import Factor
from core.factors.registry import FactorRegistry
from core.providers.base import Bar, Financial, Quote
from core.timeseries import filter_closed, slice_until


def zscore(values: list[Optional[float]]) -> list[float]:
    """横截面 z-score。None 不参与统计, 填 0(中性)。"""
    valid = [v for v in values if v is not None]
    if len(valid) < 2:
        return [0.0] * len(values)
    mean = sum(valid) / len(valid)
    var = sum((v - mean) ** 2 for v in valid) / (len(valid) - 1)
    std = math.sqrt(var) if var > 0 else 1.0
    return [(v - mean) / std if v is not None else 0.0 for v in values]


class FactorEngine:
    """因子组合引擎。注入 FactorRegistry(含 IC/IR 权重)。"""

    REGIME_ADJ = {
        "trending": {"momentum_5d": 1.5, "momentum_10d": 1.3, "momentum_20d": 1.3,
                     "valuation": 0.7, "quality": 0.8, "reversal": 0.5, "volatility": 0.8},
        "ranging":  {"momentum_5d": 0.7, "momentum_10d": 0.7, "momentum_20d": 0.7,
                     "valuation": 1.5, "quality": 1.3, "reversal": 1.3, "volatility": 1.0},
        "shock":    {"momentum_5d": 0.3, "momentum_10d": 0.3, "momentum_20d": 0.3,
                     "valuation": 1.5, "quality": 1.8, "reversal": 1.5, "volatility": 1.3},
    }

    def __init__(self, registry: FactorRegistry, regime: str = "ranging"):
        self.registry = registry
        self.regime = regime

    def compute_scores(
        self,
        bars_by_symbol: dict[str, list[Bar]],
        as_of: str,
        quotes: Optional[dict[str, Quote]] = None,
        financials: Optional[dict[str, Financial]] = None,
    ) -> dict[str, dict]:
        """计算所有标的综合因子分。

        Args:
            bars_by_symbol: {symbol: [Bar]}(未切片, engine 内部 slice_until+filter_closed)
            as_of: 计算日
            quotes: {symbol: Quote}(估值因子用, 可选)
            financials: {symbol: Financial}(质量因子用, 可选)

        Returns:
            {symbol: {factor_name: z_score_contribution, composite, rank}}
        """
        factor_names = list(self.registry.factors.keys())
        quotes = quotes or {}
        financials = financials or {}

        # 1. 切片 + 过滤 + 算各因子原始值
        raw: dict[str, dict[str, Optional[float]]] = {}
        for sym, bars in bars_by_symbol.items():
            sliced = slice_until(bars, as_of)
            closed = filter_closed(sliced)
            q = quotes.get(sym)
            f = financials.get(sym)
            raw[sym] = {
                fn: self.registry.factors[fn].compute(closed, as_of, q, f)
                for fn in factor_names
            }

        # 2. z-score 横截面 + higher_is_better 反向
        z_by_factor: dict[str, list[float]] = {}
        for fn in factor_names:
            col = [raw[sym][fn] for sym in raw]
            z = zscore(col)
            if not self.registry.factors[fn].higher_is_better:
                z = [-x for x in z]  # 反向: 统一高分=好
            z_by_factor[fn] = z

        # 3. IC/IR 加权 + regime 调整
        weights = self.registry.weights()
        regime_adj = self.REGIME_ADJ.get(self.regime, {})

        scores = []
        for i, sym in enumerate(raw):
            composite = 0.0
            dim_scores: dict[str, float] = {}
            for fn in factor_names:
                z = z_by_factor[fn][i]
                w = weights.get(fn, 0.0)
                ra = regime_adj.get(fn, 1.0)
                contrib = round(z * w * ra * 100, 2)
                dim_scores[fn] = contrib
                composite += contrib
            scores.append((sym, composite, dim_scores))

        # 4. 排序
        scores.sort(key=lambda x: x[1], reverse=True)
        return {
            sym: {"composite_score": round(cs, 2), "rank": i + 1, "dim_scores": ds}
            for i, (sym, cs, ds) in enumerate(scores)
        }
