"""G1-G8 风控硬门(迁自 hard_gate.py, 内存 dict 输入)。

含: G1 基本面/G2 社交过热/G3 入场时机/G4 供给/G5 因子排名/G8 回测分级
+ 改造2 否决预算(单票最多1主否决) + 改造1 回测按样本量分级。
G6/G7 system_flags 简化(mcp_status/data_link_broken 标志), 动量优先全逻辑留接口。
"""
from __future__ import annotations


def _safe(st: dict, key: str, default: float) -> float:
    """dict.get 安全版: None/非数值 → default。"""
    v = st.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def apply_gates(
    stocks: dict[str, dict],
    mcp_status: str = "ok",
    data_link_broken: bool = False,
) -> tuple[dict[str, dict], dict]:
    """逐票执行 G1-G8 硬门。

    Args:
        stocks: {code: {composite_score, timing_score, social_heat, hype_risk,
                        supply_risk, roe, pe, backtest_verdict, sample_count, name}}
        mcp_status: ok / partial_down / all_down
        data_link_broken: 非K线维全<50%可用率(改造3)

    Returns:
        ({code: {status, gates_failed, max_rank}}, system_flags)
    """
    system = {
        "mcp_status": mcp_status,
        "confidence_floor": "中",
        "position_cap": 0.70,
    }
    if mcp_status == "all_down":
        system["confidence_floor"] = "低"
        system["position_cap"] = 0.40
    elif mcp_status == "partial_down":
        system["position_cap"] = 0.55
    if data_link_broken:
        system["data_link_broken"] = True
        system["confidence_floor"] = "低"
        system["position_cap"] = min(system["position_cap"], 0.30)

    results: dict[str, dict] = {}
    for code, st in stocks.items():
        gf: list[str] = []
        status = "ok"
        max_rank = None

        # G1 基本面否决
        if _safe(st, "roe", 999) < 5 and (
            _safe(st, "pe", 0) > 50 or _safe(st, "pe", 0) < 0
        ):
            gf.append(f"G1: ROE={st.get('roe')} PE={st.get('pe')} → 基本面弱+高估值")
            status = "reject"

        # G2 社交过热(否决/降级分级)
        if _safe(st, "social_heat", 0) > 95 and _safe(st, "hype_risk", 0) > 60:
            gf.append(f"G2: heat={st.get('social_heat')} hype={st.get('hype_risk')} → 过热否决")
            status = "reject"
        elif _safe(st, "social_heat", 0) > 90 and _safe(st, "hype_risk", 0) > 40:
            gf.append("G2(warn): 社交偏热降级")
            if status == "ok":
                status = "downgrade_observe"

        # G3 入场时机(降级/警告分级)
        if _safe(st, "timing_score", 99) < 0:
            gf.append(f"G3: timing={st.get('timing_score')} <0 → 强制降级")
            if status != "reject":
                status = "downgrade_observe"
                max_rank = None
        elif _safe(st, "timing_score", 99) < 10:
            gf.append(f"G3(warn): timing={st.get('timing_score')} 偏低, 追涨风险")

        # G4 供给风险否决
        if _safe(st, "supply_risk", 0) >= 30:
            gf.append(f"G4: supply_risk={st.get('supply_risk')} → 大额解禁否决")
            status = "reject"

        # G5 因子排名降级
        if _safe(st, "composite_score", 999) < 0:
            gf.append(f"G5: composite={st.get('composite_score')} <0 → 不得Top1")
            if status == "ok":
                status = "downgrade_not_top1"
                max_rank = 2

        # G8 回测(改造1: 按样本量分级)
        bv = st.get("backtest_verdict", "")
        sc = st.get("sample_count", 0) or 0
        if bv == "rejected" and sc >= 20:
            gf.append(f"G8: 回测rejected sample={sc}≥20 → 否决")
            status = "reject"
        elif bv == "rejected" and 0 <= sc < 20:
            gf.append(f"G8(warn): 回测rejected sample={sc}<20 → 降级不否决(改造1)")
            if status == "ok":
                status = "downgrade_not_top1"
                max_rank = 3

        # 改造2: 否决预算(单票最多1主否决, 其余标关联)
        if status == "reject":
            veto_idxs = [
                i for i, g in enumerate(gf)
                if g.startswith(("G1:", "G2:", "G4:", "G8:"))
                and "(warn)" not in g
                and "(关联)" not in g
            ]
            for idx in veto_idxs[1:]:
                gf[idx] = "(关联) " + gf[idx]

        if not gf:
            gf.append("✅ 全部通过")

        results[code] = {
            "status": status,
            "gates_failed": gf,
            "max_rank": max_rank,
            "name": st.get("name", ""),
            "composite_score": st.get("composite_score", 0),
        }

    return results, system
