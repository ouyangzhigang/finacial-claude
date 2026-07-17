#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
astock_data.py — a-stock-data skill 共享数据模块

从 a-stock-data skill (V3.4, 43端点) 提取核心函数，供各量化引擎和 agent 复用。
所有东财请求走 em_get() 统一限流防封。

包含端点:
  - ths_hot_reason(): 同花顺热点+题材归因 (信号层 §3.1)
  - eastmoney_fund_flow_minute(): 分钟级资金流 (信号层 §3.4)
  - stock_fund_flow_120d(): 120日资金流 (资金面 §4.5)
  - lockup_expiry(): 解禁日历 (信号层 §3.6)
  - holder_num_change(): 股东户数变化 (资金面 §4.3)
  - margin_trading(): 融资融券 (资金面 §4.1)
  - block_trade(): 大宗交易 (资金面 §4.2)
  - eastmoney_concept_blocks(): 板块归属 (信号层 §3.3)
  - dragon_tiger_board(): 龙虎榜席位 (信号层 §3.5)
  - eastmoney_stock_news(): 个股新闻 (新闻层 §5.1)
  - cls_telegraph(): 财联社快讯 (新闻层 §5.2)

用法:
  from astock_data import ths_hot_reason, stock_fund_flow_120d
  reasons = ths_hot_reason()
  flows = stock_fund_flow_120d("600519")
"""
import json
import sys
import os
import time
import random
from typing import Optional
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ════════════════════════════════════════════
# 依赖检测
# ════════════════════════════════════════════
try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ════════════════════════════════════════════
# 东财防封: em_get 统一限流入口
# ════════════════════════════════════════════
EM_MIN_INTERVAL = 1.0  # 两次东财请求最小间隔(秒)
_em_last_call = [0.0]

if HAS_REQUESTS:
    EM_SESSION = _requests.Session()
    EM_SESSION.headers.update({"User-Agent": UA})
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        _adapter = HTTPAdapter(max_retries=Retry(
            total=3, connect=3, backoff_factor=0.6,
            status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]))
        EM_SESSION.mount("https://", _adapter)
        EM_SESSION.mount("http://", _adapter)
    except Exception:
        pass
else:
    EM_SESSION = None


def em_get(url, params=None, headers=None, timeout=15, **kwargs):
    """东财统一限流请求。所有 eastmoney.com 接口走此入口。"""
    if not HAS_REQUESTS:
        return None
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        r = EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
        return r
    except Exception:
        return None
    finally:
        _em_last_call[0] = time.time()


def em_post(url, json_data=None, headers=None, timeout=15):
    """东财 POST 请求(限流)。"""
    if not HAS_REQUESTS:
        return None
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        r = EM_SESSION.post(url, json=json_data, headers=headers, timeout=timeout)
        return r
    except Exception:
        return None
    finally:
        _em_last_call[0] = time.time()


# ════════════════════════════════════════════
# 东财数据中心统一查询 (龙虎榜/解禁/融资融券/大宗/股东户数/分红共用)
# ════════════════════════════════════════════
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def eastmoney_datacenter(report_name, columns="ALL", filter_str="",
                          page_size=50, sort_columns="", sort_types="-1"):
    """东财数据中心统一查询(已内置限流)。"""
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = em_get(DATACENTER_URL, params=params, timeout=15)
    if r is None:
        return []
    try:
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            return d["result"]["data"]
    except Exception:
        pass
    return []


# ════════════════════════════════════════════
# 信号层端点
# ════════════════════════════════════════════

def ths_hot_reason(date=None):
    """同花顺当日强势股归因。返回 [{code, name, reason(题材标签), pct, turnover, amount}]。
    reason 是核心: 人工编辑的题材标签, 如"算力租赁+Token工厂+AI政务"。"""
    if not HAS_REQUESTS:
        return []
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    try:
        url = (f"http://zx.10jqka.com.cn/event/api/getharden/"
               f"date/{date}/orderby/date/orderway/desc/charset/GBK/")
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=10)
        data = r.json()
        rows = data.get("data") or []
        return [{
            "code": it.get("code", ""),
            "name": it.get("name", ""),
            "reason": it.get("reason", ""),
            "pct": it.get("zhangfu", 0),
            "turnover": it.get("huanshou", 0),
            "amount": it.get("chengjiaoe", 0),
        } for it in rows]
    except Exception as e:
        sys.stderr.write(f"[astock] THS热点归因失败: {e}\n")
        return []


def eastmoney_concept_blocks(code):
    """个股所属板块/概念归属(东财 slist)。
    返回 {total, boards: [{name, code(BK), change_pct, lead_stock}], concept_tags: [...]}"""
    if not HAS_REQUESTS:
        return {"total": 0, "boards": [], "concept_tags": []}
    market_code = 1 if code.startswith("6") else 0
    params = {
        "fltt": "2", "invt": "2",
        "secid": f"{market_code}.{code}",
        "spt": "3", "pi": "0", "pz": "200", "po": "1",
        "fields": "f12,f14,f3,f128",
    }
    try:
        r = em_get("https://push2.eastmoney.com/api/qt/slist/get",
                   params=params, headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"},
                   timeout=15)
        if r is None:
            return {"total": 0, "boards": [], "concept_tags": []}
        d = r.json()
        diff = (d.get("data") or {}).get("diff") or {}
        items = diff.values() if isinstance(diff, dict) else diff
        boards = [{
            "name": it.get("f14", ""), "code": it.get("f12", ""),
            "change_pct": it.get("f3", ""), "lead_stock": it.get("f128", ""),
        } for it in items]
        return {"total": len(boards), "boards": boards,
                "concept_tags": [b["name"] for b in boards]}
    except Exception as e:
        sys.stderr.write(f"[astock] 板块归属失败({code}): {e}\n")
        return {"total": 0, "boards": [], "concept_tags": []}


def eastmoney_fund_flow_minute(code):
    """个股资金流向(分钟级, 当日盘中)。
    返回 [{time, main_net, small_net, mid_net, large_net, super_net}] 单位:元"""
    if not HAS_REQUESTS:
        return []
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    params = {
        "secid": secid, "klt": 1,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}
    try:
        r = em_get("https://push2.eastmoney.com/api/qt/stock/fflow/kline/get",
                   params=params, headers=headers, timeout=10)
        if r is None:
            return []
        d = r.json()
        rows = []
        for line in d.get("data", {}).get("klines", []):
            parts = line.split(",")
            if len(parts) >= 6:
                rows.append({
                    "time": parts[0],
                    "main_net": float(parts[1]),
                    "small_net": float(parts[2]),
                    "mid_net": float(parts[3]),
                    "large_net": float(parts[4]),
                    "super_net": float(parts[5]),
                })
        return rows
    except Exception as e:
        sys.stderr.write(f"[astock] 分钟资金流失败({code}): {e}\n")
        return []


def _fmt_zt_time(t):
    s = str(t).zfill(6)
    return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"


ZTB_UT = "7eea3edcaed734bea9cbfc24409ed989"


def _em_zt_api(endpoint, sort, date):
    if not HAS_REQUESTS:
        return []
    url = f"https://push2ex.eastmoney.com/{endpoint}"
    params = {"ut": ZTB_UT, "dpt": "wz.ztzt", "Pageindex": 0,
              "pagesize": 10000, "sort": sort, "date": date}
    try:
        r = em_get(url, params=params,
                   headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"},
                   timeout=10)
        if r is None:
            return []
        return (r.json().get("data") or {}).get("pool") or []
    except Exception:
        return []


def dragon_tiger_board(code, trade_date=None, look_back=30):
    """龙虎榜数据: 上榜记录+买卖席位TOP5+机构动向。"""
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=look_back)).strftime("%Y-%m-%d")

    records = []
    data = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f'(TRADE_DATE>="{start}")(TRADE_DATE<="{trade_date}")(SECURITY_CODE="{code}")',
        page_size=50, sort_columns="TRADE_DATE", sort_types="-1",
    )
    for row in data:
        records.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "reason": row.get("EXPLANATION", ""),
            "net_buy": round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
            "turnover": round(float(row.get("TURNOVERRATE") or 0), 2),
        })
    return {"records": records}


# ════════════════════════════════════════════
# 资金面端点
# ════════════════════════════════════════════

def stock_fund_flow_120d(code):
    """个股资金流(日级, 最近120个交易日)。
    返回 [{date, main_net, small_net, mid_net, large_net, super_net}] 单位:元"""
    if not HAS_REQUESTS:
        return []
    market_code = 1 if code.startswith("6") else 0
    params = {
        "secid": f"{market_code}.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "120",
    }
    headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/",
               "Origin": "https://quote.eastmoney.com"}
    try:
        r = em_get("https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
                   params=params, headers=headers, timeout=15)
        if r is None:
            return []
        d = r.json()
        rows = []
        for line in (d.get("data") or {}).get("klines", []):
            parts = line.split(",")
            if len(parts) >= 7:
                rows.append({
                    "date": parts[0],
                    "main_net": float(parts[1]) if parts[1] != "-" else 0,
                    "small_net": float(parts[2]) if parts[2] != "-" else 0,
                    "mid_net": float(parts[3]) if parts[3] != "-" else 0,
                    "large_net": float(parts[4]) if parts[4] != "-" else 0,
                    "super_net": float(parts[5]) if parts[5] != "-" else 0,
                })
        return rows
    except Exception as e:
        sys.stderr.write(f"[astock] 120日资金流失败({code}): {e}\n")
        return []


def margin_trading(code, page_size=30):
    """融资融券明细(日级)。
    返回 [{date, rzye(融资余额), rzmre(融资买入), rqye(融券余额), rzrqye(合计)}]"""
    data = eastmoney_datacenter(
        "RPTA_WEB_RZRQ_GGMX",
        filter_str=f'(SCODE="{code}")',
        page_size=page_size,
        sort_columns="DATE", sort_types="-1",
    )
    return [{
        "date": str(row.get("DATE", ""))[:10],
        "rzye": row.get("RZYE", 0),
        "rzmre": row.get("RZMRE", 0),
        "rqye": row.get("RQYE", 0),
        "rzrqye": row.get("RZRQYE", 0),
    } for row in data]


def block_trade(code, page_size=20):
    """大宗交易记录。
    返回 [{date, price, close, premium_pct, vol, amount, buyer, seller}]"""
    data = eastmoney_datacenter(
        "RPT_DATA_BLOCKTRADE",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="TRADE_DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        close = row.get("CLOSE_PRICE") or 0
        deal_price = row.get("DEAL_PRICE") or 0
        premium = ((deal_price / close - 1) * 100) if close else 0
        rows.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "price": deal_price, "close": close,
            "premium_pct": round(premium, 2),
            "vol": row.get("DEAL_VOLUME", 0),
            "amount": row.get("DEAL_AMT", 0),
            "buyer": row.get("BUYER_NAME", ""),
            "seller": row.get("SELLER_NAME", ""),
        })
    return rows


def holder_num_change(code, page_size=10):
    """股东户数变化(季度级)。
    返回 [{date, holder_num, change_num, change_ratio, avg_shares}]
    股东户数持续减少 = 筹码集中 = 主力吸筹信号"""
    data = eastmoney_datacenter(
        "RPT_HOLDERNUMLATEST",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="END_DATE", sort_types="-1",
    )
    return [{
        "date": str(row.get("END_DATE", ""))[:10],
        "holder_num": row.get("HOLDER_NUM", 0),
        "change_num": row.get("HOLDER_NUM_CHANGE", 0),
        "change_ratio": row.get("HOLDER_NUM_RATIO", 0),
        "avg_shares": row.get("AVG_FREE_SHARES", 0),
    } for row in data]


def lockup_expiry(code, trade_date=None, forward_days=90):
    """限售解禁日历: 历史解禁+未来90天待解禁。
    返回 {history: [...], upcoming: [...]}"""
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")
    history_data = eastmoney_datacenter(
        "RPT_LIFT_STAGE",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=15, sort_columns="FREE_DATE", sort_types="-1",
    )
    history = [{
        "date": str(row.get("FREE_DATE", ""))[:10],
        "type": row.get("FREE_SHARES_TYPE", ""),
        "shares": row.get("FREE_SHARES", 0),
        "able_shares": row.get("ABLE_FREE_SHARES", 0),
        "ratio": row.get("FREE_RATIO", 0),
    } for row in history_data]

    end_date = (datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)).strftime("%Y-%m-%d")
    upcoming_data = eastmoney_datacenter(
        "RPT_LIFT_STAGE",
        filter_str=f'(SECURITY_CODE="{code}")(FREE_DATE>="{trade_date}")(FREE_DATE<="{end_date}")',
        page_size=20, sort_columns="FREE_DATE", sort_types="1",
    )
    upcoming = [{
        "date": str(row.get("FREE_DATE", ""))[:10],
        "type": row.get("FREE_SHARES_TYPE", ""),
        "shares": row.get("FREE_SHARES", 0),
        "able_shares": row.get("ABLE_FREE_SHARES", 0),
        "ratio": row.get("FREE_RATIO", 0),
    } for row in upcoming_data]
    return {"history": history, "upcoming": upcoming}


# ════════════════════════════════════════════
# 新闻层端点
# ════════════════════════════════════════════

def eastmoney_stock_news(code, page_size=30):
    """东财个股新闻。返回 [{title, url, source, date, summary}]"""
    if not HAS_REQUESTS:
        return []
    try:
        url = f"https://search-api-web.eastmoney.com/search/jsonp"
        params = {
            "cb": "jQuery_cb",
            "param": json.dumps({
                "uid": "", "keyword": code, "type": ["cmsArticleWebOld"],
                "client": "web", "clientType": "web", "clientVersion": "curr",
                "param": {"cmsArticleWebOld": {"searchScope": "default", "sort": "default",
                    "pageIndex": 1, "pageSize": page_size, "preTag": "", "postTag": ""}}
            }),
        }
        r = em_get(url, params=params, headers={"Referer": "https://so.eastmoney.com/"}, timeout=15)
        if r is None:
            return []
        text = r.text
        # 去 JSONP 壳
        i = text.find("(")
        j = text.rfind(")")
        if i < 0 or j < 0:
            return []
        d = json.loads(text[i+1:j])
        articles = (d.get("result") or {}).get("cmsArticleWebOld", {}).get("list", [])
        return [{
            "title": a.get("title", "").replace("<em>", "").replace("</em>", ""),
            "url": a.get("url", ""),
            "source": a.get("mediaName", ""),
            "date": a.get("date", ""),
            "summary": a.get("content", "")[:200],
        } for a in articles]
    except Exception as e:
        sys.stderr.write(f"[astock] 个股新闻失败({code}): {e}\n")
        return []


def cls_telegraph(count=50):
    """财联社快讯(7x24)。返回 [{title, content, time, level}]"""
    if not HAS_REQUESTS:
        return []
    try:
        import hashlib
        ts = str(int(time.time()))
        sign = hashlib.md5(hashlib.sha1(ts.encode()).hexdigest().encode()).hexdigest()
        url = "https://www.cls.cn/v1/roll/get_roll_list"
        params = {"app": "CailianpressWeb", "os": "web", "sv": "8.4.6",
                  "sign": sign, "time": ts}
        r = _requests.get(url, params=params, headers={"User-Agent": UA}, timeout=10)
        data = r.json().get("data") or {}
        items = data.get("roll_data") or []
        return [{
            "title": it.get("title", ""),
            "content": it.get("content", "")[:200],
            "time": datetime.fromtimestamp(it.get("ctime", 0)).strftime("%H:%M:%S") if it.get("ctime") else "",
            "level": it.get("level", ""),
        } for it in items[:count]]
    except Exception as e:
        sys.stderr.write(f"[astock] 财联社快讯失败: {e}\n")
        return []


# ════════════════════════════════════════════
# 便捷: 资金流量化评分 (供 factor_engine 使用)
# ════════════════════════════════════════════

def compute_capital_score(code):
    """综合资金流数据 → capital_score (0-100)。
    供 factor_engine.py 替代 LLM 主观判断。

    评分维度:
    - 120日主力净流入趋势 (近5日 vs 近20日 vs 近60日)
    - 分钟级资金方向 (当日主力累计)
    - 融资融券变化 (融资余额增长 = 杠杆看多)
    - 大宗交易 (近期溢价 = 看好, 折价 = 抛压)
    """
    score = 50  # 中性起点

    # 1. 120日资金流趋势
    flows = stock_fund_flow_120d(code)
    if flows:
        n = len(flows)
        # 近5日主力净流入
        main_5d = sum(f["main_net"] for f in flows[-5:]) if n >= 5 else 0
        # 近20日
        main_20d = sum(f["main_net"] for f in flows[-20:]) if n >= 20 else 0
        # 近60日
        main_60d = sum(f["main_net"] for f in flows[-60:]) if n >= 60 else 0

        # 趋势: 短期>中期 = 资金加速流入
        if main_5d > 0 and main_20d > 0:
            accel = (main_5d / 5) / max(abs(main_20d / 20), 1)
            if accel > 1.5:
                score += 20  # 加速流入
            elif accel > 1.0:
                score += 10
        elif main_5d < 0 and main_20d < 0:
            score -= 15  # 持续流出
        elif main_5d > 0 and main_20d < 0:
            score += 15  # 短期反转流入

    # 2. 融资融券
    margin = margin_trading(code, page_size=10)
    if len(margin) >= 5:
        rzye_now = margin[0].get("rzye", 0) or 0
        rzye_5d = margin[4].get("rzye", 0) or 0
        if rzye_5d > 0:
            margin_change = (rzye_now - rzye_5d) / rzye_5d
            if margin_change > 0.05:  # 融资余额增5%+
                score += 10
            elif margin_change < -0.05:  # 融资余额降5%+
                score -= 10

    # 3. 大宗交易
    trades = block_trade(code, page_size=10)
    if trades:
        recent = [t for t in trades[:5] if t.get("premium_pct") is not None]
        if recent:
            avg_premium = sum(t["premium_pct"] for t in recent) / len(recent)
            if avg_premium > 0:  # 溢价成交
                score += 5
            elif avg_premium < -3:  # 大幅折价
                score -= 10

    return max(0, min(100, score))


# ════════════════════════════════════════════
# 便捷: 供给端风险评估 (供 risk-portfolio 使用)
# ════════════════════════════════════════════

def compute_supply_risk(code):
    """评估供给端风险: 解禁+股东户数+大宗交易。
    返回 {risk_score: 0-100, details: {...}}
    0=无风险, 100=高风险"""
    risk = 0
    details = {}

    # 1. 解禁日历
    lockup = lockup_expiry(code)
    upcoming = lockup.get("upcoming", [])
    if upcoming:
        # 未来30天内有解禁
        near = [u for u in upcoming if u.get("shares", 0) > 0]
        total_shares = sum(u.get("shares", 0) or 0 for u in near)
        if total_shares > 0:
            risk += min(40, int(total_shares / 1e6 * 2))  # 每百万股+2分
            details["lockup_shares"] = total_shares
            details["lockup_dates"] = [u["date"] for u in near[:3]]

    # 2. 股东户数变化
    holders = holder_num_change(code, page_size=4)
    if len(holders) >= 2:
        latest = holders[0]
        prev = holders[1]
        ratio = latest.get("change_ratio", 0) or 0
        if ratio > 10:  # 股东户数增加10%+ = 筹码分散
            risk += 15
        elif ratio < -10:  # 股东户数减少10%+ = 筹码集中(利好)
            risk -= 10
        details["holder_change_ratio"] = ratio

    # 3. 大宗交易折价
    trades = block_trade(code, page_size=5)
    if trades:
        discounts = [t for t in trades if t.get("premium_pct", 0) < -5]
        if discounts:
            risk += min(20, len(discounts) * 5)
            details["discount_trades"] = len(discounts)

    return {
        "risk_score": max(0, min(100, risk)),
        "details": details,
    }
