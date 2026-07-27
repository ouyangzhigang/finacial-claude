#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ultra_factor.py — 超短6维因子评分引擎

专为1天超短线设计: 封板质量 + 资金强度 + 舆情热度 + 事件催化 + 技术动量 + 龙虎榜信号

用法:
  python scripts/ultra_factor.py --date 20260722 --output data/runs/20260722_ultra-short-picks/ultra_scores.json

数据源:
  - market_radar.py (涨停池/龙虎榜/资金流/新闻/板块)
  - sentiment_engine.py (舆情热度)
  - cn_fetch.py (K线/腾讯行情)
  - hot_trend_dig.py (龙虎榜深度)
"""

import json
import os
import sys
import math
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ════════════════════════════════════════════
# 6维因子权重
# ════════════════════════════════════════════

FACTOR_WEIGHTS = {
    'seal_quality':     0.25,  # 封板质量
    'capital_flow':     0.20,  # 资金强度
    'sentiment':        0.15,  # 舆情热度
    'catalyst':         0.20,  # 事件催化
    'momentum':         0.10,  # 技术动量
    'lhb_signal':       0.10,  # 龙虎榜信号
}

# ════════════════════════════════════════════
# 硬门过滤(超短版)
# ════════════════════════════════════════════

ULTRA_GATES = {
    '一字板': {
        'desc': '一字板不追(买不到, 买到就是坑)',
        'check': lambda st: st.get('is_yizi', False),
    },
    '6连板': {
        'desc': '6连板以上不追(接力风险极大)',
        'check': lambda st: st.get('consecutive_boards', 0) >= 6,
    },
    '尾盘炸板': {
        'desc': '尾盘炸板不买(封板失败信号)',
        # 无 last_seal_time 数据, 改为: 炸板>3次(烂板) OR 下午封板+炸板
        'check': lambda st: (
            st.get('seal_break_count', 0) > 3 or
            (st.get('seal_break_count', 0) > 0 and str(st.get('first_seal_time', '99')) >= '14')
        ),
    },
    '烂板': {
        'desc': '炸板>=5次不买(超级烂板)',
        'check': lambda st: st.get('seal_break_count', 0) >= 5,
    },
    '拉萨主导': {
        'desc': '拉萨席位主导不买(散户接盘)',
        'check': lambda st: st.get('lasa_dominant', False),
    },
    '流动性不足': {
        'desc': '成交额<1亿不买',
        'check': lambda st: st.get('amount_yi', 0) < 1.0,
    },
    'ST股票': {
        'desc': 'ST股票不买',
        'check': lambda st: st.get('is_st', False),
    },
}


# ════════════════════════════════════════════
# 市场温度计
# ════════════════════════════════════════════

def compute_market_temperature(zt_count, seal_rate, blast_rate, max_board, profit_effect):
    """计算市场温度 (0-100)"""
    scores = []

    # 涨停家数: 0-100映射
    if zt_count >= 100: scores.append(100)
    elif zt_count >= 60: scores.append(75)
    elif zt_count >= 40: scores.append(50)
    elif zt_count >= 20: scores.append(25)
    else: scores.append(5)

    # 封板率: 0-100映射
    if seal_rate >= 90: scores.append(95)
    elif seal_rate >= 80: scores.append(75)
    elif seal_rate >= 65: scores.append(50)
    elif seal_rate >= 50: scores.append(25)
    else: scores.append(5)

    # 炸板率: 扣分
    if blast_rate <= 5: scores.append(95)
    elif blast_rate <= 15: scores.append(70)
    elif blast_rate <= 25: scores.append(45)
    elif blast_rate <= 40: scores.append(20)
    else: scores.append(5)

    # 连板高度
    if max_board >= 6: scores.append(90)
    elif max_board >= 4: scores.append(75)
    elif max_board >= 3: scores.append(55)
    elif max_board >= 2: scores.append(35)
    else: scores.append(15)

    # 赚钱效应
    if profit_effect >= 70: scores.append(90)
    elif profit_effect >= 55: scores.append(70)
    elif profit_effect >= 45: scores.append(50)
    elif profit_effect >= 30: scores.append(25)
    else: scores.append(5)

    return sum(scores) / len(scores)


def temperature_decision(temp):
    """温度 -> 仓位/操作建议"""
    if temp < 30:
        return {'verdict': '拒绝', 'max_position': 0.0, 'max_picks': 0, 'reason': '市场冰点, 超短胜率极低'}
    elif temp < 60:
        return {'verdict': '谨慎', 'max_position': 0.30, 'max_picks': 2, 'reason': '市场偏冷, 仅选最优1-2只'}
    elif temp < 80:
        return {'verdict': '正常', 'max_position': 0.50, 'max_picks': 3, 'reason': '市场活跃, 正常出击'}
    else:
        return {'verdict': '积极但警惕', 'max_position': 0.40, 'max_picks': 2, 'reason': '市场过热, 防炸板潮'}


# ════════════════════════════════════════════
# 因子计算
# ════════════════════════════════════════════

def score_seal_quality(st):
    """封板质量评分 (0-100)"""
    score = 60  # 基础分

    # 封板时间: 越早越好
    seal_time = st.get('first_seal_time', '99:99')
    try:
        hour = int(seal_time.split(':')[0]) if ':' in seal_time else 99
        minute = int(seal_time.split(':')[1]) if ':' in seal_time else 99
        if hour < 10: score += 30  # 开盘就封 -> 最强
        elif hour == 10: score += 20
        elif hour < 11: score += 10
        elif hour < 13: score += 5
        elif hour < 14: score -= 5
        else: score -= 15  # 尾盘封板 -> 最弱
    except (ValueError, IndexError):
        pass

    # 封单量/流通市值
    seal_amount = st.get('seal_amount_yi', 0)  # 亿
    if seal_amount > 5: score += 20
    elif seal_amount > 2: score += 15
    elif seal_amount > 1: score += 10
    elif seal_amount > 0.5: score += 5
    else: score -= 10

    # 开板次数: 0=满分
    break_count = st.get('seal_break_count', 0)
    if break_count == 0: score += 10
    elif break_count <= 2: score -= 5
    else: score -= 20

    # 连板高度: 2-4板最优
    boards = st.get('consecutive_boards', 1)
    if boards == 1: score += 5   # 首板: 安全但溢价低
    elif 2 <= boards <= 3: score += 15  # 2-3板: 最佳
    elif boards == 4: score += 5  # 4板: 还行
    elif boards == 5: score -= 5  # 5板: 偏高
    # 6板以上已被硬门过滤

    return max(0, min(100, score))


def score_capital_flow(st):
    """资金活跃度评分 (0-100) — 基于实际可获取的指标。

    主力资金流数据(push2.eastmoney.com)在部分网络环境下被代理拦截，
    此处使用成交额/换手率/量比/涨跌幅作为资金活跃度的代理指标。
    若实际主力资金数据可用，则优先使用。
    """
    score = 40  # 基础分

    main_net = st.get('main_net_yi', 0)  # 亿
    big_order = st.get('big_order_ratio', 0)
    has_real_flow = (main_net != 0 or big_order != 0)

    if has_real_flow:
        # 有真实资金流数据 → 优先使用
        amount = st.get('amount_yi', 1)
        if amount > 0:
            ratio = main_net / amount * 100
            if ratio > 10: score += 25
            elif ratio > 5: score += 15
            elif ratio > 0: score += 5
            elif ratio > -5: score -= 10
            else: score -= 25

        if big_order > 50: score += 15
        elif big_order > 30: score += 8
        elif big_order < 10: score -= 10
    else:
        # 无真实资金流 → 使用代理指标
        # 成交额(亿) — 流动性好=资金关注度高
        amt = st.get('amount_yi', 0)
        if amt > 20: score += 20
        elif amt > 10: score += 15
        elif amt > 5: score += 10
        elif amt > 2: score += 5
        elif amt < 1: score -= 10

        # 换手率 — 活跃但不极端
        turnover = st.get('turnover', 0)
        if 5 <= turnover <= 15: score += 15
        elif 15 < turnover <= 25: score += 10
        elif turnover > 25: score += 5
        elif turnover < 2: score -= 10

        # 量比 — 放量涨停
        vol_ratio = st.get('volume_ratio', 1)
        if vol_ratio > 2.5: score += 15
        elif vol_ratio > 1.5: score += 10
        elif vol_ratio > 1.0: score += 5

        # 涨跌幅 — 涨停板确定性
        pct = st.get('pct', 0)
        if pct >= 20: score += 5  # 20cm
        elif pct >= 10: score += 3

    # 北向资金 (日度已停止实时披露, 保留字段)
    north_flow = st.get('north_flow_yi', 0)
    if north_flow > 5: score += 10
    elif north_flow > 0: score += 3

    return max(0, min(100, score))


def score_sentiment(st):
    """舆情热度评分 (0-100)"""
    social_heat = st.get('social_heat', 50)
    heat_momentum = st.get('heat_momentum', 0)
    bull_ratio = st.get('bull_ratio', 0.5)
    hype_risk = st.get('hype_risk', 0)

    score = social_heat * 0.5  # 基础: 热度

    # 热度动量加分
    if heat_momentum > 0.3: score += 20
    elif heat_momentum > 0: score += 10
    elif heat_momentum < -0.3: score -= 15

    # 多空比加分
    if bull_ratio > 0.7: score += 15
    elif bull_ratio > 0.5: score += 5

    # 炒作风险扣分
    if hype_risk > 70: score -= 20
    elif hype_risk > 50: score -= 10

    return max(0, min(100, score))


def score_catalyst(st):
    """事件催化评分 (0-100)"""
    score = 50

    # 新闻新鲜度
    news_hours = st.get('latest_news_hours', 999)
    if news_hours < 1: score += 25
    elif news_hours < 3: score += 20
    elif news_hours < 6: score += 15
    elif news_hours < 12: score += 10
    elif news_hours < 24: score += 5

    # 政策级别
    policy_level = st.get('policy_level', 0)
    if policy_level >= 3: score += 20  # 国务院级别
    elif policy_level >= 2: score += 15  # 部委级别
    elif policy_level >= 1: score += 10  # 地方级别

    # 业绩超预期
    earnings_surprise = st.get('earnings_surprise', 0)
    if earnings_surprise > 50: score += 20
    elif earnings_surprise > 20: score += 10
    elif earnings_surprise > 0: score += 5

    # 板块效应
    sector_zt_count = st.get('sector_zt_count', 0)
    if sector_zt_count >= 5: score += 15
    elif sector_zt_count >= 3: score += 10
    elif sector_zt_count >= 1: score += 5

    # 多催化叠加
    catalyst_count = st.get('catalyst_count', 1)
    if catalyst_count >= 3: score += 10
    elif catalyst_count >= 2: score += 5

    return max(0, min(100, score))


def score_momentum(st):
    """技术动量评分 (0-100)"""
    score = 50

    # 近5日涨幅
    m5 = st.get('m5', 0)
    if 5 <= m5 <= 15: score += 20  # 温和上涨, 未透支
    elif 0 < m5 < 5: score += 10
    elif m5 > 15 and m5 <= 25: score += 5  # 注意透支
    elif m5 > 25: score -= 15  # 透支严重
    elif m5 < 0: score -= 10

    # 量比
    volume_ratio = st.get('volume_ratio', 1)
    if 1.5 <= volume_ratio <= 3: score += 15
    elif volume_ratio > 3: score += 5  # 放量太大
    elif volume_ratio < 0.5: score -= 10

    # RSI
    rsi = st.get('rsi', 50)
    if 50 <= rsi <= 75: score += 10  # 健康强势
    elif rsi > 75: score -= 5  # 超买
    elif rsi < 30: score -= 10  # 弱势

    # 站上MA5
    above_ma5 = st.get('above_ma5', True)
    if above_ma5: score += 5

    return max(0, min(100, score))


def score_lhb(st):
    """龙虎榜信号评分 (0-100)"""
    score = 50

    # 机构净买入
    inst_net = st.get('inst_net_buy_yi', 0)
    if inst_net > 1: score += 30
    elif inst_net > 0.5: score += 20
    elif inst_net > 0: score += 10
    elif inst_net < -0.5: score -= 20

    # 知名游资
    has_top_trader = st.get('has_top_trader', False)
    if has_top_trader: score += 15

    # 拉萨席位
    has_lasa = st.get('has_lasa', False)
    if has_lasa: score -= 25

    # 净买额/成交额
    lhb_ratio = st.get('lhb_amount_ratio', 0)
    if lhb_ratio > 10: score += 15
    elif lhb_ratio > 5: score += 10

    return max(0, min(100, score))


# ════════════════════════════════════════════
# 综合评分
# ════════════════════════════════════════════

def compute_ultra_score(st):
    """计算综合超短评分"""
    dims = {
        'seal_quality': score_seal_quality(st),
        'capital_flow': score_capital_flow(st),
        'sentiment': score_sentiment(st),
        'catalyst': score_catalyst(st),
        'momentum': score_momentum(st),
        'lhb_signal': score_lhb(st),
    }

    composite = sum(dims[k] * FACTOR_WEIGHTS[k] for k in FACTOR_WEIGHTS)

    return {
        'composite_score': round(composite, 1),
        'dim_scores': {k: round(v, 1) for k, v in dims.items()},
        'weights': FACTOR_WEIGHTS,
    }


# ════════════════════════════════════════════
# 数据采集
# ════════════════════════════════════════════

def fetch_market_data(date_str):
    """采集市场雷达数据 -> 返回解析后的 dict。

    market_radar.py 输出 JSON，包含:
      ztPool: [{code, name, fund, zbc, fbt, lbc, hybk, ...}]
      longhu: [{code, name, netBuyAmt, buyAmt, sellAmt, reason, ...}]
      capitalFlow: [{code, name, mainNetInflow, mainNetPct, ...}]
      news: [{title, time, level, ...}]
      coreSignals: [{level, text, ...}]
      conceptTop: [{name, changePct, ...}]
    """
    try:
        result = subprocess.run(
            ['python', 'scripts/market_radar.py', '--section', 'zt,longhu,capital,news,sector'],
            capture_output=True, text=True, encoding='utf-8', timeout=60,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception as e:
        print(f"market_radar.py 失败: {e}", file=sys.stderr)
    return {}


def fetch_lhb_deep(date_str):
    """采集龙虎榜深度数据 -> 返回 DataFrame。

    直接 import hot_trend_dig(已修复为东财直连), 避免 subprocess 文本解析。
    自动回退到最近交易日(盘中无当天数据)。
    """
    try:
        from hot_trend_dig import fetch_lhb_data, parse_interpretation
        df = fetch_lhb_data(date_str)
        if df is not None and not df.empty:
            # 解析每条记录的解读字段, 补充机构/拉萨/游资信号
            signals = []
            for _, row in df.iterrows():
                parsed = parse_interpretation(row.get('解读', ''))
                signals.append({
                    'type': parsed.get('type', 'unknown'),
                    'count': parsed.get('count', 0),
                    'success_rate': parsed.get('success_rate'),
                })
            df['_parsed'] = signals
            return df
    except Exception as e:
        print(f"hot_trend_dig import 失败: {e}", file=sys.stderr)
    return None


def fetch_sentiment_scores(codes, data_dir):
    """采集舆情热度 -> 返回 {code: {social_heat, heat_momentum, bull_ratio}}。

    三层降级:
    1. sentiment_engine.em_hot_rank (emappdata API, 已验证可用)
    2. 腾讯行情换手率作为热度代理
    3. 默认值
    """
    result = {}
    codes_set = set(str(c).strip() for c in codes)

    # ── 方式1: emappdata 人气榜 (已验证可绕过代理) ──
    try:
        from sentiment_engine import em_hot_rank, ths_hot_list, compute_social_scores
        em_list = em_hot_rank(top=200) or []
        ths_list = ths_hot_list(period="day") or []

        em_map = {}
        for item in (em_list if isinstance(em_list, list) else []):
            if isinstance(item, dict):
                c = str(item.get('code', '')).strip()
                if c:
                    em_map[c] = item

        ths_map = {}
        for item in (ths_list if isinstance(ths_list, list) else []):
            if isinstance(item, dict):
                c = str(item.get('code', '')).strip()
                if c:
                    ths_map[c] = item

        if em_map or ths_map:
            for code in codes:
                scores = compute_social_scores(code, ths_map, em_map, [], None)
                if scores and (scores.get('social_heat', 50) != 50 or em_map.get(code) or ths_map.get(code)):
                    result[code] = {
                        'social_heat': scores.get('social_heat', 50),
                        'heat_momentum': scores.get('heat_momentum', 0),
                        'bull_ratio': scores.get('bull_ratio', 0.5),
                        'hype_risk': scores.get('hype_risk', 0),
                    }
            if result:
                print(f"  [sentiment] emappdata 匹配 {len(result)} 只", file=sys.stderr)
                return result
    except Exception as e:
        print(f"  [sentiment] sentiment_engine 失败: {e}", file=sys.stderr)

    # ── 方式2: 直接调用 emappdata API (兜底) ──
    try:
        from astock_data import em_post
        r = em_post(
            'https://emappdata.eastmoney.com/stockrank/getAllCurrentList',
            json_data={'appId': 'appId01', 'globalId': '786e4c21-70dc-435a-93bb-a'},
            headers={'Referer': 'https://quote.eastmoney.com/'},
            timeout=10
        )
        if r and r.status_code == 200:
            data = r.json()
            hot_list = data.get('data', [])
            if hot_list:
                # 构建排名映射: code -> rank (1=最热)
                rank_map = {}
                for item in hot_list:
                    sc = str(item.get('sc', '')).replace('SH', '').replace('SZ', '').strip()
                    rk = item.get('rk', 999)
                    if sc and rk:
                        rank_map[sc] = int(rk)

                for code in codes:
                    code_str = str(code).strip()
                    rank = rank_map.get(code_str, 999)
                    if rank <= 10:
                        result[code_str] = {'social_heat': 90, 'heat_momentum': 0.5, 'bull_ratio': 0.75, 'hype_risk': 30}
                    elif rank <= 30:
                        result[code_str] = {'social_heat': 75, 'heat_momentum': 0.3, 'bull_ratio': 0.65, 'hype_risk': 15}
                    elif rank <= 100:
                        result[code_str] = {'social_heat': 60, 'heat_momentum': 0.1, 'bull_ratio': 0.55, 'hype_risk': 0}

                if result:
                    print(f"  [sentiment] emappdata 直接匹配 {len(result)} 只", file=sys.stderr)
                    return result
    except Exception as e:
        print(f"  [sentiment] emappdata 直接调用失败: {e}", file=sys.stderr)

    # ── 方式3: 腾讯换手率作为热度代理 ──
    if not result:
        try:
            from cn_fetch import quote as cn_quote
            syms = [f"sh{c}" if c.startswith(('6','9')) else f"sz{c}" for c in codes]
            quotes = cn_quote(syms) or {}
            for code in codes:
                code_str = str(code).strip()
                q = quotes.get(code_str, {})
                if q and isinstance(q, dict):
                    turnover = q.get('turnover', 0)
                    pct = q.get('pct', 0)
                    # 换手率越高 + 涨幅越大 → 热度越高
                    heat = min(100, 50 + turnover * 1.5 + abs(pct) * 0.5)
                    result[code_str] = {
                        'social_heat': round(heat, 1),
                        'heat_momentum': 0.1 if pct > 5 else 0,
                        'bull_ratio': 0.6 if pct > 0 else 0.4,
                        'hype_risk': min(80, turnover * 2) if turnover > 25 else 0,
                    }
            if result:
                print(f"  [sentiment] 腾讯换手率代理 {len(result)} 只", file=sys.stderr)
        except Exception as e:
            print(f"  [sentiment] 腾讯代理失败: {e}", file=sys.stderr)

    return result


def _parse_seal_time(fbt):
    """解析封板时间: '92501' -> '09:25', '103015' -> '10:30'"""
    if not fbt or fbt == '99:99' or len(str(fbt)) < 4:
        return '99:99'
    s = str(fbt).zfill(6)
    h, m = s[:2], s[2:4]
    if h == '99':
        return '99:99'
    return f'{h}:{m}'


def _match_news_to_codes(core_signals, candidates, zt_industries, concept_top=None):
    """将新闻信号匹配到候选股票。

    三层匹配:
    1. 行业关键词词典: 新闻关键词 → 行业名 → 板块内所有候选股
    2. 概念板块排名: 热门概念 → 概念内个股
    3. 股票名称直接匹配: 新闻中提到股票名

    返回: {code: {catalyst_count, policy_level, latest_news_hours}}
    """
    # ── 行业关键词词典 ──
    INDUSTRY_KEYWORDS = {
        '半导体': ['半导体', '芯片', '封装', '光刻', '晶圆', 'EDA', 'AI芯片', '算力芯片', '存储', 'HBM', '先进封装', '电子特气'],
        '电网设备': ['电网', '特高压', '电力设备', '电缆', '输配电', '智能电网', '变压器', '开关'],
        '军工': ['军工', '武器', '导弹', '军机', '舰船', '雷达', '卫星', '地缘', '伊朗', '美军', '国防', '兵装', '兵器'],
        '新能源': ['光伏', '风电', '储能', '氢能', '锂电', '电池', '新能源', '绿色能源', '碳中和', '节能'],
        '汽车零部件': ['汽车', '新能源车', '零部件', '智能驾驶', '自动驾驶', '线控', '底盘'],
        '房地产开发': ['房地产', '地产', '住房', '城建', '物业'],
        '化工': ['化工', '染料', '化学', '中间体', '涨价', '调价', '原材料'],
        '电力': ['电力', '发电', '绿电', '火电', '水电', '核电', '供电'],
        '医疗器械': ['医疗', '器械', '诊断', '检测', '试剂'],
        '通信设备': ['通信', '5G', '6G', '光模块', '光通信', '卫星通信'],
        '机器人': ['机器人', '人形机器人', '工业机器人', '伺服', '减速器'],
        '消费电子': ['消费电子', '手机', '苹果', '华为', 'MLCC', '面板'],
        'AI算力': ['算力', 'AI', '人工智能', '大模型', 'GPU', '服务器', '数据中心'],
        '银行': ['银行', '金融', '券商', '保险', '降息', '降准'],
        '资源': ['黄金', '铜', '铝', '稀土', '矿产', '石油', '天然气', '煤炭'],
    }

    # 构建行业→代码反向索引
    industry_to_codes = {}
    for code, ind in (zt_industries or {}).items():
        if ind:
            industry_to_codes.setdefault(ind, []).append(code)

    # 构建代码→名称查找表
    code_to_name = {}
    if candidates:
        for c in candidates:
            if isinstance(c, dict):
                code_to_name[c.get('code', '')] = c.get('name', '')
    else:
        # candidates 可能为空列表, 从 zt_industries 构建
        for code in (zt_industries or {}):
            code_to_name[code] = ''

    name_to_code = {v: k for k, v in code_to_name.items() if v}

    now = datetime.now()
    result = {}
    for code in code_to_name:
        result[code] = {
            'catalyst_count': 1,
            'policy_level': 0,
            'latest_news_hours': 999,
        }

    # ── 匹配逻辑 ──
    for sig in (core_signals or []):
        if not isinstance(sig, dict):
            continue
        text = sig.get('text', '')
        level_str = sig.get('level', 'normal')
        policy_bonus = 3 if level_str == 'critical' else (2 if level_str == 'important' else 0)

        # 新鲜度
        time_str = sig.get('time', '')
        hours_ago = 999
        if time_str:
            try:
                if ' ' in time_str:
                    t = datetime.strptime(time_str[:16], '%Y-%m-%d %H:%M')
                else:
                    t = datetime.strptime(time_str[:5], '%H:%M')
                    t = t.replace(year=now.year, month=now.month, day=now.day)
                hours_ago = max(0, (now - t).total_seconds() / 3600)
            except Exception:
                pass

        matched_codes = set()

        # 层1: 行业关键词匹配
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                for code in industry_to_codes.get(industry, []):
                    matched_codes.add(code)

        # 层2: 股票名称直接匹配
        for name, code in name_to_code.items():
            if len(name) >= 2 and name in text:
                matched_codes.add(code)

        # 层3: 概念板块匹配 (从 concept_top 中提取)
        if concept_top:
            for concept in concept_top:
                cname = concept.get('name', '') if isinstance(concept, dict) else ''
                if cname and cname in text:
                    # 概念板块中的个股已在 industry_to_codes 中
                    for code in industry_to_codes.get(cname, []):
                        matched_codes.add(code)

        # 更新匹配结果
        for code in matched_codes:
            if code not in result:
                result[code] = {'catalyst_count': 1, 'policy_level': 0, 'latest_news_hours': 999}
            r = result[code]
            r['catalyst_count'] += 1
            r['policy_level'] = max(r['policy_level'], policy_bonus)
            r['latest_news_hours'] = min(r['latest_news_hours'], hours_ago)

    return result


def fetch_kline_factors(codes):
    """采集K线因子 (含RSI计算)"""
    from cn_fetch import factors as cn_factors
    result = {}
    for code in codes:
        sym = f"sh{code}" if code.startswith(('6', '9')) else f"sz{code}"
        try:
            fc = cn_factors(sym)
            if fc and isinstance(fc, dict):
                # RSI 计算: 从近14日涨跌幅估算
                # m5/m10/m20 是5/10/20日动量, 用加权平均近似RSI
                m5 = fc.get('m5', 0)
                m10 = fc.get('m10', 0)
                m20 = fc.get('m20', 0)
                # 简化RSI: 近期涨幅越大, RSI越高
                # RSI = 50 + (短期动量加权 - 长期动量) * 系数
                short_momentum = m5 * 0.5 + m10 * 0.35 + m20 * 0.15
                rsi_raw = 50 + short_momentum * 1.5
                rsi = max(5, min(95, rsi_raw))

                result[code] = {
                    'm5': m5,
                    'm10': m10,
                    'm20': m20,
                    'ma5': fc.get('ma5', 0),
                    'ma20': fc.get('ma20', 0),
                    'above_ma5': fc.get('above_ma5', False),
                    'above_ma20': fc.get('above_ma20', False),
                    'volume_ratio': fc.get('v5', 0) / fc.get('v20', 1) if fc.get('v20', 0) > 0 else 1,
                    'amt20_yi': fc.get('amt20_yi', 0),
                    'last': fc.get('last', 0),
                    'date': fc.get('date', ''),
                    'rsi': round(rsi, 1),
                }
        except Exception:
            pass
    return result


# ════════════════════════════════════════════
# 主流程: 候选池构建
# ════════════════════════════════════════════

def build_candidates(date_str, data_dir):
    """从涨停池+龙虎榜+资金流+新闻+舆情构建候选池。

    数据集成:
      - 封板质量 ← market_radar.py ztPool JSON (fund/zbc/fbt/lbc/hybk)
      - 资金流   ← market_radar.py capitalFlow JSON (mainNetInflow/mainNetPct)
      - 龙虎榜   ← hot_trend_dig.fetch_lhb_data() 直接 import
      - 催化     ← market_radar.py coreSignals 关键词->股票匹配
      - 舆情     ← sentiment_engine 直接 import
      - 动量     ← cn_fetch.factors() (已有)
    """
    candidates = []

    # ── 1. 采集 market_radar 数据 (JSON) ──
    radar = fetch_market_data(date_str)
    if not radar:
        print("[WARN] market_radar 无数据", file=sys.stderr)
        return [], {'zt_count': 0, 'seal_rate': 0, 'blast_rate': 0, 'max_board': 0, 'profit_effect': 0}

    zt_pool = radar.get('ztPool') or []
    # 防御: 数据源失败时可能返回 dict(error) 而非 list
    longhu_list = radar.get('longhu') or []
    if isinstance(longhu_list, dict):
        longhu_list = []
    capital_list = radar.get('capitalFlow') or []
    if isinstance(capital_list, dict):
        capital_list = []
    core_signals = radar.get('coreSignals') or []
    if isinstance(core_signals, dict):
        core_signals = []
    concept_top = radar.get('conceptTop') or []
    if isinstance(concept_top, dict):
        concept_top = []

    if not zt_pool:
        print("[WARN] 涨停池为空", file=sys.stderr)
        return [], {'zt_count': 0, 'seal_rate': 0, 'blast_rate': 0, 'max_board': 0, 'profit_effect': 0}

    # ── 2. 构建查找表 ──
    # 封板信息: zt_pool 中 code -> {fund, zbc, fbt, lbc, hybk}
    zt_map = {}
    zt_industries = {}  # code -> industry
    sector_zt_counts = {}  # industry -> count
    max_board = 0
    zbc_total = 0  # 总开板次数(用于计算炸板率)
    seal_time_ok = 0  # 有效封板时间数

    for item in zt_pool:
        code = str(item.get('code', '')).strip()
        if not code:
            continue
        zt_map[code] = item
        ind = item.get('hybk', '')
        if ind:
            zt_industries[code] = ind
            sector_zt_counts[ind] = sector_zt_counts.get(ind, 0) + 1
        lbc = item.get('lianban') or item.get('lbc') or 0
        try:
            lbc = int(lbc)
        except (ValueError, TypeError):
            lbc = 0
        max_board = max(max_board, lbc)
        zbc = item.get('zbc') or 0
        try:
            zbc_total += int(zbc)
        except (ValueError, TypeError):
            pass
        fbt = item.get('firstSealTime') or item.get('fbt') or ''
        if fbt and fbt != '99:99':
            seal_time_ok += 1

    # 资金流: code -> {mainNetInflow, mainNetPct}
    capital_map = {}
    for item in capital_list:
        if not isinstance(item, dict):
            continue
        c = str(item.get('code', '')).strip()
        if c:
            capital_map[c] = item

    # 龙虎榜: code -> {netBuyAmt, buyAmt, sellAmt, reason}
    lhb_map = {}
    for item in longhu_list:
        if not isinstance(item, dict):
            continue
        c = str(item.get('code', '')).strip()
        if c:
            lhb_map[c] = item

    # ── 3. 龙虎榜深度 (hot_trend_dig 直接 import) ──
    lhb_deep_map = {}  # code -> {inst_net_buy_yi, has_lasa, lhb_amount_ratio, ...}
    try:
        lhb_df = fetch_lhb_deep(date_str)
        if lhb_df is not None and not lhb_df.empty:
            for _, row in lhb_df.iterrows():
                c = str(row.get('代码', '')).strip()
                if not c:
                    continue
                parsed = row.get('_parsed')
                if isinstance(parsed, dict):
                    sig_type = parsed.get('type', 'unknown')
                else:
                    sig_type = 'unknown'

                # 净买额(元->亿)
                net_amt = row.get('龙虎榜净买额', 0) or 0
                try:
                    net_amt_yi = float(net_amt) / 1e8
                except (ValueError, TypeError):
                    net_amt_yi = 0

                # 成交额(元)
                deal_amt = row.get('龙虎榜成交额', 0) or 0
                try:
                    deal_amt = float(deal_amt)
                except (ValueError, TypeError):
                    deal_amt = 0
                amount = row.get('流通市值', 0) or 1
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    amount = 1

                lhb_deep_map[c] = {
                    'inst_net_buy_yi': round(net_amt_yi, 4),
                    'has_top_trader': sig_type == 'ordinary' and abs(net_amt_yi) > 0.5,
                    'has_lasa': sig_type == 'lhasa',
                    'lasa_dominant': sig_type == 'lhasa',
                    'lhb_amount_ratio': round(deal_amt / amount * 100, 2) if amount > 0 else 0,
                }
    except Exception as e:
        print(f"  lhb_deep 匹配失败: {e}", file=sys.stderr)

    # ── 4. 新闻催化匹配 (传入 zt_pool 以启用个股名匹配) ──
    catalyst_map = _match_news_to_codes(core_signals, zt_pool, zt_industries, concept_top)

    # ── 5. 获取股票代码列表 + 腾讯行情 ──
    codes_for_quote = list(zt_map.keys())[:80]
    if not codes_for_quote:
        return [], {'zt_count': 0, 'seal_rate': 0, 'blast_rate': 0, 'max_board': 0, 'profit_effect': 0}

    try:
        from cn_fetch import quote as cn_quote
        quotes = cn_quote([f"sh{c}" if c.startswith(('6','9')) else f"sz{c}" for c in codes_for_quote])
    except Exception:
        quotes = {}

    # ── 6. K线因子 + 舆情 ──
    kline_factors = fetch_kline_factors(codes_for_quote)
    sentiment_scores = fetch_sentiment_scores(codes_for_quote, data_dir)

    # ── 7. 构建候选 ──
    for code in codes_for_quote:
        q = quotes.get(code, {})
        if not q or not isinstance(q, dict):
            continue

        kf = kline_factors.get(code, {})
        zt = zt_map.get(code, {})
        cap = capital_map.get(code, {})
        lhb = lhb_map.get(code, {})
        lhb_d = lhb_deep_map.get(code, {})
        cat = catalyst_map.get(code, {})
        sent = sentiment_scores.get(code, {})

        # 封板时间解析
        fbt = zt.get('firstSealTime') or zt.get('fbt') or ''
        seal_time = _parse_seal_time(fbt)

        # 封单额(万->亿)
        fund_raw = zt.get('fund') or 0
        try:
            seal_amount_yi = round(float(fund_raw) / 1e8, 2)
        except (ValueError, TypeError):
            seal_amount_yi = 0

        # 开板次数
        zbc = zt.get('zbc') or 0
        try:
            seal_break_count = int(zbc)
        except (ValueError, TypeError):
            seal_break_count = 0

        # 连板数
        lbc = zt.get('lianban') or zt.get('lbc') or 0
        try:
            consecutive_boards = int(lbc)
        except (ValueError, TypeError):
            consecutive_boards = 1

        # 板块涨停数
        ind = zt_industries.get(code, '')
        sector_zt_count = sector_zt_counts.get(ind, 0)

        # 资金流
        main_net = cap.get('mainNetInflow') or 0
        try:
            main_net_yi = round(float(main_net) / 1e8, 4)
        except (ValueError, TypeError):
            main_net_yi = 0
        big_order = cap.get('mainNetPct') or 0
        try:
            big_order_ratio = float(big_order)
        except (ValueError, TypeError):
            big_order_ratio = 0

        st = {
            'code': code,
            'name': q.get('name', '?'),
            'price': q.get('price', 0),
            'prev_close': q.get('prev', 0),
            'pct': q.get('pct', 0),
            'high': q.get('high', 0),
            'low': q.get('low', 0),
            'amount_yi': q.get('amount_yi', 0),
            'turnover': q.get('turnover', 0),
            'pe_ttm': q.get('pe_ttm'),
            'mktcap_yi': q.get('mktcap_yi'),
            'is_st': 'ST' in str(q.get('name', '')),
            'is_yizi': q.get('pct', 0) >= 9.9 and q.get('low', 0) == q.get('high', 0),

            # ── 封板信息 (来自 market_radar ztPool) ──
            'first_seal_time': seal_time,
            'seal_amount_yi': seal_amount_yi,
            'seal_break_count': seal_break_count,
            'consecutive_boards': consecutive_boards,
            'sector_zt_count': sector_zt_count,

            # ── 资金流 (来自 market_radar capitalFlow) ──
            'main_net_yi': main_net_yi,
            'big_order_ratio': big_order_ratio,
            'north_flow_yi': 0,  # 北向资金日度已停止实时披露

            # ── 舆情 (来自 sentiment_engine) ──
            'social_heat': sent.get('social_heat', 50),
            'heat_momentum': sent.get('heat_momentum', 0),
            'bull_ratio': sent.get('bull_ratio', 0.5),
            'hype_risk': sent.get('hype_risk', 0),

            # ── 事件催化 (来自 news 关键词匹配) ──
            'latest_news_hours': cat.get('latest_news_hours', 999),
            'policy_level': cat.get('policy_level', 0),
            'earnings_surprise': 0,
            'catalyst_count': cat.get('catalyst_count', 1),

            # ── 龙虎榜 (来自 market_radar longhu + hot_trend_dig) ──
            'inst_net_buy_yi': lhb_d.get('inst_net_buy_yi', 0),
            'has_top_trader': lhb_d.get('has_top_trader', False),
            'has_lasa': lhb_d.get('has_lasa', False),
            'lasa_dominant': lhb_d.get('lasa_dominant', False),
            'lhb_amount_ratio': lhb_d.get('lhb_amount_ratio', 0),

            # ── 技术动量 (来自 cn_fetch factors) ──
            'm5': kf.get('m5', 0),
            'm10': kf.get('m10', 0),
            'volume_ratio': kf.get('volume_ratio', 1),
            'rsi': kf.get('rsi', 50),
            'above_ma5': kf.get('above_ma5', True),
        }
        candidates.append(st)

    # ── 8. 市场温度 (基于实际数据) ──
    zt_count = len(candidates)
    # 封板率: 有有效封板时间且未炸板的占比
    sealed_ok = sum(1 for c in candidates if c['seal_break_count'] == 0)
    seal_rate = round(sealed_ok / zt_count * 100, 1) if zt_count > 0 else 0
    # 炸板率: 至少炸过一次的占比
    blasted = sum(1 for c in candidates if c['seal_break_count'] > 0)
    blast_rate = round(blasted / zt_count * 100, 1) if zt_count > 0 else 0
    # 赚钱效应: 基于涨停股占比估算
    profit_effect = 55  # 保守默认值

    market = {
        'zt_count': zt_count,
        'seal_rate': seal_rate,
        'blast_rate': blast_rate,
        'max_board': max_board,
        'profit_effect': profit_effect,
        # 附加元数据(供调试)
        '_meta': {
            'zt_pool_raw': len(zt_pool),
            'lhb_matched': len(lhb_deep_map),
            'capital_matched': len(capital_map),
            'sentiment_matched': len(sentiment_scores),
            'catalyst_signals': len(core_signals),
        },
    }

    return candidates, market


def _enrich_fund_flow(candidates, top_n=15):
    """个股资金流补充: 对未匹配到 capitalFlow 的候选股, 批量查询东财个股资金流。

    使用 astock_data.stock_fund_flow_120d() 获取最近1日的资金流数据,
    补充 main_net_yi 和 big_order_ratio 字段。

    Args:
        candidates: 候选股列表 (会被原地修改)
        top_n: 最多查询前 N 只 (控制 API 调用量)
    """
    # 找出需要补充的候选股 (main_net_yi == 0 且 big_order_ratio == 0)
    need_enrich = [
        c for c in candidates
        if c.get('main_net_yi', 0) == 0 and c.get('big_order_ratio', 0) == 0
    ][:top_n]

    if not need_enrich:
        return

    try:
        from astock_data import stock_fund_flow_120d
    except ImportError:
        print("  astock_data import 失败, 跳过资金流补充", file=sys.stderr)
        return

    enriched = 0
    for c in need_enrich:
        code = c.get('code', '')
        try:
            rows = stock_fund_flow_120d(code)
            if rows and len(rows) > 0:
                latest = rows[-1]  # 最近一个交易日
                main_net = latest.get('main_net', 0)
                super_net = latest.get('super_net', 0)
                large_net = latest.get('large_net', 0)
                amount = c.get('amount_yi', 1) * 1e8  # 亿→元

                # 主力净流入: 元→亿
                c['main_net_yi'] = round(main_net / 1e8, 4)

                # 大单占比: (超大单+大单) / 成交额 * 100
                if amount > 0:
                    c['big_order_ratio'] = round((super_net + large_net) / amount * 100, 2)
                else:
                    c['big_order_ratio'] = 0

                enriched += 1
        except Exception:
            pass

    if enriched > 0:
        print(f"  [fund_flow] 补充 {enriched} 只个股资金流", file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description='超短6维因子评分引擎')
    p.add_argument('--date', required=True, help='日期 YYYYMMDD')
    p.add_argument('--data-dir', default='', help='数据目录')
    p.add_argument('--output', default='', help='输出文件路径')
    p.add_argument('--top-n', type=int, default=5, help='TopN数量')
    args = p.parse_args()

    data_dir = args.data_dir or f'data/runs/{args.date}_ultra-short-picks'
    os.makedirs(data_dir, exist_ok=True)

    # 1. 构建候选池
    print(f"[build] 构建候选池 (日期: {args.date})...", file=sys.stderr)
    candidates, market = build_candidates(args.date, data_dir)

    # 1.5. 补充个股资金流 (对未匹配 capitalFlow 的候选股)
    if candidates:
        _enrich_fund_flow(candidates, top_n=15)

    if not candidates:
        print("[WARN] 候选池为空, 无法评分", file=sys.stderr)
        output = {
            'date': args.date,
            'market': market,
            'temperature': 0,
            'temperature_decision': {'verdict': '拒绝', 'reason': '无候选标的'},
            'stocks': [],
            'summary': '候选池为空',
        }
    else:
        # 2. 市场温度
        temp = compute_market_temperature(
            market['zt_count'], market['seal_rate'],
            market['blast_rate'], market['max_board'],
            market['profit_effect']
        )
        temp_decision = temperature_decision(temp)

        print(f"[temp] 市场温度: {temp:.1f} -> {temp_decision['verdict']} ({temp_decision['reason']})", file=sys.stderr)

        if temp_decision['verdict'] == '拒绝':
            print("[REJECT] 市场温度过低, 拒绝选股", file=sys.stderr)
            output = {
                'date': args.date,
                'market': market,
                'temperature': round(temp, 1),
                'temperature_decision': temp_decision,
                'stocks': [],
                'summary': f"市场温度{temp:.1f}, 拒绝选股",
            }
        else:
            # 3. 硬门过滤
            passed = []
            rejected = []
            for st in candidates:
                rejected_by = []
                for gate_name, gate in ULTRA_GATES.items():
                    if gate['check'](st):
                        rejected_by.append(f"{gate_name}: {gate['desc']}")

                if rejected_by:
                    st['gate_status'] = 'reject'
                    st['gate_reasons'] = rejected_by
                    rejected.append(st)
                else:
                    st['gate_status'] = 'pass'
                    passed.append(st)

            print(f"[gate] 硬门过滤: {len(passed)} 通过 / {len(rejected)} 否决", file=sys.stderr)

            # 4. 因子评分
            for st in passed:
                scores = compute_ultra_score(st)
                st.update(scores)

            # 5. 排序
            passed.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

            # 6. 输出
            top_n = passed[:args.top_n]
            output = {
                'date': args.date,
                'market': market,
                'temperature': round(temp, 1),
                'temperature_decision': temp_decision,
                'gates_summary': {
                    'passed': len(passed),
                    'rejected': len(rejected),
                    'total': len(candidates),
                },
                'stocks': passed,
                'rejected': [{'code': r['code'], 'name': r.get('name', '?'), 'reasons': r.get('gate_reasons', [])} for r in rejected],
                'top_n': [{'code': s['code'], 'name': s.get('name', '?'), 'composite_score': s.get('composite_score', 0),
                           'dim_scores': s.get('dim_scores', {})} for s in top_n],
                'summary': f"{len(passed)}只评分完成, 温度{temp:.1f}, Top1={top_n[0]['code'] if top_n else 'N/A'}",
            }

    # 写输出
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(data_dir, 'ultra_scores.json')

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[OK] 输出到 {output_path}", file=sys.stderr)
    top_n = output.get('stocks', [])
    if top_n:
        print(f"   Top{args.top_n}: {[s['code'] for s in top_n]}", file=sys.stderr)

    # 打印到 stdout 供 agent 读取
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()