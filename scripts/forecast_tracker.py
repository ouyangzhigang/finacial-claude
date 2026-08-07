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
        pred = {
            "code": code,
            "name": t.get("name", ""),
            "horizon": horizon,
            "windowDays": window_days,
            "predictDate": predict_date,
            "expireDate": (datetime.strptime(predict_date, "%Y%m%d") + timedelta(days=window_days)).strftime("%Y%m%d"),
            "basePrice": base_price,
            "benchBase": bench_base,  # 大盘基准价(预测日),供算alpha超额
            "role": t.get("role", ""),
            "position": t.get("position", ""),
            "reasoningChain": t.get("reasoningChain") or t.get("signals") or [],
            "runId": args.run_id,
            "verified": False,
            "actualChangePct": None,
            "benchChangePct": None,  # 大盘同期涨幅
            "alphaPct": None,  # 超额收益=个股涨幅-大盘涨幅(真选股alpha)
            "hit": None,  # True=跑赢大盘(alpha>0)/False=跑输/None=未到期
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
        base = p.get("basePrice")
        if base and cur and base > 0:
            chg = (cur - base) / base * 100
            p["actualChangePct"] = round(chg, 2)
            p["benchChangePct"] = round(bench_chg, 2) if bench_chg is not None else None
            # alpha=个股涨幅-大盘涨幅(真选股超额能力)
            alpha = chg - bench_chg if bench_chg is not None else chg
            p["alphaPct"] = round(alpha, 2)
            p["hit"] = alpha > 0  # 跑赢大盘才算命中(非仅绝对涨跌)
            p["verified"] = True
            checked += 1
            if p["hit"]:
                hits += 1
    _save(data)
    total = sum(1 for p in preds if p.get("verified"))
    total_hits = sum(1 for p in preds if p.get("hit"))
    rate = (total_hits / total * 100) if total else 0
    # alpha统计
    alphas = [p.get("alphaPct", 0) for p in preds if p.get("verified") and p.get("alphaPct") is not None]
    avg_alpha = sum(alphas) / len(alphas) if alphas else 0
    data["stats"] = {"totalPredictions": len(preds), "verified": total, "hits": total_hits, "hitRate": round(rate, 1), "avgAlpha": round(avg_alpha, 2), "benchChange": round(bench_chg, 2) if bench_chg else None}
    _save(data)
    print(f"forecast_tracker: 本次回看 {checked} 只,命中 {hits} 只。累计命中率 {rate:.1f}% ({total_hits}/{total})")
    print(f"  待到期(未到回看日): {len(pending)} 只")


def cmd_stats(args):
    """查命中率+alpha超额收益"""
    data = _load()
    stats = data.get("stats", {})
    preds = data.get("predictions", [])
    print(f"=== 预测兑现统计(alpha口径:跑赢大盘才算命中) ===")
    print(f"总预测: {len(preds)} 只")
    print(f"已回看: {stats.get('verified', 0)} 只")
    print(f"跑赢大盘: {stats.get('hits', 0)} 只")
    print(f"命中率(跑赢大盘): {stats.get('hitRate', 0)}%")
    print(f"平均alpha超额: {stats.get('avgAlpha', 0)}%  (大盘同期: {stats.get('benchChange', '?')}%)")
    # 按周期分
    for h in HORIZON_DAYS:
        hp = [p for p in preds if p.get("horizon") == h]
        hv = [p for p in hp if p.get("verified")]
        hh = [p for p in hv if p.get("hit")]
        r = (len(hh) / len(hv) * 100) if hv else 0
        alphas = [p.get("alphaPct", 0) for p in hv if p.get("alphaPct") is not None]
        avg_a = sum(alphas) / len(alphas) if alphas else 0
        print(f"  {h}: 总{len(hp)} 已验{len(hv)} 跑赢大盘{len(hh)} 命中率{r:.1f}% 平均alpha{avg_a:+.2f}%")


def main():
    p = argparse.ArgumentParser(description="未来预测兑现跟踪器")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("record", help="记录一次预测")
    pr.add_argument("--run-id", required=True)
    pr.add_argument("--horizon", default="波段")
    pr.add_argument("--as-of", default="", help="预测基准日 YYYYMMDD")
    pr.add_argument("--json", default="")
    pr.add_argument("--json-file", default="")
    pr.set_defaults(func=cmd_record)
    pc = sub.add_parser("check", help="回看历史预测兑现")
    pc.add_argument("--as-of", default="")
    pc.set_defaults(func=cmd_check)
    ps = sub.add_parser("stats", help="查命中率")
    ps.set_defaults(func=cmd_stats)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
