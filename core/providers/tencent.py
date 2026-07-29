"""腾讯 HTTP 行情 Provider(主通道)。

迁自 scripts/cn_fetch.py 的 _get/kline/quote/sina_quote, 影子迁移输出一致。
统一字段命名(以 cn_fetch.quote 为准): pe_ttm / mktcap_yi / float_mktcap_yi。
末根 K 线 is_closed 判断防穿越(盘中 K 不得进回测)。
报价失败降级到新浪 sinajs。
"""
from __future__ import annotations

import datetime
import json
import ssl
import time
import urllib.request
from typing import Optional

from core._compat import disk_cached
from core.providers.base import (
    Bar,
    BarAdjust,
    Financial,
    ProviderError,
    Quote,
    QuoteProvider,
)

_UA = {"User-Agent": "Mozilla/5.0"}
_CTX = ssl._create_unverified_context()  # 腾讯 HTTP 实际不走 SSL, 仅 _get 兜底用


def _get(url: str, encoding: str = "utf-8", timeout: int = 25, retry: int = 3,
         headers: Optional[dict] = None) -> str:
    """HTTP GET + 重试。迁自 cn_fetch._get。"""
    h = dict(_UA)
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    last: Optional[Exception] = None
    for _ in range(retry):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                return r.read().decode(encoding, "ignore")
        except Exception as e:
            last = e
            time.sleep(0.7)
    raise ProviderError(f"GET {url[:60]} 失败: {last}")


def _is_last_bar_closed(last_date_str: str) -> bool:
    """末根 K 线是否收盘。盘中(< 15:00)→ False, 防穿越。"""
    if not last_date_str:
        return True
    today = datetime.date.today().isoformat()
    if last_date_str < today:
        return True  # 历史 K, 已收盘
    if last_date_str == today:
        return datetime.datetime.now().hour >= 15  # 今日: 15:00 后收盘
    return True  # 未来日期不应发生


@disk_cached(ttl=300, suffix=".json")
def _tencent_kline_raw(symbol: str, n: int, adjust_value: str) -> list:
    """取腾讯日 K(原始 list[list])。迁自 cn_fetch.kline, 影子一致。

    返回 [[date, open, close, high, low, vol, ?dividend], ...]
    """
    url = (
        f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
        f"param={symbol},day,,,{n},{adjust_value}"
    )
    j = json.loads(_get(url))
    data = j.get("data")
    if not isinstance(data, dict):
        return []
    sym_data = data.get(symbol)
    if not isinstance(sym_data, dict):
        return []
    arr = sym_data.get("qfqday") if adjust_value == "qfq" else sym_data.get("day", [])
    return arr or []


def _tencent_quote_raw(codes: list[str]) -> dict[str, dict]:
    """腾讯批量报价(原始 dict)。迁自 cn_fetch.quote, 字段统一。"""
    q = ",".join(codes)
    txt = _get(f"http://qt.gtimg.cn/q={q}", encoding="gbk")
    out: dict[str, dict] = {}
    for line in txt.strip().split(";"):
        line = line.strip()
        if not line:
            continue
        m = line.split("~")
        if len(m) < 50:
            continue
        try:
            code = m[2]
            out[code] = {
                "code": code,
                "name": m[1],
                "price": float(m[3]) if m[3] else None,
                "prev_close": float(m[4]) if m[4] else None,
                "open": float(m[5]) if m[5] else None,
                "vol": float(m[6]) if m[6] else None,           # 手
                "pct": float(m[32]) if m[32] else None,          # %
                "high": float(m[33]) if m[33] else None,
                "low": float(m[34]) if m[34] else None,
                "amount": float(m[37]) * 1e4 if m[37] else None,  # 万元→元
                "turnover": float(m[38]) if m[38] else None,      # %
                "pe_ttm": float(m[39]) if m[39] else None,
                "float_mktcap_yi": round(float(m[44]), 2) if m[44] else None,
                "mktcap_yi": round(float(m[45]), 2) if m[45] else None,
                "time": m[30],
            }
        except (ValueError, IndexError):
            continue  # 解析失败跳过, 不填假值(下游知缺该标的)
    return out


def _sina_quote_raw(codes: list[str]) -> dict[str, dict]:
    """新浪 sinajs 批量报价(降级源)。迁自 cn_fetch.sina_quote。

    成交额单位=元(最准), 但无 PE/市值, 这些字段缺失(None)。
    """
    q = ",".join(codes)
    txt = _get(
        f"http://hq.sinajs.cn/list={q}",
        encoding="gbk",
        headers={"Referer": "https://finance.sina.com.cn/"},
    )
    out: dict[str, dict] = {}
    for line in txt.strip().split("\n"):
        line = line.strip().rstrip(";")
        if '="' not in line:
            continue
        prefix = line.split('="')[0]
        scode = prefix.split("_")[-1]
        body = line.split('="', 1)[1].rstrip('"')
        f = body.split(",")
        if len(f) < 10:
            continue
        try:
            out[scode] = {
                "code": scode,
                "name": f[0],
                "open": float(f[1]) if f[1] else None,
                "prev_close": float(f[2]) if f[2] else None,
                "price": float(f[3]) if f[3] else None,
                "high": float(f[4]) if f[4] else None,
                "low": float(f[5]) if f[5] else None,
                "vol": float(f[8]) if f[8] else None,        # 手
                "amount": float(f[9]) if f[9] else None,     # 元
                "date": f[30] if len(f) > 30 else None,
                "time": f[31] if len(f) > 31 else None,
            }
        except (ValueError, IndexError):
            continue
    return out


class TencentProvider(QuoteProvider):
    """腾讯 HTTP 行情主通道 + 新浪降级。"""

    name = "tencent"

    def get_bars(self, symbol: str, n: int = 30,
                 adjust: BarAdjust = BarAdjust.QFQ) -> list[Bar]:
        arr = _tencent_kline_raw(symbol, n, adjust.value)
        if not arr:
            return []
        last_closed = _is_last_bar_closed(arr[-1][0]) if arr else True
        bars: list[Bar] = []
        for i, x in enumerate(arr):
            vol = float(x[5]) if len(x) > 5 and isinstance(x[5], (int, float, str)) else 0.0
            dividend = x[6] if len(x) > 6 and isinstance(x[6], dict) else None
            bars.append(
                Bar(
                    date=x[0],
                    open=float(x[1]),
                    close=float(x[2]),
                    high=float(x[3]),
                    low=float(x[4]),
                    vol=vol,
                    dividend=dividend,
                    is_closed=True if i < len(arr) - 1 else last_closed,
                )
            )
        return bars

    def get_quotes(self, codes: list[str]) -> dict[str, Quote]:
        if not codes:
            return {}
        raw = _tencent_quote_raw(codes)
        if not raw:  # 腾讯全失败 → 降级新浪
            raw = _sina_quote_raw(codes)
        if not raw:
            raise ProviderError(f"腾讯+新浪报价均不可达: {codes}")
        return {code: self._to_quote(d) for code, d in raw.items()}

    def get_financials(self, code: str) -> Optional[Financial]:
        """腾讯报价仅含 pe_ttm, 无 roe。主力走 fundamentals agent / mootdx。"""
        sym = f"sh{code}" if code.startswith(("6", "9")) else f"sz{code}"
        try:
            # get_quotes 返回的 key 是腾讯 m[2](无前缀), 用 code 取
            q = self.get_quotes([sym]).get(code)
        except ProviderError:
            return None
        if not q or q.pe_ttm is None:
            return None
        return Financial(code=code, pe_ttm=q.pe_ttm)

    def health_check(self) -> bool:
        try:
            return bool(self.get_quotes(["sh600519"]))
        except ProviderError:
            return False

    @staticmethod
    def _to_quote(d: dict) -> Quote:
        return Quote(
            code=d.get("code", ""),
            name=d.get("name"),
            price=d.get("price"),
            prev_close=d.get("prev_close"),
            open=d.get("open"),
            high=d.get("high"),
            low=d.get("low"),
            vol=d.get("vol"),
            amount=d.get("amount"),
            pct=d.get("pct"),
            turnover=d.get("turnover"),
            pe_ttm=d.get("pe_ttm"),
            pb=None,  # 腾讯报价无 PB
            mktcap_yi=d.get("mktcap_yi"),
            float_mktcap_yi=d.get("float_mktcap_yi"),
            time=d.get("time"),
        )
