"""通达信 mootdx 财务 Provider(TCP 7709, 不经 HTTP 代理)。

兜底用: MCP 全挂且腾讯报价无 ROE 时, 从通达信财务表取 roe/净利润/营收增速等。
迁自 scripts/factor_engine.py 2f 块已验证的 mootdx 列索引(20260728 run 验证)。
行情方法 get_bars/get_quotes 不支持(raise), 仅财务。
"""
from __future__ import annotations

from typing import Optional

from core._compat import cached_http
from core.providers.base import (
    Bar,
    BarAdjust,
    Financial,
    ProviderError,
    Quote,
    QuoteProvider,
)

# mootdx gpcw 财务表列索引(与 factor_engine 2f 块一致, 20260728 验证)
_COLS = {
    "roe": 6,
    "goodwill": 35,
    "total_equity": 72,
    "net_profit": 95,
    "revenue_growth": 183,
    "profit_growth": 184,
    "gross_margin": 202,
    "debt_ratio": 210,
}

# 尝试的财报文件(最新在前, 年报最全; 失败回退)
_GPCW_FILES = ["gpcw20251231.zip", "gpcw20250930.zip", "gpcw20250630.zip"]


@cached_http(maxsize=4, ttl=3600)
def _load_gpcw(filename: str = "") -> dict[str, dict]:
    """下载+解析 mootdx gpcw 财务表, 返回 {code: {field: val}}。

    进程内缓存(cached_http LRU); 跨进程后续由 storage/parquet 解决。
    """
    try:
        from mootdx.affair import Affair
    except ImportError as e:
        raise ProviderError(f"mootdx 未安装: {e}")

    a = Affair()
    df = None
    files = [filename] if filename else _GPCW_FILES
    for fn in files:
        if not fn:
            continue
        try:
            df = a.parse(filename=fn)
            if df is not None and len(df) > 0:
                break
        except Exception:
            continue
    if df is None or len(df) == 0:
        raise ProviderError("mootdx gpcw 财务表不可用(下载/解析失败)")

    out: dict[str, dict] = {}
    ncol = len(df.columns)
    for code, row in df.iterrows():
        d: dict = {}
        for field, idx in _COLS.items():
            if idx >= ncol:
                d[field] = None
                continue
            v = row.iloc[idx]
            try:
                fv = float(v)
                d[field] = fv if fv == fv else None  # NaN→None
            except (ValueError, TypeError):
                d[field] = None
        # 商誉占净资产比
        gw = d.get("goodwill")
        eq = d.get("total_equity")
        d["goodwill_ratio"] = (gw / eq * 100) if (gw and eq and eq > 0) else None
        out[str(code).zfill(6)] = d
    return out


class MootdxProvider(QuoteProvider):
    """通达信 TCP 财务兜底。不支持行情(仅财务)。"""

    name = "mootdx"

    def get_bars(self, symbol: str, n: int = 30,
                 adjust: BarAdjust = BarAdjust.QFQ) -> list[Bar]:
        raise ProviderError("mootdx 不支持行情 K 线, 仅财务")

    def get_quotes(self, codes: list[str]) -> dict[str, Quote]:
        raise ProviderError("mootdx 不支持实时报价, 仅财务")

    def get_financials(self, code: str) -> Optional[Financial]:
        code = code.replace("sh", "").replace("sz", "").zfill(6)
        try:
            g = _load_gpcw()
        except ProviderError:
            return None
        d = g.get(code)
        if not d:
            return None
        return Financial(
            code=code,
            report_date="2025-12-31",
            roe=d.get("roe"),
            net_profit=d.get("net_profit"),
            revenue_growth=d.get("revenue_growth"),
            profit_growth=d.get("profit_growth"),
            gross_margin=d.get("gross_margin"),
            debt_ratio=d.get("debt_ratio"),
            goodwill_ratio=d.get("goodwill_ratio"),
        )

    def health_check(self) -> bool:
        """轻量: 仅检查 mootdx 可 import(不下载, 避免慢)。"""
        try:
            import mootdx.affair  # noqa: F401
            return True
        except ImportError:
            return False
