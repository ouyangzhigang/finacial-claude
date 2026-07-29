"""core/backtest — 回测引擎(walk-forward 防过拟合)。"""
from core.backtest.costs import net_return_pct, trade_cost
from core.backtest.engine import WalkForwardEngine
from core.backtest.metrics import (
    avg_return,
    confidence_interval,
    max_drawdown,
    sharpe,
    win_rate,
)

__all__ = [
    "WalkForwardEngine",
    "avg_return",
    "confidence_interval",
    "max_drawdown",
    "net_return_pct",
    "sharpe",
    "trade_cost",
    "win_rate",
]
