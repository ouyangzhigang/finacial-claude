"""providers 层影子迁移测试。

验证四件事(对应 v2 改造的防回归):
1. TencentProvider.get_bars vs cn_fetch.kline 逐字段一致(影子迁移)
2. 报价字段统一 pe_ttm/mktcap_yi, 与 cn_fetch.quote 一致
3. is_closed 防穿越守卫(历史 K = True)
4. 空值 None 不填 0(防 PE=0 误判低估)
5. QuoteClient 降级链结构 + 多源合并 get_financials
"""
import pytest

from core.providers import (
    Bar,
    ProviderError,
    Quote,
    QuoteClient,
    TencentProvider,
)
from core.providers.tencent import _is_last_bar_closed

cn_fetch = pytest.importorskip("cn_fetch")


# ─────────────── 影子迁移(需网络, 真请求腾讯) ───────────────


@pytest.mark.network
def test_shadow_kline_matches_cn_fetch():
    """K 线影子: TencentProvider.get_bars vs cn_fetch.kline 逐字段一致"""
    sym, n = "sh600519", 10
    old = cn_fetch.kline(sym, n)
    new = TencentProvider().get_bars(sym, n)
    assert len(new) == len(old)
    for bar, raw in zip(new, old):
        assert bar.date == raw[0]
        assert bar.open == float(raw[1])
        assert bar.close == float(raw[2])
        assert bar.high == float(raw[3])
        assert bar.low == float(raw[4])


@pytest.mark.network
def test_shadow_quote_field_unified():
    """报价影子: 字段统一 pe_ttm/mktcap_yi, 与 cn_fetch.quote 一致"""
    sym = "sh600519"
    old = cn_fetch.quote([sym])
    new = TencentProvider().get_quotes([sym])
    code = "600519"
    assert code in new
    o, n = old[code], new[code]
    assert n.price == o["price"]
    assert n.pe_ttm == o["pe_ttm"]
    assert n.mktcap_yi == o["mktcap_yi"]
    assert n.float_mktcap_yi == o["float_mktcap_yi"]


@pytest.mark.network
def test_quoteclient_bars_works():
    """QuoteClient.get_bars 降级链可用(腾讯主通道)"""
    bars = QuoteClient().get_bars("sh600519", n=5)
    assert len(bars) == 5
    assert all(isinstance(b, Bar) for b in bars)


@pytest.mark.network
def test_quoteclient_financials_pe_from_tencent():
    """QuoteClient.get_financials: pe_ttm 来自腾讯报价(多源合并)"""
    fin = QuoteClient().get_financials("600519")
    assert fin is not None
    assert fin.pe_ttm is not None


# ─────────────── 逻辑测试(不需网络) ───────────────


def test_is_closed_history_true():
    """历史 K 线 is_closed=True(防穿越: 末根若是今日盘中才 False)"""
    assert _is_last_bar_closed("2020-01-01") is True


def test_is_closed_empty_true():
    """空日期视为收盘(不应发生, 但保守处理)"""
    assert _is_last_bar_closed("") is True


def test_quote_empty_values_none():
    """空值 None 不填 0(防 PE=0 误判低估)"""
    q = Quote(code="600519")
    assert q.pe_ttm is None
    assert q.pb is None
    assert q.mktcap_yi is None
    assert q.price is None


def test_bar_amount_yi_property():
    """Bar.amount_yi 单位换算(元→亿)"""
    b = Bar(date="2026-07-28", open=10, close=10, high=10, low=10, amount=6.4e8)
    assert b.amount_yi == 6.4
    b_none = Bar(date="2026-07-28", open=10, close=10, high=10, low=10)
    assert b_none.amount_yi is None


def test_quoteclient_fallback_structure():
    """QuoteClient 降级链结构: [tencent, mootdx]"""
    qc = QuoteClient()
    assert len(qc.providers) == 2
    assert qc.providers[0].name == "tencent"
    assert qc.providers[1].name == "mootdx"


def test_mootdx_bars_raises_not_supported():
    """mootdx 不支持行情(仅财务), 调 get_bars 抛 ProviderError"""
    from core.providers import MootdxProvider

    with pytest.raises(ProviderError):
        MootdxProvider().get_bars("sh600519")
