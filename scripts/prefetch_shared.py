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
    """调用 market_radar 获取核心信号(快速模式,只扫 index+news+sector+capital)"""
    try:
        r = subprocess.run(
            [sys.executable, "scripts/market_radar.py",
             "--section", "index,sector,news,capital", "--summary"],
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
    p = argparse.ArgumentParser(description="共享数据预取")
    p.add_argument("--run-id", required=True, help="运行 ID,如 20260709_short-term-picks")
    p.add_argument("--extra", default="", help="额外数据类型: hot(涨停池+板块排名), stock(个股快照)")
    p.add_argument("--ticker", default="", help="个股代码(extra=stock 时用)")
    args = p.parse_args()

    run_dir = f"data/runs/{args.run_id}"
    os.makedirs(run_dir, exist_ok=True)
    out_path = os.path.join(run_dir, "_shared.json")

    sys.stderr.write(f"[prefetch] 开始预取 → {out_path}\n")
    t0 = time.time()

    shared = {
        "runId": args.run_id,
        "fetchedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "indices": fetch_index_realtime(),
        "rankChangePct": fetch_rank("changepercent", 50),
        "rankAmount": fetch_rank("amount", 50),
        "marketBreadth": fetch_market_overview(),
        "radarSignals": fetch_radar_core_signals(),
    }

    if "hot" in args.extra:
        shared["ztPool"] = fetch_zt_pool()
        shared["sectorRanking"] = fetch_sector_ranking()

    if args.ticker:
        shared["stock"] = fetch_stock_snapshot(args.ticker)

    elapsed = round(time.time() - t0, 1)
    ok_count = sum(1 for v in shared.values() if isinstance(v, dict) and "_error" not in v)
    total = sum(1 for v in shared.values() if isinstance(v, dict) and not isinstance(v, str))
    sys.stderr.write(f"[prefetch] 完成: {ok_count}/{total} 成功, 耗时 {elapsed}s\n")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(shared, f, ensure_ascii=False, indent=2)

    # stdout 输出摘要供 workflow ctx 引用
    summary_parts = []
    idx = shared.get("indices", {})
    if isinstance(idx, dict) and "data" in idx:
        for code, info in idx["data"].items():
            summary_parts.append(f"{info.get('name','?')} {info.get('price','?')} ({info.get('changePct','?')}%)")
    print(f"预取完成({elapsed}s): {'; '.join(summary_parts[:4]) or '指数数据见 _shared.json'}")


if __name__ == "__main__":
    main()
