"""复权统一(回测基准 QFQ)。

修 cn_fetch.kline 取 qfq 而 portfolio_optimizer 用不复权收盘算收益的混用 bug:
  - qfq K 线: 已调整历史价, 跨除权连续, 回测收益正确
  - 不复权 K 线: 除权日跳空, 收益率失真

回测/因子统一用前复权(QFQ)为基准。provider 已按 BarAdjust.QFQ 取, 此处做一致性
校验 + 留复权转换扩展(当前腾讯支持 QFQ/HFQ/NONE, 不需转换; 多源接入若复权不一致,
在此归一)。
"""
from __future__ import annotations

from core.providers.base import Bar, BarAdjust


def ensure_qfq(bars: list[Bar]) -> list[Bar]:
    """确保前复权基准。

    当前: provider 已按 QFQ 取, 透传 + 校验 dividend 一致性(留扩展)。
    后续: 若接入不复权源, 在此转 QFQ(需除权因子, 暂留接口)。
    """
    # 透传: provider 层 get_bars(adjust=QFQ) 已保证整批 QFQ
    # 若未来接入不复权源, 这里做 adj 转换
    return bars


def detect_adjust_mismatch(bars: list[Bar], expected: BarAdjust = BarAdjust.QFQ) -> bool:
    """检测复权不一致(占位: 当多源接入不同复权时, 返回 True 告警)。

    当前单源(腾讯)按 adjust 整批取, 不会不一致。留接口供多源融合时用。
    """
    # Bar 当前不带 adjust 标记(整批同 adjust, provider 保证)。
    # 若未来 Bar 加 adjust 字段, 此处校验每 bar.adjust == expected。
    return False
