#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sentiment_engine.py — 社交舆情量化引擎 (Layer 1.5: Social Sentiment)
V2.1 — 基于 a-stock-data skill 生产级端点, 共享 astock_data 基础模块

数据源(全部免密钥):
  - 同花顺热榜 (ths_hot_list): 人气值+概念标签+排名变化
  - 东财人气榜 (em_hot_rank): 排名+排名变化
  - 东财概念命中 (em_hot_concept): 个股被归到哪些概念在炒
  - 打板情绪 (limit_up_sentiment): 涨停/炸板/跌停/连板梯队/炸板率
  - astock_data: 共享 em_get/em_post 限流 + eastmoney_datacenter

用法:
  python scripts/sentiment_engine.py --codes 600519,002001 --output sentiment_scores.json
  python scripts/sentiment_engine.py --codes 600519 --data-dir data/runs/... --json '{"regime":"ranging"}'

输出: JSON 到 stdout 或 --output 文件
"""
import json
import sys
import os
import re
import math
import argparse
import time
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ════════════════════════════════════════════
# 共享模块: 从 astock_data 导入基础工具
# ════════════════════════════════════════════
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from astock_data import em_get, em_post, UA, HAS_REQUESTS
    _requests = None  # 不直接 import requests, 走 astock_data
    if not HAS_REQUESTS:
        import requests as _requests
except ImportError:
    # astock_data 不可用时自行降级
    try:
        import requests as _requests
        HAS_REQUESTS = True
    except ImportError:
        HAS_REQUESTS = False
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    EM_MIN_INTERVAL = 1.0
    _em_last_call = [0.0]
    import random

    if HAS_REQUESTS:
        EM_SESSION = _requests.Session()
        EM_SESSION.headers.update({"User-Agent": UA})
    else:
        EM_SESSION = None

    def em_get(url, params=None, headers=None, timeout=15, **kwargs):
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
# a-stock-data 端点函数 (从 skill 提取, 生产级)
# ════════════════════════════════════════════

def ths_hot_list(period="hour"):
    """同花顺热榜: 人气值+概念标签+排名变化。
    返回: [{rank, code, name, heat, pct, rank_chg, concepts, tag}]
    """
    if not HAS_REQUESTS:
        return []
    try:
        r = _requests.get("https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock",
            params={"stock_type": "a", "type": period, "list_type": "normal"},
            headers={"User-Agent": UA}, timeout=10)
        lst = (r.json().get("data") or {}).get("stock_list") or []
    except Exception as e:
        sys.stderr.write(f"[sentiment] THS热榜失败: {e}\n")
        return []
    out = []
    for it in lst:
        tag = it.get("tag") or {}
        out.append({
            "rank": it.get("order"),
            "code": it.get("code"),
            "name": it.get("name"),
            "heat": it.get("rate"),
            "pct": it.get("rise_and_fall"),
            "rank_chg": it.get("hot_rank_chg"),
            "concepts": tag.get("concept_tag") or [],
            "tag": tag.get("popularity_tag", ""),
        })
    return out


EM_HOT_BODY = {"appId": "appId01", "globalId": "786e4c21-70dc-435a-93bb-38"}

def em_hot_rank(top=100):
    """东财人气榜: 排名+排名变化+名称价格。
    返回: [{rank, code, name, price, pct, rank_chg}]
    """
    if not HAS_REQUESTS:
        return []
    try:
        r = _requests.post("https://emappdata.eastmoney.com/stockrank/getAllCurrentList",
            json={**EM_HOT_BODY, "marketType": "", "pageNo": 1, "pageSize": top},
            headers={"User-Agent": UA}, timeout=10)
        data = r.json().get("data") or []
        if not data:
            return []
        secids = [("0." if it["sc"].startswith("SZ") else "1.") + it["sc"][2:] for it in data]
        u = _requests.get("https://push2.eastmoney.com/api/qt/ulist.np/get",
            params={"ut": "f057cbcbce2a86e2866ab8877db1d059", "fltt": 2, "invt": 2,
                    "fields": "f14,f3,f12,f2", "secids": ",".join(secids)},
            headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}, timeout=10)
        diff = (u.json().get("data") or {}).get("diff") or []
        if isinstance(diff, dict):
            diff = list(diff.values())
        nm = {x["f12"]: (x.get("f14"), x.get("f2"), x.get("f3")) for x in diff}
    except Exception as e:
        sys.stderr.write(f"[sentiment] 东财人气榜失败: {e}\n")
        return []
    out = []
    for it in data:
        code = it["sc"][2:]
        name, price, pct = nm.get(code, ("", None, None))
        out.append({
            "rank": it["rk"],
            "code": code,
            "name": name,
            "price": price,
            "pct": pct,
            "rank_chg": it.get("hisRc"),
        })
    return out


def em_hot_concept(code):
    """东财个股热门概念命中: 这只票当下被归到哪些概念在炒。
    返回: [{concept, bk, hit}] 按热度降序。
    """
    if not HAS_REQUESTS:
        return []
    try:
        prefix = "SH" if code.startswith("6") else "SZ"
        r = _requests.post("https://emappdata.eastmoney.com/stockrank/getHotStockRankList",
            json={**EM_HOT_BODY, "srcSecurityCode": prefix + code},
            headers={"User-Agent": UA}, timeout=10)
        data = r.json().get("data") or []
    except Exception as e:
        sys.stderr.write(f"[sentiment] 东财概念命中失败({code}): {e}\n")
        return []
    return [{"concept": x.get("conceptName"), "bk": x.get("conceptId"),
             "hit": x.get("hitCount")} for x in data]


# ── 打板层 (东财 push2ex) ──

ZTB_UT = "7eea3edcaed734bea9cbfc24409ed989"

def _fmt_zt_time(t):
    s = str(t).zfill(6)
    return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"

def _em_zt_api(endpoint, sort, date):
    if not HAS_REQUESTS:
        return []
    url = f"https://push2ex.eastmoney.com/{endpoint}"
    params = {"ut": ZTB_UT, "dpt": "wz.ztzt", "Pageindex": 0,
              "pagesize": 10000, "sort": sort, "date": date}
    headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}
    try:
        r = em_get(url, params=params, headers=headers, timeout=10)
        if r is None:
            return []
        return (r.json().get("data") or {}).get("pool") or []
    except Exception as e:
        sys.stderr.write(f"[sentiment] 涨停板池 {endpoint} 失败: {e}\n")
        return []

def em_zt_pool(date):
    out = []
    for p in _em_zt_api("getTopicZTPool", "fbt:asc", date):
        out.append({"code": p["c"], "name": p["n"], "price": p["p"] / 1000,
            "pct": round(p["zdp"], 2), "limit_days": p["lbc"],
            "seal_fund": p["fund"], "break_times": p["zbc"],
            "industry": p.get("hybk", "")})
    return out

def em_zb_pool(date):
    out = []
    for p in _em_zt_api("getTopicZBPool", "fbt:asc", date):
        out.append({"code": p["c"], "name": p["n"], "price": p["p"] / 1000,
            "break_times": p["zbc"], "industry": p.get("hybk", "")})
    return out

def em_dt_pool(date):
    out = []
    for p in _em_zt_api("getTopicDTPool", "fund:asc", date):
        out.append({"code": p["c"], "name": p["n"], "price": p["p"] / 1000,
            "pct": round(p["zdp"], 2), "industry": p.get("hybk", "")})
    return out


def limit_up_sentiment(date):
    """打板情绪温度计: 连板梯队+炸板率+涨跌停对比。"""
    zt, zb, dt = em_zt_pool(date), em_zb_pool(date), em_dt_pool(date)
    ladder = {}
    for s in zt:
        ladder[s["limit_days"]] = ladder.get(s["limit_days"], 0) + 1
    zt_n, zb_n = len(zt), len(zb)
    return {
        "date": date,
        "zt_count": zt_n,
        "zb_count": zb_n,
        "dt_count": len(dt),
        "break_rate": round(zb_n / (zt_n + zb_n) * 100, 1) if (zt_n + zb_n) else 0,
        "max_height": max((s["limit_days"] for s in zt), default=0),
        "ladder": dict(sorted(ladder.items())),
    }


# ════════════════════════════════════════════
# 读取 _shared.json 补充信号
# ════════════════════════════════════════════

def read_market_emotion(data_dir):
    """从 _shared.json 读取 market_radar 补充信号。"""
    shared_path = os.path.join(data_dir, '_shared.json') if data_dir else ''
    if shared_path and os.path.exists(shared_path):
        try:
            with open(shared_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            radar = data.get('data', data).get('market_radar', {})
            signals = radar.get('core_signals', [])
            for sig in signals:
                text = sig.get('text', '') if isinstance(sig, dict) else str(sig)
                if any(kw in text for kw in ['critical', 'important', '涨停', '炸板']):
                    return {"_shared_signals": signals[:10]}
        except Exception:
            pass
    return None


# ════════════════════════════════════════════
# 综合评分计算
# ════════════════════════════════════════════

def compute_social_scores(code, ths_map, em_map, concepts, market_emotion):
    """综合多源社交数据 → 量化评分。

    Args:
        code: 股票代码
        ths_map: 同花顺热榜 {code: {rank, heat, rank_chg, concepts, tag}}
        em_map: 东财人气榜 {code: {rank, name, pct, rank_chg}}
        concepts: em_hot_concept(code) 结果 [{concept, bk, hit}]
        market_emotion: limit_up_sentiment() 结果
    """

    # ── 1. 社交热度 (0-100) ──
    ths_data = ths_map.get(code)
    em_data = em_map.get(code)

    heat_score = 0
    source_count = 0

    # 同花顺热榜: rank 越小越热, heat 值越大越热
    if ths_data:
        source_count += 1
        rank = ths_data.get('rank', 999) or 999
        heat_val = ths_data.get('heat', 0) or 0
        # rank 1-10 → 90-100分, rank 11-50 → 60-89分, rank 50+ → 0-59分
        if rank <= 10:
            heat_score = max(heat_score, 90 + (10 - rank))
        elif rank <= 50:
            heat_score = max(heat_score, 60 + (50 - rank) * 0.75)
        elif rank <= 100:
            heat_score = max(heat_score, 30 + (100 - rank) * 0.6)
        else:
            heat_score = max(heat_score, min(30, heat_val / 100))

    # 东财人气榜: rank 越小越热
    if em_data:
        source_count += 1
        rank = em_data.get('rank', 999) or 999
        if rank <= 10:
            heat_score = max(heat_score, 85 + (10 - rank))
        elif rank <= 50:
            heat_score = max(heat_score, 55 + (50 - rank) * 0.75)
        elif rank <= 100:
            heat_score = max(heat_score, 25 + (100 - rank) * 0.6)
        else:
            heat_score = max(heat_score, 10)

    # 概念命中加成: 被归到多个热门概念 = 额外热度
    if concepts:
        source_count += 1
        concept_count = len(concepts)
        total_hits = sum(c.get('hit', 0) or 0 for c in concepts)
        heat_score = min(100, heat_score + min(15, concept_count * 3 + total_hits * 0.01))

    if source_count == 0:
        heat_score = 50  # 无数据时中性

    social_heat = round(min(100, max(0, heat_score)), 1)

    # ── 2. 热度动量 (-1 到 1) ──
    heat_momentum = 0.0
    if ths_data:
        rank_chg = ths_data.get('rank_chg', 0) or 0
        # rank_chg > 0 = 排名上升(热度增加), < 0 = 排名下降
        heat_momentum = max(-1.0, min(1.0, rank_chg / 50))
    if em_data and heat_momentum == 0:
        rank_chg = em_data.get('rank_chg', 0) or 0
        heat_momentum = max(-1.0, min(1.0, rank_chg / 50))

    # ── 3. 看多比例 (0-1) ──
    # 从概念命中和排名变化推断: 排名上升+多概念命中 = 市场看多
    bull_ratio = 0.5
    if heat_momentum > 0.2 and concepts:
        bull_ratio = min(0.9, 0.5 + heat_momentum * 0.3 + len(concepts) * 0.03)
    elif heat_momentum < -0.2:
        bull_ratio = max(0.1, 0.5 + heat_momentum * 0.3)

    # ── 4. 炒作风险 (0-100) ──
    hype_risk = 0
    # 极端热度 + 排名快速上升 = 短期炒作信号
    if social_heat > 80:
        hype_risk += 30
    if social_heat > 60 and heat_momentum > 0.5:
        hype_risk += 25  # 热度快速上升
    if concepts and len(concepts) > 5:
        hype_risk += 15  # 被归到太多概念 = 万金油炒作
    # 打板情绪过热也加风险
    if market_emotion:
        break_rate = market_emotion.get('break_rate', 0) or 0
        max_height = market_emotion.get('max_height', 0) or 0
        if break_rate > 40:  # 炸板率>40% = 分歧严重
            hype_risk += 10
        if max_height >= 7:  # 7连板以上 = 市场极端亢奋
            hype_risk += 10
    hype_risk = min(100, hype_risk)

    # ── 5. 讨论加速度 ──
    discussion_accel = heat_momentum * 0.8

    # ── 6. 市场情绪 ──
    emotion = {
        'limit_up_count': market_emotion.get('zt_count', 0) if market_emotion else 0,
        'seal_rate': round(1 - (market_emotion.get('break_rate', 50) if market_emotion else 50) / 100, 3),
        'fail_rate': round((market_emotion.get('break_rate', 0) if market_emotion else 0) / 100, 3),
        'board_height': market_emotion.get('max_height', 0) if market_emotion else 0,
    }

    return {
        'code': code,
        'social_heat': social_heat,
        'heat_momentum': round(heat_momentum, 3),
        'bull_ratio': round(bull_ratio, 3),
        'discussion_accel': round(discussion_accel, 3),
        'hype_risk': round(hype_risk, 1),
        'sources_available': source_count,
        'raw': {
            'ths_rank': ths_data.get('rank') if ths_data else None,
            'ths_heat': ths_data.get('heat') if ths_data else None,
            'ths_rank_chg': ths_data.get('rank_chg') if ths_data else None,
            'ths_concepts': ths_data.get('concepts', []) if ths_data else [],
            'em_rank': em_data.get('rank') if em_data else None,
            'em_rank_chg': em_data.get('rank_chg') if em_data else None,
            'concept_hits': len(concepts) if concepts else 0,
            'top_concepts': [c['concept'] for c in (concepts or [])[:5]],
        },
        'market_emotion': emotion,
    }


# ════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='社交舆情量化引擎 V2 (a-stock-data)')
    parser.add_argument('--codes', required=True, help='逗号分隔的股票代码')
    parser.add_argument('--data-dir', default='', help='读取 _shared.json 等上下文的目录')
    parser.add_argument('--json', default='{}', help='额外参数 JSON (regime)')
    parser.add_argument('--output', default='', help='输出文件路径 (默认 stdout)')
    args = parser.parse_args()

    codes = [c.strip() for c in args.codes.split(',') if c.strip()]
    params = json.loads(args.json) if args.json else {}
    regime = params.get('regime', 'ranging')

    if not HAS_REQUESTS:
        sys.stderr.write("[sentiment] WARNING: requests 库未安装, 全部降级为中性评分\n")

    # 1. 获取全市场热榜 (一次调用, 所有股票共享)
    sys.stderr.write("[sentiment] 获取同花顺热榜...")
    ths_list = ths_hot_list()
    ths_map = {s['code']: s for s in ths_list if s.get('code')}
    sys.stderr.write(f"OK ({len(ths_map)}只)\n")

    sys.stderr.write("[sentiment] 获取东财人气榜...")
    em_list = em_hot_rank(100)
    em_map = {s['code']: s for s in em_list if s.get('code')}
    sys.stderr.write(f"OK ({len(em_map)}只)\n")

    # 2. 打板情绪 (全市场)
    today = time.strftime("%Y%m%d")
    sys.stderr.write("[sentiment] 获取打板情绪...")
    market_emotion = limit_up_sentiment(today)
    sys.stderr.write(f"OK (涨停{market_emotion.get('zt_count',0)} "
                     f"炸板{market_emotion.get('zb_count',0)} "
                     f"跌停{market_emotion.get('dt_count',0)} "
                     f"最高{market_emotion.get('max_height',0)}连板)\n")

    # 3. 补充 _shared.json
    shared = read_market_emotion(args.data_dir)

    # 4. 逐票采集概念命中 + 计算评分
    results = []
    for code in codes:
        sys.stderr.write(f"[sentiment] {code}: 概念命中...")
        concepts = em_hot_concept(code)
        sys.stderr.write(f"{'OK' if concepts else 'NONE'} ({len(concepts)}个)\n")

        scores = compute_social_scores(code, ths_map, em_map, concepts, market_emotion)
        results.append(scores)

    # 排序(按 social_heat 降序)
    results.sort(key=lambda x: x['social_heat'], reverse=True)
    for i, r in enumerate(results):
        r['rank'] = i + 1

    # 输出
    summary_parts = []
    for r in results[:3]:
        summary_parts.append(f"{r['code']}(heat={r['social_heat']},hype={r['hype_risk']})")
    summary = f'{len(results)}只股票舆情评分完成, Top3: {", ".join(summary_parts)}'

    output = {
        'regime': regime,
        'stocks': results,
        'market_emotion': {
            'zt_count': market_emotion.get('zt_count', 0),
            'zb_count': market_emotion.get('zb_count', 0),
            'dt_count': market_emotion.get('dt_count', 0),
            'break_rate': market_emotion.get('break_rate', 0),
            'max_height': market_emotion.get('max_height', 0),
            'ladder': market_emotion.get('ladder', {}),
        },
        'ths_hot_count': len(ths_map),
        'em_rank_count': len(em_map),
        'summary': summary,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    output_json = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        sys.stderr.write(f"[sentiment] 输出到 {args.output}\n")
    else:
        print(output_json)

    sys.stderr.write(f"[sentiment] {summary}\n")


if __name__ == '__main__':
    main()
