#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""共享数据预取——workflow Phase 0 调用,为后续 agent 提供统一的宏观+市场快照。

用法:
  python scripts/prefetch_shared.py --run-id 20260709_short-term-picks
  python scripts/prefetch_shared.py --run-id 20260709_hot-trends --extra hot
  python scripts/prefetch_shared.py --run-id 20260709_single-stock-deep --ticker 600519

输出: data/runs/{run-id}/_shared.json
  包含 indices, marketBreadth, sectorRanking, newsHeadlines, macroIndicators, stock(若指定)

数据源降级链(与项目一致):
  cn_fetch.py(rank, 免密钥) → 东方财富 HTTP(clist/涨停池) → 空则标注 missing

不依赖 MCP(脚本用 urllib+SSL 自处理,避免 Python certifi 企业证书问题)。
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import ssl

# Windows GBK → UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CTX = ssl._create_unverified_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def _http_json(url, timeout=15):
    """GET URL → parsed JSON, with retry."""
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt == 1:
                return {"_error": f"{type(e).__name__}: {str(e)[:120]}"}
            time.sleep(0.5)
    return {"_error": "unknown"}


def fetch_rank(sort="changepercent", num=80):
    """新浪榜单 via cn_fetch.py"""
    try:
        r = subprocess.run(
            [sys.executable, "scripts/cn_fetch.py", "rank", sort, str(num)],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace"
        )
        if r.returncode == 0 and r.stdout.strip():
            lines = r.stdout.strip().split("\n")
            if len(lines) > 1:
                return {"source": "sina_rank", "sort": sort, "count": len(lines) - 1, "tsv": r.stdout.strip()}
        return {"_error": f"cn_fetch rank exit={r.returncode}", "stderr": r.stderr[:200]}
    except Exception as e:
        return {"_error": str(e)[:120]}


def fetch_a_stock_data(run_id):
    """调用 data_prefetch.py（a-stock-data 端点，不封IP）"""
    try:
        r = subprocess.run(
            [sys.executable, "scripts/data_prefetch.py",
             "--run-id", run_id,
             "--section", "index,hot,zt,industry,north,dragon,sentiment"],
            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace"
        )
        if r.returncode == 0:
            return {"source": "a-stock-data", "summary": r.stdout.strip()[:3000]}
        return {"_error": f"data_prefetch exit={r.returncode}", "stderr": r.stderr[:200]}
    except Exception as e:
        return {"_error": str(e)[:120]}


def fetch_market_overview():
    """东方财富市场概览 via sector_data.py"""
    try:
        r = subprocess.run(
            [sys.executable, "scripts/sector_data.py", "--market-overview"],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace",
            cwd=".claude/skills/findata-toolkit-cn"
        )
        if r.returncode == 0:
            return {"source": "sector_data", "text": r.stdout.strip()[:2000]}
        return {"_error": f"sector_data exit={r.returncode}"}
    except Exception as e:
        return {"_error": str(e)[:120]}


def fetch_radar_core_signals():
    """调用 market_radar 获取核心信号(fast 模式:跳过 slow 端点,HTTP 并行)"""
    try:
        r = subprocess.run(
            [sys.executable, "scripts/market_radar.py",
             "--section", "index,sector,news,capital", "--fast", "--summary"],
            capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace"
        )
        if r.returncode == 0:
            return {"source": "market_radar", "summary": r.stdout.strip()[:3000]}
        return {"_error": f"market_radar exit={r.returncode}", "stderr": r.stderr[:200]}
    except Exception as e:
        return {"_error": str(e)[:120]}


def fetch_zt_pool():
    """涨停池"""
    try:
        r = subprocess.run(
            [sys.executable, "scripts/sector_data.py", "--zt-pool"],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace",
            cwd=".claude/skills/findata-toolkit-cn"
        )
        if r.returncode == 0:
            return {"source": "sector_data", "text": r.stdout.strip()[:2000]}
        return {"_error": f"zt_pool exit={r.returncode}"}
    except Exception as e:
        return {"_error": str(e)[:120]}


def fetch_index_realtime():
    """腾讯实时指数"""
    try:
        url = "http://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10, context=CTX) as resp:
            raw = resp.read().decode("gbk", errors="ignore")
        indices = {}
        for line in raw.strip().split(";"):
            if "~" not in line:
                continue
            parts = line.split("~")
            if len(parts) > 45:
                code = parts[2]
                indices[code] = {
                    "name": parts[1], "price": parts[3], "prevClose": parts[4],
                    "changePct": parts[32], "amount": parts[37], "turnover": parts[38]
                }
        return {"source": "tencent_qt", "data": indices}
    except Exception as e:
        return {"_error": str(e)[:120]}


def fetch_sector_ranking():
    """东方财富概念板块涨幅 Top20"""
    url = ("http://push2.eastmoney.com/api/qt/clist/get?"
           "pn=1&pz=20&po=1&fid=f3&fs=m:90+t:2&fields=f2,f3,f6,f8,f12,f14&np=1&fltt=2&invt=2")
    data = _http_json(url)
    if "_error" not in data and data.get("data", {}).get("diff"):
        items = [{"code": d.get("f12"), "name": d.get("f14"), "changePct": d.get("f3"),
                   "amount": d.get("f6"), "turnover": d.get("f8")}
                 for d in data["data"]["diff"][:20]]
        return {"source": "eastmoney_clist", "data": items}
    return data


def fetch_stock_snapshot(code):
    """腾讯个股快照"""
    prefix = "sh" if code.startswith("6") else "sz"
    sid = prefix + code
    try:
        url = f"http://qt.gtimg.cn/q={sid}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10, context=CTX) as resp:
            raw = resp.read().decode("gbk", errors="ignore")
        parts = raw.split("~")
        if len(parts) > 45:
            return {
                "source": "tencent_qt", "code": code,
                "name": parts[1], "price": parts[3], "prevClose": parts[4],
                "changePct": parts[32], "amount": parts[37], "turnover": parts[38],
                "pe": parts[39], "mktCap": parts[45]
            }
        return {"_error": "parse failed"}
    except Exception as e:
        return {"_error": str(e)[:120]}


def main():
    p = argparse.ArgumentParser(description="共享数据预取(50并发异步引擎)")
    p.add_argument("--run-id", required=True, help="运行 ID,如 20260716_short-term-picks")
    p.add_argument("--extra", default="hot", help="额外数据: hot(涨停池+板块), stock(个股快照)")
    p.add_argument("--ticker", default="", help="个股代码")
    p.add_argument("--max-workers", type=int, default=50, help="并发数(默认50)")
    args = p.parse_args()

    run_dir = f"data/runs/{args.run_id}"
    os.makedirs(run_dir, exist_ok=True)
    out_path = os.path.join(run_dir, "_shared.json")

    sys.stderr.write(f"[prefetch] 启动 50 并发异步预取 → {out_path}\n")
    t0 = time.time()

    # ── 第一步: 调用 data_prefetch.py (50并发, 覆盖 index/hot/zt/industry/north/dragon/news/capital/sentiment) ──
    section = "all"
    if args.extra and "hot" in args.extra:
        section = "index,hot,zt,industry,north,dragon,news,capital,sentiment,sector"
    prefetch_cmd = [
        sys.executable, "scripts/data_prefetch.py",
        "--run-id", args.run_id,
        "--section", section,
        "--max-workers", str(args.max_workers),
    ]
    if args.ticker:
        prefetch_cmd.extend(["--ticker", args.ticker])

    try:
        r = subprocess.run(prefetch_cmd, capture_output=True, text=True,
                           timeout=60, encoding="utf-8", errors="replace")
        prefetch_ok = r.returncode == 0
        prefetch_stdout = r.stdout.strip()
        prefetch_stderr = r.stderr.strip()
    except subprocess.TimeoutExpired:
        prefetch_ok = False
        prefetch_stdout = ""
        prefetch_stderr = "timeout(60s)"

    # ── 第二步: 读取 data_prefetch.py 的输出 _prefetch.json ──
    prefetch_path = os.path.join(run_dir, "_prefetch.json")
    prefetch_data = {}
    if os.path.exists(prefetch_path):
        try:
            with open(prefetch_path, "r", encoding="utf-8") as f:
                prefetch_data = json.load(f)
        except Exception:
            pass

    # ── 第三步: 补充数据(新浪榜单 + 市场概览, 走 cn_fetch.py) ──
    rank_data = fetch_rank("changepercent", 50)
    market_data = fetch_market_overview()

    # ── 第三步b: 国际形势快照(隔夜美股+大宗, 走 global_snapshot.py) ──
    # 轻量增强:为 macro-strategist 提供国际传导路径的实证数据(非新闻拼凑)
    global_snap = {}
    try:
        from global_snapshot import build_snapshot
        global_snap = build_snapshot()
    except Exception as e:
        sys.stderr.write(f"[prefetch] global_snapshot 失败: {e}\n")
        global_snap = {"_error": str(e)[:200]}

    # ── 合并输出 _shared.json ──
    shared = {
        "runId": args.run_id,
        "fetchedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        # 来自 data_prefetch.py (50 并发)
        "indices": prefetch_data.get("indices", {}),
        "limit_up_sentiment": prefetch_data.get("limit_up_sentiment", {}),
        "northbound": prefetch_data.get("northbound", {}),
        "hot_tags": prefetch_data.get("hot_tags", []),
        "dragon_tiger": prefetch_data.get("dragon_tiger", {}),
        "news_headlines": prefetch_data.get("news_headlines", []),
        "coreSignals": prefetch_data.get("coreSignals", []),
        "prefetch_stats": prefetch_data.get("_stats", {}),
        # 来自 cn_fetch.py / sector_data.py
        "rankChangePct": rank_data,
        "marketBreadth": market_data,
        # 来自 global_snapshot.py (隔夜美股三大指数+大宗商品+对A股传导路径)
        "globalSnapshot": global_snap,
    }

    elapsed = round(time.time() - t0, 1)
    stats = shared.get("prefetch_stats", {})
    sys.stderr.write(
        f"[prefetch] 完成: {stats.get('ok', '?')}/{stats.get('total', '?')} 成功, "
        f"异步耗时 {stats.get('elapsed', '?')}s, 总耗时 {elapsed}s\n"
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(shared, f, ensure_ascii=False, indent=2)

    # stdout 输出摘要供 workflow ctx 引用
    summary_lines = []
    idx = shared.get("indices", {})
    if isinstance(idx, dict):
        for code in ["000001", "399001", "399006"]:
            info = idx.get(code, {})
            if info:
                summary_lines.append(f"{info.get('name','?')} {info.get('price','?')}({info.get('changePct','?')}%)")
    signals = shared.get("coreSignals", [])
    for s in signals[:5]:
        summary_lines.append(f"{s.get('level','')} {s.get('text','')}")

    print(f"预取完成({elapsed}s): {' | '.join(summary_lines[:4]) or '数据见 _shared.json'}")


if __name__ == "__main__":
    main()
