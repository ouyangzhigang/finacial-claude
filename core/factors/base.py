"""因子抽象基类 + 数据模型。

防穿越核心(决策A): compute 是纯函数, 不碰 provider。
engine 注入已 slice_until(as_of) + filter_closed 的 bars + 可选 quote/financial,
因子拿不到未来数据。

6 族因子按数据依赖分:
  纯K线:  momentum / liquidity / reversal / volatility
  行情快照: valuation(需 quote.pe_ttm)
  财务:    quality(需 financial.roe 等)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from core.providers.base import Bar, Financial, Quote


@dataclass
class FactorValue:
    """单次因子计算结果(含元数据, 供调试/报告)。"""

    symbol: str
    date: str
    value: Optional[float]            # None = 数据不足, 不编造
    lookback: int
    is_valid: bool = True             # False = 该因子对这只票失效


class Factor(ABC):
    """量化因子基类。纯函数, 不触碰 provider(防穿越)。"""

    name: str = "base"
    lookback: int = 20                # 声明的历史 Bar 依赖
    higher_is_better: bool = True     # 排序方向(engine z-score 后按此反向)

    @abstractmethod
    def compute(
        self,
        bars: list[Bar],
        as_of: str,
        quote: Optional[Quote] = None,
        financial: Optional[Financial] = None,
    ) -> Optional[float]:
        """计算因子原始值(engine 负责 z-score 标准化)。

        Args:
            bars: engine 已切片(date<=as_of)+过滤(仅收盘)的 K 线
            as_of: 计算日 YYYY-MM-DD
            quote: 该标的实时快照(估值因子用)
            financial: 该标的财务(质量因子用)

        Returns:
            float: 因子原始值
            None: 数据不足(lookback 不够/字段缺失), 不编造, 不参与排序
        """
