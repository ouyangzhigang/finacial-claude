"""timeseries 层测试 — 防穿越/对齐/复权(不依赖网络, 用假 Bar)。

覆盖:
1. align_by_date 停牌日 None(不借位) — 修索引对齐 bug 的核心
2. forward_fill 前向填充(无穿越: 用历史收盘)
3. filter_closed 拒绝盘中未收盘 K(软防穿越)
4. slice_until 仅历史(date <= as_of)
5. assert_no_lookahead 未来 K 抛 LookaheadError
6. latest_closed 取最近收盘(跳过盘中末根)
"""
import pytest

from core.providers.base import Bar
from core.timeseries import (
    LookaheadError,
    align_by_date,
    assert_no_lookahead,
    ensure_qfq,
    filter_closed,
    forward_fill,
    latest_closed,
    slice_until,
)


def _bar(date: str, close: float, is_closed: bool = True) -> Bar:
    return Bar(date=date, open=close, close=close, high=close, low=close, is_closed=is_closed)


# ─────────── align ───────────


def test_align_by_date_suspension_is_none():
    """停牌日该票 None(不借位), 修索引对齐 bug"""
    bars_a = [_bar("2026-07-01", 10), _bar("2026-07-02", 11), _bar("2026-07-03", 12)]
    bars_b = [_bar("2026-07-01", 20), _bar("2026-07-03", 22)]  # B 停牌 07-02
    aligned = align_by_date({"A": bars_a, "B": bars_b})

    dates = [d for d, _ in aligned]
    assert dates == ["2026-07-01", "2026-07-02", "2026-07-03"]
    d2 = dict((d, sb) for d, sb in aligned)["2026-07-02"]
    assert d2["A"] is not None and d2["A"].close == 11
    assert d2["B"] is None  # 停牌, 不借位


def test_forward_fill_no_lookahead():
    """前向填充用历史收盘, 无穿越"""
    bars_a = [_bar("2026-07-01", 10), _bar("2026-07-02", 11), _bar("2026-07-03", 12)]
    bars_b = [_bar("2026-07-01", 20), _bar("2026-07-03", 22)]
    aligned = align_by_date({"A": bars_a, "B": bars_b})
    filled = forward_fill(aligned, ["A", "B"])
    d2 = dict((d, sb) for d, sb in filled)["2026-07-02"]
    assert d2["B"] is not None and d2["B"].close == 20  # 填前收盘(07-01)


def test_forward_fill_first_day_none():
    """首日该 symbol 无历史 → 仍 None(不编造)"""
    bars_a = [_bar("2026-07-02", 10)]  # A 07-02 才上市
    bars_b = [_bar("2026-07-01", 20)]
    aligned = align_by_date({"A": bars_a, "B": bars_b})
    filled = forward_fill(aligned, ["A", "B"])
    d1 = dict((d, sb) for d, sb in filled)["2026-07-01"]
    assert d1["A"] is None  # 无历史, 不编造


# ─────────── point_in_time ───────────


def test_filter_closed_rejects_intraday():
    """盘中未收盘 K 被滤(软防穿越: 盘中可看, 回测不用)"""
    bars = [
        _bar("2026-07-01", 10, is_closed=True),
        _bar("2026-07-02", 11, is_closed=True),
        _bar("2026-07-03", 12, is_closed=False),  # 盘中末根
    ]
    closed = filter_closed(bars)
    assert len(closed) == 2
    assert closed[-1].date == "2026-07-02"  # 跳过盘中末根


def test_latest_closed_skips_intraday():
    """最近收盘 K 跳过盘中末根"""
    bars = [_bar("2026-07-01", 10, True), _bar("2026-07-02", 11, False)]
    latest = latest_closed(bars)
    assert latest is not None and latest.date == "2026-07-01"


def test_slice_until_only_history():
    """回测切片: 仅 date <= as_of(只用历史)"""
    bars = [_bar("2026-07-01", 10), _bar("2026-07-02", 11), _bar("2026-07-03", 12)]
    sliced = slice_until(bars, "2026-07-02")
    assert len(sliced) == 2 and sliced[-1].date == "2026-07-02"


def test_assert_no_lookahead_raises():
    """未来 K 触发 LookaheadError(防穿越闸门)"""
    bars = [_bar("2026-07-01", 10), _bar("2026-07-03", 12)]
    with pytest.raises(LookaheadError):
        assert_no_lookahead(bars, as_of="2026-07-02")


def test_assert_no_lookahead_ok():
    """无未来数据不抛"""
    bars = [_bar("2026-07-01", 10), _bar("2026-07-02", 11)]
    assert_no_lookahead(bars, as_of="2026-07-02")  # 不抛


# ─────────── adjust ───────────


def test_ensure_qfq_passthrough():
    """ensure_qfq 透传(provider 已按 QFQ 取)"""
    bars = [_bar("2026-07-01", 10)]
    assert ensure_qfq(bars) is bars
