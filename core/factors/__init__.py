"""core/factors — 模块化因子库 + IC/IR 滚动加权。

治痛点6"没好算法支撑因子计算": 权重从静态 BASE_WEIGHTS 变成数据驱动。
- 因子纯函数 compute(bars, as_of, quote, financial), engine 注入已切片+过滤数据(防穿越)
- 6 族量化因子: momentum/liquidity/valuation/quality/reversal/volatility
- IC/IR 滚动 60 窗口加权, 衰减因子自动降权
- LLM 质化评分(catalyst/sentiment/social)归 forecasting 层分层融合, 不污染因子库统计基础
"""
from core.factors.base import Factor, FactorValue
from core.factors.engine import FactorEngine, zscore
from core.factors.registry import FactorRegistry, ICRoller

__all__ = ["Factor", "FactorEngine", "FactorRegistry", "FactorValue", "ICRoller", "zscore"]
