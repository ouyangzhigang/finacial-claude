"""China News MCP Server — Chinese financial news via MCP protocol.

Aggregates financial news from publicly available Chinese sources:
individual stock news, market headlines, and industry news.

Usage:
    python server.py                    # stdio (local Claude Desktop)
    python server.py --transport sse    # HTTP/SSE (deployment)
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Optional

import requests
import urllib3
# akshare 内部 requests 默认 verify=True，本机证书链不全致东方财富 HTTPS 端点
# SSL CERTIFICATE_VERIFY_FAILED，get_stock_news/get_market_headlines 返回空 DataFrame
# 被 _df_to_json 当作"SSL/限流失败"。强制所有 requests 调用 verify=False 绕过证书验证
# （MCP 服务器为独立进程，影响域可控，且数据源为公开新闻，可接受）。
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_orig_session_request = requests.Session.request


def _session_request_no_verify(self, *args, **kwargs):
    self.trust_env = False  # 绕过系统代理(Whistle 8899),与 ifind/wind-mcp 一致
    kwargs.setdefault("verify", False)
    return _orig_session_request(self, *args, **kwargs)


requests.Session.request = _session_request_no_verify

import akshare as ak
import pandas as pd

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from mcp import FastMCP

server = FastMCP("china-news-mcp", instructions="Chinese financial news — stock news, market headlines, industry news")


def _df_to_json(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        # 不得返回 [] 冒充"无新闻"——空 DataFrame 通常是 SSL/限流致抓取失败(本机东方财富全球端点 SSL 挂),
        # 静默返回 [] 会让情绪/催化分析在无声中跳过
        return json.dumps({"error": "news fetch returned empty (likely SSL/rate-limit), NOT 'no news'", "source": "china-news"}, ensure_ascii=False)
    df = df.where(pd.notna(df), None)
    result = []
    for _, row in df.head(30).iterrows():
        item = {}
        for col in df.columns:
            val = row[col]
            if isinstance(val, (datetime, pd.Timestamp)):
                val = val.isoformat()
            elif val is not None:
                val = str(val)
            item[str(col)] = val
        result.append(item)
    return json.dumps(result, ensure_ascii=False)


@server.tool()
def get_stock_news(ticker: str) -> str:
    """Get latest news for a specific A-share stock.

    Args:
        ticker: Stock code (e.g., "600519" for Maotai).
    """
    try:
        df = ak.stock_news_em(symbol=ticker)
        return _df_to_json(df)
    except Exception as e:
        return json.dumps({"error": f"get_stock_news failed: {e}"}, ensure_ascii=False)


@server.tool()
def get_market_headlines(top_n: int = 20) -> str:
    """Get latest A-share market headlines / hot news from East Money.

    Args:
        top_n: Number of headlines to return (default 20, max 50).
    """
    try:
        df = ak.stock_info_global_em()
        return _df_to_json(df.head(min(top_n, 50)))
    except Exception as e:
        return json.dumps({"error": f"get_market_headlines failed: {e}"}, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="China News MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    if args.transport == "sse":
        print(f"Starting SSE server on http://{args.host}:{args.port}/mcp", file=sys.stderr)
        server.run(transport="sse", host=args.host, port=args.port)
    else:
        print("Starting stdio MCP server...", file=sys.stderr)
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
