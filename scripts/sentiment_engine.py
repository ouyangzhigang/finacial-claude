#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sentiment_engine.py — 社交舆情量化引擎 (Layer 1.5: Social Sentiment)

借鉴: 雪球热度因子 + 股吧情绪指标 + 社交动量策略
核心: 将社交舆情从 LLM 质化判断升级为量化评分。
     讨论量+情绪+拐点 → 社交热度分 + 炒作风险分。

数据源(免密钥):
  - 东方财富股吧: 帖子数/阅读量/情绪词频
  - 雪球讨论: 讨论帖数/评论数(需 stealthy 通道)
  - 新浪股吧: 热帖/讨论密度
  - market_radar: 涨停/封板率/炸板率/连板高度(从 _shared.json 读取)

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
import urllib.request
import ssl
import time
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CTX = ssl._create_unverified_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ════════════════════════════════════════════
# 情绪词典
# ════════════════════════════════════════════
BULL_WORDS = [
    '看多', '看涨', '利好', '涨停', '突破', '新高', '加仓', '满仓', '牛市',
    '起飞', '暴涨', '翻倍', '低估', '价值', '主力', '拉升', '启动', '放量',
    '金叉', '底部', '反弹', '回调买入', '抄底', '机构', '增持',
]
BEAR_WORDS = [
    '看空', '看跌', '利空', '跌停', '破位', '新低', '减仓', '清仓', '熊市',
    '崩盘', '暴跌', '腰斩', '高估', '泡沫', '出货', '砸盘', '套牢', '缩量',
    '死叉', '顶部', '割肉', '跑路', '散户', '减持', '质押', '暴雷',
]


# ════════════════════════════════════════════
# HTTP 工具
# ════════════════════════════════════════════

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
        except Exception:
            if attempt == 1:
                return None
            time.sleep(0.5)
    return None


# ════════════════════════════════════════════
# 数据源采集器
# ════════════════════════════════════════════

def fetch_guba_eastmoney(code: str) -> Optional[dict]:
    """东方财富股吧: 帖子列表 → 讨论量 + 情绪分析。
    URL: https://guba.eastmoney.com/list,{code}.html
    """
    url = f"https://guba.eastmoney.com/list,{code}.html"
    html = _http(url, encoding="utf-8")
    if not html:
        return None

    # 提取帖子标题和阅读量
    posts = []
    # 东方财富股吧帖子格式: <span class="l3">标题</span> ... <span class="l4">阅读</span>
    title_pattern = re.findall(r'class="l3[^"]*"[^>]*>([^<]+)<', html)
    read_pattern = re.findall(r'class="l4[^"]*"[^>]*>(\d+)<', html)

    for i, title in enumerate(title_pattern[:30]):  # 取前30帖
        reads = int(read_pattern[i]) if i < len(read_pattern) else 0
        posts.append({'title': title.strip(), 'reads': reads})

    if not posts:
        # 备用: 尝试 JSON API
        api_url = f"https://guba.eastmoney.com/interface/GetData?path=guba/newfeedlist&param=ps%3D30%26code%3D{code}"
        raw = _http(api_url)
        if raw:
            try:
                data = json.loads(raw)
                for item in data.get('re', [])[:30]:
                    posts.append({
                        'title': item.get('post_title', ''),
                        'reads': item.get('post_click_count', 0),
                    })
            except Exception:
                pass

    if not posts:
        return None

    # 情绪分析
    bull_count = 0
    bear_count = 0
    total_reads = 0
    for p in posts:
        title = p['title']
        total_reads += p['reads']
        for w in BULL_WORDS:
            if w in title:
                bull_count += 1
                break
        for w in BEAR_WORDS:
            if w in title:
                bear_count += 1
                break

    total = bull_count + bear_count
    bull_ratio = bull_count / max(total, 1)

    return {
        'source': 'guba_eastmoney',
        'post_count': len(posts),
        'total_reads': total_reads,
        'avg_reads': total_reads // max(len(posts), 1),
        'bull_count': bull_count,
        'bear_count': bear_count,
        'bull_ratio': round(bull_ratio, 3),
        'titles': [p['title'] for p in posts[:5]],
    }


def fetch_sina_guba(code: str) -> Optional[dict]:
    """新浪股吧: 讨论密度。
    URL: https://guba.sina.com.cn/?symbol={code}
    """
    # 新浪股吧 API
    prefix = "sh" if code.startswith(('6', '9')) else "sz"
    url = f"https://guba.sina.com.cn/interface/GetData?path=bar/barlist&param=bar_code%3D{prefix}{code}%26num%3D30"
    raw = _http(url)
    if not raw:
        return None

    try:
        data = json.loads(raw)
        items = data.get('result', {}).get('data', [])
        if not items:
            return None

        post_count = len(items)
        total_comments = sum(item.get('comment_count', 0) for item in items)
        return {
            'source': 'sina_guba',
            'post_count': post_count,
            'total_comments': total_comments,
            'avg_comments': total_comments // max(post_count, 1),
        }
    except Exception:
        return None


def fetch_xueqiu_social(code: str) -> Optional[dict]:
    """雪球社交: 关注人数 + 讨论量(通过雪球 API)。
    注意: 雪球反爬强, 此处用轻量 API 而非页面爬取。
    """
    prefix = "SH" if code.startswith(('6', '9')) else "SZ"
    # 雪球讨论 API (轻量, 不需要 stealthy)
    url = f"https://stock.xueqiu.com/v5/stock/portfolio/stock/list.json?symbol={prefix}{code}&size=30&page=1"
    headers = {
        "User-Agent": UA,
        "Referer": f"https://xueqiu.com/S/{prefix}{code}",
        "Origin": "https://xueqiu.com",
    }
    raw = _http(url, headers=headers)
    if not raw:
        return None

    try:
        data = json.loads(raw)
        items = data.get('data', {}).get('items', [])
        if not items:
            return None

        post_count = len(items)
        total_reply = sum(item.get('reply_count', 0) for item in items)
        total_retweet = sum(item.get('retweet_count', 0) for item in items)
        return {
            'source': 'xueqiu',
            'post_count': post_count,
            'total_replies': total_reply,
            'total_retweets': total_retweet,
            'engagement': total_reply + total_retweet * 2,
        }
    except Exception:
        return None


def read_market_emotion(data_dir: str) -> Optional[dict]:
    """从 _shared.json 或 market_radar 输出读取市场情绪指标。"""
    shared_path = os.path.join(data_dir, '_shared.json') if data_dir else ''
    if shared_path and os.path.exists(shared_path):
        try:
            with open(shared_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            radar = data.get('data', data).get('market_radar', {})
            signals = radar.get('core_signals', [])
            # 提取情绪相关信号
            zt_count = 0
            seal_rate = 0.5
            fail_rate = 0.2
            board_height = 3
            for sig in signals:
                text = sig.get('text', '') if isinstance(sig, dict) else str(sig)
                # 尝试从信号文本提取数值
                m = re.search(r'涨停(\d+)家', text)
                if m:
                    zt_count = int(m.group(1))
                m = re.search(r'封板率(\d+)%', text)
                if m:
                    seal_rate = int(m.group(1)) / 100
                m = re.search(r'炸板率(\d+)%', text)
                if m:
                    fail_rate = int(m.group(1)) / 100
                m = re.search(r'连板高度(\d+)', text)
                if m:
                    board_height = int(m.group(1))
            return {
                'limit_up_count': zt_count,
                'seal_rate': round(seal_rate, 3),
                'fail_rate': round(fail_rate, 3),
                'board_height': board_height,
            }
        except Exception:
            pass
    return None


# ════════════════════════════════════════════
# 综合评分计算
# ════════════════════════════════════════════

def compute_social_scores(code: str, guba: Optional[dict], sina: Optional[dict],
                          xueqiu: Optional[dict], market_emotion: Optional[dict]) -> dict:
    """综合多源社交数据 → 量化评分。"""

    # ── 1. 社交热度 (0-100) ──
    # 综合: 帖子数 + 阅读量 + 评论数 + 转发数
    heat_raw = 0
    source_count = 0

    if guba:
        heat_raw += guba['post_count'] * 2 + guba['avg_reads'] * 0.01
        source_count += 1
    if sina:
        heat_raw += sina['post_count'] * 1.5 + sina['avg_comments'] * 0.5
        source_count += 1
    if xueqiu:
        heat_raw += xueqiu['post_count'] * 2 + xueqiu['engagement'] * 0.02
        source_count += 1

    # 归一化到 0-100 (经验值: heat_raw=50 为中位热度)
    social_heat = min(100, max(0, heat_raw * 1.5))
    if source_count == 0:
        social_heat = 50  # 无数据时中性

    # ── 2. 看多比例 (0-1) ──
    bull_ratio = 0.5  # 默认中性
    if guba and guba.get('bull_count', 0) + guba.get('bear_count', 0) > 0:
        bull_ratio = guba['bull_ratio']

    # ── 3. 热度动量 (-1 到 1) ──
    # 当前无法获取历史数据对比, 用帖子活跃度估算
    heat_momentum = 0.0
    if guba and guba['avg_reads'] > 500:
        heat_momentum = min(1.0, (guba['avg_reads'] - 200) / 800)
    if xueqiu and xueqiu.get('engagement', 0) > 50:
        heat_momentum = max(heat_momentum, min(1.0, xueqiu['engagement'] / 200))

    # ── 4. 炒作风险 (0-100) ──
    # 社交热度高但情绪极端看多 → 炒作风险高
    hype_risk = 0
    if social_heat > 60 and bull_ratio > 0.7:
        hype_risk = min(100, int((social_heat - 50) * 1.5 + (bull_ratio - 0.5) * 100))
    if social_heat > 80:
        hype_risk = min(100, hype_risk + 20)  # 极端热度额外加风险

    # ── 5. 讨论加速度 ──
    discussion_accel = heat_momentum * 0.8  # 简化版

    # ── 6. 市场情绪 (从 market_radar) ──
    emotion = market_emotion or {
        'limit_up_count': 0,
        'seal_rate': 0.5,
        'fail_rate': 0.2,
        'board_height': 3,
    }

    return {
        'code': code,
        'social_heat': round(social_heat, 1),
        'heat_momentum': round(heat_momentum, 3),
        'bull_ratio': round(bull_ratio, 3),
        'discussion_accel': round(discussion_accel, 3),
        'hype_risk': round(hype_risk, 1),
        'sources_available': source_count,
        'raw': {
            'guba': {k: v for k, v in (guba or {}).items() if k != 'titles'} if guba else None,
            'sina': sina,
            'xueqiu': xueqiu,
        },
        'market_emotion': emotion,
    }


# ════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='社交舆情量化引擎')
    parser.add_argument('--codes', required=True, help='逗号分隔的股票代码')
    parser.add_argument('--data-dir', default='', help='读取 _shared.json 等上下文的目录')
    parser.add_argument('--json', default='{}', help='额外参数 JSON (regime)')
    parser.add_argument('--output', default='', help='输出文件路径 (默认 stdout)')
    args = parser.parse_args()

    codes = [c.strip() for c in args.codes.split(',') if c.strip()]
    params = json.loads(args.json) if args.json else {}
    regime = params.get('regime', 'ranging')

    # 读取市场情绪
    market_emotion = read_market_emotion(args.data_dir)

    # 批量采集 + 计算
    results = []
    for code in codes:
        sys.stderr.write(f'[sentiment] {code}: 采集股吧...')
        guba = fetch_guba_eastmoney(code)
        sys.stderr.write(f'{"OK" if guba else "FAIL"}; ')

        sys.stderr.write(f'采集新浪...')
        sina = fetch_sina_guba(code)
        sys.stderr.write(f'{"OK" if sina else "FAIL"}; ')

        sys.stderr.write(f'采集雪球...')
        xueqiu = fetch_xueqiu_social(code)
        sys.stderr.write(f'{"OK" if xueqiu else "FAIL"}\n')

        scores = compute_social_scores(code, guba, sina, xueqiu, market_emotion)
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
        'market_emotion': market_emotion or {},
        'summary': summary,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    output_json = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        sys.stderr.write(f'[sentiment] 输出到 {args.output}\n')
    else:
        print(output_json)

    sys.stderr.write(f'[sentiment] {summary}\n')


if __name__ == '__main__':
    main()
