#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""推荐追踪与持仓视图——workflow 结束时记录推荐,workflow 开始时更新行情。

用法:
  python scripts/portfolio_tracker.py record --run-id 20260709_short-term-picks --json '{"topN":[...]}'
  python scripts/portfolio_tracker.py update
  python scripts/portfolio_tracker.py summary

数据文件: data/portfolio.json
  {
    recommendations: [
      {code, name, recommendedAt, recommendedPrice, role, workflow, confidence,
       currentPrice, changePct, status: "active"|"expired"|"closed"}
    ],
    lastUpdated: "..."
  }
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import ssl

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CTX = ssl._create_unverified_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
PORTFOLIO_PATH = "data/portfolio.json"


def _load():
    if os.path.exists(PORTFOLIO_PATH):
        with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"recommendations": [], "lastUpdated": None}


def _save(data):
    os.makedirs("data", exist_ok=True)
    data["lastUpdated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _fetch_prices(codes):
    """批量取腾讯实时价格"""
    sids = []
    for c in codes:
        prefix = "sh" if str(c).startswith("6") else "sz"
        sids.append(prefix + str(c))
    if not sids:
        return {}
    url = f"http://qt.gtimg.cn/q={','.join(sids)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as resp:
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
            prices[code] = {
                "price": parts[3], "prevClose": parts[4],
                "changePct": parts[32], "amount": parts[37]
            }
    return prices


def cmd_record(args):
    """记录新推荐"""
    data = _load()
    try:
        if args.json_file:
            with open(args.json_file, "r", encoding="utf-8") as f:
                rec = json.load(f)
        else:
            rec = json.loads(args.json)
    except Exception as e:
        sys.stderr.write(f"JSON 解析失败: {e}\n")
        return 2

    topN = rec.get("topN", [])
    run_id = args.run_id
    as_of = run_id.split("_")[0] if "_" in run_id else run_id

    added = 0
    for item in topN:
        code = str(item.get("code", ""))
        if not code:
            continue
        # 检查是否已有同 code 的 active 推荐
        existing = [r for r in data["recommendations"] if r["code"] == code and r.get("status") == "active"]
        if existing:
            sys.stderr.write(f"  {code} 已有活跃推荐,跳过\n")
            continue

        data["recommendations"].append({
            "code": code,
            "name": item.get("name", ""),
            "recommendedAt": as_of,
            "recommendedPrice": item.get("price") or item.get("recommendedPrice"),
            "role": item.get("role", ""),
            "workflow": run_id.split("_", 1)[1] if "_" in run_id else run_id,
            "confidence": rec.get("confidence", ""),
            "currentPrice": None,
            "changePct": None,
            "status": "active",
        })
        added += 1

    _save(data)
    sys.stderr.write(f"记录 {added} 条推荐\n")
    print(f"portfolio: 新增 {added} 条,总计 {len([r for r in data['recommendations'] if r.get('status')=='active'])} 条活跃推荐")
    return 0


def cmd_update(args):
    """更新所有活跃推荐的当前价格"""
    data = _load()
    active = [r for r in data["recommendations"] if r.get("status") == "active"]
    if not active:
        print("portfolio: 无活跃推荐需更新")
        return 0

    codes = list(set(r["code"] for r in active))
    prices = _fetch_prices(codes)
    updated = 0
    for rec in active:
        p = prices.get(rec["code"])
        if p:
            rec["currentPrice"] = p["price"]
            rec["currentChangePct"] = p["changePct"]
            if rec.get("recommendedPrice"):
                try:
                    rec_price = float(rec["recommendedPrice"])
                    cur_price = float(p["price"])
                    if rec_price > 0:
                        rec["profitPct"] = round((cur_price - rec_price) / rec_price * 100, 2)
                except (ValueError, TypeError):
                    pass
            updated += 1

    _save(data)
    sys.stderr.write(f"更新 {updated}/{len(active)} 条\n")

    # 输出摘要
    parts = []
    for r in active[:10]:
        profit = r.get("profitPct")
        profit_str = f"{profit:+.1f}%" if profit is not None else "?"
        parts.append(f"{r['code']}({r.get('name','?')}) {profit_str}")
    print(f"portfolio: {updated} 条已更新 | " + " ".join(parts))
    return 0


def cmd_summary(args):
    """输出持仓视图摘要(供 workflow ctx 引用)"""
    data = _load()
    active = [r for r in data["recommendations"] if r.get("status") == "active"]
    if not active:
        print("portfolio: 无活跃推荐")
        return

    lines = [f"## 活跃推荐追踪({len(active)} 只)"]
    lines.append("| 代码 | 名称 | 推荐日 | 推荐价 | 现价 | 盈亏 | 角色 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in active:
        profit = r.get("profitPct")
        profit_str = f"{profit:+.1f}%" if profit is not None else "待更新"
        lines.append(f"| {r['code']} | {r.get('name','?')} | {r.get('recommendedAt','?')} | "
                      f"{r.get('recommendedPrice','?')} | {r.get('currentPrice','?')} | "
                      f"{profit_str} | {r.get('role','?')} |")

    # 统计
    with_profit = [r for r in active if r.get("profitPct") is not None]
    if with_profit:
        profits = [r["profitPct"] for r in with_profit]
        win = sum(1 for p in profits if p > 0)
        avg = sum(profits) / len(profits)
        lines.append(f"\n胜率 {win}/{len(with_profit)} ({win*100//len(with_profit)}%) | 平均盈亏 {avg:+.1f}%")

    print("\n".join(lines))


def main():
    p = argparse.ArgumentParser(description="推荐追踪与持仓视图")
    sub = p.add_subparsers(dest="cmd")

    p_rec = sub.add_parser("record", help="记录新推荐")
    p_rec.add_argument("--run-id", required=True)
    p_rec.add_argument("--json", default="", help="JSON 字符串(不推荐,用 --json-file)")
    p_rec.add_argument("--json-file", default="", help="JSON 文件路径(推荐)")

    sub.add_parser("update", help="更新活跃推荐行情")
    sub.add_parser("summary", help="输出持仓视图摘要")

    args = p.parse_args()
    if args.cmd == "record":
        return cmd_record(args)
    elif args.cmd == "update":
        return cmd_update(args)
    elif args.cmd == "summary":
        return cmd_summary(args)
    else:
        p.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
