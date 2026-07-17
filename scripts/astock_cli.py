#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
astock_cli.py — a-stock-data CLI 包装器

供 agent 通过 Bash 快速调用 astock_data 端点。

用法:
  python scripts/astock_cli.py ths_hot_reason [--date YYYY-MM-DD]
  python scripts/astock_cli.py capital_score --codes 600519,002001
  python scripts/astock_cli.py supply_risk --codes 600519,002001
  python scripts/astock_cli.py concept_blocks --code 600519
  python scripts/astock_cli.py fund_flow --code 600519 [--days 120]
  python scripts/astock_cli.py lockup --code 600519
  python scripts/astock_cli.py holders --code 600519
  python scripts/astock_cli.py margin --code 600519
  python scripts/astock_cli.py dragon --code 600519
  python scripts/astock_cli.py news --code 600519
  python scripts/astock_cli.py cls_news [--count 50]
"""
import json
import sys
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    parser = argparse.ArgumentParser(description='a-stock-data CLI')
    sub = parser.add_subparsers(dest='cmd')

    # ths_hot_reason
    p1 = sub.add_parser('ths_hot_reason', help='同花顺热点+题材归因')
    p1.add_argument('--date', default=None, help='日期 YYYY-MM-DD')

    # capital_score
    p2 = sub.add_parser('capital_score', help='资金流量化评分')
    p2.add_argument('--codes', required=True, help='逗号分隔代码')

    # supply_risk
    p3 = sub.add_parser('supply_risk', help='供给端风险评估')
    p3.add_argument('--codes', required=True, help='逗号分隔代码')

    # concept_blocks
    p4 = sub.add_parser('concept_blocks', help='板块/概念归属')
    p4.add_argument('--code', required=True, help='股票代码')

    # fund_flow
    p5 = sub.add_parser('fund_flow', help='资金流(120日)')
    p5.add_argument('--code', required=True, help='股票代码')
    p5.add_argument('--days', type=int, default=120, help='天数')

    # lockup
    p6 = sub.add_parser('lockup', help='解禁日历')
    p6.add_argument('--code', required=True, help='股票代码')

    # holders
    p7 = sub.add_parser('holders', help='股东户数变化')
    p7.add_argument('--code', required=True, help='股票代码')

    # margin
    p8 = sub.add_parser('margin', help='融资融券')
    p8.add_argument('--code', required=True, help='股票代码')

    # dragon
    p9 = sub.add_parser('dragon', help='龙虎榜')
    p9.add_argument('--code', required=True, help='股票代码')

    # news
    p10 = sub.add_parser('news', help='个股新闻')
    p10.add_argument('--code', required=True, help='股票代码')

    # cls_news
    p11 = sub.add_parser('cls_news', help='财联社快讯')
    p11.add_argument('--count', type=int, default=50, help='条数')

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    from astock_data import (
        ths_hot_reason, compute_capital_score, compute_supply_risk,
        eastmoney_concept_blocks, stock_fund_flow_120d, lockup_expiry,
        holder_num_change, margin_trading, dragon_tiger_board,
        eastmoney_stock_news, cls_telegraph,
    )

    if args.cmd == 'ths_hot_reason':
        data = ths_hot_reason(args.date)
        print(json.dumps(data, ensure_ascii=False, indent=2))

    elif args.cmd == 'capital_score':
        codes = [c.strip() for c in args.codes.split(',')]
        result = {}
        for code in codes:
            result[code] = compute_capital_score(code)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == 'supply_risk':
        codes = [c.strip() for c in args.codes.split(',')]
        result = {}
        for code in codes:
            result[code] = compute_supply_risk(code)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.cmd == 'concept_blocks':
        data = eastmoney_concept_blocks(args.code)
        print(json.dumps(data, ensure_ascii=False, indent=2))

    elif args.cmd == 'fund_flow':
        data = stock_fund_flow_120d(args.code)
        # 只返回最近 N 天
        if args.days and args.days < len(data):
            data = data[-args.days:]
        print(json.dumps(data, ensure_ascii=False, indent=2))

    elif args.cmd == 'lockup':
        data = lockup_expiry(args.code)
        print(json.dumps(data, ensure_ascii=False, indent=2))

    elif args.cmd == 'holders':
        data = holder_num_change(args.code)
        print(json.dumps(data, ensure_ascii=False, indent=2))

    elif args.cmd == 'margin':
        data = margin_trading(args.code)
        print(json.dumps(data, ensure_ascii=False, indent=2))

    elif args.cmd == 'dragon':
        data = dragon_tiger_board(args.code)
        print(json.dumps(data, ensure_ascii=False, indent=2))

    elif args.cmd == 'news':
        data = eastmoney_stock_news(args.code)
        print(json.dumps(data, ensure_ascii=False, indent=2))

    elif args.cmd == 'cls_news':
        data = cls_telegraph(args.count)
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
