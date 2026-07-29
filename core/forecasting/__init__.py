"""core/forecasting — 走势判断(概率路径)。

治痛点6'预期走势判断': 旧"动量高→看涨"单点 → 新 composite分→{上涨/震荡/下跌概率}+置信度。
用 walk-forward 回测验证概率校准(Brier score, 累积后用)。
"""
from core.forecasting.prob_path import ProbPathForecaster, brier_score, forecast_prob_path

__all__ = ["ProbPathForecaster", "brier_score", "forecast_prob_path"]
