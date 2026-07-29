"""core/portfolio — 组合/资金管理。

等权起步(简单可复现)+ 现有约束(单票/行业/催化/手数)+ regime 仓位上限。
"""
from core.portfolio.optimizer import optimize
from core.portfolio.sizing import REGIME_CAP, equal_weight

__all__ = ["REGIME_CAP", "equal_weight", "optimize"]
