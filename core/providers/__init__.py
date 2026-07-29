"""core/providers — 数据接入层。

统一 QuoteProvider 抽象, 多源可替换:
    腾讯 HTTP (主通道, 行情/K线/PE/PB)
    通达信 TCP 7709 (财务兜底)
    akshare / MCP (可选, 修复后插入)

治"数据源时好时坏":
    每个 provider 实现 health_check(), QuoteClient 降级链据此切源;
    空值统一 None(不用 0, 防 PE=0 误判低估);
    Bar 带 is_closed 守卫(盘中 K 线不得进回测, 防穿越)。
"""
from core.providers.base import (
    Bar,
    BarAdjust,
    Financial,
    ProviderError,
    Quote,
    QuoteProvider,
)
from core.providers.client import QuoteClient
from core.providers.mootdx import MootdxProvider
from core.providers.tencent import TencentProvider

__all__ = [
    "Bar",
    "BarAdjust",
    "Financial",
    "MootdxProvider",
    "ProviderError",
    "Quote",
    "QuoteClient",
    "QuoteProvider",
    "TencentProvider",
]
