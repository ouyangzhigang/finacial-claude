"""core/timeseries — 时序处理层(防穿越核心)。

align         多源 date-key join(修 portfolio_optimizer 索引对齐 bug: 停牌错位)
adjust        复权统一(回测基准 QFQ; 修 cn_fetch qfq vs portfolio_optimizer 不复权混用)
point_in_time is_closed 守卫执行层 + 切片 + 防穿越断言

软防穿越策略: 盘中 K(is_closed=False)可看(实时观察), 回测/因子拒绝(用 filter_closed)。
"""
from core.timeseries.align import align_by_date, forward_fill
from core.timeseries.adjust import ensure_qfq
from core.timeseries.point_in_time import (
    LookaheadError,
    assert_no_lookahead,
    filter_closed,
    latest_closed,
    slice_until,
)

__all__ = [
    "LookaheadError",
    "align_by_date",
    "assert_no_lookahead",
    "ensure_qfq",
    "filter_closed",
    "forward_fill",
    "latest_closed",
    "slice_until",
]
