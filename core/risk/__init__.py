"""core/risk — 风控硬门(G1-G8 代码化)。

迁自 scripts/hard_gate.py, 用 core 数据结构(内存 dict 而非 JSON)。
governor 不可 override(否决权归代码, 改造2)。
"""
from core.risk.gate import apply_gates

__all__ = ["apply_gates"]
