"""多源时序对齐(修索引对齐 bug)。

旧 bug(portfolio_optimizer:121): `idx_offset = len(index_closes) - n`
假设股票与指数末端对齐, 用索引偏移取环境窗口。一旦股票停牌(n 比 index 少),
idx_offset 假成立但中间停牌日错位 —— entry_price 与 env 对应的不是同一交易日。

修法: 按 date-key join, 停牌日该票 None(不借位)。回测取窗口时显式处理 None
(跳过或前向填充明确标记)。
"""
from __future__ import annotations

from typing import Optional

from core.providers.base import Bar


def align_by_date(
    symbol_bars: dict[str, list[Bar]],
) -> list[tuple[str, dict[str, Optional[Bar]]]]:
    """多只票按 date 对齐(停牌日 None, 不借位)。

    Args:
        symbol_bars: {symbol: [Bar, ...]}, 每只票的 K 线(可能日期不齐/停牌)

    Returns:
        [(date, {symbol: Bar or None})], 日期升序。
        停牌日该 symbol 为 None, 调用方须显式处理(不静默借位)。
    """
    if not symbol_bars:
        return []
    all_dates = sorted({b.date for bars in symbol_bars.values() for b in bars})
    by_sd = {sym: {b.date: b for b in bars} for sym, bars in symbol_bars.items()}
    return [
        (d, {sym: by_sd[sym].get(d) for sym in symbol_bars})
        for d in all_dates
    ]


def forward_fill(
    aligned: list[tuple[str, dict[str, Optional[Bar]]]],
    symbols: list[str],
) -> list[tuple[str, dict[str, Optional[Bar]]]]:
    """停牌日用前一根收盘 K 前向填充(回测常用: 停牌价=前收盘)。

    填充的 Bar 是前值的引用(只读使用)。首日仍可能 None(该 symbol 无历史)。

    注意: 前向填充的是历史收盘, 不引入未来信息, 无穿越。
    """
    last: dict[str, Optional[Bar]] = {s: None for s in symbols}
    out: list[tuple[str, dict[str, Optional[Bar]]]] = []
    for d, sb in aligned:
        new_sb: dict[str, Optional[Bar]] = {}
        for s in symbols:
            cur = sb.get(s)
            if cur is not None:
                last[s] = cur
                new_sb[s] = cur
            else:
                new_sb[s] = last[s]  # 前向填充(可能仍 None)
        out.append((d, new_sb))
    return out
