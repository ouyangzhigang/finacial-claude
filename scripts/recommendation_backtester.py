#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
recommendation_backtester.py — 改造8: 执行反馈闭环
==============================================
扫描 data/portfolio.json 的历史推荐, 用 cn_fetch.py kline 取 T+1/T+5/T+14 收盘价,
计算每条推荐的实际涨幅 + 命中率(涨幅≥2%计命中) + 因子 IC 衰减(composite_score vs T+5 涨幅 Spearman).

输出:
  - data/backtest_report.json  (每条推荐 T+N 涨幅 + 命中率汇总)
  - data/factor_ic.json        (因子 IC + 衰减, 供 governor 报告引用)

用法:
  python scripts/recommendation_backtester.py
  python scripts/recommendation_backtester.py --lookback 60   # 只看近60天推荐
"""
import sys, os, json, math, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO = "data/portfolio.json"
RUNS_DIR = "data/runs"
OUT_REPORT = "data/backtest_report.json"
OUT_IC = "data/factor_ic.json"
HIT_THRESHOLD = 2.0  # 涨幅≥2%计命中


def _cn_kline(code, n=30):
    """调 cn_fetch.py kline 取日K, 返回 [[date, open, close, high, low, vol], ...]"""
    import subprocess
    prefix = "sh" if code.startswith("6") else ("sz" if code.startswith(("0", "3")) else "bj")
    try:
        r = subprocess.run(
            ["python", "scripts/cn_fetch.py", "kline", f"{prefix}{code}", str(n)],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace"
        )
        txt = r.stdout.strip()
        # cn_fetch kline 输出 JSON 数组
        return json.loads(txt) if txt.startswith("[") else []
    except Exception:
        return []


def _find_close_after(klines, target_date_str, t_days):
    """从日K找 target_date 之后第 t_days 个交易日的收盘价.
    klines: [[date, open, close, high, low, vol], ...] (date=YYYY-MM-DD)
    target_date_str: 推荐日 YYYY-MM-DD
    """
    # 按 date 排序
    sorted_kl = sorted(klines, key=lambda x: x[0])
    future = [k for k in sorted_kl if k[0] > target_date_str]
    if len(future) >= t_days:
        try:
            return float(future[t_days - 1][2])
        except (ValueError, IndexError):
            return None
    return None


def _spearman_ic(scores, returns):
    """简化 Spearman 等级相关 (IC). scores/returns 同长度对齐."""
    n = len(scores)
    if n < 3:
        return None
    def rank(lst):
        idx = sorted(range(len(lst)), key=lambda i: lst[i])
        r = [0] * len(lst)
        for i, ix in enumerate(idx):
            r[ix] = i + 1
        return r
    try:
        r1, r2 = rank(scores), rank(returns)
        d2 = sum((a - b) ** 2 for a, b in zip(r1, r2))
        return round(1 - 6 * d2 / (n * (n * n - 1)), 3)
    except Exception:
        return None


def _load_composite_scores(recommended_at):
    """根据推荐日找对应的 factor_scores.json, 提取 composite_score {code: score}."""
    # 推荐日 YYYY-MM-DD → YYYYMMDD, 找 run 目录
    ymd = recommended_at.replace("-", "")[:8]
    if not os.path.isdir(RUNS_DIR):
        return {}
    result = {}
    for d in os.listdir(RUNS_DIR):
        if d.startswith(ymd) and d.endswith("short-term-picks"):
            fs = os.path.join(RUNS_DIR, d, "factor_scores.json")
            if os.path.exists(fs):
                try:
                    with open(fs, encoding="utf-8") as f:
                        data = json.load(f)
                    for s in data.get("stocks", []):
                        code = s.get("symbol", "").replace("sh", "").replace("sz", "")
                        result[code] = s.get("composite_score", 0)
                except Exception:
                    pass
    return result


def main():
    if not os.path.exists(PORTFOLIO):
        print("⚠️ 无 portfolio.json, 无推荐可回测", file=sys.stderr)
        return
    with open(PORTFOLIO, encoding="utf-8") as f:
        pf = json.load(f)
    recs = [r for r in pf.get("recommendations", []) if r.get("status") == "active" or r.get("recommendedPrice")]

    lookback = 60
    today = datetime.date.today()
    cutoff = (today - datetime.timedelta(days=lookback)).isoformat()
    recs = [r for r in recs if (r.get("recommendedAt") or "") >= cutoff]

    if not recs:
        print("⚠️ 近期无推荐可回测", file=sys.stderr)
        return

    print(f"🔄 回测 {len(recs)} 条推荐 (近{lookback}天)...")

    results = []
    ic_scores, ic_returns = [], []
    for rec in recs:
        code = str(rec.get("code", ""))
        rec_at = rec.get("recommendedAt", "")  # YYYY-MM-DD
        rec_price = float(rec.get("recommendedPrice") or 0)
        if not code or not rec_at or rec_price <= 0:
            continue

        klines = _cn_kline(code, 30)
        if not klines:
            continue

        p1 = _find_close_after(klines, rec_at, 1)
        p5 = _find_close_after(klines, rec_at, 5)
        p14 = _find_close_after(klines, rec_at, 14)
        r1 = round((p1 - rec_price) / rec_price * 100, 2) if p1 else None
        r5 = round((p5 - rec_price) / rec_price * 100, 2) if p5 else None
        r14 = round((p14 - rec_price) / rec_price * 100, 2) if p14 else None

        hit = r5 is not None and r5 >= HIT_THRESHOLD
        results.append({
            "code": code, "name": rec.get("name", ""),
            "recommendedAt": rec_at, "recommendedPrice": rec_price,
            "t1_return": r1, "t5_return": r5, "t14_return": r14,
            "hit": hit, "workflow": rec.get("workflow", ""),
            "role": rec.get("role", ""),
        })

        if r5 is not None:
            ic_scores.append(rec.get("_composite") or 0)
            ic_returns.append(r5)

    # 补: 用 factor_scores 给每条推荐补 composite_score
    for r in results:
        if not r.get("_composite"):
            fs = _load_composite_scores(r["recommendedAt"])
            r["_composite"] = fs.get(r["code"], 0)
    ic_scores = [r.get("_composite", 0) for r in results if r.get("t5_return") is not None]
    ic_returns = [r["t5_return"] for r in results if r.get("t5_return") is not None]

    total = len(results)
    hits = sum(1 for r in results if r["hit"])
    hit_rate = round(hits / total * 100, 1) if total else 0
    avg_t5 = round(sum(r["t5_return"] for r in results if r["t5_return"] is not None) / max(1, len([r for r in results if r["t5_return"] is not None])), 2)

    ic = _spearman_ic(ic_scores, ic_returns)

    report = {
        "asOf": today.isoformat(),
        "total_recommendations": total,
        "hit_rate": hit_rate,
        "hit_threshold_pct": HIT_THRESHOLD,
        "avg_t5_return": avg_t5,
        "details": results,
    }
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    ic_out = {
        "asOf": today.isoformat(),
        "factor_ic_t5": ic,  # composite_score vs T+5 涨幅的 Spearman IC
        "sample_size": len(ic_scores),
        "interpretation": (
            "IC>0.1 因子有正向预测力" if (ic or 0) > 0.1 else
            "IC<-0.1 因子反向(需调权)" if (ic or 0) < -0.1 else
            "IC≈0 因子无预测力(数据不足或失效)"
        ),
    }
    with open(OUT_IC, "w", encoding="utf-8") as f:
        json.dump(ic_out, f, ensure_ascii=False, indent=2)

    print(f"✅ 回测完成: {total}条推荐, 命中率{hit_rate}%, 平均T+5涨幅{avg_t5}%")
    print(f"   因子IC(T+5)={ic} (样本{len(ic_scores)}) → {ic_out['interpretation']}")
    print(f"   报告: {OUT_REPORT} / {OUT_IC}")


if __name__ == "__main__":
    main()
