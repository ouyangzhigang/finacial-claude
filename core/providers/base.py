"""QuoteProvider 抽象基类 + 数据模型。

设计原则:
1. 字段空值统一用 None, 不用 0 —— PE=0 会被选股误判为"无估值压力/低估"(教训:
   cn_fetch.quote 早期填 0 导致选股 GIGO, 后已改 None, 此处固化)。
2. Bar 带 is_closed —— 盘中最后一根 K 线 is_closed=False, 回测/因子计算须拒绝
   未收盘 K(防数据穿越: 用未完成 K 的 close 算动量 = 用未来信息)。
3. 复权统一 QFQ(前复权) 为回测基准 —— 修 cn_fetch 取 qfq 而 portfolio_optimizer
   用不复权收盘算收益的混用 bug。
4. provider 必须实现 health_check() —— QuoteClient 降级链据此切源,
   不再"时好时坏"地静默吞。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class BarAdjust(str, Enum):
    """复权方式。回测统一用 QFQ(前复权)为基准。"""

    QFQ = "qfq"    # 前复权(默认, 回测基准)
    HFQ = "hfq"    # 后复权
    NONE = "none"  # 不复权


class ProviderError(Exception):
    """数据接入失败(网络/解析/源不可达)。QuoteClient 据此切下一个 provider。"""


@dataclass
class Bar:
    """单根 K 线。

    空值字段用 None; 成交量/额默认 0(无交易的票 0 是真实值)。
    is_closed=False 的 Bar 不得进回测(防穿越)。
    """

    date: str                         # YYYY-MM-DD
    open: float
    close: float
    high: float
    low: float
    vol: float = 0.0                  # 成交量(手)
    amount: Optional[float] = None    # 成交额(元)
    is_closed: bool = True            # 是否收盘 K(盘中末根=False)
    dividend: Optional[dict] = None   # 除权除息信息(腾讯 K 线附带)

    @property
    def amount_yi(self) -> Optional[float]:
        """成交额(亿元)。"""
        return round(self.amount / 1e8, 2) if self.amount is not None else None


@dataclass
class Quote:
    """实时报价快照。字段空值 None, 不填 0(防误判)。"""

    code: str
    name: Optional[str] = None
    price: Optional[float] = None
    prev_close: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    vol: Optional[float] = None             # 成交量(手)
    amount: Optional[float] = None           # 成交额(元)
    pct: Optional[float] = None              # 涨跌幅 %
    turnover: Optional[float] = None         # 换手率 %
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    mktcap_yi: Optional[float] = None        # 总市值(亿)
    float_mktcap_yi: Optional[float] = None  # 流通市值(亿)
    time: Optional[str] = None


@dataclass
class Financial:
    """单只票、单报告期财务基本面(兜底用; 主力走 fundamentals agent)。

    所有字段 None 表示缺失。不编造。
    """

    code: str
    report_date: Optional[str] = None       # YYYY-MM-DD
    report_type: Optional[str] = None       # 年报/季报
    roe: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    net_profit: Optional[float] = None       # 净利润(亿)
    revenue_growth: Optional[float] = None   # 营收增速 %
    profit_growth: Optional[float] = None    # 利润增速 %
    gross_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    goodwill_ratio: Optional[float] = None
    cashflow_ratio: Optional[float] = None


class QuoteProvider(ABC):
    """行情/财务接入抽象。多源可替换(腾讯/通达信/akshare/MCP)。

    实现方只需填 4 个方法 + name 属性; 缓存/降级由 QuoteClient 负责。
    """

    name: str = "base"

    @abstractmethod
    def get_bars(
        self, symbol: str, n: int = 30, adjust: BarAdjust = BarAdjust.QFQ
    ) -> list[Bar]:
        """取日 K 线。symbol 带交易所前缀(sh/sz)。

        末根 K 线若为今日且盘中, 须置 is_closed=False(防穿越)。
        """

    @abstractmethod
    def get_quotes(self, codes: list[str]) -> dict[str, Quote]:
        """批量实时报价。codes 带交易所前缀。返回 {code: Quote}。

        源不可达抛 ProviderError; 部分标的解析失败则缺该 key(不填假值)。
        """

    @abstractmethod
    def get_financials(self, code: str) -> Optional[Financial]:
        """财务基本面。code 无前缀(6 位)。主力走 agent, 此为兜底。"""

    @abstractmethod
    def health_check(self) -> bool:
        """源可用性自检(轻量探针, 如取 1 只票报价)。

        QuoteClient 降级链据此切源, 不让"时好时坏"静默吞。
        """
