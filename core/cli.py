"""core 统一 CLI 入口。

pyproject entry point: core = core.cli:main
也可: python -m core factor --codes 600519 --as-of 20260728 --regime trending

子命令(对应 core 7 层):
  factor    因子分(momentum×3/liquidity/valuation/quality/reversal/volatility + IC 加权)
  backtest  walk-forward 回测(扣成本 + 样本分级)
  gate      G1-G8 硬门(读 run-dir 各 companion JSON 合并)
  forecast  概率路径走势判断

workflow 通过此稳定 CLI 调 core, 不再散调 scripts/。
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _to_date(yyyymmdd: str) -> str:
    """YYYYMMDD → YYYY-MM-DD"""
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _sym(code: str) -> str:
    return f"sh{code}" if code.startswith(("6", "9")) else f"sz{code}"


def _output(obj: dict, path: str = ""):
    s = json.dumps(obj, ensure_ascii=False, indent=2)
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
        print(f"输出到 {path}", file=sys.stderr)
    else:
        print(s)


def _load_ic(path: str, registry):
    """读每因子 IC 喂 registry。格式: {factor_name: [{date, ic}]}。
    当前 recommendation_backtester 只产整体 composite IC, 每因子 IC 累积后对接(留接口)。"""
    if not path or not os.path.exists(path):
        return
    try:
        data = json.load(open(path, encoding="utf-8"))
        for fname, records in data.items():
            if isinstance(records, list):
                for r in records:
                    registry.record_ic(fname, r.get("date", ""), r.get("ic", 0))
    except Exception:
        pass


def _fetch_data(qc, codes: list[str], n: int = 260):
    """取 bars + quotes + financials(QuoteClient 降级链)。"""
    bars_by_sym, quotes, financials = {}, {}, {}
    for code in codes:
        sym = _sym(code)
        bars_by_sym[sym] = qc.get_bars(sym, n)
        try:
            q = qc.get_quotes([sym]).get(code)
            if q:
                quotes[sym] = q
        except Exception:
            pass
        try:
            fin = qc.get_financials(code)
            if fin:
                financials[sym] = fin
        except Exception:
            pass
    return bars_by_sym, quotes, financials


def _build_registry():
    from core.factors import FactorRegistry
    from core.factors.liquidity import Liquidity
    from core.factors.momentum import Momentum10D, Momentum20D, Momentum5D
    from core.factors.quality import Quality
    from core.factors.reversal import Reversal
    from core.factors.valuation import Valuation
    from core.factors.volatility import Volatility

    reg = FactorRegistry()
    for f in [Momentum5D(), Momentum10D(), Momentum20D(), Liquidity(),
              Valuation(), Quality(), Reversal(), Volatility()]:
        reg.register(f)
    return reg


def cmd_factor(args):
    from core.factors import FactorEngine
    from core.providers import QuoteClient

    qc = QuoteClient()
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    as_of = _to_date(args.as_of)
    bars_by_sym, quotes, financials = _fetch_data(qc, codes, 260)

    reg = _build_registry()
    _load_ic(args.ic_file, reg)
    eng = FactorEngine(reg, args.regime)
    scores = eng.compute_scores(bars_by_sym, as_of, quotes, financials)

    out = {
        "regime": args.regime,
        "as_of": as_of,
        "stocks": [
            {"symbol": sym, "composite_score": s["composite_score"],
             "rank": s["rank"], "dim_scores": s["dim_scores"]}
            for sym, s in scores.items()
        ],
        "ic_status": reg.status(),
        "source_status": qc.source_status(),
        "data_link_broken": not any(qc.source_status().values()),  # 全源挂→True
    }
    _output(out, args.output)


def cmd_backtest(args):
    from core.backtest import WalkForwardEngine
    from core.factors import FactorEngine
    from core.providers import QuoteClient

    qc = QuoteClient()
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    as_of = _to_date(args.as_of)
    bars_by_sym, quotes, financials = _fetch_data(qc, codes, 260)

    reg = _build_registry()
    _load_ic(args.ic_file, reg)
    eng = FactorEngine(reg, args.regime)
    bt = WalkForwardEngine(eng, top_n=args.top_n, window=args.window)
    result = bt.run(bars_by_sym, quotes, financials)
    _output(result, args.output)


def _merge_run_dir(run_dir: str) -> tuple[dict, str, bool]:
    """读 run-dir 各 companion JSON 合并为 stocks dict + mcp_status + data_link_broken。"""
    def _load(name):
        p = os.path.join(run_dir, name)
        if not os.path.exists(p):
            return {}
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return {}

    fs = _load("factor_scores.json")
    stocks = {}
    for s in fs.get("stocks", []):
        sym = s.get("symbol", "")
        code = sym.replace("sh", "").replace("sz", "")
        stocks[code] = {"composite_score": s.get("composite_score", 0), "name": ""}

    # fundamentals (roe/pe)
    fa = _load("fundamentals-analyst.json")
    fd = fa.get("data", fa)
    for key in ("all", "passed", "downgraded", "vetoed"):
        for item in fd.get(key, []) or []:
            c = str(item.get("code", ""))
            if c in stocks:
                stocks[c]["roe"] = item.get("roe")
                stocks[c]["pe"] = item.get("peTtm")

    timing = _load("timing_scores.json")
    for s in timing.get("stocks", []):
        c = str(s.get("code", s.get("symbol", ""))).replace("sh", "").replace("sz", "")
        if c in stocks:
            stocks[c]["timing_score"] = s.get("timing_score", 0)

    sent = _load("sentiment_scores.json")
    for s in sent.get("stocks", []):
        c = str(s.get("code", s.get("symbol", ""))).replace("sh", "").replace("sz", "")
        if c in stocks:
            stocks[c]["social_heat"] = s.get("social_heat", 0)
            stocks[c]["hype_risk"] = s.get("hype_risk", 0)

    sup = _load("supply_risk.json")
    for c, v in sup.items():
        if c in stocks and isinstance(v, dict):
            stocks[c]["supply_risk"] = v.get("risk_score", 0)

    bt = _load("backtest.json")
    for b in bt.get("backtest", []):
        c = str(b.get("code", "")).replace("sh", "").replace("sz", "")
        if c in stocks:
            stocks[c]["backtest_verdict"] = b.get("verdict", "")
            stocks[c]["sample_count"] = b.get("sample_count", 0)

    shared = _load("_shared.json")
    mcp = shared.get("mcp_status", shared.get("data_source_status", "ok"))
    if isinstance(mcp, dict):
        down = sum(1 for v in mcp.values() if v in ("down", "ssl_error", "502"))
        mcp = "all_down" if down == len(mcp) and down > 0 else ("partial_down" if down else "ok")

    return stocks, mcp, fs.get("data_link_broken", False)


def cmd_gate(args):
    from core.risk import apply_gates

    run_dir = f"data/runs/{args.run_id}"
    stocks, mcp, dlb = _merge_run_dir(run_dir)
    if not stocks:
        print(f"⚠️ 无股票数据 in {run_dir}", file=sys.stderr)
        return
    results, system = apply_gates(stocks, mcp, dlb)
    ok = sum(1 for r in results.values() if r["status"] == "ok")
    rej = sum(1 for r in results.values() if r["status"] == "reject")
    _output(
        {"run_id": args.run_id, "system_flags": system,
         "summary": {"total": len(results), "ok": ok, "reject": rej},
         "stocks": results},
        args.output,
    )


def cmd_forecast(args):
    from core.forecasting import forecast_prob_path

    def _lj(run_dir, name):
        p = os.path.join(run_dir, name)
        if not os.path.exists(p):
            return {}
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return {}

    if args.run_id:
        run_dir = f"data/runs/{args.run_id}"
        fs = _lj(run_dir, "factor_scores.json")
        regime = fs.get("regime", "ranging")
        sent = _lj(run_dir, "sentiment_scores.json")
        sent_map = {}
        for s in sent.get("stocks", []):
            c = str(s.get("code", s.get("symbol", ""))).replace("sh", "").replace("sz", "")
            sent_map[c] = s
        cap = _lj(run_dir, "capital_scores.json")
        out_stocks = []
        for s in fs.get("stocks", []):
            sym = s.get("symbol", "")
            code = sym.replace("sh", "").replace("sz", "")
            composite = s.get("composite_score", 0)
            sm = sent_map.get(code, {})
            social_heat = sm.get("social_heat")
            hype_risk = sm.get("hype_risk")
            catalyst = min(90, (social_heat or 50) * 0.7 + 20) if social_heat else None
            capital_score = cap.get(code) if isinstance(cap, dict) else None
            r = forecast_prob_path(
                composite, regime,
                catalyst=catalyst, social_heat=social_heat,
                hype_risk=hype_risk, capital=capital_score,
            )
            r["symbol"] = sym
            r["composite"] = composite
            out_stocks.append(r)
        _output({"run_id": args.run_id, "regime": regime, "stocks": out_stocks}, args.output)
    else:
        if args.composite is None:
            print("⚠️ 需要 --composite 或 --run-id", file=sys.stderr)
            return
        r = forecast_prob_path(args.composite, args.regime)
        _output(r, args.output)


def main():
    p = argparse.ArgumentParser(prog="core", description="finacial-invest 核心库 CLI")
    sub = p.add_subparsers(dest="cmd")

    pf = sub.add_parser("factor", help="因子分(6 族 + IC 加权)")
    pf.add_argument("--codes", required=True, help="逗号分隔代码(无前缀)")
    pf.add_argument("--as-of", required=True, help="YYYYMMDD")
    pf.add_argument("--regime", default="ranging")
    pf.add_argument("--ic-file", default="", help="每因子 IC JSON(留接口)")
    pf.add_argument("--output", default="")
    pf.set_defaults(func=cmd_factor)

    pb = sub.add_parser("backtest", help="walk-forward 回测")
    pb.add_argument("--codes", required=True)
    pb.add_argument("--as-of", required=True)
    pb.add_argument("--regime", default="ranging")
    pb.add_argument("--top-n", type=int, default=5)
    pb.add_argument("--window", type=int, default=5)
    pb.add_argument("--ic-file", default="")
    pb.add_argument("--output", default="")
    pb.set_defaults(func=cmd_backtest)

    pg = sub.add_parser("gate", help="G1-G8 硬门")
    pg.add_argument("--run-id", required=True, help="如 20260728_short-term-picks")
    pg.add_argument("--output", default="")
    pg.set_defaults(func=cmd_gate)

    pfc = sub.add_parser("forecast", help="概率路径走势判断")
    pfc.add_argument("--composite", type=float, default=None, help="composite 因子分(单只模式)")
    pfc.add_argument("--run-id", default="", help="run-id(批量模式, 读 factor_scores+sentiment+capital)")
    pfc.add_argument("--regime", default="ranging")
    pfc.add_argument("--output", default="")
    pfc.set_defaults(func=cmd_forecast)

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
