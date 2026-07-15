#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""a-stock-data 数据预取 — workflow Phase 0 调用，为后续 agent 提供批量市场数据。

数据源优先级（不封IP优先）：
  1. mootdx（TCP 7709）— K线/报价/财务快照，不封IP
  2. 腾讯财经（HTTP）— PE/PB/市值/换手率，不封IP
  3. 同花顺热点（HTTP）— 强势股+题材归因，73ms
  4. 东财（HTTP，内置限流）— 涨停池/行业排名/龙虎榜/北向

用法:
  python scripts/data_prefetch.py --run-id 20260715_short-term-picks
  python scripts/data_prefetch.py --run-id xxx --codes 600519,000858,300476
  python scripts/data_prefetch.py --run-id xxx --section index,hot,zt,industry,north,dragon
"""
import argparse
import json
import os
import socket
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date as _date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ═══════════════════════════════════════════════════════════
# mootdx（通达信 TCP 7709，不封IP）
# ═══════════════════════════════════════════════════════════

_TDX_SERVERS = [
    ('119.97.185.59', 7709), ('124.70.133.119', 7709), ('116.205.183.150', 7709),
    ('123.60.73.44', 7709),  ('116.205.163.254', 7709), ('121.36.225.169', 7709),
]

def _tdx_client():
    """创建 mootdx 客户端（规避 0.11.x BESTIP bug）"""
    try:
        from mootdx.quotes import Quotes
    except ImportError:
        return None
    for ip, port in _TDX_SERVERS:
        try:
            with socket.create_connection((ip, port), timeout=3):
                return Quotes.factory(market='std', server=(ip, port))
        except Exception:
            continue
    try:
        return Quotes.factory(market='std', bestip=True)
    except Exception:
        return None


def fetch_tdx_klines(codes, count=30):
    """mootdx 批量拉日K线（不复权）"""
    client = _tdx_client()
    if not client:
        return {"_error": "mootdx unavailable"}
    result = {}
    for code in codes[:50]:  # 限制批量数
        try:
            bars = client.bars(symbol=code, frequency=9, offset=count)
            if bars is not None and len(bars) > 0:
                klines = []
                for _, row in bars.iterrows():
                    klines.append([
                        str(row.get('datetime', '')),
                        float(row.get('open', 0)),
                        float(row.get('close', 0)),
                        float(row.get('high', 0)),
                        float(row.get('low', 0)),
                        float(row.get('vol', 0)),
                    ])
                result[code] = klines
        except Exception as e:
            result[code] = {"_error": str(e)[:100]}
    return result


def fetch_tdx_quotes(codes):
    """mootdx 批量实时报价（46字段）"""
    client = _tdx_client()
    if not client:
        return {"_error": "mootdx unavailable"}
    try:
        quotes = client.quotes(symbol=codes[:50])
        if quotes is not None and len(quotes) > 0:
            result = {}
            for _, row in quotes.iterrows():
                code = str(row.get('code', row.name if hasattr(row, 'name') else ''))
                result[code] = {
                    "price": float(row.get('price', 0)),
                    "open": float(row.get('open', 0)),
                    "high": float(row.get('high', 0)),
                    "low": float(row.get('low', 0)),
                    "last_close": float(row.get('last_close', 0)),
                    "vol": float(row.get('vol', 0)),
                    "amount": float(row.get('amount', 0)),
                }
            return result
    except Exception as e:
        return {"_error": str(e)[:100]}
    return {}


# ═══════════════════════════════════════════════════════════
# 腾讯财经（HTTP，不封IP）
# ═══════════════════════════════════════════════════════════

def fetch_tencent_quotes(codes):
    """腾讯财经批量行情（PE/PB/市值/换手率/涨跌停）"""
    prefixed = []
    for c in codes:
        c = str(c).strip()
        # 已有前缀(sh/sz/bj)则跳过
        if c.startswith(("sh", "sz", "bj")):
            prefixed.append(c)
        elif c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed[:80])
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")
    except Exception as e:
        return {"_error": str(e)[:100]}

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "last_close": float(vals[4]) if vals[4] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "amount_wan": float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "float_mcap_yi": float(vals[45]) if vals[45] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "limit_up": float(vals[47]) if vals[47] else 0,
            "limit_down": float(vals[48]) if vals[48] else 0,
            "vol_ratio": float(vals[49]) if vals[49] else 0,
        }
    return result


def fetch_tencent_indices():
    """4大指数实时行情"""
    return fetch_tencent_quotes(["sh000001", "sh000300", "sz399006", "sh000688"])


# ═══════════════════════════════════════════════════════════
# 东财（HTTP，内置限流）
# ═══════════════════════════════════════════════════════════

import requests as _requests

EM_SESSION = _requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = 0.8
_em_last = [0.0]

def _em_get(url, params=None, headers=None, timeout=12):
    wait = EM_MIN_INTERVAL - (time.time() - _em_last[0])
    if wait > 0:
        time.sleep(wait + 0.1)
    try:
        r = EM_SESSION.get(url, params=params, headers=headers, timeout=timeout)
    finally:
        _em_last[0] = time.time()
    return r


def fetch_zt_pool(date_str=None):
    """东财涨停池"""
    if date_str is None:
        date_str = _date.today().strftime("%Y%m%d")
    url = "https://push2ex.eastmoney.com/getTopicZTPool"
    params = {"ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.ztzt",
              "Pageindex": 0, "pagesize": 500, "sort": "fbt:asc", "date": date_str}
    try:
        r = _em_get(url, params=params, headers={"Referer": "https://quote.eastmoney.com/"})
        pool = (r.json().get("data") or {}).get("pool") or []
    except Exception as e:
        return {"_error": str(e)[:100], "count": 0}
    items = []
    for p in pool[:100]:
        items.append({
            "code": p.get("c", ""), "name": p.get("n", ""),
            "price": (p.get("p", 0) or 0) / 1000,
            "pct": round(p.get("zdp", 0) or 0, 2),
            "amount": p.get("amount", 0),
            "limit_days": p.get("lbc", 0),
            "seal_fund": p.get("fund", 0),
            "break_times": p.get("zbc", 0),
            "industry": p.get("hybk", ""),
        })
    return {"date": date_str, "count": len(items), "items": items}


def fetch_zb_pool(date_str=None):
    """东财炸板池"""
    if date_str is None:
        date_str = _date.today().strftime("%Y%m%d")
    url = "https://push2ex.eastmoney.com/getTopicZBPool"
    params = {"ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.ztzt",
              "Pageindex": 0, "pagesize": 500, "sort": "fbt:asc", "date": date_str}
    try:
        r = _em_get(url, params=params, headers={"Referer": "https://quote.eastmoney.com/"})
        pool = (r.json().get("data") or {}).get("pool") or []
    except Exception as e:
        return {"_error": str(e)[:100], "count": 0}
    return {"date": date_str, "count": len(pool),
            "items": [{"code": p.get("c",""), "name": p.get("n",""),
                        "break_times": p.get("zbc",0)} for p in pool[:50]]}


def fetch_industry_ranking(top_n=20):
    """东财行业板块排名"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "fltt": "2", "invt": "2", "fid": "f3",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136",
    }
    try:
        r = _em_get(url, params=params, timeout=12)
        items = (r.json().get("data") or {}).get("diff") or []
    except Exception as e:
        return {"_error": str(e)[:100], "top": [], "bottom": []}
    rows = []
    for i, it in enumerate(items):
        rows.append({
            "rank": i+1, "name": it.get("f14",""), "code": it.get("f12",""),
            "change_pct": it.get("f3", 0),
            "up_count": it.get("f104", 0), "down_count": it.get("f105", 0),
            "leader": it.get("f128", ""),
        })
    return {"total": len(rows), "top": rows[:top_n], "bottom": rows[-top_n:]}


def fetch_daily_dragon_tiger(trade_date=None, min_net_buy=3000):
    """全市场龙虎榜（净买额排名）"""
    if trade_date is None:
        trade_date = _date.today().strftime("%Y-%m-%d")
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
        "columns": "ALL", "pageNumber": "1", "pageSize": "100",
        "sortColumns": "BILLBOARD_NET_AMT", "sortTypes": "-1",
        "source": "WEB", "client": "WEB",
        "filter": f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
    }
    try:
        r = _em_get(url, params=params, timeout=12)
        data = (r.json().get("result") or {}).get("data") or []
    except Exception as e:
        return {"_error": str(e)[:100], "stocks": []}
    stocks = []
    for row in data[:50]:
        net = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
        if net < min_net_buy:
            continue
        stocks.append({
            "code": row.get("SECURITY_CODE",""), "name": row.get("SECURITY_NAME_ABBR",""),
            "reason": row.get("EXPLANATION",""),
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
            "net_buy_wan": round(net, 1),
        })
    return {"date": trade_date, "count": len(stocks), "stocks": stocks}


# ═══════════════════════════════════════════════════════════
# 同花顺热点（HTTP，零鉴权，73ms）
# ═══════════════════════════════════════════════════════════

def fetch_ths_hot_reason(date_str=None):
    """同花顺当日强势股+题材归因"""
    if date_str is None:
        date_str = _date.today().strftime("%Y-%m-%d")
    url = (f"http://zx.10jqka.com.cn/event/api/getharden/"
           f"date/{date_str}/orderby/date/orderway/desc/charset/GBK/")
    try:
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=10)
        data = r.json()
        rows = data.get("data") or []
    except Exception as e:
        return {"_error": str(e)[:100], "count": 0}
    items = []
    for row in rows[:100]:
        items.append({
            "code": row.get("code",""), "name": row.get("name",""),
            "reason": row.get("reason",""),
            "change_pct": row.get("zhangfu", 0),
            "turnover": row.get("huanshou", 0),
            "amount": row.get("chengjiaoe", 0),
        })
    # 题材热度统计
    from collections import Counter
    all_tags = []
    for it in items:
        if it["reason"]:
            all_tags.extend([t.strip() for t in str(it["reason"]).split("+") if t.strip()])
    tag_counts = Counter(all_tags).most_common(15)
    return {"date": date_str, "count": len(items), "items": items,
            "hot_tags": [{"tag": t, "count": n} for t, n in tag_counts]}


# ═══════════════════════════════════════════════════════════
# 北向资金（同花顺 hsgtApi）
# ═══════════════════════════════════════════════════════════

def fetch_northbound_flow():
    """北向资金当日实时分钟流向"""
    url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
    try:
        r = _requests.get(url, headers={
            "User-Agent": UA, "Host": "data.hexin.cn",
            "Referer": "https://data.hexin.cn/"
        }, timeout=10)
        d = r.json()
        times = d.get("time", [])
        hgt = d.get("hgt", [])
        sgt = d.get("sgt", [])
        n = len(times)
        hgt_val = hgt[-1] if hgt else 0
        sgt_val = sgt[-1] if sgt else 0
        return {
            "hgt_yi": hgt_val, "sgt_yi": sgt_val,
            "total_yi": round((hgt_val or 0) + (sgt_val or 0), 2),
            "points": n,
            "note": "hgt可靠,sgt仅供参考(2024-08后披露收紧)"
        }
    except Exception as e:
        return {"_error": str(e)[:100]}


# ═══════════════════════════════════════════════════════════
# 打板情绪速算
# ═══════════════════════════════════════════════════════════

def calc_limit_up_sentiment(zt_data, zb_data):
    """炸板率 + 连板梯队 + 最高连板"""
    zt_items = zt_data.get("items", []) if isinstance(zt_data, dict) else []
    zb_count = zb_data.get("count", 0) if isinstance(zb_data, dict) else 0
    zt_count = len(zt_items)
    total = zt_count + zb_count
    break_rate = round(zb_count / total * 100, 1) if total > 0 else 0

    ladder = {}
    max_height = 0
    for s in zt_items:
        d = s.get("limit_days", 0) or 0
        ladder[d] = ladder.get(d, 0) + 1
        if d > max_height:
            max_height = d

    return {
        "zt_count": zt_count, "zb_count": zb_count,
        "break_rate": break_rate, "max_height": max_height,
        "ladder": dict(sorted(ladder.items(), reverse=True)),
    }


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

ALL_SECTIONS = ["index", "hot", "zt", "industry", "north", "dragon", "sentiment"]

def run_prefetch(run_id, sections=None, codes=None):
    """执行预取，返回结构化数据"""
    sections = sections or ALL_SECTIONS
    t0 = time.time()
    result = {
        "runId": run_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sections": sections,
    }
    tasks = {}

    # 并行任务（不封IP的优先）
    if "index" in sections:
        tasks["indices"] = fetch_tencent_indices
    if "hot" in sections:
        tasks["ths_hot"] = fetch_ths_hot_reason
    if "zt" in sections:
        tasks["zt_pool"] = fetch_zt_pool
        tasks["zb_pool"] = fetch_zb_pool
    if "industry" in sections:
        tasks["industry"] = fetch_industry_ranking
    if "north" in sections:
        tasks["northbound"] = fetch_northbound_flow
    if "dragon" in sections:
        tasks["dragon_tiger"] = fetch_daily_dragon_tiger

    # 个股数据
    if codes and "quotes" in sections:
        tasks["tencent_quotes"] = lambda: fetch_tencent_quotes(codes)

    # 并行执行
    sys.stderr.write(f"[prefetch] {len(tasks)} tasks, sections={sections}\n")
    with ThreadPoolExecutor(max_workers=min(len(tasks), 6)) as pool:
        futures = {pool.submit(fn): key for key, fn in tasks.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                result[key] = future.result()
            except Exception as e:
                result[key] = {"_error": str(e)[:100]}

    # 打板情绪速算（依赖 zt/zb 数据）
    if "zt" in sections and "zt_pool" in result and "zb_pool" in result:
        result["limit_up_sentiment"] = calc_limit_up_sentiment(
            result["zt_pool"], result["zb_pool"])

    elapsed = round(time.time() - t0, 1)
    result["elapsed"] = elapsed

    # 核心信号提取
    signals = _extract_signals(result)
    result["coreSignals"] = signals

    sys.stderr.write(f"[prefetch] done in {elapsed}s, {len(signals)} signals\n")
    return result


def _extract_signals(data):
    """从预取数据中提取核心信号"""
    signals = []

    # 指数信号
    idx = data.get("indices", {})
    if isinstance(idx, dict):
        for code, info in idx.items():
            if isinstance(info, dict):
                pct = float(info.get("change_pct", 0) or 0)
                if abs(pct) >= 2:
                    signals.append({
                        "level": "🔴" if abs(pct) >= 3 else "🟡",
                        "type": "index",
                        "text": f"{info.get('name', code)} {pct:+.2f}%",
                    })

    # 涨停情绪信号
    sentiment = data.get("limit_up_sentiment", {})
    if sentiment:
        zt = sentiment.get("zt_count", 0)
        br = sentiment.get("break_rate", 0)
        mh = sentiment.get("max_height", 0)
        if zt > 50:
            signals.append({"level": "🟡", "type": "sentiment",
                            "text": f"涨停{zt}只 炸板率{br}% 最高{mh}连板"})
        if br > 40:
            signals.append({"level": "🟡", "type": "sentiment",
                            "text": f"炸板率{br}%偏高，分歧加大"})

    # 题材热度信号
    hot = data.get("ths_hot", {})
    if isinstance(hot, dict) and hot.get("hot_tags"):
        top3 = hot["hot_tags"][:3]
        tags = ", ".join(f"{t['tag']}({t['count']})" for t in top3)
        signals.append({"level": "🟡", "type": "theme",
                        "text": f"热门题材: {tags}"})

    # 北向信号
    north = data.get("northbound", {})
    if isinstance(north, dict):
        total = north.get("total_yi", 0)
        if abs(total) > 50:
            direction = "流入" if total > 0 else "流出"
            signals.append({"level": "🟡", "type": "capital",
                            "text": f"北向{direction}{abs(total):.0f}亿"})

    # 行业信号
    ind = data.get("industry", {})
    if isinstance(ind, dict) and ind.get("top"):
        top3 = ind["top"][:3]
        names = ", ".join(f"{r['name']}({r['change_pct']:+.1f}%)" for r in top3)
        signals.append({"level": "🟢", "type": "sector",
                        "text": f"领涨行业: {names}"})

    # 龙虎榜信号
    dragon = data.get("dragon_tiger", {})
    if isinstance(dragon, dict) and dragon.get("stocks"):
        top3 = dragon["stocks"][:3]
        names = ", ".join(f"{s['name']}(净买{s['net_buy_wan']:.0f}万)" for s in top3)
        signals.append({"level": "🟢", "type": "dragon",
                        "text": f"龙虎榜净买TOP3: {names}"})

    return signals


def main():
    p = argparse.ArgumentParser(description="a-stock-data 数据预取")
    p.add_argument("--run-id", required=True, help="运行 ID")
    p.add_argument("--section", default="", help="指定板块(逗号分隔)")
    p.add_argument("--codes", default="", help="个股代码(逗号分隔)")
    p.add_argument("--output", default="", help="输出文件路径")
    args = p.parse_args()

    sections = args.section.split(",") if args.section else None
    codes = [c.strip() for c in args.codes.split(",") if c.strip()] if args.codes else None

    data = run_prefetch(args.run_id, sections=sections, codes=codes)

    # 输出
    if args.output:
        out_path = args.output
    else:
        run_dir = f"data/runs/{args.run_id}"
        os.makedirs(run_dir, exist_ok=True)
        out_path = os.path.join(run_dir, "_prefetch.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # stdout 输出摘要
    signals = data.get("coreSignals", [])
    idx_parts = []
    idx = data.get("indices", {})
    if isinstance(idx, dict):
        for code in ["000001", "399006", "000688"]:
            info = idx.get(code, {})
            if isinstance(info, dict):
                idx_parts.append(f"{info.get('name','?')} {info.get('price','?')}({info.get('change_pct','?')}%)")
    summary = " | ".join(idx_parts) if idx_parts else "预取完成"
    print(f"prefetch: {data.get('elapsed', 0)}s | {summary}")
    for s in signals[:5]:
        print(f"  {s['level']} [{s['type']}] {s['text']}")


if __name__ == "__main__":
    main()
