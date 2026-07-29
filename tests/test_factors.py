"""core/factors 测试 — 6 族因子 + IC/IR 加权(不依赖网络)。

覆盖:
1. 各因子 compute(数据不足→None / 正常值 / 防穿越只用 as_of 之前)
2. higher_is_better=False 因子(engine 反向 z)
3. IC/IR 滚动(正IR获权/负IR降权/样本<12→None/全失效等权)
4. engine 组合分(z-score + IC 加权 + regime)
5. valuation/quality 用 quote/financial
"""
from datetime import date, timedelta

from core.factors.base import Factor
from core.factors.engine import FactorEngine, zscore
from core.factors.liquidity import Liquidity
from core.factors.momentum import Momentum10D, Momentum20D, Momentum5D
from core.factors.quality import Quality
from core.factors.registry import FactorRegistry, ICRoller
from core.factors.reversal import Reversal
from core.factors.valuation import Valuation
from core.factors.volatility import Volatility
from core.providers.base import Bar, Financial, Quote


def _bars(closes: list[float], start="2026-06-01", closed=True) -> list[Bar]:
    """造 N 根 K 线, 日期从 start 递增。"""
    base = date.fromisoformat(start)
    return [
        Bar(date=(base + timedelta(days=i)).isoformat(),
            open=c, close=c, high=c, low=c, vol=1000, is_closed=closed)
        for i, c in enumerate(closes)
    ]


# ─────────── 因子族 ───────────


def test_momentum_insufficient_returns_none():
    assert Momentum5D().compute(_bars([10, 11, 12]), "2026-06-03") is None


def test_momentum_5d_value():
    bars = _bars([10, 11, 12, 13, 14, 15])  # 6 根
    assert Momentum5D().compute(bars, "2026-06-06") == 50.0  # (15-10)/10


def test_factor_no_lookahead():
    """因子只用 as_of 之前的数据(防穿越)"""
    from core.timeseries import filter_closed, slice_until
    bars = _bars([10, 11, 12, 13, 14, 15, 16, 30])  # 末根 30 是"未来"
    sliced = slice_until(bars, "2026-06-06")          # 切到 06-06(含第7根=15)
    closed = filter_closed(sliced)
    val = Momentum5D().compute(closed, "2026-06-06")
    # 用 close[5]=15 vs close[0]=10, 不含 30
    assert val == 50.0


def test_liquidity_value():
    bars = _bars([10] * 21, start="2026-05-01")
    # vol=1000手, close=10 → 日均额=1000*100*10=1e6元=0.01亿
    assert Liquidity().compute(bars, "2026-05-22") == 0.01


def test_valuation_uses_quote():
    """估值因子用 quote.pe_ttm"""
    q = Quote(code="600519", pe_ttm=19.95)
    assert Valuation().compute([], "2026-07-28", quote=q) == 19.95


def test_valuation_loss_returns_none():
    """亏损 PE<=0 → None(不参与排序)"""
    q = Quote(code="000001", pe_ttm=-5)
    assert Valuation().compute([], "2026-07-28", quote=q) is None
    assert Valuation().compute([], "2026-07-28") is None  # 无 quote


def test_quality_uses_financial():
    fin = Financial(code="600519", roe=30.0)
    assert Quality().compute([], "2026-07-28", financial=fin) == 30.0
    assert Quality().compute([], "2026-07-28") is None  # 无 financial


def test_reversal_direction():
    """反转: 跌的票 m5 负, engine 反向后高分"""
    bars_up = _bars([10, 11, 12, 13, 14, 15])    # 涨
    bars_dn = _bars([15, 14, 13, 12, 11, 10])    # 跌
    r_up = Reversal().compute(bars_up, "2026-06-06")
    r_dn = Reversal().compute(bars_dn, "2026-06-06")
    assert r_up > 0 and r_dn < 0  # higher_is_better=False, engine 反向


def test_volatility_value():
    bars = _bars([10] * 22, start="2026-05-01")  # 恒定 → 波动 0
    assert Volatility().compute(bars, "2026-05-23") == 0.0


# ─────────── IC/IR 滚动 ───────────


def test_ic_roller_ir_positive():
    r = ICRoller(window=60)
    for i in range(20):
        r.add(f"2026-01-{i+1:02d}", 0.1)
    assert r.ir > 0 and r.sample_size == 20


def test_ic_roller_insufficient_returns_none():
    r = ICRoller(window=60)
    for i in range(5):
        r.add(f"2026-01-{i+1:02d}", 0.1)
    assert r.ir is None and r.mean_ic is None


def test_registry_weights_positive_ir_only():
    """正 IR 因子获权, 负 IR 降权为 0"""
    reg = FactorRegistry()
    reg.register(Momentum5D())
    reg.register(Reversal())
    for i in range(20):
        reg.record_ic("momentum_5d", f"2026-01-{i+1:02d}", 0.15)
        reg.record_ic("reversal", f"2026-01-{i+1:02d}", -0.1)
    w = reg.weights()
    assert w["momentum_5d"] > 0
    assert w["reversal"] == 0.0


def test_registry_weights_fallback_equal():
    """全失效回退等权"""
    reg = FactorRegistry()
    reg.register(Momentum5D())
    reg.register(Valuation())
    w = reg.weights()
    assert w["momentum_5d"] == w["valuation"] == 0.5


# ─────────── engine ───────────


def test_zscore_none_to_zero():
    z = zscore([1.0, 2.0, 3.0, None])
    assert z[3] == 0.0
    assert z[0] < z[2]


def test_engine_composite_ranking():
    """引擎组合分: 涨的票(A) > 跌的票(B)"""
    reg = FactorRegistry()
    reg.register(Momentum5D())
    for i in range(20):
        reg.record_ic("momentum_5d", f"2026-01-{i+1:02d}", 0.1)
    eng = FactorEngine(reg, regime="trending")
    bars_by_sym = {
        "A": _bars([10, 11, 12, 13, 14, 15]),
        "B": _bars([15, 14, 13, 12, 11, 10]),
    }
    scores = eng.compute_scores(bars_by_sym, "2026-06-06")
    assert scores["A"]["composite_score"] > scores["B"]["composite_score"]
    assert scores["A"]["rank"] == 1 and scores["B"]["rank"] == 2


def test_engine_higher_is_better_false_reverses():
    """reversal(higher=False): 跌的票反转分高 → rank 1"""
    reg = FactorRegistry()
    reg.register(Reversal())
    for i in range(20):
        reg.record_ic("reversal", f"2026-01-{i+1:02d}", 0.1)
    eng = FactorEngine(reg, regime="ranging")
    bars_by_sym = {
        "UP": _bars([10, 11, 12, 13, 14, 15]),    # 涨, 反转分低
        "DN": _bars([15, 14, 13, 12, 11, 10]),    # 跌, 反转分高
    }
    scores = eng.compute_scores(bars_by_sym, "2026-06-06")
    assert scores["DN"]["composite_score"] > scores["UP"]["composite_score"]


def test_engine_uses_quote_financial():
    """engine 注入 quote/financial 给 valuation/quality"""
    reg = FactorRegistry()
    reg.register(Valuation())
    reg.register(Quality())
    for i in range(20):
        reg.record_ic("valuation", f"2026-01-{i+1:02d}", 0.1)
        reg.record_ic("quality", f"2026-01-{i+1:02d}", 0.1)
    eng = FactorEngine(reg, regime="ranging")
    bars = {"X": _bars([10] * 5)}
    quotes = {"X": Quote(code="X", pe_ttm=15.0)}                    # 低 PE
    financials = {"X": Financial(code="X", roe=25.0)}                # 高 ROE
    scores = eng.compute_scores(bars, "2026-06-05", quotes, financials)
    assert "valuation" in scores["X"]["dim_scores"]
    assert "quality" in scores["X"]["dim_scores"]
