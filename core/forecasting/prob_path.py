"""走势判断(概率路径, 治痛点6'预期走势判断')。

旧 factor_engine 只给"动量高→看涨"的单点逻辑 + 回测胜率。
新: composite 因子分 → {上涨/震荡/下跌 三概率} + 置信度, 报告给
"上涨概率 62%±8%" 而非"会涨", 这是机构级走势判断。

方法:
  - logistic 映射: composite 正 → up_prob > 0.5
  - regime 偏移: trending 加成 up, shock 偏 down
  - 置信度: 距 0.5 越远越自信
  - 历史校准(留接口): walk-forward 累积后用 Brier score 验证概率校准度
"""
from __future__ import annotations

import math
from typing import Optional

# regime 对 up_prob 的偏移(正值=偏多)
REGIME_BIAS = {
    "trending": 0.10,
    "ranging": 0.00,
    "shock": -0.10,
    "style_rotation": 0.00,
    "high_volatility": -0.05,
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def forecast_prob_path(
    composite_score: float,
    regime: str = "ranging",
    catalyst: Optional[float] = None,
    social_heat: Optional[float] = None,
    hype_risk: Optional[float] = None,
    capital: Optional[float] = None,
    historical_samples: Optional[list] = None,
) -> dict:
    """composite 因子分 + 质化信号 → {up/neutral/down 概率} + 置信度。

    量化基线(core factors composite)+ 质化偏移(agent catalyst/social/capital):
      - catalyst >70 → up +0.05(催化强); <30 → -0.05(催化弱)
      - capital >70 → up +0.05(资金流入); <30 → -0.05(资金撤退)
      - social_heat >70 → up +0.03(关注度高, 短线有利)
      - hype_risk >60 → up -0.05(过热回调风险)

    Args:
        composite_score: FactorEngine 综合分(量化基线)
        regime: 市场环境
        catalyst/social_heat/hype_risk/capital: agent 质化评分(0-100, None=缺失不偏移)

    Returns:
        {up_prob, neutral_prob, down_prob, confidence, label, regime, qual_bias} (%)
    """
    # logistic 映射: composite/50 控制斜率(composite=50→0.73, 0→0.5, -50→0.27)
    up = 1.0 / (1.0 + math.exp(-composite_score / 50.0))
    up += REGIME_BIAS.get(regime, 0.0)

    qual_bias = 0.0
    if catalyst is not None:
        adj = 0.05 if catalyst > 70 else (-0.05 if catalyst < 30 else 0.0)
        up += adj; qual_bias += adj
    if capital is not None:
        adj = 0.05 if capital > 70 else (-0.05 if capital < 30 else 0.0)
        up += adj; qual_bias += adj
    if social_heat is not None and social_heat > 70:
        up += 0.03; qual_bias += 0.03
    if hype_risk is not None and hype_risk > 60:
        up -= 0.05; qual_bias -= 0.05

    up = _clamp(up, 0.05, 0.95)

    rest = 1.0 - up
    neutral = rest * 0.6
    down = rest * 0.4

    confidence = round(abs(up - 0.5) * 2 * 100, 0)  # 距 0.5 越远越自信(0-100)
    label = "偏多" if up > 0.55 else ("偏空" if up < 0.45 else "中性")

    return {
        "up_prob": round(up * 100, 1),
        "neutral_prob": round(neutral * 100, 1),
        "down_prob": round(down * 100, 1),
        "confidence": confidence,
        "label": label,
        "regime": regime,
        "qual_bias": round(qual_bias * 100, 1),  # 质化偏移合计(%)
    }


def brier_score(forecasts: list[float], actuals: list[int]) -> Optional[float]:
    """概率校准度(0=完美, 1=最差)。

    forecasts: up_prob 序列(0-1), actuals: 实际涨跌(1=涨, 0=未涨)
    walk-forward 累积样本后调用, 验证概率是否校准(0.1 以下为好校准)。
    """
    if not forecasts or len(forecasts) != len(actuals):
        return None
    return round(sum((f - a) ** 2 for f, a in zip(forecasts, actuals)) / len(forecasts), 3)


class ProbPathForecaster:
    """走势判断器。封装 forecast_prob_path + 历史校准。"""

    def __init__(self, regime: str = "ranging"):
        self.regime = regime
        self._history: list[tuple[float, int]] = []  # (forecast_up, actual)

    def forecast(self, composite_score: float, regime: Optional[str] = None,
                 catalyst=None, social_heat=None, hype_risk=None, capital=None) -> dict:
        return forecast_prob_path(
            composite_score, regime or self.regime,
            catalyst=catalyst, social_heat=social_heat,
            hype_risk=hype_risk, capital=capital,
        )

    def record(self, forecast_up: float, actual_up: int):
        """记录预测结果(实际涨跌已知后), 供 brier_score 校准。"""
        self._history.append((forecast_up, actual_up))

    def brier(self) -> Optional[float]:
        if len(self._history) < 12:
            return None
        fs = [f for f, _ in self._history]
        acs = [a for _, a in self._history]
        return brier_score(fs, acs)
