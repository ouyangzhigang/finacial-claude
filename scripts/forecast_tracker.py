#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""未来预测兑现跟踪器——记录每次预测,回看命中率,反馈改进预测模型。

宗旨:future-picks 预测"未来N天将涨"的票,这里记录+回看兑现,量化命中率。
这是让"预测"真正有反馈闭环的机制——不是跑完就忘,而是回看准不准。

用法:
  # 记录一次预测(future-picks 结束时调用)
  python scripts/forecast_tracker.py record --run-id 20260731_future-picks_波段 --horizon 波段 --json-file data/runs/.../final.json

  # 回看历史预测兑现(check: 看之前预测的票今天涨了吗)
  python scripts/forecast_tracker.py check --as-of 20260731

  # 查命中率
  python scripts/forecast_tracker.py stats
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

# 加 import 路径(复用 portfolio_tracker 的腾讯报价)
sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'reconfigure') else None
sys.stderr.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stderr, 'reconfigure') else None

TRACKER_PATH = "data/forecast_tracker.json"
HORIZON_DAYS = {"短线": 5, "波段": 14, "中线": 90}  # 各周期预测窗口

# ═══ A股交易成本模型(8-11新增,堵"收益测算虚高"病根) ═══
# 病根:旧版收益测算只算价差不扣费,1万账户小额交易佣金最低5元占比高,
# "微赚14元"扣费后实亏。现加完整费用模型诚实重算命中率。
COMMISSION_RATE = 0.00025   # 佣金费率万2.5(双边)
COMMISSION_MIN = 5.0         # 佣金最低5元/笔(小额交易主成本)
STAMP_DUTY_RATE = 0.0005     # 印花税卖出千0.5(2023-08-28起由千1减半,现行税率)
SLIPPAGE_BUY = 0.003        # 买入滑点0.3%(理想价之上,真实成交价更高)
DEFAULT_CAPITAL = 10000      # 默认1万账户
DEFAULT_POSITION_PCT = 0.25  # 默认单票仓位25%


def _trade_fees(buy_value, sell_value):
    """A股单次往返交易费用(元):佣金万2.5最低5元/笔(双边)+印花税卖出千1。
    买入滑点单独在 buyPrice 体现(已*1.003),此处只算显性费用。
    返回 (总费用, 买佣金, 卖佣金, 印花税)。
    """
    buy_comm = max(buy_value * COMMISSION_RATE, COMMISSION_MIN)
    sell_comm = max(sell_value * COMMISSION_RATE, COMMISSION_MIN)
    stamp = sell_value * STAMP_DUTY_RATE
    return (buy_comm + sell_comm + stamp, buy_comm, sell_comm, stamp)


def _net_return_pct(gross_chg_pct, capital, position_pct):
    """给定价差涨跌(%)与仓位,算扣费后净收益率(%)。
    买入滑点已在 buyPrice 体现,这里只扣显性费用(佣金+印花税)。
    """
    if capital <= 0 or position_pct <= 0:
        return gross_chg_pct
    buy_value = capital * position_pct
    # 卖出金额=买入金额*(1+价差涨幅)
    sell_value = buy_value * (1 + gross_chg_pct / 100.0)
    fees, _, _, _ = _trade_fees(buy_value, sell_value)
    net_value = sell_value - fees - buy_value
    return net_value / buy_value * 100.0


def _load():
    if os.path.exists(TRACKER_PATH):
        try:
            with open(TRACKER_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"predictions": [], "lastUpdated": None, "stats": {}}


def _save(data):
    os.makedirs("data", exist_ok=True)
    data["lastUpdated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(TRACKER_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _fetch_prices(codes):
    """批量取腾讯实时价格(复用 portfolio_tracker 逻辑)
    注意:指数(000001上证/399006创业板)与股票code可能冲突(如sz000001平安银行),
    故指数用带前缀key(sh000001/sz399006),股票用去前缀code。
    """
    import urllib.request
    import ssl
    sids = []
    index_codes = {"000001", "399001", "399006"}  # 指数:用前缀key避免与股票code冲突
    for c in codes:
        c = str(c).replace("sh", "").replace("sz", "")
        # 指数强制对应前缀(000001上证/399006创业板),否则会被当成股票(sz000001=平安银行)
        if c == "000001":
            prefix = "sh"  # 上证指数
        elif c in ("399001", "399006"):
            prefix = "sz"  # 深证/创业板
        else:
            prefix = "sh" if c.startswith("6") else "sz"
        sids.append(prefix + c)
    if not sids:
        return {}
    url = f"http://qt.gtimg.cn/q={','.join(sids)}"
    ctx = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            raw = resp.read().decode("gbk", errors="ignore")
    except Exception as e:
        sys.stderr.write(f"价格获取失败: {e}\n")
        return {}
    prices = {}
    for line in raw.strip().split(";"):
        if "~" not in line:
            continue
        parts = line.split("~")
        if len(parts) > 45:
            code = parts[2]
            name = parts[1]
            # 指数用带前缀key(sh000001/sz399006),避免与股票code冲突(如sz000001平安银行覆盖sh000001上证)
            if code == "000001" and "上证" in name:
                sid = "sh000001"
            elif code == "399001" and "深证" in name:
                sid = "sz399001"
            elif code == "399006" and ("创业板" in name or "创业" in name):
                sid = "sz399006"
            else:
                sid = code  # 普通股票用纯code
            try:
                prices[sid] = {
                    "price": float(parts[3]) if parts[3] else 0,
                    "changePct": float(parts[32]) if parts[32] else 0,
                }
            except (ValueError, IndexError):
                pass
    return prices


def cmd_record(args):
    """记录一次预测"""
    data = _load()
    preds = data.get("predictions", [])

    # 读 final.json 的 topN
    topn = []
    if args.json_file and os.path.exists(args.json_file):
        try:
            d = json.load(open(args.json_file, encoding="utf-8"))
            topn = d.get("topN") or d.get("data", {}).get("topN", [])
        except Exception as e:
            sys.stderr.write(f"读取 {args.json_file} 失败: {e}\n")
    elif args.json:
        try:
            d = json.loads(args.json)
            topn = d.get("topN", [])
        except Exception:
            pass

    horizon = args.horizon or "波段"
    window_days = HORIZON_DAYS.get(horizon, 14)
    predict_date = args.as_of or (args.run_id.split("_")[0] if args.run_id else time.strftime("%Y%m%d"))
    capital = args.capital if args.capital and args.capital > 0 else DEFAULT_CAPITAL

    # T7改进:记录大盘基准价(上证+创业板),供check时算alpha超额收益
    # 病根:旧hit只看"涨了没",大盘涨4%时随便买都涨,无选股alpha——必须算超额
    bench_prices = _fetch_prices(["000001", "399006"])
    bench_base = {
        "sh000001": bench_prices.get("sh000001", {}).get("price"),
        "sz399006": bench_prices.get("sz399006", {}).get("price"),
    }

    # 记录每只预测票
    for t in topn:
        code = str(t.get("code", "")).replace("sh", "").replace("sz", "")
        if not code:
            continue
        # 取当前价(预测基准价)
        prices = _fetch_prices([code]) if code else {}
        base_price = prices.get(code, {}).get("price") if prices else None
        # 8-11:买入价加滑点(理想价*1.003),反映真实成交价高于盘中低点
        buy_price = round(base_price * (1 + SLIPPAGE_BUY), 3) if base_price else None
        # 仓位:优先用topN里的position百分比,否则默认25%
        pos_str = str(t.get("position", "")).replace("%", "").replace("仓", "").strip()
        try:
            position_pct = float(pos_str) / 100.0 if pos_str else DEFAULT_POSITION_PCT
        except (ValueError, TypeError):
            position_pct = DEFAULT_POSITION_PCT
        pred = {
            "code": code,
            "name": t.get("name", ""),
            "horizon": horizon,
            "windowDays": window_days,
            "predictDate": predict_date,
            "expireDate": (datetime.strptime(predict_date, "%Y%m%d") + timedelta(days=window_days)).strftime("%Y%m%d"),
            "basePrice": base_price,  # 理想基准价(盘中低点)
            "buyPrice": buy_price,     # 含滑点的真实买入价=理想价*1.003
            "capital": capital,
            "positionPct": position_pct,
            "benchBase": bench_base,  # 大盘基准价(预测日),供算alpha超额
            "role": t.get("role", ""),
            "position": t.get("position", ""),
            "reasoningChain": t.get("reasoningChain") or t.get("signals") or [],
            "runId": args.run_id,
            "verified": False,
            "actualChangePct": None,
            "benchChangePct": None,  # 大盘同期涨幅
            "alphaPct": None,  # 毛超额收益=个股涨幅-大盘涨幅
            "feeDragPct": None,  # 手续费拖累(%):佣金+印花税占仓位比
            "netActualChangePct": None,  # 扣费后净涨幅(%)
            "netAlphaPct": None,  # 扣费后净超额=毛超额-手续费拖累(真选股alpha)
            "hit": None,  # True=扣费后跑赢大盘(netAlpha>0)/False=跑输/None=未到期
        }
        # 去重:同一runId+code只记一次
        if not any(p["runId"] == args.run_id and p["code"] == code for p in preds):
            preds.append(pred)

    data["predictions"] = preds
    _save(data)
    print(f"forecast_tracker: 记录 {len(topn)} 只预测票,周期={horizon},到期日={preds[-1]['expireDate'] if preds else '?'}")


def cmd_check(args):
    """回看历史预测兑现——看之前预测的票跑赢大盘了吗(alpha超额)
    T7改进:不再只看"涨了没"(大盘涨4%随便买都涨),改看alpha=个股涨幅-大盘涨幅。
    hit=True=跑赢大盘(真选股alpha),False=跑输(吃了beta不算本事)。
    """
    data = _load()
    preds = data.get("predictions", [])
    as_of = args.as_of or time.strftime("%Y%m%d")
    checked = 0
    hits = 0
    pending = []
    # 取大盘当前价算同期涨幅(用预测日基准价benchBase)
    bench_base = preds[0].get("benchBase", {}) if preds else {}
    bench_cur_prices = _fetch_prices(["000001", "399006"]) if bench_base else {}
    bench_cur = {
        "sh000001": bench_cur_prices.get("sh000001", {}).get("price"),
        "sz399006": bench_cur_prices.get("sz399006", {}).get("price"),
    }
    # 大盘同期涨幅(取上证,创业板作参考)
    bench_chg = None
    bb = bench_base.get("sh000001"); bc = bench_cur.get("sh000001")
    if bb and bc and bb > 0:
        bench_chg = (bc - bb) / bb * 100
    for p in preds:
        if p.get("verified"):
            continue
        # 到期日 <= as_of 才回看
        if p.get("expireDate", "99999999") > as_of:
            pending.append(p)
            continue
        # 取当前价算实际涨跌
        prices = _fetch_prices([p["code"]]) if p["code"] else {}
        cur = prices.get(p["code"], {}).get("price")
        # 8-11:优先用含滑点的buyPrice算毛收益(真实买入价),旧记录无buyPrice则回退basePrice
        buy_price = p.get("buyPrice") or p.get("basePrice")
        capital = p.get("capital", DEFAULT_CAPITAL)
        position_pct = p.get("positionPct", DEFAULT_POSITION_PCT)
        if buy_price and cur and buy_price > 0:
            chg = (cur - buy_price) / buy_price * 100
            p["actualChangePct"] = round(chg, 2)
            p["benchChangePct"] = round(bench_chg, 2) if bench_chg is not None else None
            # 毛超额=个股涨幅-大盘涨幅
            alpha = chg - bench_chg if bench_chg is not None else chg
            p["alphaPct"] = round(alpha, 2)
            # 8-11手续费建模:佣金万2.5最低5元/笔(双边)+印花税卖千1,算扣费后净收益
            net_chg = _net_return_pct(chg, capital, position_pct)
            fee_drag = chg - net_chg  # 手续费拖累(%)
            p["feeDragPct"] = round(fee_drag, 2)
            p["netActualChangePct"] = round(net_chg, 2)
            # 净超额=毛超额-手续费拖累(真选股alpha,扣费后跑赢大盘才算命中)
            net_alpha = alpha - fee_drag
            p["netAlphaPct"] = round(net_alpha, 2)
            p["hit"] = net_alpha > 0  # 扣费后跑赢大盘才算命中
            p["verified"] = True
            checked += 1
            if p["hit"]:
                hits += 1
    _save(data)
    total = sum(1 for p in preds if p.get("verified"))
    total_hits = sum(1 for p in preds if p.get("hit"))
    rate = (total_hits / total * 100) if total else 0
    # alpha统计(毛+净)
    alphas = [p.get("alphaPct", 0) for p in preds if p.get("verified") and p.get("alphaPct") is not None]
    avg_alpha = sum(alphas) / len(alphas) if alphas else 0
    net_alphas = [p.get("netAlphaPct", 0) for p in preds if p.get("verified") and p.get("netAlphaPct") is not None]
    avg_net_alpha = sum(net_alphas) / len(net_alphas) if net_alphas else 0
    fee_drags = [p.get("feeDragPct", 0) for p in preds if p.get("verified") and p.get("feeDragPct") is not None]
    avg_fee_drag = sum(fee_drags) / len(fee_drags) if fee_drags else 0
    data["stats"] = {"totalPredictions": len(preds), "verified": total, "hits": total_hits, "hitRate": round(rate, 1), "avgAlpha": round(avg_alpha, 2), "avgNetAlpha": round(avg_net_alpha, 2), "avgFeeDrag": round(avg_fee_drag, 2), "benchChange": round(bench_chg, 2) if bench_chg else None}
    _save(data)
    print(f"forecast_tracker: 本次回看 {checked} 只,扣费后命中 {hits} 只。累计命中率 {rate:.1f}% ({total_hits}/{total})")
    print(f"  待到期(未到回看日): {len(pending)} 只")
    print(f"  平均毛alpha {avg_alpha:+.2f}% → 扣费后净alpha {avg_net_alpha:+.2f}% (手续费拖累 {avg_fee_drag:.2f}%)")


def cmd_stats(args):
    """查命中率+alpha超额收益(毛/净双口径)"""
    data = _load()
    stats = data.get("stats", {})
    preds = data.get("predictions", [])
    print(f"=== 预测兑现统计(扣费后跑赢大盘才算命中) ===")
    print(f"总预测: {len(preds)} 只")
    print(f"已回看: {stats.get('verified', 0)} 只")
    print(f"扣费后跑赢大盘: {stats.get('hits', 0)} 只")
    print(f"命中率(扣费后净alpha>0): {stats.get('hitRate', 0)}%")
    print(f"平均毛alpha: {stats.get('avgAlpha', 0):+.2f}%")
    print(f"平均手续费拖累: {stats.get('avgFeeDrag', 0):.2f}%")
    print(f"平均净alpha(扣费后): {stats.get('avgNetAlpha', 0):+.2f}%  (大盘同期: {stats.get('benchChange', '?')}%)")
    # 按周期分
    for h in HORIZON_DAYS:
        hp = [p for p in preds if p.get("horizon") == h]
        hv = [p for p in hp if p.get("verified")]
        hh = [p for p in hv if p.get("hit")]
        r = (len(hh) / len(hv) * 100) if hv else 0
        alphas = [p.get("alphaPct", 0) for p in hv if p.get("alphaPct") is not None]
        avg_a = sum(alphas) / len(alphas) if alphas else 0
        net_alphas = [p.get("netAlphaPct", 0) for p in hv if p.get("netAlphaPct") is not None]
        avg_na = sum(net_alphas) / len(net_alphas) if net_alphas else 0
        print(f"  {h}: 总{len(hp)} 已验{len(hv)} 扣费后跑赢{len(hh)} 命中率{r:.1f}% 毛alpha{avg_a:+.2f}% 净alpha{avg_na:+.2f}%")


def cmd_recheck(args):
    """重算已验证记录的扣费后净收益(8-11手续费建模后,补算旧记录的费用拖累)。
    用已存储的 actualChangePct(到期日毛涨幅)反推费用,不重新取价(避免用今日价污染到期日兑现)。
    """
    data = _load()
    preds = data.get("predictions", [])
    recomputed = 0
    for p in preds:
        if not p.get("verified"):
            continue
        chg = p.get("actualChangePct")
        if chg is None:
            continue
        capital = p.get("capital", DEFAULT_CAPITAL)
        position_pct = p.get("positionPct", DEFAULT_POSITION_PCT)
        bench_chg = p.get("benchChangePct")
        # 毛超额(若旧记录无alphaPct,现算)
        alpha = (chg - bench_chg) if bench_chg is not None else chg
        if p.get("alphaPct") is None:
            p["alphaPct"] = round(alpha, 2)
        net_chg = _net_return_pct(chg, capital, position_pct)
        fee_drag = chg - net_chg
        p["feeDragPct"] = round(fee_drag, 2)
        p["netActualChangePct"] = round(net_chg, 2)
        net_alpha = alpha - fee_drag
        p["netAlphaPct"] = round(net_alpha, 2)
        p["hit"] = net_alpha > 0  # 重判命中(扣费后口径)
        recomputed += 1
    # 重算总命中
    total = sum(1 for p in preds if p.get("verified"))
    total_hits = sum(1 for p in preds if p.get("hit"))
    rate = (total_hits / total * 100) if total else 0
    alphas = [p.get("alphaPct", 0) for p in preds if p.get("verified") and p.get("alphaPct") is not None]
    avg_alpha = sum(alphas) / len(alphas) if alphas else 0
    net_alphas = [p.get("netAlphaPct", 0) for p in preds if p.get("verified") and p.get("netAlphaPct") is not None]
    avg_net_alpha = sum(net_alphas) / len(net_alphas) if net_alphas else 0
    fee_drags = [p.get("feeDragPct", 0) for p in preds if p.get("verified") and p.get("feeDragPct") is not None]
    avg_fee_drag = sum(fee_drags) / len(fee_drags) if fee_drags else 0
    data["stats"] = {"totalPredictions": len(preds), "verified": total, "hits": total_hits, "hitRate": round(rate, 1), "avgAlpha": round(avg_alpha, 2), "avgNetAlpha": round(avg_net_alpha, 2), "avgFeeDrag": round(avg_fee_drag, 2), "benchChange": data.get("stats", {}).get("benchChange")}
    _save(data)
    print(f"forecast_tracker: 重算 {recomputed} 条已验证记录的扣费后净收益")
    print(f"  毛口径命中率 {sum(1 for p in preds if p.get('verified') and p.get('alphaPct',0)>0)}/{total} → 扣费后命中率 {rate:.1f}% ({total_hits}/{total})")
    print(f"  平均毛alpha {avg_alpha:+.2f}% → 扣费后净alpha {avg_net_alpha:+.2f}% (手续费拖累 {avg_fee_drag:.2f}%)")


def main():
    p = argparse.ArgumentParser(description="未来预测兑现跟踪器")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("record", help="记录一次预测")
    pr.add_argument("--run-id", required=True)
    pr.add_argument("--horizon", default="波段")
    pr.add_argument("--as-of", default="", help="预测基准日 YYYYMMDD")
    pr.add_argument("--capital", type=float, default=DEFAULT_CAPITAL, help=f"账户资金(元),默认{DEFAULT_CAPITAL}用于算手续费")
    pr.add_argument("--json", default="")
    pr.add_argument("--json-file", default="")
    pr.set_defaults(func=cmd_record)
    pc = sub.add_parser("check", help="回看历史预测兑现")
    pc.add_argument("--as-of", default="")
    pc.set_defaults(func=cmd_check)
    ps = sub.add_parser("stats", help="查命中率")
    ps.set_defaults(func=cmd_stats)
    prc = sub.add_parser("recheck", help="重算已验证记录的扣费后净收益(手续费建模后补算)")
    prc.set_defaults(func=cmd_recheck)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
