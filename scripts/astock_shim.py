#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
astock_shim.py — 向后兼容层 (Shim)

旧文件(已删除的 fetch_stock.py / fetch_market.py / fetch_stock2.py)
中可能引用的函数和变量, 统一重定向到 astock_data.py。

用法: 无需直接导入此模块。依赖旧代码会自动使用 astock_data.py 端点。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 将所有公共接口从 astock_data 重新导出, 确保旧 import path 不崩
try:
    from astock_data import *  # noqa: F401, F403
except ImportError:
    pass

# ── 常见旧调用路径兼容 ──
# 以下函数名是旧 fetcher 文件曾暴露的别名
tencent_quote = None  # 实际在 astock_data.tencent_quote
baidu_kline_with_ma = None  # 实际在 astock_data.baidu_kline_with_ma
sina_financial_report = None  # 实际在 astock_data.sina_financial_report
industry_comparison = None  # 实际在 astock_data.industry_comparison
em_zt_pool = None  # 实际在 astock_data.em_zt_pool
em_zb_pool = None  # 实际在 astock_data.em_zb_pool
em_dt_pool = None  # 实际在 astock_data.em_dt_pool
limit_up_sentiment = None  # 实际在 astock_data.limit_up_sentiment
cninfo_announcements = None  # 实际在 astock_data.cninfo_announcements
eastmoney_global_news = None  # 实际在 astock_data.eastmoney_global_news
hsgt_realtime = None  # 实际在 astock_data.hsgt_realtime
dividend_history = None  # 实际在 astock_data.dividend_history

__all__ = [
    'astock_data', 'HAS_SSL', '_SSL_CTX', '_urllib_req',
    'em_get', 'em_post', 'UA', 'HAS_REQUESTS',
    'EM_SESSION', 'eastmoney_datacenter',
    'ths_hot_reason', 'eastmoney_concept_blocks', 'eastmoney_fund_flow_minute',
    'stock_fund_flow_120d', 'margin_trading', 'block_trade',
    'holder_num_change', 'lockup_expiry', 'dragon_tiger_board',
    'eastmoney_stock_news', 'cls_telegraph',
    'compute_capital_score', 'compute_supply_risk',
    'tencent_quote', 'baidu_kline_with_ma', 'sina_financial_report',
    'industry_comparison', 'em_zt_pool', 'em_zb_pool', 'em_dt_pool',
    'limit_up_sentiment', 'cninfo_announcements', 'eastmoney_global_news',
    'hsgt_realtime', 'dividend_history',
    'forward_pe', 'pe_digestion', 'calc_peg',
]
