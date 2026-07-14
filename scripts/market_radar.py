#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""市场雷达——多源数据采集 + 核心信号自动提取。

用法:
  python scripts/market_radar.py                    # 全量扫描
  python scripts/market_radar.py --section index    # 只扫指数
  python scripts/market_radar.py --section news     # 只扫新闻
  python scripts/market_radar.py --ticker 600519    # 加个股维度
  python scripts/market_radar.py --run-id 20260709_short-term-picks  # 写入 run dir

数据源(全部免密钥,urllib+SSL 自处理):
  新浪: 7x24 快讯 + 榜单 + 日K
  腾讯: 实时行情 + 指数
  东方财富: 概念/行业板块 + 涨停池 + 龙虎榜 + 资金流 + 市场概览
  同花顺: 备用

核心信号自动分类:
  🔴 critical  — 政策变动/重大事件/黑天鹅
  🟡 important — 板块异动/业绩超预期/大额资金/评级变动
  🟢 normal    — 常规涨跌/一般资讯

输出: JSON (stdout) + 核心信号摘要 (stderr)
"""
import argparse
import json
import os
import re
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
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ═══════════════════════════════════════════════════════════
# 通用工具
# ═══════════════════════════════════════════════════════════

def _http(url, encoding="utf-8", timeout=15, headers=None):
    """GET → raw string, with retry."""
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
                return resp.read().decode(encoding, "ignore")
        except Exception as e:
            if attempt == 1:
                return None
            time.sleep(0.5)
    return None


def _http_json(url, **kw):
    """GET → parsed JSON."""
    raw = _http(url, **kw)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        # 东方财富 502 裹 HTML-JSON 容错
        raw = raw.strip()
        for start_ch, end_ch in [("{", "}"), ("[", "]")]:
            i = raw.find(start_ch)
            if i >= 0:
                j = raw.rfind(end_ch)
                if j > i:
                    try:
                        return json.loads(raw[i:j + 1])
                    except Exception:
                        pass
        return None


# ═══════════════════════════════════════════════════════════
# 数据采集器
# ═══════════════════════════════════════════════════════════

def fetch_indices():
    """4 大指数实时行情(腾讯)"""
    raw = _http("http://qt.gtimg.cn/q=sh000001,sz399001,sz399006,sh000688", encoding="gbk")
    if not raw:
        return {"_error": "tencent failed"}
    result = {}
    for line in raw.strip().split(";"):
        if "~" not in line:
            continue
        p = line.split("~")
        if len(p) > 45:
            result[p[2]] = {
                "name": p[1], "price": p[3], "prevClose": p[4],
                "open": p[5], "high": p[33] if len(p) > 33 else p[3],
                "low": p[34] if len(p) > 34 else p[3],
                "changePct": p[32], "amount": p[37],  # 成交额(万)
                "turnover": p[38], "vol": p[36],
            }
    return result


def fetch_market_breadth():
    """市场涨跌分布(东方财富)"""
    url = ("http://push2.eastmoney.com/api/qt/clist/get?"
           "pn=1&pz=1&po=1&fid=f3&np=1&fltt=2&invt=2&"
           "fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f2,f3,f12,f14")
    data = _http_json(url)
    if not data or not data.get("data"):
        return {"_error": "eastmoney breadth failed"}
    total = data["data"].get("total", 0)

    # 涨幅分布: 分别取 >5%, >3%, >0%, <-3%, <-5% 的数量
    dist = {}
    for threshold, label in [("5", "涨>5%"), ("3", "涨>3%"), ("0", "上涨"),
                              ("-3", "跌>3%"), ("-5", "跌>5%")]:
        fs_filter = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
        if threshold.startswith("-"):
            # 跌幅: po=0 升序, f3 <= threshold
            url2 = (f"http://push2.eastmoney.com/api/qt/clist/get?"
                    f"pn=1&pz=1&po=0&fid=f3&np=1&fltt=2&invt=2&"
                    f"fs={fs_filter}&fields=f3")
        else:
            url2 = (f"http://push2.eastmoney.com/api/qt/clist/get?"
                    f"pn=1&pz=1&po=1&fid=f3&np=1&fltt=2&invt=2&"
                    f"fs={fs_filter}&fields=f3")
        d2 = _http_json(url2)
        if d2 and d2.get("data"):
            # 用 total 粗略估 (精确需遍历,太慢)
            pass
    # 简化: 取涨幅 Top5 + 跌幅 Top5 做样本推断
    top5_up = fetch_rank_sina("changepercent", 5)
    top5_down = fetch_rank_sina("changepercent", 5, asc=True)
    return {
        "totalStocks": total,
        "top5Up": top5_up,
        "top5Down": top5_down,
    }


def fetch_rank_sina(sort="changepercent", num=80, asc=False):
    """新浪榜单"""
    asc_val = "1" if asc else "0"
    url = (f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"Market_Center.getHQNodeData?page=1&num={num}&sort={sort}&asc={asc_val}"
           f"&node=hs_a&_s_r_a=auto")
    data = _http_json(url)
    if not data:
        return []
    result = []
    for item in data[:num]:
        result.append({
            "code": item.get("symbol", ""),
            "name": item.get("name", ""),
            "price": item.get("trade"),
            "changePct": item.get("changepercent"),
            "amount": item.get("amount"),  # 元
            "turnover": item.get("turnoverratio"),
            "mktCap": item.get("nmc"),  # 万元
            "pe": item.get("per"),
            "pb": item.get("pb"),
        })
    return result


def fetch_sector_ranking(market_type="concept", top=20):
    """东方财富板块排名(concept=概念, industry=行业)"""
    fs = "m:90+t:2" if market_type == "concept" else "m:90+t:1"
    url = (f"http://push2.eastmoney.com/api/qt/clist/get?"
           f"pn=1&pz={top}&po=1&fid=f3&fs={fs}&np=1&fltt=2&invt=2&"
           f"fields=f2,f3,f6,f8,f12,f14,f104,f105")
    data = _http_json(url)
    if not data or not data.get("data", {}).get("diff"):
        return {"_error": f"sector {market_type} failed"}
    items = []
    for d in data["data"]["diff"][:top]:
        items.append({
            "code": d.get("f12"),
            "name": d.get("f14"),
            "changePct": d.get("f3"),
            "amount": d.get("f6"),
            "turnover": d.get("f8"),
            "upCount": d.get("f104"),  # 上涨家数
            "downCount": d.get("f105"),  # 下跌家数
        })
    return items


def fetch_zt_pool():
    """涨停池(东方财富)"""
    today = time.strftime("%Y%m%d")
    url = (f"https://push2ex.eastmoney.com/getTopicZTPool?"
           f"ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt"
           f"&Pageindex=0&pagesize=200&sort=fbt:asc&date={today}")
    data = _http_json(url)
    if not data or not data.get("data", {}).get("pool"):
        return []
    result = []
    for item in data["data"]["pool"]:
        result.append({
            "code": item.get("c", ""),
            "name": item.get("n", ""),
            "changePct": item.get("zdp"),
            "amount": item.get("amount"),
            "lianban": item.get("lbc"),  # 连板次数
            "circMktCap": item.get("ltsz"),  # 流通市值
            "firstSealTime": item.get("fbt"),  # 首次封板时间
        })
    return result


def fetch_longhu_bang():
    """龙虎榜(东方财富 datacenter)"""
    today = time.strftime("%Y-%m-%d")
    url = (f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
           f"reportName=RPT_DAILYBILLBOARD_DETAILSNEW&pageSize=50&pageNumber=1"
           f"&sortColumns=SECURITY_CODE&sortTypes=1"
           f"&filter=(TRADE_DATE%3E%27{today}%27)")
    data = _http_json(url)
    if not data or not data.get("result", {}).get("data"):
        # 尝试昨天
        yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
        url = url.replace(today, yesterday)
        data = _http_json(url)
        if not data or not data.get("result", {}).get("data"):
            return []
    result = []
    for item in data["result"]["data"][:30]:
        result.append({
            "code": item.get("SECURITY_CODE", ""),
            "name": item.get("SECURITY_NAME_ABBR", ""),
            "close": item.get("CLOSE_PRICE"),
            "changePct": item.get("CHANGE_RATE"),
            "netBuyAmt": item.get("BILLBOARD_NET_AMT"),  # 净买入额
            "buyAmt": item.get("BILLBOARD_BUY_AMT"),
            "sellAmt": item.get("BILLBOARD_SELL_AMT"),
            "amount": item.get("BILLBOARD_DEAL_AMT"),
            "reason": item.get("EXPLAIN"),  # 上榜原因
        })
    return result


def fetch_capital_flow(top=20):
    """个股资金流向 Top20(东方财富)"""
    url = ("http://push2.eastmoney.com/api/qt/clist/get?"
           "pn=1&pz=20&po=1&fid=f62&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
           "&np=1&fltt=2&invt=2&fields=f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87")
    data = _http_json(url)
    if not data or not data.get("data", {}).get("diff"):
        return []
    result = []
    for d in data["data"]["diff"][:top]:
        result.append({
            "code": d.get("f12"),
            "name": d.get("f14"),
            "price": d.get("f2"),
            "changePct": d.get("f3"),
            "mainNetInflow": d.get("f62"),  # 主力净流入
            "mainNetPct": d.get("f184"),
            "superLargeNet": d.get("f66"),  # 超大单净流入
            "largeNet": d.get("f72"),  # 大单净流入
            "mediumNet": d.get("f78"),  # 中单净流入
            "smallNet": d.get("f84"),  # 小单净流入
        })
    return result


def fetch_news_sina_7x24(count=50):
    """新浪 7x24 实时快讯"""
    url = ("https://zhibo.sina.com.cn/api/zhibo/feed?"
           "page=1&page_size=50&zhibo_id=152&cat_id=0&tag_id=0&type=0")
    data = _http_json(url)
    if not data or not data.get("result", {}).get("data"):
        return []
    result = []
    for item in data["result"]["data"].get("feed", {}).get("list", []):
        text = item.get("rich_text", "") or item.get("text", "")
        # 去 HTML 标签
        text = re.sub(r"<[^>]+>", "", text)
        if text:
            result.append({
                "time": item.get("create_time", ""),
                "text": text[:300],
                "tag": item.get("tag", []),
            })
    return result[:count]


def fetch_stock_snapshot(code):
    """腾讯个股快照"""
    prefix = "sh" if str(code).startswith("6") else "sz"
    sid = prefix + str(code)
    raw = _http(f"http://qt.gtimg.cn/q={sid}", encoding="gbk")
    if not raw or "~" not in raw:
        return {"_error": "snapshot failed"}
    p = raw.split("~")
    if len(p) < 46:
        return {"_error": "parse failed"}
    return {
        "code": code, "name": p[1], "price": p[3], "prevClose": p[4],
        "changePct": p[32], "amount": p[37], "turnover": p[38],
        "pe": p[39], "mktCap": p[45], "high": p[33] if len(p) > 33 else "",
        "low": p[34] if len(p) > 34 else "",
    }


# ═══════════════════════════════════════════════════════════
# 核心信号提取
# ═══════════════════════════════════════════════════════════

# 关键词权重词典
_CRITICAL_KW = [
    "央行", "降准", "降息", "LPR", "MLF", "政治局", "国务院", "证监会", "暂停IPO",
    "熔断", "千股跌停", "千股涨停", "战争", "制裁", "断供", "黑天鹅",
    "退市", "ST", "立案调查", "财务造假", "暴跌", "暴涨",
]
_IMPORTANT_KW = [
    "涨停", "跌停", "连板", "封板", "炸板", "龙虎榜", "机构", "游资",
    "增持", "回购", "减持", "解禁", "业绩预告", "超预期", "不及预期",
    "突破", "新高", "新低", "放量", "缩量",
    "北向", "外资", "主力", "净流入", "净流出",
    "评级", "上调", "下调", "目标价",
    "并购", "重组", "资产注入", "国企改革",
    "芯片", "半导体", "AI", "人工智能", "新能源", "光伏", "锂电",
    "医药", "创新药", "军工", "稀土", "有色",
]
_POLICY_KW = [
    "政策", "补贴", "扶持", "规划", "意见", "通知", "管理办法",
    "关税", "反制", "制裁", "出口管制", "实体清单",
]


def extract_signals(all_data):
    """从全部数据中提取核心信号"""
    signals = []

    # 1. 指数信号
    indices = all_data.get("indices", {})
    for code, info in indices.items():
        pct = float(info.get("changePct", 0) or 0)
        if abs(pct) >= 3:
            signals.append({
                "level": "🔴", "type": "index",
                "text": f"{info.get('name', code)} {'大涨' if pct > 0 else '大跌'} {pct:+.2f}%",
                "data": info,
            })
        elif abs(pct) >= 1.5:
            signals.append({
                "level": "🟡", "type": "index",
                "text": f"{info.get('name', code)} {'上涨' if pct > 0 else '下跌'} {pct:+.2f}%",
                "data": info,
            })

    # 2. 板块异动信号
    for sector_type in ["conceptTop", "industryTop"]:
        sectors = all_data.get(sector_type, [])
        if isinstance(sectors, list):
            for s in sectors[:5]:
                pct = float(s.get("changePct", 0) or 0)
                if abs(pct) >= 5:
                    signals.append({
                        "level": "🔴", "type": "sector",
                        "text": f"板块异动: {s.get('name', '?')} {pct:+.2f}% (涨{s.get('upCount','?')}跌{s.get('downCount','?')})",
                        "data": s,
                    })
                elif abs(pct) >= 3:
                    signals.append({
                        "level": "🟡", "type": "sector",
                        "text": f"板块活跃: {s.get('name', '?')} {pct:+.2f}%",
                        "data": s,
                    })

    # 3. 涨停池信号
    zt_pool = all_data.get("ztPool", [])
    if isinstance(zt_pool, list) and zt_pool:
        lianban = [s for s in zt_pool if int(s.get("lianban", 0) or 0) >= 3]
        if lianban:
            names = ", ".join(s.get("name", "?") for s in lianban[:5])
            signals.append({
                "level": "🟡", "type": "sentiment",
                "text": f"连板梯队(≥3板): {names} (共{len(lianban)}只)",
            })
        signals.append({
            "level": "🟢", "type": "sentiment",
            "text": f"涨停 {len(zt_pool)} 只",
        })

    # 4. 龙虎榜信号
    lhb = all_data.get("longhu", [])
    if isinstance(lhb, list):
        inst_buy = [s for s in lhb if s.get("reason") and "机构" in str(s.get("reason", ""))]
        if inst_buy:
            names = ", ".join(s.get("name", "?") for s in inst_buy[:5])
            signals.append({
                "level": "🟡", "type": "capital",
                "text": f"龙虎榜机构买入: {names}",
            })

    # 5. 资金流信号
    cap_flow = all_data.get("capitalFlow", [])
    if isinstance(cap_flow, list):
        big_inflow = [s for s in cap_flow if float(s.get("mainNetInflow", 0) or 0) > 1e8]
        if big_inflow:
            names = ", ".join(f"{s['name']}({float(s['mainNetInflow'])/1e8:+.1f}亿)" for s in big_inflow[:5])
            signals.append({
                "level": "🟡", "type": "capital",
                "text": f"主力大额净流入: {names}",
            })

    # 6. 新闻信号(关键词匹配)
    news = all_data.get("news", [])
    if isinstance(news, list):
        for item in news:
            text = item.get("text", "")
            for kw in _CRITICAL_KW:
                if kw in text:
                    signals.append({
                        "level": "🔴", "type": "news",
                        "text": f"[{kw}] {text[:120]}",
                        "time": item.get("time", ""),
                    })
                    break
            else:
                for kw in _IMPORTANT_KW:
                    if kw in text:
                        signals.append({
                            "level": "🟡", "type": "news",
                            "text": f"[{kw}] {text[:120]}",
                            "time": item.get("time", ""),
                        })
                        break

    # 7. 政策信号(从新闻中单独提取)
    if isinstance(news, list):
        for item in news:
            text = item.get("text", "")
            for kw in _POLICY_KW:
                if kw in text:
                    already = any(s.get("text", "").startswith(f"[{kw}]") for s in signals)
                    if not already:
                        signals.append({
                            "level": "🟡", "type": "policy",
                            "text": f"[政策:{kw}] {text[:120]}",
                            "time": item.get("time", ""),
                        })
                    break

    # 去重(同 text 只保留最高 level)
    seen = {}
    for s in signals:
        key = s["text"][:60]
        if key not in seen or _level_rank(s["level"]) > _level_rank(seen[key]["level"]):
            seen[key] = s
    result = sorted(seen.values(), key=lambda x: -_level_rank(x["level"]))
    return result


def _level_rank(level):
    return {"🔴": 3, "🟡": 2, "🟢": 1}.get(level, 0)


def format_summary(radar_data):
    """生成人类可读的核心摘要"""
    signals = radar_data.get("coreSignals", [])
    indices = radar_data.get("indices", {})

    lines = []
    # 指数概览
    idx_parts = []
    for code in ["000001", "399001", "399006", "000688"]:
        info = indices.get(code, {})
        if info:
            idx_parts.append(f"{info.get('name','?')} {info.get('price','?')}({info.get('changePct','?')}%)")
    if idx_parts:
        lines.append("📊 " + " | ".join(idx_parts))

    # 核心信号
    critical = [s for s in signals if s["level"] == "🔴"]
    important = [s for s in signals if s["level"] == "🟡"]
    normal = [s for s in signals if s["level"] == "🟢"]

    if critical:
        lines.append(f"\n🔴 关键信号({len(critical)}):")
        for s in critical[:5]:
            lines.append(f"  • {s['text']}")
    if important:
        lines.append(f"\n🟡 重要信号({len(important)}):")
        for s in important[:10]:
            lines.append(f"  • {s['text']}")
    if normal:
        lines.append(f"\n🟢 一般({len(normal)})")

    # 市场概况
    zt = radar_data.get("ztPool", [])
    lhb = radar_data.get("longhu", [])
    if isinstance(zt, list):
        lines.append(f"\n涨停: {len(zt)}只" + (f" | 龙虎榜: {len(lhb)}条" if isinstance(lhb, list) else ""))

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def run_radar(sections=None, ticker=None, fast=False):
    """执行全量扫描,返回结构化数据。

    fast=True 时跳过高延迟端点(longhu/capital),HTTP 调用并行化。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    all_sections = sections or ["index", "rank", "sector", "zt", "longhu", "capital", "news"]
    if fast:
        all_sections = [s for s in all_sections if s not in ("longhu", "capital")]

    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sections": all_sections,
        "fast": fast,
    }

    sys.stderr.write(f"[radar] 开始扫描({len(all_sections)} sections, fast={fast})...\n")
    t0 = time.time()

    # 构建并行任务列表
    tasks = {}
    if "index" in all_sections:
        tasks["indices"] = fetch_indices
    if "rank" in all_sections:
        tasks["rankUp"] = lambda: fetch_rank_sina("changepercent", 30)
        tasks["rankAmount"] = lambda: fetch_rank_sina("amount", 30)
    if "sector" in all_sections:
        tasks["conceptTop"] = lambda: fetch_sector_ranking("concept", 20)
        tasks["industryTop"] = lambda: fetch_sector_ranking("industry", 15)
    if "zt" in all_sections:
        tasks["ztPool"] = fetch_zt_pool
    if "longhu" in all_sections:
        tasks["longhu"] = fetch_longhu_bang
    if "capital" in all_sections:
        tasks["capitalFlow"] = lambda: fetch_capital_flow(20)
    if "news" in all_sections:
        tasks["news"] = lambda: fetch_news_sina_7x24(50)
    if ticker:
        tasks["stock"] = lambda: fetch_stock_snapshot(ticker)

    # 并行执行所有 HTTP 调用
    with ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as pool:
        futures = {pool.submit(fn): key for key, fn in tasks.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                result[key] = future.result()
            except Exception as e:
                result[key] = {"_error": str(e)[:120]}

    # 提取核心信号
    result["coreSignals"] = extract_signals(result)

    elapsed = round(time.time() - t0, 1)
    result["elapsed"] = elapsed
    sys.stderr.write(f"[radar] 完成: {elapsed}s, {len(result['coreSignals'])} 条核心信号\n")
    return result


def main():
    p = argparse.ArgumentParser(description="市场雷达——多源数据采集+核心信号提取")
    p.add_argument("--section", default="", help="只扫指定板块: index/rank/sector/zt/longhu/capital/news")
    p.add_argument("--ticker", default="", help="加个股维度(6位代码)")
    p.add_argument("--run-id", default="", help="写入 data/runs/{run-id}/_radar.json")
    p.add_argument("--summary", action="store_true", help="只输出摘要到 stdout")
    p.add_argument("--fast", action="store_true", help="快速模式:跳过 slow 端点(longhu/capital),HTTP 并行")
    args = p.parse_args()

    sections = args.section.split(",") if args.section else None
    data = run_radar(sections=sections, ticker=args.ticker or None, fast=args.fast)

    if args.run_id:
        run_dir = f"data/runs/{args.run_id}"
        os.makedirs(run_dir, exist_ok=True)
        out_path = os.path.join(run_dir, "_radar.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        sys.stderr.write(f"[radar] 写入 {out_path}\n")

    if args.summary:
        print(format_summary(data))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
