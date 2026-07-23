#!/usr/bin/env python3
"""
🔥 A股热点趋势挖掘脚本 — 龙虎榜 + 热门个股 + 板块资金流 + 涨跌停池 + 连板梯队

数据源: akshare(经新浪源) + findata-toolkit sector_data.py(自动降级)
网络: 绕过 Whistle 代理, 直连东财 HTTP

用法:
    python hot_trend_dig.py              # 默认今天/最近交易日
    python hot_trend_dig.py --date 20260630  # 指定日期
    python hot_trend_dig.py --top 20       # 展示Top N(默认15)
"""
import os
# 绕过系统代理(Whistle), 直连东财/新浪 API
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import akshare as ak
import pandas as pd
import re
import json
import subprocess
import sys
from datetime import datetime, timedelta


# ──────────────────────────────── 数据获取 ────────────────────────────────

def get_target_date(date_str=None):
    """获取目标日期,自动回退到最近交易日"""
    if date_str:
        return date_str
    today = datetime.now()
    if today.weekday() == 5:
        today -= timedelta(days=1)
    elif today.weekday() == 6:
        today -= timedelta(days=2)
    return today.strftime('%Y%m%d')


def fetch_lhb_data(date_str):
    """获取龙虎榜数据(akshare)"""
    try:
        df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
        if df.empty:
            print(f"[{date_str}] 龙虎榜无数据。")
            return None
        return df
    except Exception as e:
        print(f"龙虎榜获取失败: {e}")
        return None


def fetch_hot_rank():
    """获取今日热榜(akshare,经新浪源,代理可用)"""
    try:
        df = ak.stock_hot_rank_em()
        if df.empty:
            return None
        # 标准化列名
        df = df.rename(columns={
            '代码': 'code', '股票名称': 'name', '最新价': 'price',
            '涨跌幅': 'pct_change', '当前排名': 'rank'
        })
        return df[['rank', 'code', 'name', 'price', 'pct_change']]
    except Exception as e:
        print(f"热门榜获取失败: {e}")
        return None


def fetch_hot_up():
    """获取飙升榜(akshare)"""
    try:
        df = ak.stock_hot_up_em()
        if df.empty:
            return None
        df = df.rename(columns={
            '代码': 'code', '股票名称': 'name', '最新价': 'price',
            '涨跌幅': 'pct_change', '当前排名': 'rank',
            '排名较昨日变动': 'rank_change'
        })
        return df[['rank', 'code', 'name', 'price', 'pct_change', 'rank_change']]
    except Exception as e:
        print(f"飙升榜获取失败: {e}")
        return None


def fetch_zt_pool(_date_str):
    """通过 sector_data.py 获取涨停池+连板梯队(自动降级到新浪源)"""
    try:
        result = subprocess.run(
            [sys.executable, '-c',
             f'''
import sys, json
sys.path.insert(0, ".claude/skills/findata-toolkit-cn")
from scripts.sector_data import fetch_zt_pool
print(json.dumps(fetch_zt_pool(), ensure_ascii=False, default=str))
             '''],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data
        # returncode != 0 不得静默返 None —— 下游不知是"无涨停"还是"子进程崩了"
        print(f"涨停池子进程失败 rc={result.returncode}: {result.stderr[:300]}", file=sys.stderr)
        return {"_error": f"sector_data.py exit {result.returncode}: {result.stderr[:200]}"}
    except Exception as e:
        print(f"涨停池获取失败: {e}", file=sys.stderr)
    return None


def fetch_market_overview(date_str):
    """通过 sector_data.py 获取市场概览(涨跌分布/总成交额)"""
    try:
        result = subprocess.run(
            [sys.executable, '-c',
             f'''
import sys, json
sys.path.insert(0, ".claude/skills/findata-toolkit-cn")
from scripts.sector_data import fetch_market_overview
print(json.dumps(fetch_market_overview(), ensure_ascii=False, default=str))
             '''],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        print(f"市场概览子进程失败 rc={result.returncode}: {result.stderr[:300]}", file=sys.stderr)
        return {"_error": f"sector_data.py exit {result.returncode}: {result.stderr[:200]}"}
    except Exception as e:
        print(f"市场概览获取失败: {e}", file=sys.stderr)
    return None


def fetch_connected_stocks(date_str):
    """通过 sector_data.py 获取连板梯队"""
    try:
        result = subprocess.run(
            [sys.executable, '-c',
             f'''
import sys, json
sys.path.insert(0, ".claude/skills/findata-toolkit-cn")
from scripts.sector_data import fetch_connected_stocks
print(json.dumps(fetch_connected_stocks(), ensure_ascii=False, default=str))
             '''],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        print(f"连板梯队子进程失败 rc={result.returncode}: {result.stderr[:300]}", file=sys.stderr)
        return {"_error": f"sector_data.py exit {result.returncode}: {result.stderr[:200]}"}
    except Exception as e:
        print(f"连板梯队获取失败: {e}", file=sys.stderr)
    return None


# ──────────────────────────────── 解析逻辑 ────────────────────────────────

def parse_interpretation(text):
    """从龙虎榜'解读'字段解析机构/拉萨/游资信号"""
    if pd.isna(text) or str(text).strip() == '':
        return {'type': 'unknown', 'count': 0, 'success_rate': None}  # None=未知,不得0.0(否则<20触发伪造"低胜率")
    text = str(text)
    result = {'type': 'unknown', 'count': 0, 'success_rate': None}  # None=未知,不得默认0(否则伪造"低胜率机构"扣分)

    if '机构买入' in text:
        result['type'] = 'institution_buy'
        for p in text.split('，'):
            m = re.search(r'(\d+)家', p)
            if m:
                result['count'] = int(m.group(1))
            if '成功率' in p:
                try:
                    result['success_rate'] = float(p.split('成功率')[1].rstrip('%'))
                except ValueError:
                    pass
        return result

    if '机构卖出' in text:
        result['type'] = 'institution_sell'
        for p in text.split('，'):
            m = re.search(r'(\d+)家', p)
            if m:
                result['count'] = int(m.group(1))
            if '成功率' in p:
                try:
                    result['success_rate'] = float(p.split('成功率')[1].rstrip('%'))
                except ValueError:
                    pass
        return result

    if '拉萨' in text or '西藏自治区' in text:
        result['type'] = 'lhasa'
        return result

    if '普通席位' in text:
        result['type'] = 'ordinary'
        for p in text.split('，'):
            if '成功率' in p:
                try:
                    result['success_rate'] = float(p.split('成功率')[1].rstrip('%'))
                except ValueError:
                    pass
        return result

    return result


def score_lhb_row(row, parsed):
    """对单只龙虎榜股票打分,返回(分数, 信号列表)"""
    signal_type = parsed.get('type', 'unknown')
    success_rate = parsed.get('success_rate')  # None=解析失败/未知,不得默认0(否则<20触发伪造"低胜率")
    count = int(parsed.get('count', 0))
    net_buy = 0.0
    try:
        net_buy = float(str(row.get('龙虎榜净买额', 0)).replace(',', '')) / 10000
    except (ValueError, TypeError):
        pass

    score = 0
    signals = []

    # 机构买入 — 最强正向信号
    if signal_type == 'institution_buy':
        signals.append(f'机构买入{count}家')
        score += count * 2
        if success_rate is None:
            signals.append('胜率未知(不加分不扣分)')
        elif success_rate > 40:
            signals.append('高胜率机构')
            score += 1
        elif success_rate < 20:
            signals.append('低胜率机构(警惕)')
            score -= 1

    # 机构卖出 — 负面
    elif signal_type == 'institution_sell':
        signals.append(f'机构卖出{count}家')
        score -= count * 2

    # 拉萨天团 — 高风险
    elif signal_type == 'lhasa':
        signals.append('拉萨席位接盘')
        score -= 3

    # 净买额
    if net_buy > 5000:
        signals.append(f'净买入{net_buy:.0f}万')
        score += 1
    elif net_buy < -5000:
        signals.append(f'净卖出{abs(net_buy):.0f}万')
        score -= 1

    return score, '; '.join(signals)


def cross_reference(lhb_df, hot_df, up_df, zt_data, sector_data):
    """
    多源交叉:龙虎榜 + 热榜 + 飙升榜 + 涨停池 + 连板梯队
    为每只龙虎榜股票叠加热度/板块/连板信号
    """
    # 源缺失/失败须显式标注 —— 不得静默降级让用户以为全源交叉完成
    _failed = []
    if hot_df is None or (isinstance(hot_df, dict) and hot_df.get('_error')):
        _failed.append('hot_df')
    if up_df is None or (isinstance(up_df, dict) and up_df.get('_error')):
        _failed.append('up_df')
    if zt_data is None or (isinstance(zt_data, dict) and zt_data.get('_error')):
        _failed.append('zt_data')
    if sector_data is None or (isinstance(sector_data, dict) and sector_data.get('_error')):
        _failed.append('sector_data')
    if _failed:
        print(f"[cross_reference] 源缺失/失败: {', '.join(_failed)} —— 交叉结果基于部分源", file=sys.stderr)
    if lhb_df is None or lhb_df.empty:
        return pd.DataFrame()

    # 构建代码→热度映射
    hot_map = {}
    if hot_df is not None and not hot_df.empty:
        for _, r in hot_df.iterrows():
            code = str(r.get('code', '')).lower().replace('sh.', '').replace('sz.', '')
            hot_map[code] = {'hot_rank': r.get('rank', 999), 'hot_price': r.get('price', 0), 'hot_pct': r.get('pct_change', 0)}

    up_map = {}
    if up_df is not None and not up_df.empty:
        for _, r in up_df.iterrows():
            code = str(r.get('code', '')).lower().replace('sh.', '').replace('sz.', '')
            up_map[code] = {'up_rank': r.get('rank', 999), 'up_change': r.get('rank_change', 0)}

    # 涨停池代码集
    zt_codes = set()
    zt_industries = {}
    if zt_data and isinstance(zt_data, dict):
        # zt_pool 返回的结构: {connected_stocks: [{code, name, industry, connected, turnover, amount_亿}], industry_distribution: {...}}
        for stock in zt_data.get('connected_stocks', []):
            code = str(stock.get('code', '')).lower().replace('sh.', '').replace('sz.', '')
            zt_codes.add(code)
            ind = stock.get('industry', '')
            if ind:
                zt_industries[code] = ind

    # 连板梯队
    connected_map = {}
    if sector_data and isinstance(sector_data, dict):
        # fetch_connected_stocks 返回: {tiers: [{code, name, connected, industry, turnover, amount_亿}, ...]}
        for tier in sector_data.get('tiers', []):
            for stock in tier.get('stocks', []) if isinstance(tier, dict) else []:
                code = str(stock.get('code', '')).lower().replace('sh.', '').replace('sz.', '')
                connected_map[code] = {
                    'connected': stock.get('connected', '0/0'),
                    'industry': stock.get('industry', ''),
                    'turnover': stock.get('turnover', 0),
                    'amount_亿': stock.get('amount_亿', 0)
                }

    # 概念板块资金流
    concept_flow = {}
    if isinstance(sector_data, dict) and 'concept_flow' in sector_data:
        for item in sector_data['concept_flow']:
            name = item.get('行业', item.get('name', ''))
            concept_flow[name] = item

    results = []
    for _, row in lhb_df.iterrows():
        code_raw = str(row.get('代码', ''))
        code = code_raw.lower().replace('sh.', '').replace('sz.', '')
        name = row.get('名称', '')

        # 解析龙虎榜信号
        interp = row.get('解读', '')
        parsed = parse_interpretation(interp)
        score, lhb_signals = score_lhb_row(row, parsed)

        # 叠加热榜信号
        hot_signals = []
        if code in hot_map:
            hr = hot_map[code]
            if hr['hot_rank'] <= 10:
                hot_signals.append(f'热榜Top{hr["hot_rank"]}')
                score += 2
            elif hr['hot_rank'] <= 30:
                hot_signals.append(f'热榜#{hr["hot_rank"]}')
                score += 1
            # 热榜股如果涨停/大涨,加分
            if hr.get('hot_pct', 0) >= 9.5:
                hot_signals.append('热榜+涨停')
                score += 1

        # 叠加飙升榜信号
        if code in up_map:
            ur = up_map[code]
            if ur['up_change'] > 500:
                hot_signals.append(f'飙升榜↑{ur["up_change"]}')
                score += 2
            elif ur['up_change'] > 100:
                hot_signals.append(f'飙升榜↑{ur["up_change"]}')
                score += 1

        # 叠加涨停池信号
        if code in zt_codes:
            hot_signals.append('今日涨停')
            score += 3
            ind = zt_industries.get(code, '')
            if ind:
                hot_signals.append(f'板块:{ind}')
                score += 1

        # 叠加连板信号
        if code in connected_map:
            cm = connected_map[code]
            conn = cm.get('connected', '0/0')
            if '/' in conn:
                days, streak = conn.split('/')
                days, streak = int(days), int(streak)
                if streak >= 3:
                    hot_signals.append(f'连板{streak}天({days}板)')
                    score += streak * 2
                elif streak >= 2:
                    hot_signals.append(f'连板{streak}天')
                    score += streak

        # 合并信号
        all_signals = hot_signals
        if lhb_signals:
            all_signals = [lhb_signals] + all_signals
        if all_signals:
            results.append({
                '代码': code_raw,
                '名称': name,
                '收盘价': row.get('收盘价', ''),
                '涨跌幅%': row.get('涨跌幅', ''),
                '净买额(万)': round(float(str(row.get('龙虎榜净买额', 0)).replace(',', '')) / 10000, 1) if pd.notna(row.get('龙虎榜净买额')) else 0,
                '龙虎榜信号': lhb_signals,
                '热度/板块信号': '; '.join(hot_signals) if hot_signals else '-',
                '综合评分': score,
                '上榜原因': row.get('上榜原因', ''),
                '流通市值': row.get('流通市值', ''),
            })

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values(by='综合评分', ascending=False).reset_index(drop=True)
    return df


# ──────────────────────────────── 输出 ────────────────────────────────

def print_report(df, market_overview, hot_df, up_df, zt_data, connected_data):
    """打印完整报告"""
    print("\n" + "=" * 70)
    print("  📈 A股热点趋势综合挖掘报告")
    print("=" * 70)

    # ── 市场概览 ──
    if market_overview:
        stats = market_overview.get('statistics', {})
        breadth = market_overview.get('breadth', {})
        print(f"\n【市场概览】")
        print(f"  上涨: {breadth.get('up', '?')} ({breadth.get('up_pct', '?')}%)  "
              f"下跌: {breadth.get('down', '?')} ({breadth.get('down_pct', '?')}%)  "
              "平盘: {0}".format(breadth.get('flat', '?')))
        print(f"  涨停: {stats.get('limit_up', '?')}  跌停: {stats.get('limit_down', '?')}  "
              "大涨(10-20%): {0}  大跌(-10~-20%): {1}".format(
            stats.get('big_up_10_20', '?'), stats.get('big_down_minus10_minus20', '?')))
        print(f"  两市成交: {market_overview.get('total_amount', '?')} 万亿  "
              "均涨跌: {0}%  中位涨跌: {1}%".format(
            market_overview.get('avg_change', '?'), market_overview.get('median_change', '?')))

    # ── 涨停行业分布 ──
    if zt_data and isinstance(zt_data, dict) and zt_data.get('industry_distribution'):
        ind_dist = zt_data['industry_distribution']
        top_inds = sorted(ind_dist.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"\n【涨停行业分布 Top5】")
        for ind, cnt in top_inds:
            print(f"  {ind}: {cnt} 只")

    # ── 连板梯队 ──
    if connected_data and isinstance(connected_data, dict) and connected_data.get('stocks'):
        print(f"\n【连板梯队 Top5】")
        for s in connected_data['stocks'][:5]:
            conn = s.get('connected', '?')
            print(f"  {s.get('name','?')}({s.get('code','?')}) 连板{conn}  "
                  "行业:{0}  换手:{1}%  成交额:{2}亿".format(
                s.get('industry', '?'), s.get('turnover', '?'), s.get('amount_亿', '?')))

    # ── 热门榜 Top10 ──
    if hot_df is not None and not hot_df.empty:
        print(f"\n【今日热榜 Top10】")
        for _, r in hot_df.head(10).iterrows():
            print(f"  #{r.get('rank','?')} {r.get('name','?')}({r.get('code','?')})  "
                  "价:{0}  涨:{1}%".format(r.get('price', '?'), r.get('pct_change', '?')))

    # ── 飙升榜 Top10 ──
    if up_df is not None and not up_df.empty:
        print(f"\n【飙升榜 Top10】")
        for _, r in up_df.head(10).iterrows():
            print(f"  #{r.get('rank','?')} {r.get('name','?')}({r.get('code','?')})  "
                  "涨:{0}%  排名变化:+{1}".format(r.get('pct_change', '?'), r.get('rank_change', '?')))

    # ── 龙虎榜价值挖掘 ──
    if df is not None and not df.empty:
        positive = df[df['综合评分'] > 0]
        negative = df[df['综合评分'] <= 0]

        print(f"\n{'=' * 70}")
        print(f"  龙虎榜价值挖掘 — 共 {len(df)} 只, 正向 {len(positive)} 只, 负面 {len(negative)} 只")
        print(f"{'=' * 70}")

        if not positive.empty:
            print(f"\n>>> 【正向信号】评分 > 0:")
            cols = ['代码', '名称', '收盘价', '涨跌幅%', '净买额(万)', '龙虎榜信号', '热度/板块信号', '综合评分']
            print(positive[cols].head(15).to_string(index=False))

        if not negative.empty:
            print(f"\n>>> 【负面信号】评分 <= 0 (机构卖出/拉萨/净卖出):")
            cols = ['代码', '名称', '收盘价', '涨跌幅%', '净买额(万)', '龙虎榜信号', '热度/板块信号', '综合评分']
            print(negative.tail(5)[cols].to_string(index=False))

    else:
        print("\n>>> 无符合条件的龙虎榜数据。")

    print(f"\n{'=' * 70}")
    print("  ⚠️ 风险提示: 龙虎榜数据为盘后统计,不构成投资建议")
    print("  机构买入不代表次日必涨,拉萨席位不代表必跌,请结合大盘环境综合判断")
    print(f"{'=' * 70}")


# ──────────────────────────────── 主流程 ────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='A股热点趋势挖掘')
    parser.add_argument('--date', type=str, help='日期 YYYYMMDD, 默认最近交易日')
    parser.add_argument('--top', type=int, default=15, help='展示Top N(默认15)')
    args = parser.parse_args()

    date_str = get_target_date(args.date)
    print(f"📅 目标日期: {date_str}\n")

    # ── Step 1: 龙虎榜 ──
    print("🔍 Step 1/5: 获取龙虎榜数据...")
    lhb_df = fetch_lhb_data(date_str)

    # ── Step 2: 今日热榜 ──
    print("🔍 Step 2/5: 获取热门个股榜...")
    hot_df = fetch_hot_rank()

    # ── Step 3: 飙升榜 ──
    print("🔍 Step 3/5: 获取飙升榜...")
    up_df = fetch_hot_up()

    # ── Step 4: 涨停池+连板梯队 ──
    print("🔍 Step 4/5: 获取涨停池/连板梯队...")
    zt_data = fetch_zt_pool(date_str)
    connected_data = fetch_connected_stocks(date_str)

    # ── Step 5: 市场概览 ──
    print("🔍 Step 5/5: 获取市场概览...")
    market_overview = fetch_market_overview(date_str)

    # ── 交叉分析 ──
    print("\n🔗 多源交叉分析中...")
    result_df = cross_reference(lhb_df, hot_df, up_df, zt_data, connected_data)

    # ── 输出报告 ──
    print_report(result_df, market_overview, hot_df, up_df, zt_data, connected_data)


if __name__ == "__main__":
    main()
