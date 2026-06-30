#!/usr/bin/env python3
"""
A-Share Market Stock Data Fetcher
=================================
Fetch A-share stock fundamentals, price history, financial metrics,
and insider trading data using multiple data sources:

  Tier-1: AkShare (free, no API key)
  Tier-2: BaoStock (free, no API key, stable server-side data)
  Tier-3: East Money push2 API (direct HTTP, no scraping)

Usage:
    python stock_data.py 600519                       # Basic info (Kweichow Moutai)
    python stock_data.py 600519 --metrics             # Full financial metrics
    python stock_data.py 600519 --history             # Price history
    python stock_data.py 600519 --financials          # Financial statements
    python stock_data.py 600519 --insider             # Insider trades
    python stock_data.py 600519 000858 --screen       # Screen with filters
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.utils import output_json, safe_div, safe_float, error_exit
from common.cache import cached


def _normalize_symbol(symbol: str) -> str:
    """Normalize A-share symbol to 6-digit format."""
    sym = symbol.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    return sym.zfill(6)


def _get_exchange_suffix(symbol: str) -> str:
    """Determine exchange from symbol prefix."""
    sym = _normalize_symbol(symbol)
    if sym.startswith(("6",)):
        return "sh"  # Shanghai
    elif sym.startswith(("0", "3")):
        return "sz"  # Shenzhen
    elif sym.startswith(("4", "8")):
        return "bj"  # Beijing Stock Exchange
    return "sh"


def _to_baostock_code(symbol: str) -> str:
    """Convert 6-digit symbol to baostock format (sh.600519 / sz.000858)."""
    sym = _normalize_symbol(symbol)
    if sym.startswith("6"):
        return f"sh.{sym}"
    else:
        return f"sz.{sym}"


# ---------------------------------------------------------------------------
# BaoStock helpers
# ---------------------------------------------------------------------------

def _bs_login():
    """Login to BaoStock (cached per session)."""
    import baostock as bs
    lg = bs.login()
    if lg.error_code != '0':
        raise RuntimeError(f"BaoStock login failed: {lg.error_msg}")
    return bs


def _bs_logout(bs_mod):
    """Logout from BaoStock."""
    bs_mod.logout()


# ---------------------------------------------------------------------------
# Tier-1: AkShare functions (optimized — no full-market pull)
# ---------------------------------------------------------------------------

@cached(ttl=30)
def fetch_basic_info(symbols: list[str]) -> list[dict]:
    """Fetch basic company info via East Money push2 API (fast JSON)."""
    import requests

    results = []
    for symbol in symbols:
        sym = _normalize_symbol(symbol)
        try:
            # secid format: exchange_id.stock_code (SH=1, SZ=0)
            secid = f"1.{sym}" if sym.startswith("6") else f"0.{sym}"
            url = (
                f"https://push2.eastmoney.com/api/qt/stock/get"
                f"?secid={secid}"
                f"&fields=f43,f57,f58,f60,f162"
            )
            resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()
            d = data.get("data", {})
            if d:
                results.append({
                    "symbol": sym,
                    "name": d.get("f58", ""),
                    "market_cap": safe_float(d.get("f60")) * 10000 if d.get("f60") else None,
                    "circulating_cap": safe_float(d.get("f57")) * 10000 if d.get("f57") else None,
                    "exchange": _get_exchange_suffix(sym),
                })
            else:
                results.append({"symbol": sym, "error": "Empty data from API"})
        except Exception as e:
            results.append({"symbol": sym, "error": str(e)})

    return results


# ---------------------------------------------------------------------------
# Tier-2: BaoStock functions
# ---------------------------------------------------------------------------

@cached(ttl=3600)
def fetch_price_history_bs(symbol: str, period: str = "1y",
                           adjust: str = "qfq") -> dict:
    """
    Fetch historical OHLCV data via BaoStock (stable, server-side data).

    BaoStock advantages over AkShare:
    - Own server infrastructure, not dependent on upstream web APIs
    - Reliable 5-min / 60-min intraday bars
    - Forward/backward adjusted prices
    """
    bs_mod = _bs_login()
    try:
        sym = _normalize_symbol(symbol)
        bs_code = _to_baostock_code(symbol)

        period_map = {
            "1m": 30, "3m": 90, "6m": 180, "1y": 365,
            "2y": 730, "5y": 1825, "max": 7300,
        }
        days = period_map.get(period, 365)
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")

        # adjustflag: 1=后复权 2=前复权 3=不复权
        adj_map = {"qfq": "2", "hfq": "1", "": "3"}
        adj_flag = adj_map.get(adjust, "2")

        rs = bs_mod.query_history_k_data_plus(
            bs_code,
            "date,code,open,high,low,close,volume,amount,pctChg,turn",
            start_date=start, end_date=end,
            frequency="d", adjustflag=adj_flag
        )

        if rs.error_code != '0':
            return {"symbol": sym, "error": f"BaoStock query failed: {rs.error_msg}"}

        records = []
        while rs.next():
            row = rs.get_row_data()
            # BaoStock fields: 0=date, 1=code, 2=open, 3=high, 4=low, 5=close, 6=volume, 7=amount, 8=pctChg, 9=turn
            records.append({
                "date": row[0] if len(row) > 0 else "",
                "open": safe_float(row[2]) if len(row) > 2 else None,
                "high": safe_float(row[3]) if len(row) > 3 else None,
                "low": safe_float(row[4]) if len(row) > 4 else None,
                "close": safe_float(row[5]) if len(row) > 5 else None,
                "volume": safe_float(row[6]) if len(row) > 6 else None,
                "amount": safe_float(row[7]) if len(row) > 7 else None,
                "change_pct": safe_float(row[8]) if len(row) > 8 else None,
                "turnover_rate": safe_float(row[9]) if len(row) > 9 else None,
            })

        if not records:
            return {"symbol": sym, "error": "No price data found"}

        return {
            "symbol": sym,
            "source": "baostock",
            "period": period,
            "adjust": adjust,
            "data_points": len(records),
            "start_date": records[0]["date"],
            "end_date": records[-1]["date"],
            "prices": records,
        }
    finally:
        _bs_logout(bs_mod)


# ---------------------------------------------------------------------------
# Unified fetchers (Tier-1 primary, Tier-2 fallback)
# ---------------------------------------------------------------------------

@cached(ttl=3600)
def fetch_financial_metrics(symbol: str) -> dict:
    """
    Fetch comprehensive financial metrics.
    Data sources: East Money push2 API (quote) + AkShare (financials)
    """
    sym = _normalize_symbol(symbol)

    result = {
        "symbol": sym,
        "name": "",
        "industry": "",
        "current_price": None,
        "market_cap": None,
    }

    # --- Basic info (East Money push2 API) ---
    try:
        import requests
        secid = f"1.{sym}" if sym.startswith("6") else f"0.{sym}"
        url = (
            f"https://push2.eastmoney.com/api/qt/stock/get"
            f"?secid={secid}"
            f"&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f169,f170,f171,f162"
        )
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        data = resp.json()
        d = data.get("data", {})
        if d:
            result["name"] = d.get("f58", "")
            result["current_price"] = safe_float(d.get("f43")) / 100 if d.get("f43") else None
            result["market_cap"] = safe_float(d.get("f60")) * 10000 if d.get("f60") else None
            result["valuation"] = {
                "pe_ttm": safe_float(d.get("f169")) / 100 if d.get("f169") else None,
                "pb": safe_float(d.get("f170")) / 100 if d.get("f170") else None,
                "total_market_cap": safe_float(d.get("f60")) * 10000 if d.get("f60") else None,
                "circulating_cap": safe_float(d.get("f57")) * 10000 if d.get("f57") else None,
            }
            result["trading"] = {
                "change_pct": safe_float(d.get("f44")) / 100 if d.get("f44") else None,
                "turnover_rate": safe_float(d.get("f171")) / 100 if d.get("f171") else None,
                "volume": safe_float(d.get("f47")),
                "amount": safe_float(d.get("f48")),
                "amplitude": safe_float(d.get("f45")) / 100 if d.get("f45") else None,
            }
    except Exception:
        pass

    # --- Financial indicators (AkShare) ---
    try:
        import akshare as ak
        df_fin = ak.stock_financial_abstract_ths(symbol=sym, indicator="按报告期")
        if df_fin is not None and not df_fin.empty:
            latest = df_fin.iloc[-1]
            result["profitability"] = {
                "roe": safe_float(latest.get("净资产收益率")),
                "gross_margin": safe_float(latest.get("销售毛利率")),
                "net_margin": safe_float(latest.get("销售净利率")),
            }
            result["leverage"] = {
                "debt_to_asset_ratio": safe_float(latest.get("资产负债率")),
                "current_ratio": safe_float(latest.get("流动比率")),
                "quick_ratio": safe_float(latest.get("速动比率")),
            }
            result["growth"] = {
                "revenue_growth_yoy": safe_float(latest.get("营业总收入同比增长率")),
                "profit_growth_yoy": safe_float(latest.get("净利润同比增长率")),
            }
            result["per_share"] = {
                "eps": safe_float(latest.get("基本每股收益")),
                "bvps": safe_float(latest.get("每股净资产")),
                "ocf_per_share": safe_float(latest.get("每股经营现金流")),
            }
    except Exception:
        pass

    # --- Dividend data ---
    try:
        import akshare as ak
        df_div = ak.stock_history_dividend_detail(symbol=sym, indicator="分红")
        if df_div is not None and not df_div.empty:
            recent_divs = df_div.head(5)
            dividends = []
            for _, row in recent_divs.iterrows():
                dividends.append({
                    "report_date": str(row.get("公告日期", "")),
                    "dividend_per_share": safe_float(row.get("派息")),
                    "ex_date": str(row.get("除权除息日", "")),
                })
            result["dividends"] = dividends
    except Exception:
        result["dividends"] = []

    return result


@cached(ttl=3600)
def fetch_price_history(symbol: str, period: str = "1y",
                        adjust: str = "qfq") -> dict:
    """
    Fetch historical OHLCV data.
    Tier-1: AkShare → Tier-2: BaoStock (fallback, more stable).
    """
    sym = _normalize_symbol(symbol)

    # Try AkShare first
    try:
        import akshare as ak

        period_map = {
            "1m": 30, "3m": 90, "6m": 180, "1y": 365,
            "2y": 730, "5y": 1825, "max": 7300,
        }
        days = period_map.get(period, 365)
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        end = datetime.now().strftime("%Y%m%d")

        df = ak.stock_zh_a_hist(
            symbol=sym, period="daily",
            start_date=start, end_date=end,
            adjust=adjust
        )

        if df is not None and not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "date": str(row.get("日期", "")),
                    "open": safe_float(row.get("开盘")),
                    "high": safe_float(row.get("最高")),
                    "low": safe_float(row.get("最低")),
                    "close": safe_float(row.get("收盘")),
                    "volume": safe_float(row.get("成交量")),
                    "amount": safe_float(row.get("成交额")),
                    "turnover_rate": safe_float(row.get("换手率")),
                })

            return {
                "symbol": sym,
                "source": "akshare",
                "period": period,
                "adjust": adjust,
                "data_points": len(records),
                "start_date": records[0]["date"] if records else "",
                "end_date": records[-1]["date"] if records else "",
                "prices": records,
            }
    except Exception:
        pass

    # Fallback to BaoStock (more stable server-side data)
    return fetch_price_history_bs(symbol, period, adjust)


@cached(ttl=86400)
def fetch_financial_statements(symbol: str) -> dict:
    """Fetch income statement, balance sheet, and cash flow."""
    sym = _normalize_symbol(symbol)
    result = {"symbol": sym}

    try:
        import akshare as ak

        # --- Income Statement ---
        try:
            df = ak.stock_financial_report_sina(stock=sym, symbol="利润表")
            if df is not None and not df.empty:
                records = []
                for col in df.columns[:5]:  # Last 5 periods
                    period_data = {"period": str(col)}
                    for idx in df.index:
                        val = safe_float(df.loc[idx, col])
                        period_data[str(idx)] = val
                    records.append(period_data)
                result["income_statement"] = records
        except Exception:
            result["income_statement"] = []

        # --- Balance Sheet ---
        try:
            df = ak.stock_financial_report_sina(stock=sym, symbol="资产负债表")
            if df is not None and not df.empty:
                records = []
                for col in df.columns[:5]:
                    period_data = {"period": str(col)}
                    for idx in df.index:
                        val = safe_float(df.loc[idx, col])
                        period_data[str(idx)] = val
                    records.append(period_data)
                result["balance_sheet"] = records
        except Exception:
            result["balance_sheet"] = []

        # --- Cash Flow Statement ---
        try:
            df = ak.stock_financial_report_sina(stock=sym, symbol="现金流量表")
            if df is not None and not df.empty:
                records = []
                for col in df.columns[:5]:
                    period_data = {"period": str(col)}
                    for idx in df.index:
                        val = safe_float(df.loc[idx, col])
                        period_data[str(idx)] = val
                    records.append(period_data)
                result["cash_flow"] = records
        except Exception:
            result["cash_flow"] = []

    except Exception as e:
        result["error"] = str(e)

    return result


def _get_exchange_prefix(symbol: str) -> str:
    """Return exchange prefix for insider trade filtering (e.g. 'SH688557')."""
    sym = _normalize_symbol(symbol)
    if sym.startswith("6"):
        return "SH" + sym
    elif sym.startswith(("0", "3")):
        return "SZ" + sym
    elif sym.startswith(("4", "8")):
        return "BJ" + sym
    return "SH" + sym


@cached(ttl=86400)
def fetch_insider_trades(symbol: str) -> dict:
    """Fetch insider trading (董监高增减持) data for an A-share stock."""
    sym = _normalize_symbol(symbol)
    prefixed = _get_exchange_prefix(sym)

    try:
        import akshare as ak
        df = ak.stock_inner_trade_xq()
        if df is None or df.empty:
            return {"symbol": sym, "transactions": [], "note": "No insider trades found"}

        # Filter for our target symbol
        df = df[df["股票代码"] == prefixed]
        if df.empty:
            return {"symbol": sym, "transactions": [], "note": "No insider trades found"}

        trades = []
        for _, row in df.iterrows():
            shares_changed = safe_float(row.get("变动股数"))
            if shares_changed is not None and shares_changed > 0:
                change_type = "增持"
            elif shares_changed is not None and shares_changed < 0:
                change_type = "减持"
            else:
                change_type = "未知"

            trades.append({
                "name": str(row.get("变动人", "")),
                "position": str(row.get("董监高职务", "")),
                "relationship": str(row.get("与董监高关系", "")),
                "change_type": change_type,
                "shares_changed": shares_changed,
                "price": safe_float(row.get("成交均价")),
                "shares_after": safe_float(row.get("变动后持股数")),
                "date": str(row.get("变动日期", "")),
            })

        buys = [t for t in trades if t["change_type"] == "增持"]
        sells = [t for t in trades if t["change_type"] == "减持"]

        return {
            "symbol": sym,
            "total_transactions": len(trades),
            "summary": {
                "total_purchases": len(buys),
                "total_sales": len(sells),
                "unique_buyers": len(set(t["name"] for t in buys)),
            },
            "transactions": trades,
        }
    except Exception as e:
        return {"symbol": sym, "error": str(e)}


@cached(ttl=300)
def fetch_northbound_flow() -> dict:
    """Fetch northbound capital flow data (北向资金/沪深港通)."""
    try:
        import akshare as ak
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向")
        if df is None or df.empty:
            return {"error": "No northbound flow data"}

        # Last 30 days
        records = []
        for _, row in df.tail(30).iterrows():
            records.append({
                "date": str(row.get("日期", "")),
                "net_inflow": safe_float(row.get("当日净流入")),
                "sh_connect": safe_float(row.get("沪股通净流入")),
                "sz_connect": safe_float(row.get("深股通净流入")),
            })

        return {
            "data_points": len(records),
            "flows": records,
        }
    except Exception as e:
        return {"error": str(e)}


@cached(ttl=3600)
def screen_stocks(symbols: list[str], filters: dict | None = None) -> dict:
    """
    Screen A-share stocks against financial filters.

    Default filters:
        max_pe: 30        (P/E below 30)
        max_pb: 5         (P/B below 5)
        min_roe: 8        (ROE above 8%)
        max_debt_ratio: 60 (Debt-to-asset ratio below 60%)
    """
    defaults = {
        "max_pe": 30.0,
        "max_pb": 5.0,
        "min_roe": 8.0,
        "max_debt_ratio": 60.0,
    }
    if filters:
        defaults.update(filters)

    passing = []
    failing = []

    for sym in symbols:
        try:
            m = fetch_financial_metrics(sym)
            if "error" in m:
                failing.append({"symbol": sym, "reason": m["error"]})
                continue

            reasons = []
            pe = (m.get("valuation") or {}).get("pe_ttm")
            if pe is not None and pe <= 0:
                reasons.append(f"PE {pe:.1f} 无效（为零或负值，通常表示亏损）")
            elif pe is not None and pe > defaults["max_pe"]:
                reasons.append(f"PE {pe:.1f} > {defaults['max_pe']:.1f}")

            pb = (m.get("valuation") or {}).get("pb")
            if pb is not None and pb > defaults["max_pb"]:
                reasons.append(f"PB {pb:.1f} > {defaults['max_pb']:.1f}")

            roe = (m.get("profitability") or {}).get("roe")
            if roe is not None and roe < defaults["min_roe"]:
                reasons.append(f"ROE {roe:.1f}% < {defaults['min_roe']:.1f}%")

            debt_ratio = (m.get("leverage") or {}).get("debt_to_asset_ratio")
            if debt_ratio is not None and debt_ratio > defaults["max_debt_ratio"]:
                reasons.append(
                    f"Debt ratio {debt_ratio:.1f}% > {defaults['max_debt_ratio']:.1f}%"
                )

            if reasons:
                failing.append({"symbol": sym, "reasons": reasons})
            else:
                passing.append(m)

        except Exception as e:
            failing.append({"symbol": sym, "reason": str(e)})

    return {
        "filters_applied": defaults,
        "total_screened": len(symbols),
        "passed": len(passing),
        "failed": len(failing),
        "results": passing,
        "rejected": failing,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A-Share Stock Data Fetcher (AkShare + BaoStock + EastMoney API, no API key)"
    )
    parser.add_argument("symbols", nargs="*", help="A-share stock code(s)")
    parser.add_argument("--metrics", action="store_true",
                        help="Full financial metrics")
    parser.add_argument("--history", action="store_true",
                        help="Price history")
    parser.add_argument("--financials", action="store_true",
                        help="Financial statements")
    parser.add_argument("--insider", action="store_true",
                        help="Insider trading data")
    parser.add_argument("--northbound", action="store_true",
                        help="Northbound capital flow")
    parser.add_argument("--screen", action="store_true",
                        help="Screen against default filters")
    parser.add_argument("--period", default="1y",
                        help="History period (1m,3m,6m,1y,2y,5y,max)")
    parser.add_argument("--source", default="auto",
                        choices=["auto", "akshare", "baostock"],
                        help="Data source: auto (tiered), akshare, baostock")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Clear all cached data and exit")
    args = parser.parse_args()

    # Clear cache mode
    if args.clear_cache:
        from common.cache import cache_clear_all
        count = cache_clear_all()
        output_json({"cleared_entries": count, "message": "Cache cleared"})
        return

    try:
        if args.northbound:
            data = fetch_northbound_flow()
        elif not args.symbols:
            error_exit("Please provide stock symbol(s) or use --northbound or --clear-cache")
            return
        elif args.screen:
            data = screen_stocks(args.symbols)
        elif args.metrics:
            if len(args.symbols) == 1:
                data = fetch_financial_metrics(args.symbols[0])
            else:
                data = [fetch_financial_metrics(s) for s in args.symbols]
        elif args.history:
            if args.source == "baostock":
                data = fetch_price_history_bs(args.symbols[0], period=args.period)
            else:
                data = fetch_price_history(args.symbols[0], period=args.period)
        elif args.financials:
            data = fetch_financial_statements(args.symbols[0])
        elif args.insider:
            data = fetch_insider_trades(args.symbols[0])
        else:
            data = fetch_basic_info(args.symbols)

        output_json(data)

    except ImportError as e:
        error_exit(f"Missing dependency: {e}. Install: pip install akshare baostock requests")
    except Exception as e:
        error_exit(f"Error fetching data: {e}")


if __name__ == "__main__":
    main()
