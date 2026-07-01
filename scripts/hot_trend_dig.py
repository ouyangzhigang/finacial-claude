# 💻 Python 自动化挖掘脚本
import akshare as ak
import pandas as pd
import re
from datetime import datetime, timedelta


def fetch_lhb_data(date_str):
    """获取指定日期的龙虎榜数据"""
    try:
        df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
        if df.empty:
            print(f"[{date_str}] 当日无龙虎榜数据。")
            return None
        return df
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None


def parse_interpretation(text):
    """从'解读'字段解析机构/拉萨/游资信号"""
    if pd.isna(text) or str(text).strip() == '':
        return {'type': 'unknown', 'count': 0, 'success_rate': 0.0}
    text = str(text)
    result = {'type': 'unknown', 'count': 0, 'success_rate': 0.0}

    # 机构买入: "3家机构买入，成功率48.83%"
    if '机构买入' in text:
        result['type'] = 'institution_buy'
        parts = text.split('，')
        for p in parts:
            m = re.search(r'(\d+)家', p)
            if m:
                result['count'] = int(m.group(1))
            if '成功率' in p:
                try:
                    result['success_rate'] = float(p.split('成功率')[1].rstrip('%'))
                except ValueError:
                    pass
        return result

    # 机构卖出
    if '机构卖出' in text:
        result['type'] = 'institution_sell'
        parts = text.split('，')
        for p in parts:
            m = re.search(r'(\d+)家', p)
            if m:
                result['count'] = int(m.group(1))
            if '成功率' in p:
                try:
                    result['success_rate'] = float(p.split('成功率')[1].rstrip('%'))
                except ValueError:
                    pass
        return result

    # 拉萨席位
    if '拉萨' in text:
        result['type'] = 'lhasa'
        return result

    # 西藏自治区资金(拉萨天团别名)
    if '西藏自治区' in text:
        result['type'] = 'lhasa'
        return result

    # 普通席位
    if '普通席位' in text:
        result['type'] = 'ordinary'
        parts = text.split('，')
        for p in parts:
            if '成功率' in p:
                try:
                    result['success_rate'] = float(p.split('成功率')[1].rstrip('%'))
                except ValueError:
                    pass
        return result

    return result


def analyze_lhb_data(df):
    """核心逻辑：解析解读字段 + 净买额,挖掘价值信号"""
    if df is None:
        return None

    # 解析"解读"列,生成结构化信号
    parsed = df['解读'].apply(parse_interpretation).apply(pd.Series)
    df = pd.concat([df, parsed], axis=1)

    # 计算净买额(万元)
    def safe_net_buy(val):
        try:
            return float(str(val).replace(',', '')) / 10000
        except (ValueError, TypeError):
            return 0.0

    df['净买额_万'] = df['龙虎榜净买额'].apply(safe_net_buy)

    # 筛选高价值信号
    signals = []
    for _, row in df.iterrows():
        signal_type = row.get('type', 'unknown')
        success_rate = row.get('success_rate', 0.0)
        net_buy = row.get('净买额_万', 0.0)
        score = 0
        signal_parts = []

        # 信号A: 机构买入 — 最强信号
        if signal_type == 'institution_buy':
            count = int(row.get('count', 0))
            signal_parts.append(f'【机构买入{count}家】')
            score += count * 2  # 家数越多分越高
            if success_rate > 40:
                signal_parts.append('高胜率机构')
                score += 1
            elif success_rate < 20:
                signal_parts.append('低胜率机构(警惕)')
                score -= 1

        # 信号B: 机构卖出 — 负面信号
        elif signal_type == 'institution_sell':
            count = int(row.get('count', 0))
            signal_parts.append(f'【机构卖出{count}家】')
            score -= count * 2

        # 信号C: 拉萨天团 — 高风险
        elif signal_type == 'lhasa':
            signal_parts.append('【警告:拉萨席位接盘】')
            score -= 3

        # 信号D: 净买额大 — 加分
        if net_buy > 5000:
            signal_parts.append(f'【主力净买入{net_buy:.0f}万】')
            score += 1
        elif net_buy < -5000:
            signal_parts.append(f'【主力净卖出{abs(net_buy):.0f}万】')
            score -= 1

        if signal_parts:
            signals.append({
                '代码': row['代码'],
                '名称': row['名称'],
                '解读': row['解读'],
                '收盘价': row.get('收盘价', ''),
                '涨跌幅%': row.get('涨跌幅', ''),
                '净买额(万)': round(net_buy, 1),
                '信号': '; '.join(signal_parts),
                '综合评分': score,
                '上榜原因': row.get('上榜原因', ''),
                '流通市值': row.get('流通市值', ''),
            })

    result_df = pd.DataFrame(signals)
    if not result_df.empty:
        result_df = result_df.sort_values(by='综合评分', ascending=False).reset_index(drop=True)
    return result_df


def main():
    today = datetime.now()

    # 周末自动回退到周五
    if today.weekday() == 5:
        target_date = today - timedelta(days=1)
    elif today.weekday() == 6:
        target_date = today - timedelta(days=2)
    else:
        target_date = today

    # 向前查找最多3天
    for i in range(3):
        date_str = (target_date - timedelta(days=i)).strftime('%Y%m%d')
        print(f"正在尝试获取 {date_str} 的龙虎榜数据...")
        df = fetch_lhb_data(date_str)
        if df is not None:
            print(f"成功获取数据，共 {len(df)} 条记录。开始挖掘价值...\n")
            result = analyze_lhb_data(df)
            if result is not None and not result.empty:
                pd.set_option('display.max_columns', None)
                pd.set_option('display.width', 1000)
                print("=" * 50)
                print("  龙虎榜价值挖掘报告")
                print("=" * 50)
                # 只显示评分>0的正向信号
                positive = result[result['综合评分'] > 0]
                if not positive.empty:
                    print("\n>>> 正向信号 (评分 > 0):")
                    print(positive.head(15).to_string(index=False))
                else:
                    print("\n>>> 无正向信号")

                # 显示评分最低的5只(机构卖出/拉萨)
                negative = result[result['综合评分'] <= 0]
                if not negative.empty:
                    print("\n>>> 负面信号 (机构卖出/拉萨/净卖出):")
                    print(negative.tail(5).to_string(index=False))

                print("\n" + "=" * 50)
                print(f"共分析 {len(result)} 只, 正向 {len(positive)} 只, 负面 {len(negative)} 只")
            else:
                print("当日未挖掘到符合条件的强信号标的。")
            break


if __name__ == "__main__":
    main()
