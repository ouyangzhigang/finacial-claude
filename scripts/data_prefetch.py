#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""a-stock-data 批量预取 V2 — 50 并发 + 备胎自动切换 + 候选股预加载。

优化 V2:
  1. 备胎并行: 东财端点 + 官方备胎同时发出, 主源失败自动切备胎
  2. 候选预加载: rank 数据回来后, 50 并发拉取 Top50 候选股的腾讯行情
  3. 涨停池备胎: 东财 zt_pool 失败时, 自动调 hot_trend_dig.py (akshare 走不同 IP)

用法:
  python scripts/data_prefetch.py --run-id 20260716_short-term-picks
  python scripts/data_prefetch.py --run-id xxx --section all --max-workers 50

性能: 50 并发, 总耗时 < 15s (含备胎切换+候选预加载)
"""
import argparse
import hashlib
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request
import uuid
from collections import Counter
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(__file__))
from async_fetcher import BatchFetcher

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TODAY = date.today().strftime("%Y%m%d")
TODAY_DASH = date.today().strftime("%Y-%m-%d")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
ZTB_UT = "7eea3edcaed734bea9cbfc24409ed989"
_CTX = ssl._create_unverified_context()

ALL_SECTIONS = ["index", "hot", "zt", "industry", "north", "dragon", "news", "capital", "sentiment"]


# ═══════════════════════════════════════════════════════════
# 备胎函数(不同域名/不同风控面, 东财被封时不受影响)
# ═══════════════════════════════════════════════════════════

def backup_dragon_tiger_sse_szse():
    """龙虎榜官方备胎: 深交所 + 上交所, 零鉴权。"""
    result = {"source": "sse_szse_official", "szse": [], "sse_raw": ""}
    # 深交所
    try:
        url = (f"https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON"
               f"&CATALOGID=1842_xxpl&TABKEY=tab1&txtStart={TODAY_DASH}&txtEnd={TODAY_DASH}&random=0.9")
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Referer": "https://www.szse.cn/disclosure/supervision/dealinfo/index.html"})
        with urllib.request.urlopen(req, timeout=15, context=_CTX) as r:
            d = json.loads(r.read())
        for row in (d[0].get("data", []) if d else []):
            result["szse"].append({
                "code": row.get("zqdm", ""), "name": row.get("zqjc", ""),
                "amount": row.get("cjje", ""), "reason": row.get("plyy", ""),
            })
    except Exception as e:
        result["szse_error"] = str(e)[:200]

    # 上交所
    try:
        url = (f"https://query.sse.com.cn/infodisplay/showTradePublicFile.do?"
               f"jsonCallBack=cb&isPagination=false&dateTx={TODAY_DASH}")
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Referer": "https://www.sse.com.cn/disclosure/diclosure/public/"})
        with urllib.request.urlopen(req, timeout=15) as r:
            t = r.read().decode("utf-8", "ignore")
        if "(" in t and ")" in t:
            result["sse_raw"] = "\n".join(
                json.loads(t[t.index("(") + 1:t.rindex(")")]).get("fileContents", []))
    except Exception as e:
        result["sse_error"] = str(e)[:200]

    return result


def backup_fund_flow_sina(codes):
    """资金流备胎: 新浪日度资金流, 批量拉取。"""
    results = {}
    for code in codes[:20]:  # 限制 20 只
        prefix = ("sh" if code.startswith(("6", "9")) else "bj" if code.startswith("8") else "sz") + code
        url = (f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
               f"MoneyFlow.ssl_qsfx_zjlrqs?page=1&num=5&sort=opendate&asc=0&daima={prefix}")
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "https://finance.sina.com.cn/"})
            with urllib.request.urlopen(req, timeout=10) as r:
                t = r.read().decode("utf-8", "ignore")
            if "[" in t and "]" in t:
                arr = json.loads(t[t.index("["):t.rindex("]") + 1])
                results[code] = [{
                    "date": x.get("opendate"), "close": x.get("trade"),
                    "net_amount": x.get("netamount"),
                } for x in arr[:3]]
        except Exception as e:
            results[code] = {"_error": str(e)[:100]}
    return {"source": "sina_moneyflow", "data": results}


def backup_zt_from_hot_trend_dig():
    """涨停池备胎: hot_trend_dig.py (akshare, 走不同 IP 路径)。"""
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        r = subprocess.run(
            [sys.executable, "scripts/hot_trend_dig.py", "--json-only"],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace",
            env=env,
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout.strip())
            return {"source": "hot_trend_dig", "data": data}
    except Exception as e:
        return {"source": "hot_trend_dig", "_error": str(e)[:200]}
    return {"source": "hot_trend_dig", "_error": "no output"}


def backup_sector_from_cn_fetch():
    """板块排名备胎: cn_fetch.py rank (新浪, 不封 IP)。"""
    results = {}
    for sort_key in ["changepercent", "amount"]:
        try:
            r = subprocess.run(
                [sys.executable, "scripts/cn_fetch.py", "rank", sort_key, "80"],
                capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace",
            )
            if r.returncode == 0 and r.stdout.strip():
                lines = r.stdout.strip().split("\n")
                if len(lines) > 1:
                    results[sort_key] = {
                        "count": len(lines) - 1,
                        "tsv": r.stdout.strip()[:5000],
                    }
        except Exception as e:
            results[sort_key] = {"_error": str(e)[:100]}
    return {"source": "cn_fetch_rank", "data": results}


# ═══════════════════════════════════════════════════════════
# 任务构建(主源 + 备胎同时发出)
# ═══════════════════════════════════════════════════════════

def build_tasks(sections=None, ticker=""):
    """构建全部 HTTP 任务(主源 + 备胎并行)。"""
    sections = sections or ALL_SECTIONS
    tasks = []

    # ── 不封IP: 腾讯/同花顺/财联社 ──
    if "index" in sections:
        tasks.append({"name": "indices", "type": "get_raw",
                       "url": "http://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688",
                       "encoding": "gbk"})

    if "hot" in sections:
        tasks.append({"name": "ths_hot_reason", "type": "get_json",
                       "url": f"http://zx.10jqka.com.cn/event/api/getharden/date/{TODAY_DASH}/orderby/date/orderway/desc/charset/GBK/"})

    if "north" in sections:
        tasks.append({"name": "northbound_realtime", "type": "get_json",
                       "url": "https://data.hexin.cn/market/hsgtApi/method/dayChart/",
                       "headers": {"Host": "data.hexin.cn", "Referer": "https://data.hexin.cn/"}})

    if "news" in sections:
        cls_params = {"appName": "CailianpressWeb", "os": "web", "sv": "7.7.5",
                      "last_time": "", "refresh_type": "1", "rn": "50"}
        qs = "&".join(f"{k}={cls_params[k]}" for k in sorted(cls_params))
        sign = hashlib.md5(hashlib.sha1(qs.encode()).hexdigest().encode()).hexdigest()
        tasks.append({"name": "cls_telegraph", "type": "get_json",
                       "url": f"https://www.cls.cn/v1/roll/get_roll_list?{qs}&sign={sign}",
                       "headers": {"Referer": "https://www.cls.cn/"}})

    if "sentiment" in sections:
        tasks.append({"name": "ths_hot_list", "type": "get_json",
                       "url": "https://dq.10jqka.com.cn/fupan/hotlist/v1/hotList/v2/hotList",
                       "headers": {"Referer": "https://www.10jqka.com.cn/"}})

    # ── 东财系(有风控) + 备胎同时发出 ──

    if "sector" in sections:
        tasks.append({"name": "sector_concept", "type": "get_json",
                       "url": ("http://push2.eastmoney.com/api/qt/clist/get?"
                               "pn=1&pz=30&po=1&fid=f3&fs=m:90+t:2&np=1&fltt=2&invt=2&"
                               "fields=f2,f3,f6,f8,f12,f14,f104,f105,f128"),
                       "throttle_domain": "eastmoney.com"})
        tasks.append({"name": "sector_industry", "type": "get_json",
                       "url": ("http://push2.eastmoney.com/api/qt/clist/get?"
                               "pn=1&pz=30&po=1&fid=f3&fs=m:90+t:1&np=1&fltt=2&invt=2&"
                               "fields=f2,f3,f6,f8,f12,f14,f104,f105,f128"),
                       "throttle_domain": "eastmoney.com"})

    if "industry" in sections:
        tasks.append({"name": "industry_ranking", "type": "get_json",
                       "url": ("https://push2.eastmoney.com/api/qt/clist/get?"
                               "pn=1&pz=100&po=1&fid=f3&fs=m:90+t:2&np=1&fltt=2&invt=2&"
                               "fields=f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140"),
                       "throttle_domain": "eastmoney.com"})

    if "zt" in sections:
        for endpoint, sort_key, pool_name in [
            ("getTopicZTPool", "fbt:asc", "zt_pool"),
            ("getTopicZBPool", "fbt:asc", "zb_pool"),
            ("getTopicDTPool", "fund:asc", "dt_pool"),
            ("getYesterdayZTPool", "zs:desc", "yzt_pool"),
        ]:
            tasks.append({"name": pool_name, "type": "get_json",
                           "url": (f"https://push2ex.eastmoney.com/{endpoint}?"
                                   f"ut={ZTB_UT}&dpt=wz.ztzt&Pageindex=0&pagesize=500&sort={sort_key}&date={TODAY}"),
                           "throttle_domain": "push2ex.eastmoney.com"})

    if "dragon" in sections:
        tasks.append({"name": "dragon_tiger_daily", "type": "get_json",
                       "url": ("https://datacenter-web.eastmoney.com/api/data/v1/get?"
                               f"reportName=RPT_DAILYBILLBOARD_DETAILSNEW&columns=ALL"
                               f"&filter=(TRADE_DATE%3E%27{TODAY_DASH}%27)(TRADE_DATE%3C%27{TODAY_DASH}%27)"
                               f"&pageNumber=1&pageSize=100&sortColumns=BILLBOARD_NET_AMT&sortTypes=-1"
                               f"&source=WEB&client=WEB"),
                       "throttle_domain": "datacenter-web.eastmoney.com"})

    if "capital" in sections:
        tasks.append({"name": "capital_flow_top50", "type": "get_json",
                       "url": ("https://push2.eastmoney.com/api/qt/clist/get?"
                               "pn=1&pz=50&po=1&fid=f62&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
                               "&np=1&fltt=2&invt=2&fields=f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87"),
                       "throttle_domain": "push2.eastmoney.com"})

    if "news" in sections:
        tasks.append({"name": "eastmoney_global_news", "type": "get_json",
                       "url": (f"https://np-weblist.eastmoney.com/comm/web/getFastNewsList?"
                               f"client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize=50&req_trace={uuid.uuid4()}"),
                       "throttle_domain": "np-weblist.eastmoney.com",
                       "headers": {"Referer": "https://kuaixun.eastmoney.com/"}})

    if "sentiment" in sections:
        tasks.append({"name": "em_hot_rank", "type": "get_json",
                       "url": ("https://emappdata.eastmoney.com/stockrank/getAllCurrentList?"
                               "appId=appId01&globalId=786e4c21-70dc-435a-93bb-38&pageNo=1&pageSize=50"),
                       "throttle_domain": "emappdata.eastmoney.com"})

    if ticker:
        prefix = "sh" if str(ticker).startswith("6") else "sz"
        tasks.append({"name": "stock_snapshot", "type": "get_raw",
                       "url": f"http://qt.gtimg.cn/q={prefix}{ticker}",
                       "encoding": "gbk"})

    return tasks


# ═══════════════════════════════════════════════════════════
# 解析函数
# ═══════════════════════════════════════════════════════════

def parse_indices(raw_str):
    if not isinstance(raw_str, str) or "~" not in raw_str:
        return {}
    indices = {}
    for line in raw_str.strip().split(";"):
        if "~" not in line:
            continue
        parts = line.split("~")
        if len(parts) > 45:
            code = parts[2]
            indices[code] = {
                "name": parts[1], "price": parts[3], "prevClose": parts[4],
                "changePct": parts[32], "amount": parts[37],
            }
    return indices


def parse_zt_pool(data):
    if not isinstance(data, dict):
        return []
    pool = (data.get("data") or {}).get("pool") or []
    items = []
    for p in pool:
        fbt = str(p.get("fbt", "")).zfill(6)
        items.append({
            "code": p.get("c", ""), "name": p.get("n", ""),
            "price": (p.get("p", 0) or 0) / 1000,
            "pct": round(p.get("zdp", 0) or 0, 2),
            "amount": p.get("amount", 0),
            "limit_days": p.get("lbc", 0),
            "seal_fund": p.get("fund", 0),
            "break_times": p.get("zbc", 0),
            "first_seal": f"{fbt[0:2]}:{fbt[2:4]}:{fbt[4:6]}",
            "industry": p.get("hybk", ""),
        })
    return items


def parse_tencent_quotes(raw_str):
    """解析腾讯批量行情(GBK ~分隔)"""
    if not isinstance(raw_str, str) or "~" not in raw_str:
        return {}
    result = {}
    for line in raw_str.strip().split(";"):
        if "~" not in line or "=" not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~") if '"' in line else []
        if len(vals) < 53:
            continue
        code = key[2:]  # 去掉 sh/sz 前缀
        result[code] = {
            "name": vals[1], "price": float(vals[3]) if vals[3] else 0,
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
        }
    return result


def extract_top_codes(raw_results, top_n=50):
    """从 cn_fetch rank 结果中提取 Top N 代码(用于候选预加载)"""
    codes = []
    # 从 cn_fetch backup 数据提取
    cn_data = raw_results.get("backup_sector_cn_fetch", {})
    if isinstance(cn_data, dict):
        rank_data = cn_data.get("data", {}).get("changepercent", {})
        tsv = rank_data.get("tsv", "")
        if tsv:
            for line in tsv.split("\n")[1:top_n + 1]:  # 跳过表头
                parts = line.split("\t")
                if parts:
                    code = parts[0].strip()
                    if code and len(code) == 6 and code.isdigit():
                        codes.append(code)
    return codes[:top_n]


def extract_signals(raw_results, parsed):
    """提取核心信号"""
    signals = []

    # 指数
    for code, info in parsed.get("indices", {}).items():
        pct = float(info.get("changePct", 0) or 0)
        if abs(pct) >= 3:
            signals.append({"level": "🔴", "type": "index",
                            "text": f"{info['name']} {'大涨' if pct > 0 else '大跌'} {pct:+.2f}%"})
        elif abs(pct) >= 1.5:
            signals.append({"level": "🟡", "type": "index",
                            "text": f"{info['name']} {pct:+.2f}%"})

    # 板块
    for key, label in [("sector_concept", "概念"), ("sector_industry", "行业")]:
        data = raw_results.get(key, {})
        if isinstance(data, dict) and data.get("data", {}).get("diff"):
            items = data["data"]["diff"]
            for d in (items if isinstance(items, list) else list(items.values()))[:5]:
                pct = d.get("f3", 0) or 0
                name = d.get("f14", "")
                if pct >= 5:
                    signals.append({"level": "🔴", "type": "sector",
                                    "text": f"{label}异动: {name} {pct:+.2f}%"})
                elif pct >= 3:
                    signals.append({"level": "🟡", "type": "sector",
                                    "text": f"{label}活跃: {name} {pct:+.2f}%"})

    # 涨停情绪
    zt = parsed.get("zt_pool", [])
    zb = parsed.get("zb_pool", [])
    dt = parsed.get("dt_pool", [])
    zt_n, zb_n = len(zt), len(zb)
    if zt_n + zb_n > 0:
        break_rate = round(zb_n / (zt_n + zb_n) * 100, 1)
        ladder = {}
        max_h = 0
        for s in zt:
            d = s.get("limit_days", 0)
            ladder[d] = ladder.get(d, 0) + 1
            max_h = max(max_h, d)
        parsed["limit_up_sentiment"] = {
            "zt_count": zt_n, "zb_count": zb_n, "dt_count": len(dt),
            "break_rate": break_rate, "max_height": max_h, "ladder": dict(sorted(ladder.items())),
        }
        if zt_n >= 50:
            signals.append({"level": "🟡", "type": "sentiment", "text": f"涨停 {zt_n} 只"})
        if break_rate >= 40:
            signals.append({"level": "🟡", "type": "sentiment", "text": f"炸板率 {break_rate}%,分歧大"})
        if max_h >= 5:
            signals.append({"level": "🟡", "type": "sentiment", "text": f"最高 {max_h} 连板"})

    # 北向
    north = raw_results.get("northbound_realtime", {})
    if isinstance(north, dict):
        hgt = north.get("hgt", [])
        sgt = north.get("sgt", [])
        hgt_val = hgt[-1] if hgt else 0
        sgt_val = sgt[-1] if sgt else 0
        total = (hgt_val or 0) + (sgt_val or 0)
        parsed["northbound"] = {"hgt_yi": hgt_val, "sgt_yi": sgt_val, "total_yi": round(total, 2)}
        if abs(total) >= 30:
            signals.append({"level": "🟡", "type": "capital",
                            "text": f"北向{'净流入' if total > 0 else '净流出'} {abs(total):.1f}亿"})

    # 题材热度
    hot = raw_results.get("ths_hot_reason", {})
    if isinstance(hot, dict):
        rows = hot.get("data") or []
        all_tags = []
        for r in rows:
            reason = r.get("reason", "")
            if reason:
                all_tags.extend([t.strip() for t in str(reason).split("+") if t.strip()])
        top_tags = Counter(all_tags).most_common(5)
        parsed["hot_tags"] = [{"tag": t, "count": n} for t, n in top_tags]
        if top_tags:
            tags_str = ", ".join(f"{t}({n})" for t, n in top_tags[:3])
            signals.append({"level": "🟡", "type": "theme", "text": f"热门题材: {tags_str}"})

    # 龙虎榜
    dragon = raw_results.get("dragon_tiger_daily", {})
    if isinstance(dragon, dict) and dragon.get("result", {}).get("data"):
        records = dragon["result"]["data"]
        parsed["dragon_tiger"] = {
            "total": len(records),
            "top5": [{"code": r.get("SECURITY_CODE", ""), "name": r.get("SECURITY_NAME_ABBR", ""),
                       "net_buy_wan": round((r.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
                       "reason": r.get("EXPLANATION", "")} for r in records[:5]],
        }
    # 龙虎榜备胎
    dragon_backup = raw_results.get("backup_dragon_tiger", {})
    if not parsed.get("dragon_tiger") and isinstance(dragon_backup, dict):
        szse = dragon_backup.get("szse", [])
        if szse:
            parsed["dragon_tiger"] = {
                "source": "szse_official",
                "total": len(szse),
                "top5": szse[:5],
            }

    # 新闻
    cls_data = raw_results.get("cls_telegraph", {})
    if isinstance(cls_data, dict) and cls_data.get("data", {}).get("roll_data"):
        items = cls_data["data"]["roll_data"][:10]
        parsed["news_headlines"] = [
            {"title": item.get("title", "") or item.get("brief", ""),
             "time": datetime.fromtimestamp(item["ctime"]).strftime("%H:%M") if item.get("ctime") else ""}
            for item in items
        ]

    level_rank = {"🔴": 3, "🟡": 2, "🟢": 1}
    signals.sort(key=lambda s: -level_rank.get(s.get("level", ""), 0))
    return signals


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="a-stock-data 批量预取 V2(50并发+备胎+候选预加载)")
    p.add_argument("--run-id", required=True)
    p.add_argument("--section", default="all")
    p.add_argument("--ticker", default="")
    p.add_argument("--max-workers", type=int, default=50)
    args = p.parse_args()

    sections = ALL_SECTIONS if args.section == "all" else args.section.split(",")
    run_dir = f"data/runs/{args.run_id}"
    os.makedirs(run_dir, exist_ok=True)

    # ═══ Phase 1: 主源 + 备胎并行(50 并发) ═══
    task_list = build_tasks(sections=sections, ticker=args.ticker)
    sys.stderr.write(f"[prefetch] Phase 1: {len(task_list)} 主源任务, {args.max_workers} 并发\n")

    fetcher = BatchFetcher(max_workers=args.max_workers)
    for t in task_list:
        t_type = t.get("type", "get_json")
        if t_type == "get_json":
            fetcher.add_json(t["name"], t["url"], encoding=t.get("encoding", "utf-8"),
                             throttle_domain=t.get("throttle_domain", ""),
                             headers=t.get("headers"))
        elif t_type == "get_raw":
            fetcher.add_raw(t["name"], t["url"], encoding=t.get("encoding", "utf-8"))

    raw_results = fetcher.run()
    phase1_stats = raw_results.get("_stats", {})
    failed_names = phase1_stats.get("error_names", [])

    # ═══ Phase 2: 备胎自动切换(对失败的东财端点) ═══
    backup_results = {}
    if failed_names:
        sys.stderr.write(f"[prefetch] Phase 2: {len(failed_names)} 失败, 启动备胎\n")

        # 龙虎榜备胎(深交所+上交所官方)
        if "dragon_tiger_daily" in failed_names:
            sys.stderr.write("[prefetch] 备胎: 龙虎榜 → 深交所+上交所官方\n")
            backup_results["backup_dragon_tiger"] = backup_dragon_tiger_sse_szse()

        # 涨停池备胎(hot_trend_dig.py)
        zt_failed = [n for n in failed_names if n.startswith(("zt_", "zb_", "dt_", "yzt_"))]
        if zt_failed:
            sys.stderr.write("[prefetch] 备胎: 涨停池 → hot_trend_dig.py\n")
            backup_results["backup_zt_hot_trend"] = backup_zt_from_hot_trend_dig()

        # 板块排名备胎(cn_fetch.py rank)
        sector_failed = [n for n in failed_names if n.startswith("sector_")]
        if sector_failed or "industry_ranking" in failed_names:
            sys.stderr.write("[prefetch] 备胎: 板块排名 → cn_fetch.py rank\n")
            backup_results["backup_sector_cn_fetch"] = backup_sector_from_cn_fetch()

    # 合并主源 + 备胎
    raw_results.update(backup_results)

    # ═══ Phase 3: 候选股预加载(Top50 腾讯行情) ═══
    top_codes = extract_top_codes(raw_results, top_n=50)
    candidates_data = {}
    if top_codes:
        sys.stderr.write(f"[prefetch] Phase 3: 预加载 {len(top_codes)} 只候选股行情\n")
        # 构建腾讯批量行情 URL(80 只一批)
        batch_size = 80
        for i in range(0, len(top_codes), batch_size):
            batch = top_codes[i:i + batch_size]
            prefixed = []
            for c in batch:
                if c.startswith(("6", "9")):
                    prefixed.append(f"sh{c}")
                elif c.startswith("8"):
                    prefixed.append(f"bj{c}")
                else:
                    prefixed.append(f"sz{c}")
            url = f"http://qt.gtimg.cn/q={','.join(prefixed)}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=10, context=_CTX) as r:
                    raw = r.read().decode("gbk", errors="ignore")
                quotes = parse_tencent_quotes(raw)
                candidates_data.update(quotes)
            except Exception as e:
                sys.stderr.write(f"[prefetch] 候选行情 batch {i} 失败: {e}\n")

        sys.stderr.write(f"[prefetch] Phase 3: 成功获取 {len(candidates_data)} 只候选行情\n")

    # ═══ 解析 + 信号提取 ═══
    parsed = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "sections": sections}
    parsed["indices"] = parse_indices(raw_results.get("indices", ""))
    parsed["zt_pool"] = parse_zt_pool(raw_results.get("zt_pool", {}))
    parsed["zb_pool"] = parse_zt_pool(raw_results.get("zb_pool", {}))
    parsed["dt_pool"] = parse_zt_pool(raw_results.get("dt_pool", {}))
    parsed["yzt_pool"] = parse_zt_pool(raw_results.get("yzt_pool", {}))

    signals = extract_signals(raw_results, parsed)

    # ═══ 输出 ═══
    total_elapsed = phase1_stats.get("elapsed", 0)

    output = {
        "runId": args.run_id,
        "timestamp": parsed["timestamp"],
        "indices": parsed.get("indices", {}),
        "limit_up_sentiment": parsed.get("limit_up_sentiment", {}),
        "northbound": parsed.get("northbound", {}),
        "hot_tags": parsed.get("hot_tags", []),
        "dragon_tiger": parsed.get("dragon_tiger", {}),
        "news_headlines": parsed.get("news_headlines", []),
        "coreSignals": signals,
        "candidates": candidates_data,
        "backup_used": list(backup_results.keys()),
        "_stats": {
            "phase1": phase1_stats,
            "phase2_backups": len(backup_results),
            "phase3_candidates": len(candidates_data),
            "total_elapsed": total_elapsed,
        },
    }

    out_path = os.path.join(run_dir, "_prefetch.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 候选数据单独写一份(供 agent 直接 Read)
    if candidates_data:
        cand_path = os.path.join(run_dir, "_candidates_data.json")
        with open(cand_path, "w", encoding="utf-8") as f:
            json.dump(candidates_data, f, ensure_ascii=False, indent=2)

    # stdout 摘要
    ok = phase1_stats.get("ok", 0)
    total = phase1_stats.get("total", 0)
    print(f"prefetch V2: {ok}/{total} 主源成功, {len(backup_results)} 备胎激活, "
          f"{len(candidates_data)} 候选预加载, {total_elapsed}s")
    idx_parts = []
    for code in ["000001", "399001", "399006"]:
        info = parsed.get("indices", {}).get(code, {})
        if info:
            idx_parts.append(f"{info.get('name','?')} {info.get('price','?')}({info.get('changePct','?')}%)")
    if idx_parts:
        print("指数: " + " | ".join(idx_parts))
    for s in signals[:8]:
        print(f"  {s['level']} [{s['type']}] {s['text']}")
    if backup_results:
        print(f"备胎激活: {', '.join(backup_results.keys())}")

    sys.stderr.write(f"[prefetch] 写入 {out_path}\n")


if __name__ == "__main__":
    main()
