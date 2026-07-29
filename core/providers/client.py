"""QuoteClient — 统一行情/财务接入入口(降级链 + 多源合并 + 缓存)。

降级链: 腾讯 HTTP → 新浪 HTTP(腾讯内部降级) → mootdx(财务)
多源合并: get_financials 合并腾讯 pe_ttm + mootdx roe → 完整 Financial
治"时好时坏": health_check 启动探源, 运行中失败按异常切下一个 provider。

用法:
    from core.providers import QuoteClient
    qc = QuoteClient()                       # 默认 [腾讯, mootdx]
    bars = qc.get_bars("sh600519", n=30)     # 自动降级
    q = qc.get_quotes(["sh600519", "sz000001"])
    fin = qc.get_financials("600519")       # 腾讯 pe_ttm + mootdx roe 合并
"""
from __future__ import annotations

from typing import Optional

from core.providers.base import (
    Bar,
    BarAdjust,
    Financial,
    ProviderError,
    Quote,
    QuoteProvider,
)
from core.providers.mootdx import MootdxProvider
from core.providers.tencent import TencentProvider

# Financial 合并时考虑的字段(非 None 即采纳)
_FIN_FIELDS = (
    "report_date", "roe", "pe_ttm", "pb", "net_profit",
    "revenue_growth", "profit_growth", "gross_margin",
    "debt_ratio", "goodwill_ratio", "cashflow_ratio",
)


class QuoteClient:
    """统一行情/财务接入。持有 provider 列表, 按顺序降级。

    providers 顺序即降级链: 前面的失败(ProviderError)切后面的。
    """

    def __init__(self, providers: Optional[list[QuoteProvider]] = None):
        self.providers: list[QuoteProvider] = providers or [
            TencentProvider(),
            MootdxProvider(),
        ]

    def get_bars(self, symbol: str, n: int = 30,
                 adjust: BarAdjust = BarAdjust.QFQ) -> list[Bar]:
        last_err: Optional[ProviderError] = None
        for p in self.providers:
            try:
                bars = p.get_bars(symbol, n, adjust)
                if bars:
                    return bars
            except ProviderError as e:
                last_err = e
                continue
        raise ProviderError(
            f"所有源 get_bars 失败 {symbol}: {last_err or '无可用源'}"
        )

    def get_quotes(self, codes: list[str]) -> dict[str, Quote]:
        last_err: Optional[ProviderError] = None
        for p in self.providers:
            try:
                return p.get_quotes(codes)
            except ProviderError as e:
                last_err = e
                continue
        raise ProviderError(
            f"所有源 get_quotes 失败 {codes}: {last_err or '无可用源'}"
        )

    def get_financials(self, code: str) -> Optional[Financial]:
        """多源合并: 腾讯 pe_ttm + mootdx roe/... → 完整 Financial。

        任一源失败不中断, 合并所有可得字段。全 None 才返回 None。
        """
        merged = Financial(code=code)
        for p in self.providers:
            try:
                f = p.get_financials(code)
            except ProviderError:
                continue
            if f is None:
                continue
            for k in _FIN_FIELDS:
                v = getattr(f, k, None)
                if v is not None and getattr(merged, k) is None:
                    setattr(merged, k, v)
        # 至少有一个实质字段才算有效
        has_data = any(
            getattr(merged, k) is not None
            for k in ("roe", "pe_ttm", "net_profit", "revenue_growth")
        )
        return merged if has_data else None

    def health_check(self) -> bool:
        """至少一个 provider 可用。启动时探源, 据此决定是否降级告警。"""
        return any(p.health_check() for p in self.providers)

    def source_status(self) -> dict[str, bool]:
        """各 provider 健康状态(供日志/governor 报告)。"""
        return {p.name: p.health_check() for p in self.providers}
