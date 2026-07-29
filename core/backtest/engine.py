"""walk-forward 回测引擎(防过拟合核心)。

简化版: 非重叠窗口 + core 因子分 + 扣成本 + purge(算分只用窗口前数据, 防穿越)。
完整 walk-forward(训练算 IC→测试验证)留扩展, 当前用 registry 滚动 IR 权重近似。

治旧 bug:
- portfolio_optimizer 零成本高估收益 → 扣成本(net_return_pct)
- 索引对齐停牌错位 → 用 date 找 start/end bar(不借位)
- 回测样本不足却硬否决 → verdict 按样本量分级(改造1)
"""
from __future__ import annotations

from typing import Optional

from core.backtest.costs import net_return_pct
from core.backtest.metrics import (
    avg_return,
    confidence_interval,
    max_drawdown,
    sharpe,
    win_rate,
)
from core.factors.engine import FactorEngine
from core.providers.base import Bar


class WalkForwardEngine:
    """回测引擎。注入 FactorEngine(含 registry 滚动 IR 权重)。"""

    def __init__(
        self,
        factor_engine: FactorEngine,
        top_n: int = 5,
        window: int = 5,
        with_costs: bool = True,
    ):
        self.factor_engine = factor_engine
        self.top_n = top_n
        self.window = window
        self.with_costs = with_costs

    def run(
        self,
        bars_by_symbol: dict[str, list[Bar]],
        quotes: Optional[dict] = None,
        financials: Optional[dict] = None,
    ) -> dict:
        """非重叠窗口回测。每窗口: slice_until(start) 算分→TopN→持有到 end 收益(扣成本)。"""
        all_dates = sorted({b.date for bars in bars_by_symbol.values() for b in bars})
        if len(all_dates) < self.window + 21:
            return {"sample_count": 0, "verdict": "数据不足"}

        windows: list[tuple[str, str]] = []
        i = len(all_dates) - 1
        while i - self.window >= 21:
            windows.append((all_dates[i - self.window], all_dates[i]))
            i -= self.window

        all_returns: list[float] = []
        equity = [1.0]
        for start, end in windows:
            scores = self.factor_engine.compute_scores(
                bars_by_symbol, start, quotes, financials
            )
            top = sorted(
                scores.items(), key=lambda x: -x[1]["composite_score"]
            )[: self.top_n]
            window_rets: list[float] = []
            for code, _ in top:
                bars = [b for b in bars_by_symbol.get(code, []) if b.date <= end]
                start_b = next((b for b in bars if b.date >= start), None)
                end_b = next((b for b in reversed(bars) if b.date <= end), None)
                if not start_b or not end_b or start_b.close <= 0:
                    continue
                gross = (end_b.close - start_b.close) / start_b.close * 100
                is_sh = code.startswith(("6", "9"))
                net = net_return_pct(gross, is_sh) if self.with_costs else gross
                all_returns.append(net)
                window_rets.append(net)
            if window_rets:
                equity.append(
                    equity[-1] * (1 + sum(window_rets) / len(window_rets) / 100)
                )

        n = len(all_returns)
        wins = sum(1 for r in all_returns if r > 0)
        sample_n = len(windows)
        wr = win_rate(all_returns)
        ar = avg_return(all_returns)

        pass_ct = (wr >= 55) + (ar >= 2)
        verdict = ["rejected", "observation", "cautious", "approved"][pass_ct]
        # 改造1: 样本不足不得硬否决
        if verdict == "rejected":
            if sample_n < 12:
                verdict = "observation"
            elif sample_n < 20:
                verdict = "cautious"

        return {
            "sample_count": sample_n,
            "total_trades": n,
            "win_rate": round(wr, 1),
            "avg_return": round(ar, 2),
            "max_drawdown": max_drawdown(equity),
            "sharpe": sharpe(all_returns),
            "confidence_interval": confidence_interval(wins, n),
            "verdict": verdict,
            "sample_insufficient": sample_n < 12,
            "with_costs": self.with_costs,
        }
