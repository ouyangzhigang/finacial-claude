#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
hard_gate.py — 硬门过滤引擎 (Layer 2.5: Gate Filter)

在 governor 看到数据之前，由代码执行 6 道不可逾越的硬门规则。
governor 不可 override 硬门结果。

用法:
  python scripts/hard_gate.py --run-id 20260721_short-term-picks

输入(从 data/runs/{runId}/ 读取):
  - factor_scores.json      → composite_score, rank
  - timing_scores.json      → timing_score
  - sentiment_scores.json   → social_heat, hype_risk
  - supply_risk.json        → risk_score, 解禁信息
  - fundamentals-analyst.json → ROE, PE, 红旗
  - _shared.json            → MCP 状态

输出:
  data/runs/{runId}/gate_report.json
"""

import json
import os
import sys
import argparse
from pathlib import Path

# ════════════════════════════════════════════
# 6 道硬门定义
# ════════════════════════════════════════════

def _safe(st, key, default):
    """dict.get 安全版: 处理 None / 非数值字符串"""
    v = st.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


GATES = {
    "G1_基本面": {
        "desc": "ROE<5% AND (PE>50 OR PE<0亏损) → 一票否决入TopN",
        "action": "reject",
        "check": lambda st: (
            _safe(st, "roe", 999) < 5 and (_safe(st, "pe", 0) > 50 or _safe(st, "pe", 0) < 0)
        ),
    },
    "G2_社交过热": {
        "desc": "social_heat>95 AND hype_risk>60 → 一票否决入TopN (heat>90 & hype>40 → 降级)",
        "action": "reject",
        "check": lambda st: (
            _safe(st, "social_heat", 0) > 95 and _safe(st, "hype_risk", 0) > 60
        ),
        # 二级检查: 热度较高但未达否决线 → 降级而非否决
        "check_downgrade": lambda st: (
            _safe(st, "social_heat", 0) > 90 and _safe(st, "hype_risk", 0) > 40
        ),
    },
    "G3_入场时机": {
        "desc": "timing_score<0 → 强制降级观察仓 (timing_score<10 → 仅警告标记)",
        "action": "downgrade_observe",
        "check": lambda st: _safe(st, "timing_score", 99) < 0,
        # 二级检查: timing_score 偏低但不极端 → 仅警告, 不降级
        "check_warn": lambda st: _safe(st, "timing_score", 99) < 10,
    },
    "G4_供给风险": {
        "desc": "supply_risk>=30(大额解禁30日内) → 一票否决",
        "action": "reject",
        "check": lambda st: _safe(st, "supply_risk", 0) >= 30,
    },
    "G5_因子排名": {
        "desc": "composite_score<0(后50%) → 不得排Top1, max_rank=2",
        "action": "downgrade_not_top1",
        "check": lambda st: _safe(st, "composite_score", 999) < 0,
    },
    "G6_数据降级": {
        "desc": "MCP全挂 → 置信度强制'低', 总仓位≤40%",
        "action": "system_wide",
        "check_system": True,  # 系统级，不逐票检查
    },
    "G7_自适应动量": {
        "desc": "全池≥80%降权/剔除 → 动量优先模式: fundamentals权重20%→5%, 因子排名权重30%→50%",
        "action": "system_wide",
        "check_system": True,
    },
    "G8_回测": {
        "desc": "backtest_verdict=rejected → 一票否决入TopN(驰宏锌锗纪律: 回测证伪不得强推)",
        "action": "reject",
        "check": lambda st: _safe(st, "backtest_verdict", "") == "rejected",
    },
}


def load_json(path):
    """加载 JSON 文件，支持 utf-8/gbk 自动检测"""
    if not os.path.exists(path):
        return None
    for enc in ["utf-8", "gbk", "utf-8-sig"]:
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return None


def load_factor_scores(data_dir):
    """加载因子评分 → {code: {composite_score, rank}}"""
    path = os.path.join(data_dir, "factor_scores.json")
    data = load_json(path)
    if not data:
        return {}
    stocks = data.get("stocks", [])
    result = {}
    for i, s in enumerate(stocks, 1):
        code = s.get("symbol", "").replace("sh", "").replace("sz", "")
        if code:
            result[code] = {
                "composite_score": s.get("composite_score", 0),
                "rank": i,
                "name": s.get("name", ""),
            }
    return result


def load_timing_scores(data_dir):
    """加载入场评分 → {code: {timing_score, verdict}}"""
    path = os.path.join(data_dir, "timing_scores.json")
    data = load_json(path)
    if not data:
        return {}
    stocks = data.get("stocks", data.get("data", {}).get("stocks", []))
    result = {}
    for s in stocks:
        code = str(s.get("code", s.get("symbol", "")))
        result[code] = {
            "timing_score": s.get("timing_score", 0),
            "verdict": s.get("verdict", ""),
        }
    return result


def load_sentiment_scores(data_dir):
    """加载舆情评分 → {code: {social_heat, hype_risk, heat_momentum, bull_ratio}}"""
    path = os.path.join(data_dir, "sentiment_scores.json")
    data = load_json(path)
    if not data:
        return {}
    stocks = data.get("stocks", data.get("data", {}).get("stocks", []))
    result = {}
    for s in stocks:
        code = str(s.get("code", s.get("symbol", "")))
        result[code] = {
            "social_heat": s.get("social_heat", 0),
            "hype_risk": s.get("hype_risk", 0),
            "heat_momentum": s.get("heat_momentum", 0),
            "bull_ratio": s.get("bull_ratio", 0),
        }
    return result


def load_supply_risk(data_dir):
    """加载供给风险 → {code: {risk_score, details}}"""
    path = os.path.join(data_dir, "supply_risk.json")
    data = load_json(path)
    if not data:
        return {}
    result = {}
    for code, v in data.items():
        if isinstance(v, dict):
            result[code] = {
                "supply_risk": v.get("risk_score", 0),
                "details": v.get("details", {}),
            }
    return result


def load_fundamentals(data_dir):
    """加载基本面数据 → {code: {roe, pe, status, cf_np}}
    从 fundamentals-analyst.json 的嵌套结构读取:
    data.stocks.{code}.financials.roe + data.stocks.{code}.valuation.peTtm
    """
    path = os.path.join(data_dir, "fundamentals-analyst.json")
    data = load_json(path)
    if not data:
        return {}

    d = data.get("data", data)
    stocks_dict = d.get("stocks", {})
    result = {}

    if isinstance(stocks_dict, dict):
        for code, info in stocks_dict.items():
            code = str(code)
            financials = info.get("financials", {}) if isinstance(info, dict) else {}
            valuation = info.get("valuation", {}) if isinstance(info, dict) else {}
            verdict = info.get("verdict", "")
            result[code] = {
                "roe": financials.get("roe"),
                "pe": valuation.get("peTtm"),
                "status": "reject" if "剔除" in str(verdict) else (
                    "downgrade" if "降权" in str(verdict) else "pass"),
                "cf_np": financials.get("cashflowRatio"),
            }
    else:
        # Fallback: keyFields 方式 (旧格式兼容)
        key_fields = d.get("keyFields", {})
        rejects = set(str(c) for c in key_fields.get("rejectCodes", []))
        downgrades = set(str(c) for c in key_fields.get("downgradeCodes", []))
        passes = set(str(c) for c in key_fields.get("passCodes", []))
        for code in rejects:
            result[code] = {"roe": -99, "pe": 999, "status": "reject", "cf_np": None}
        for code in downgrades:
            result[code] = {"roe": 5, "pe": 70, "status": "downgrade", "cf_np": None}
        for code in passes:
            result[code] = {"roe": 15, "pe": 25, "status": "pass", "cf_np": None}

    # ── mootdx 财务数据兜底: 当 ROE 大面积缺失时, 从通达信 TCP 补充 ──
    roe_missing = sum(1 for v in result.values() if v.get("roe") is None)
    if roe_missing > len(result) * 0.5 and len(result) > 0:
        try:
            from mootdx.affair import Affair
            a = Affair()
            df = a.parse(filename='gpcw20251231.zip')
            COL_ROE, COL_NET_PROFIT = 6, 95
            for code in list(result.keys()):
                if result[code].get("roe") is not None:
                    continue  # 已有ROE, 不覆盖
                if code in df.index:
                    row = df.loc[code]
                    try:
                        roe = float(row.iloc[COL_ROE])
                        net_profit = float(row.iloc[COL_NET_PROFIT])
                        if roe == roe:  # NaN check
                            result[code]["roe"] = roe
                            result[code]["net_profit"] = net_profit
                            # 更新 status
                            if net_profit < 0:
                                result[code]["status"] = "reject"
                            elif roe < 5:
                                result[code]["status"] = "downgrade"
                    except (ValueError, TypeError, IndexError):
                        pass
        except ImportError:
            pass  # mootdx 不可用, 静默降级
        except Exception:
            pass  # 其他错误, 静默降级

    return result


def load_capital_scores(data_dir):
    """加载资金流评分 → {code: capital_score}"""
    path = os.path.join(data_dir, "capital_scores.json")
    data = load_json(path)
    if not data:
        return {}
    result = {}
    for code, v in data.items():
        if isinstance(v, (int, float)):
            result[code] = {"capital_score": v}
        elif isinstance(v, dict):
            result[code] = {"capital_score": v.get("capital_score", v.get("score", 50))}
    return result


def load_backtest_results(data_dir):
    """加载回测结果 → {code: {backtest_verdict, win_rate, avg_return, max_drawdown}}"""
    path = os.path.join(data_dir, "backtest.json")
    data = load_json(path)
    if not data:
        return {}
    result = {}
    backtest_list = data.get("backtest", [])
    if isinstance(backtest_list, list):
        for bt in backtest_list:
            code = bt.get("code", "")
            # Normalize: strip exchange prefix (sz000975 → 000975)
            code = code.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
            if code:
                result[code] = {
                    "backtest_verdict": bt.get("verdict", "unknown"),
                    "win_rate": bt.get("win_rate", 0),
                    "avg_return": bt.get("avg_return", 0),
                    "max_drawdown": bt.get("max_drawdown", 0),
                    "pass_count": bt.get("pass_count", 0),
                }
    return result


def check_mcp_status(data_dir):
    """检测 MCP 状态 → 是否全挂(递归搜索 agent JSON)"""
    # 先检查 _shared.json
    path = os.path.join(data_dir, "_shared.json")
    data = load_json(path)
    if data:
        mcp_status = data.get("mcp_status", data.get("data_source_status", {}))
        if isinstance(mcp_status, dict):
            down_count = sum(
                1 for v in mcp_status.values() if v in ("down", "ssl_error", "502")
            )
            total = len(mcp_status)
            if total > 0 and down_count == total:
                return "all_down"
            elif down_count > 0:
                return "partial_down"
        elif isinstance(mcp_status, str):
            return mcp_status

    # 递归搜索 agent JSON 中的 MCP 状态标记
    # 先收集所有匹配，优先返回 all_down
    def search_mcp_all(obj, depth=0, results=None):
        if results is None:
            results = []
        if depth > 8:
            return results
        if isinstance(obj, str):
            if "MCP全挂" in obj or "SSL全挂" in obj or "iFind/wind/akshare MCP SSL全挂" in obj:
                results.append("all_down")
            elif "MCP SSL挂" in obj or "iFind SSL挂" in obj:
                results.append("partial_down")
        elif isinstance(obj, dict):
            for v in obj.values():
                search_mcp_all(v, depth + 1, results)
        elif isinstance(obj, list):
            for item in obj[:20]:
                search_mcp_all(item, depth + 1, results)
        return results

    for fname in ["fundamentals-analyst.json", "catalyst-scanner.json",
                  "macro-strategist.json", "sector-analyst.json"]:
        agent_path = os.path.join(data_dir, fname)
        agent_data = load_json(agent_path)
        if agent_data:
            matches = search_mcp_all(agent_data)
            if "all_down" in matches:
                return "all_down"
            if "partial_down" in matches:
                return "partial_down"

    for fname in ["fundamentals-analyst.json", "catalyst-scanner.json",
                  "macro-strategist.json", "sector-analyst.json"]:
        agent_path = os.path.join(data_dir, fname)
        agent_data = load_json(agent_path)
        if agent_data:
            r = search_mcp_all(agent_data)
            if r:
                return r

    return "ok"


def merge_stock_data(data_dir):
    """合并所有数据源为统一股票字典"""
    factor = load_factor_scores(data_dir)
    timing = load_timing_scores(data_dir)
    sentiment = load_sentiment_scores(data_dir)
    supply = load_supply_risk(data_dir)
    fundamentals = load_fundamentals(data_dir)
    capital = load_capital_scores(data_dir)
    backtest = load_backtest_results(data_dir)

    # 收集所有代码
    all_codes = set()
    all_codes.update(factor.keys())
    all_codes.update(timing.keys())
    all_codes.update(sentiment.keys())
    all_codes.update(supply.keys())
    all_codes.update(fundamentals.keys())
    all_codes.update(capital.keys())
    all_codes.update(backtest.keys())

    stocks = {}
    for code in all_codes:
        st = {"code": code}
        st.update(factor.get(code, {}))
        st.update(timing.get(code, {}))
        st.update(sentiment.get(code, {}))
        st.update(supply.get(code, {}))
        st.update(fundamentals.get(code, {}))
        st.update(capital.get(code, {}))
        st.update(backtest.get(code, {}))
        stocks[code] = st

    return stocks


def apply_gates(stocks, mcp_status, data_dir=''):
    """对每只股票逐票执行硬门检查"""
    results = {}
    system_flags = {
        "mcp_status": mcp_status,
        "confidence_floor": "中",
        "position_cap": 0.70,
    }

    # G6: 系统级数据降级
    if mcp_status == "all_down":
        system_flags["confidence_floor"] = "低"
        system_flags["position_cap"] = 0.40
        system_flags["g6_reason"] = GATES["G6_数据降级"]["desc"]
    elif mcp_status == "partial_down":
        system_flags["confidence_floor"] = "中"
        system_flags["position_cap"] = 0.55

    # G7: 自适应动量模式 — 全池基本面同质化时切到动量优先
    # 统计 fundamentals 判定为降权/剔除的比例
    total_with_fund = 0
    downgraded_fund = 0
    for code, st in stocks.items():
        roe = st.get("roe")
        pe = st.get("pe")
        if roe is not None and pe is not None:
            total_with_fund += 1
            try:
                if float(roe) < 5 or float(pe) > 100:  # ROE低或PE极端高=基本面弱
                    downgraded_fund += 1
            except (ValueError, TypeError):
                pass

    if total_with_fund > 0:
        downgrade_ratio = downgraded_fund / total_with_fund
        if downgrade_ratio >= 0.80:
            system_flags["adaptive_mode"] = "momentum_priority"
            system_flags["g7_reason"] = (
                f"全池{downgraded_fund}/{total_with_fund}({downgrade_ratio*100:.0f}%)"
                f"基本面降权/剔除 → 动量优先: fundamentals 20%→5%, 因子排名 30%→50%"
            )
            system_flags["fund_weight_override"] = 0.05  # 从 20% 降到 5%
            system_flags["factor_rank_weight_override"] = 0.50  # 从 30% 升到 50%
        elif downgrade_ratio >= 0.60:
            system_flags["adaptive_mode"] = "momentum_aware"
            system_flags["g7_reason"] = (
                f"全池{downgraded_fund}/{total_with_fund}({downgrade_ratio*100:.0f}%)"
                f"基本面大面积降权 → 适度提升因子排名权重"
            )
            system_flags["fund_weight_override"] = 0.10
            system_flags["factor_rank_weight_override"] = 0.40
        else:
            system_flags["adaptive_mode"] = "balanced"
    else:
        system_flags["adaptive_mode"] = "balanced"

    # ── G7 补丁: MCP全挂导致ROE大面积缺失时, 强制动量优先 ──
    # 无法评估基本面 → 不能依赖基本面因子, 必须切换到动量/资金/舆情驱动
    if mcp_status == "all_down" and system_flags.get("adaptive_mode") != "momentum_priority":
        roe_available = sum(1 for code, st in stocks.items() if st.get("roe") is not None)
        roe_coverage = roe_available / max(len(stocks), 1)
        if roe_coverage < 0.30:  # 不到30%的股票有ROE → 基本面数据不可靠
            system_flags["adaptive_mode"] = "momentum_priority"
            system_flags["g7_reason"] = (
                f"MCP全挂+ROE覆盖率仅{roe_coverage*100:.0f}%({roe_available}/{len(stocks)})"
                f" → 基本面数据不可靠, 强制动量优先: fundamentals权重降至5%, 因子排名权重升至50%"
            )
            system_flags["fund_weight_override"] = 0.05
            system_flags["factor_rank_weight_override"] = 0.50

    # ── 改造3: 数据链断检测(≠动量优先,是数据缺失) ──
    # 读 factor_scores.json 顶层 data_link_broken: 非K线维度全<50%可用率
    if data_dir:
        _fs_data = load_json(os.path.join(data_dir, "factor_scores.json")) or {}
        if _fs_data.get("data_link_broken"):
            system_flags["data_link_broken"] = True
            system_flags["confidence_floor"] = "低"
            system_flags["position_cap"] = min(system_flags.get("position_cap", 0.70), 0.30)
            system_flags["g_data_reason"] = (
                f"非K线维度可用率全<50%: {_fs_data.get('dim_availability_rate', {})} "
                f"→ 数据链断(≠动量优先), 置信度强制低, 仓位上限30%"
            )
        else:
            system_flags["data_link_broken"] = False
            if _fs_data.get("dim_availability_rate"):
                system_flags["dim_availability_rate"] = _fs_data["dim_availability_rate"]

    # 动量优先模式下, G1 基本面阈值放宽 (全池基本面都差, 不能用正常标准)
    if system_flags.get("adaptive_mode") == "momentum_priority":
        system_flags["g1_relaxed"] = True
        system_flags["g1_relaxed_desc"] = "G1阈值放宽: ROE<0%(亏损) AND (PE>200或PE<0亏损) → 才否决"
        system_flags["g2_relaxed"] = True
        system_flags["g2_relaxed_desc"] = "G2阈值放宽: social_heat>95 AND hype_risk>70 → 才否决(动量优先下社交热度是信号非噪音)"
        system_flags["g3_relaxed"] = True
        system_flags["g3_relaxed_desc"] = "G3阈值放宽: timing_score<-20(极端透支) → 才降级(动量优先下追涨合理)"
    elif system_flags.get("adaptive_mode") == "momentum_aware":
        system_flags["g1_relaxed"] = True
        system_flags["g1_relaxed_desc"] = "G1阈值放宽: ROE<0%(亏损) AND (PE>100或PE<0亏损) → 才否决"

    for code, st in stocks.items():
        gates_failed = []
        status = "ok"
        max_rank = None  # None = 无限制

        # G1: 基本面否决 (动量优先模式下阈值放宽)
        g1_check = GATES["G1_基本面"]["check"](st)
        if system_flags.get("g1_relaxed"):
            roe = st.get("roe")
            pe = st.get("pe")
            try:
                roe_val = float(roe) if roe is not None else 999
                pe_val = float(pe) if pe is not None else 0
            except (ValueError, TypeError):
                roe_val, pe_val = 999, 0
            if system_flags["adaptive_mode"] == "momentum_priority":
                g1_check = (roe_val < 0 and (pe_val > 200 or pe_val < 0))  # 亏损+极端估值或亏损 → 否决
            else:
                g1_check = (roe_val < 0 and (pe_val > 100 or pe_val < 0))  # 亏损股一律否决
        if g1_check:
            gates_failed.append(f"G1: ROE={st.get('roe','?')}% PE={st.get('pe','?')} → {GATES['G1_基本面']['desc']}")
            status = "reject"

        # G2: 社交过热否决 (动量优先模式下阈值放宽)
        g2_check = GATES["G2_社交过热"]["check"](st)
        g2_downgrade = GATES["G2_社交过热"].get("check_downgrade", lambda s: False)(st)
        if system_flags.get("g2_relaxed"):
            g2_check = (st.get("social_heat", 0) > 95 and st.get("hype_risk", 0) > 70)
            g2_downgrade = (st.get("social_heat", 0) > 90 and st.get("hype_risk", 0) > 50)
        if g2_check:
            gates_failed.append(f"G2: social_heat={st.get('social_heat','?')} hype_risk={st.get('hype_risk','?')} → {GATES['G2_社交过热']['desc']}")
            status = "reject"
        elif g2_downgrade and status != "reject":
            gates_failed.append(f"G2(warn): social_heat={st.get('social_heat','?')} hype_risk={st.get('hype_risk','?')} → 社交偏热, 降级观察")
            if status == "ok":
                status = "downgrade_observe"

        # G3: 入场时机降级 (动量优先模式下阈值放宽)
        g3_check = GATES["G3_入场时机"]["check"](st)
        g3_warn = GATES["G3_入场时机"].get("check_warn", lambda s: False)(st)
        if system_flags.get("g3_relaxed"):
            g3_check = (st.get("timing_score", 99) < -20)  # 仅极端透支降级
            g3_warn = (st.get("timing_score", 99) < -10)
        if g3_check:
            gates_failed.append(f"G3: timing_score={st.get('timing_score','?')} → {GATES['G3_入场时机']['desc']}")
            if status != "reject":
                status = "downgrade_observe"
                max_rank = None  # 观察仓不入TopN
        elif g3_warn:
            gates_failed.append(f"G3(warn): timing_score={st.get('timing_score','?')} → 入场时机偏低, 注意追涨风险")

        # G4: 供给风险否决
        if GATES["G4_供给风险"]["check"](st):
            gates_failed.append(f"G4: supply_risk={st.get('supply_risk','?')} → {GATES['G4_供给风险']['desc']}")
            status = "reject"

        # G5: 因子排名降级
        if GATES["G5_因子排名"]["check"](st):
            gates_failed.append(f"G5: composite={st.get('composite_score','?')} rank={st.get('rank','?')} → {GATES['G5_因子排名']['desc']}")
            if status == "ok":
                status = "downgrade_not_top1"
                max_rank = 2  # 最多排Top2

        # 汇总
        if not gates_failed:
            gates_failed.append("✅ 全部通过")

        results[code] = {
            "code": code,
            "status": status,
            "gates_failed": gates_failed,
            "max_rank": max_rank,
            "name": st.get("name", ""),
            "composite_score": st.get("composite_score", 0),
            "rank": st.get("rank", 99),
            "timing_score": st.get("timing_score", 0),
            "social_heat": st.get("social_heat", 0),
            "hype_risk": st.get("hype_risk", 0),
            "supply_risk": st.get("supply_risk", 0),
            "roe": st.get("roe"),
            "pe": st.get("pe"),
        }

    return results, system_flags


def find_eligible_topn(results, system_flags, top_n=5):
    """从通过硬门的标的中筛选 TopN 候选"""
    eligible = []
    for code, r in results.items():
        if r["status"] == "ok":
            eligible.append(r)
        elif r["status"] == "downgrade_not_top1":
            # 可以入TopN但不能排Top1
            eligible.append(r)

    # 按 composite_score 降序排列
    eligible.sort(key=lambda x: x.get("composite_score", -999), reverse=True)

    # 按 max_rank 约束重新排列
    final = []
    used_top1 = False
    for st in eligible:
        if st["status"] == "ok":
            if not used_top1:
                st["eligible_rank"] = 1
                used_top1 = True
            else:
                st["eligible_rank"] = len(final) + 1
            final.append(st)
        elif st["status"] == "downgrade_not_top1":
            st["eligible_rank"] = len(final) + 1  # 从第2名开始
            final.append(st)

    return final[:top_n]


def main():
    p = argparse.ArgumentParser(description="硬门过滤引擎")
    p.add_argument("--run-id", required=True, help="运行 ID")
    p.add_argument("--top-n", type=int, default=5, help="TopN 数量")
    args = p.parse_args()

    data_dir = f"data/runs/{args.run_id}"

    # 1. 合并数据
    stocks = merge_stock_data(data_dir)
    if not stocks:
        print(f"⚠️ 硬门过滤: 未找到任何股票数据 in {data_dir}", file=sys.stderr)
        print(f"   尝试搜索: {os.listdir(data_dir) if os.path.exists(data_dir) else '目录不存在'}", file=sys.stderr)
        return

    # 2. 检测 MCP 状态
    mcp_status = check_mcp_status(data_dir)

    # 3. 执行硬门(改造3: 传 data_dir 以读 data_link_broken)
    results, system_flags = apply_gates(stocks, mcp_status, data_dir)

    # 4. 筛选 eligible TopN
    eligible = find_eligible_topn(results, system_flags, args.top_n)

    # 5. 统计
    reject_count = sum(1 for r in results.values() if r["status"] == "reject")
    downgrade_count = sum(1 for r in results.values() if r["status"].startswith("downgrade"))
    ok_count = sum(1 for r in results.values() if r["status"] == "ok")

    # 6. 输出
    output = {
        "run_id": args.run_id,
        "gates": {
            "G1_基本面": GATES["G1_基本面"]["desc"],
            "G2_社交过热": GATES["G2_社交过热"]["desc"],
            "G3_入场时机": GATES["G3_入场时机"]["desc"],
            "G4_供给风险": GATES["G4_供给风险"]["desc"],
            "G5_因子排名": GATES["G5_因子排名"]["desc"],
            "G6_数据降级": GATES["G6_数据降级"]["desc"],
            "G7_自适应动量": GATES["G7_自适应动量"]["desc"],
            "G8_回测": GATES["G8_回测"]["desc"],
        },
        "system_flags": system_flags,
        "summary": {
            "total": len(results),
            "ok": ok_count,
            "downgrade": downgrade_count,
            "reject": reject_count,
            "eligible_topn": len(eligible),
        },
        "stocks": results,
        "eligible_topn": [{"code": s["code"], "name": s["name"], "composite_score": s["composite_score"],
                           "eligible_rank": s["eligible_rank"], "status": s["status"]}
                          for s in eligible],
    }

    os.makedirs(data_dir, exist_ok=True)
    output_path = os.path.join(data_dir, "gate_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"硬门过滤完成 → {output_path}")
    print(f"  总股票: {len(results)} | ✅通过: {ok_count} | ⚠️降级: {downgrade_count} | ❌否决: {reject_count}")
    print(f"  Eligible Top{args.top_n}: {len(eligible)}只")
    if eligible:
        for s in eligible[:args.top_n]:
            print(f"    #{s['eligible_rank']} {s['code']} {s.get('name','?')} composite={s.get('composite_score',0):.1f} status={s['status']}")
    print(f"  系统标志: 置信度下限={system_flags['confidence_floor']} 仓位上限={system_flags['position_cap']*100:.0f}% MCP={system_flags['mcp_status']} 自适应={system_flags.get('adaptive_mode','balanced')}")


if __name__ == "__main__":
    main()