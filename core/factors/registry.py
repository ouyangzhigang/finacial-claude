"""因子注册表 + IC/IR 滚动加权(治痛点6算法支撑核心)。

权重从静态 BASE_WEIGHTS 变成数据驱动:
- 每因子每日算 T+5 IC(由 recommendation_backtester 喂入, 下一批对接)
- 滚动窗口 60 个交易日
- 权重 = IR(=mean IC / std IC)归一化, IC 衰减因子自动降权
- 样本<12 不参与(与 v1 改造1 回测分级一致)
- 全失效回退等权(保守, 不让某因子独大)
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

from core.factors.base import Factor


@dataclass
class ICRecord:
    date: str
    ic: float


class ICRoller:
    """单因子 IC/IR 滚动计算。"""

    def __init__(self, window: int = 60):
        self.window = window
        self.records: deque[ICRecord] = deque(maxlen=window)

    def add(self, date: str, ic: float):
        self.records.append(ICRecord(date, ic))

    @property
    def sample_size(self) -> int:
        return len(self.records)

    @property
    def mean_ic(self) -> Optional[float]:
        if len(self.records) < 12:
            return None
        return sum(r.ic for r in self.records) / len(self.records)

    @property
    def ir(self) -> Optional[float]:
        """信息比率(=mean IC / std IC)。负则因子失效。样本<12 返回 None。

        std=0(IC 全相同, 无波动)时用 mean 符号作退化近似: 稳定正 IC 视为有效。
        """
        if len(self.records) < 12:
            return None
        ics = [r.ic for r in self.records]
        mean = sum(ics) / len(ics)
        var = sum((i - mean) ** 2 for i in ics) / (len(ics) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        if std == 0:
            return mean  # 无波动: 正 IC 视为有效(退化, 真实罕见)
        return mean / std


class FactorRegistry:
    """因子库 + IC/IR 滚动加权。"""

    def __init__(self):
        self.factors: dict[str, Factor] = {}
        self.ic_rollers: dict[str, ICRoller] = {}

    def register(self, factor: Factor):
        self.factors[factor.name] = factor
        self.ic_rollers[factor.name] = ICRoller(window=60)

    def record_ic(self, factor_name: str, date: str, ic: float):
        """喂入单日 IC(由 recommendation_backtester T+5 涨幅 Spearman 产出)。"""
        if factor_name in self.ic_rollers:
            self.ic_rollers[factor_name].add(date, ic)

    def weights(self) -> dict[str, float]:
        """IC/IR 驱动权重(IR 归一化)。

        - IR 有值且正: 权重 = IR / sum(正IR)
        - IR 负/None: 权重 = 0(失效降权, 但 key 保留, 调用方可查)
        - 全部无效: 回退等权
        """
        irs = {n: self.ic_rollers[n].ir for n in self.factors}
        positive = {n: ir for n, ir in irs.items() if ir and ir > 0}
        if not positive:
            n = len(self.factors)
            return {name: 1.0 / n for name in self.factors} if n else {}
        total = sum(positive.values())
        # 所有因子都返回, 负/None 给 0.0(保留 key 供调用方查询)
        return {name: (ir / total if (ir and ir > 0) else 0.0) for name, ir in irs.items()}

    def status(self) -> dict[str, dict]:
        """各因子 IC/IR 状态(供 governor 报告"算法支撑"透明化)。"""
        return {
            n: {
                "ir": self.ic_rollers[n].ir,
                "mean_ic": self.ic_rollers[n].mean_ic,
                "sample": self.ic_rollers[n].sample_size,
            }
            for n in self.factors
        }
