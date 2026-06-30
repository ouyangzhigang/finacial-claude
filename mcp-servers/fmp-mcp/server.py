"""FMP MCP Server — global financial data via Financial Modeling Prep API.

Covers US/global equities: stock search, real-time quotes, company profile,
financial statements (income / balance sheet / cash flow), historical prices,
and key metrics. Data source: https://financialmodelingprep.com/

Usage:
    python server.py                    # stdio (local Claude)
    python server.py --transport sse    # HTTP/SSE (deployment)

Auth: set FMP_API_KEY env var, or write it to mcp_config.json (field "api_key").
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from mcp import FastMCP

_CONFIG_PATH = Path(__file__).parent / "mcp_config.json"
_BASE_URL = "https://financialmodelingprep.com/api/v3"


def _load_api_key() -> str:
    """Load FMP API key: env var first, then mcp_config.json fallback."""
    key = os.environ.get("FMP_API_KEY", "").strip()
    if key:
        return key
    if _CONFIG_PATH.exists():
        try:
            cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            key = cfg.get("api_key", "").strip()
            if key and key != "your-fmp-api-key-here":
                return key
        except Exception:
            pass
    return ""


API_KEY = _load_api_key()

server = FastMCP(
    "fmp-mcp",
    instructions="Global financial data via FMP — stock search, quotes, profile, financial statements, historical prices, key metrics",
)


def _get(endpoint: str, params: Optional[dict] = None) -> str:
    """Call FMP REST endpoint, return JSON string. Errors -> {"error": ...}."""
    if not API_KEY:
        return json.dumps(
            {"error": "FMP API key 未配置。请设置 FMP_API_KEY 环境变量或在 mcp_config.json 中配置密钥。申请地址：https://financialmodelingprep.com/"},
            ensure_ascii=False,
        )
    params = dict(params or {})
    params["apikey"] = API_KEY
    try:
        resp = requests.get(f"{_BASE_URL}/{endpoint}", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # FMP signals a bad key with an "Error Message" field rather than an HTTP error.
        if isinstance(data, dict) and data.get("Error Message"):
            return json.dumps({"error": f"FMP: {data['Error Message']}"}, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"FMP request failed: {e}"}, ensure_ascii=False)


@server.tool()
def search_stocks(query: str, limit: int = 20) -> str:
    """Search stocks by name or ticker symbol (US/global).

    Args:
        query: Company name or ticker (e.g., "Apple" or "AAPL").
        limit: Max results (default 20).
    """
    return _get("search-ticker", {"query": query, "limit": min(limit, 100)})


@server.tool()
def get_quote(symbol: str) -> str:
    """Get real-time quote for a stock.

    Args:
        symbol: Ticker symbol (e.g., "AAPL").
    """
    return _get(f"quote/{symbol}")


@server.tool()
def get_profile(symbol: str) -> str:
    """Get company profile (sector, industry, description, market cap, etc.).

    Args:
        symbol: Ticker symbol (e.g., "AAPL").
    """
    return _get(f"profile/{symbol}")


@server.tool()
def get_income_statement(symbol: str, period: str = "annual") -> str:
    """Get income statement.

    Args:
        symbol: Ticker symbol (e.g., "AAPL").
        period: "annual" (default) or "quarter".
    """
    return _get(f"income-statement/{symbol}", {"period": period})


@server.tool()
def get_balance_sheet(symbol: str, period: str = "annual") -> str:
    """Get balance sheet statement.

    Args:
        symbol: Ticker symbol (e.g., "AAPL").
        period: "annual" (default) or "quarter".
    """
    return _get(f"balance-sheet-statement/{symbol}", {"period": period})


@server.tool()
def get_cash_flow(symbol: str, period: str = "annual") -> str:
    """Get cash flow statement.

    Args:
        symbol: Ticker symbol (e.g., "AAPL").
        period: "annual" (default) or "quarter".
    """
    return _get(f"cash-flow-statement/{symbol}", {"period": period})


@server.tool()
def get_historical_price(symbol: str, start_date: str, end_date: str) -> str:
    """Get historical daily prices.

    Args:
        symbol: Ticker symbol (e.g., "AAPL").
        start_date: Start date, YYYY-MM-DD.
        end_date: End date, YYYY-MM-DD.
    """
    return _get(f"historical-price-full/{symbol}", {"from": start_date, "to": end_date})


@server.tool()
def get_key_metrics(symbol: str, period: str = "annual") -> str:
    """Get key valuation/financial metrics (P/E, P/B, ROE, debt ratios, etc.).

    Args:
        symbol: Ticker symbol (e.g., "AAPL").
        period: "annual" (default) or "quarter".
    """
    return _get(f"key-metrics/{symbol}", {"period": period})


def main():
    parser = argparse.ArgumentParser(description="FMP MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--port", type=int, default=8004)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    if not API_KEY:
        print(
            "WARNING: FMP API key 未配置。请设置 FMP_API_KEY 环境变量或在 mcp_config.json 中配置密钥。"
            "申请地址：https://financialmodelingprep.com/",
            file=sys.stderr,
        )

    if args.transport == "sse":
        print(f"Starting SSE server on http://{args.host}:{args.port}/mcp", file=sys.stderr)
        server.run(transport="sse", host=args.host, port=args.port)
    else:
        print("Starting FMP stdio MCP server...", file=sys.stderr)
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
