"""point-in-time 守卫执行层 + 切片 + 防穿越断言。

软防穿越策略(确认): 盘中 K(is_closed=False)可看(实时观察), 回测/因子拒绝。
  - filter_closed: 回测/因子引擎必须先过滤, 拒未收盘 K
  - slice_until: 回测按 as_of 切片, 只用历史(date <= as_of)
  - assert_no_lookahead: 断言无未来数据(数据源含未来 K → 抛)

这是治痛点6"数据穿越风险"的代码层闸门, 比 prompt 纪律强。
"""
from __future__ import annotations

from typing import Optional

from core.providers.base import Bar


class LookaheadError(Exception):
    """数据穿越: 发现 as_of 之后的 K 线(未来信息)。"""


def filter_closed(bars: list[Bar]) -> list[Bar]:
    """仅收盘 K(回测/因子用, 拒绝盘中未收盘)。

    盘中末根 is_closed=False → 滤除, 防用未完成 K 的 close 算动量(= 用未来信息)。
    """
    return [b for b in bars if b.is_closed]


def latest_closed(bars: list[Bar]) -> Optional[Bar]:
    """最近一根收盘 K(实时观察可用, 但回测入场用此)。"""
    closed = filter_closed(bars)
    return closed[-1] if closed else None


def slice_until(bars: list[Bar], as_of: str) -> list[Bar]:
    """回测切片: 仅 date <= as_of 的 K(只用历史, 防穿越)。

    配合 filter_closed: 回测应 slice_until(as_of) 后再 filter_closed。
    """
    return [b for b in bars if b.date <= as_of]


def assert_no_lookahead(bars: list[Bar], as_of: str) -> None:
    """断言 bars 无 as_of 之后的数据。回测/因子引擎切片后调用, 防穿越。"""
    future = [b for b in bars if b.date > as_of]
    if future:
        raise LookaheadError(
            f"数据穿越: 发现 {len(future)} 根 {as_of} 之后的 K 线"
            f"(首根 {future[0].date}), 回测/因子不得使用"
        )
