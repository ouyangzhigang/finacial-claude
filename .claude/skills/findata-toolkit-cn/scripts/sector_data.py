#!/usr/bin/env python3
"""
A-Share Sector & Board Data Fetcher
=====================================
获取板块/行业/概念数据。优先使用 AkShare 新浪源(沙箱环境可用),
东方财富源不可用时自动降级。

Usage:
    python sector_data.py --board-concept       # 概念板块
    python sector_data.py --board-industry      # 行业板块
    python sector_data.py --zt-pool             # 涨停板
    python sector_data.py --zt-industry         # 涨停行业分布
    python sector-data.py --lt-pool             # 连板股
    python sector_data.py --dy-pool             # 跌停股
    python sector_data.py --broken-pool         # 炸板股
    python sector_data.py --top-volume          # 成交额榜
    python sector_data.py --top-change          # 涨幅榜
    python sector_data.py --market-overview     # 市场概览
    python sector_data.py --health              # 数据源健康检查
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.utils import output_json, safe_float, error_exit
from common.health_check import health_check, get_recommended_source


# ---------------------------------------------------------------------------
# 市场概览 (新浪财经源)
# ---------------------------------------------------------------------------

def fetch_market_overview() -> dict:
    """获取全市场行情概览:涨跌分布、成交额、涨停跌停统计。"""
    import akshare as ak

    result = {"timestamp": datetime.now().isoformat(), "source": "akshare_sina"}

    try:
        df = ak.stock_zh_a_spot()
        if df is None or df.empty:
            return {"error": "No market data"}

        result["total_stocks"] = len(df)
        result["columns"] = list(df.columns)

        # 涨跌分布
        df["涨跌幅"] = df["涨跌幅"].astype(float)
        df["成交额"] = df["成交额"].astype(float)

        up_count = len(df[df["涨跌幅"] > 0])
        down_count = len(df[df["涨跌幅"] < 0])
        flat_count = len(df[df["涨跌幅"] == 0])

        result["breadth"] = {
            "up": up_count,
            "down": down_count,
            "flat": flat_count,
            "up_pct": round(up_count / len(df) * 100, 1),
            "down_pct": round(down_count / len(df) * 100, 1),
        }

        # 涨跌停统计
        limit_up = len(df[df["涨跌幅"] >= 19.5])
        limit_down = len(df[df["涨跌幅"] <= -19.5])
        big_up = len(df[(df["涨跌幅"] > 9.5) & (df["涨跌幅"] < 19.5)])
        big_down = len(df[(df["涨跌幅"] < -9.5) & (df["涨跌幅"] > -19.5)])
        st_count = len(df[df["名称"].str.contains("ST", na=False)])

        result["statistics"] = {
            "limit_up": limit_up,
            "limit_down": limit_down,
            "big_up_10_20": big_up,
            "big_down_minus10_minus20": big_down,
            "st_count": st_count,
            "limit_up_down_ratio": round(limit_up / max(limit_down, 1), 1),
        }

        # 平均/中位数
        result["avg_change"] = round(df["涨跌幅"].mean(), 2)
        result["median_change"] = round(df["涨跌幅"].median(), 2)
        result["total_amount"] = round(df["成交额"].sum() / 1e12, 2)  # 万亿

    except Exception as e:
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# 涨幅榜
# ---------------------------------------------------------------------------

def fetch_top_gainers(n: int = 20) -> dict:
    """涨幅榜 Top N (新浪财经源)。"""
    import akshare as ak

    try:
        df = ak.stock_zh_a_spot()
        df["涨跌幅"] = df["涨跌幅"].astype(float)
        df["成交额"] = df["成交额"].astype(float)
        top = df.nlargest(n, "涨跌幅")

        records = []
        for _, r in top.iterrows():
            records.append({
                "code": r["代码"],
                "name": r["名称"],
                "price": round(r["最新价"], 2),
                "change_pct": round(r["涨跌幅"], 2),
                "amount_亿": round(r["成交额"] / 1e8, 1),
            })

        return {"source": "akshare_sina", "top_gainers": records}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 成交额榜
# ---------------------------------------------------------------------------

def fetch_top_volume(n: int = 20) -> dict:
    """成交额榜 Top N (新浪财经源)。"""
    import akshare as ak

    try:
        df = ak.stock_zh_a_spot()
        df["成交额"] = df["成交额"].astype(float)
        top = df.nlargest(n, "成交额")

        records = []
        for _, r in top.iterrows():
            records.append({
                "code": r["代码"],
                "name": r["名称"],
                "price": round(r["最新价"], 2),
                "change_pct": round(r["涨跌幅"], 2),
                "amount_亿": round(r["成交额"] / 1e8, 1),
            })

        return {"source": "akshare_sina", "top_volume": records}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 涨停板
# ---------------------------------------------------------------------------

def fetch_zt_pool(date_str: str = None) -> dict:
    """
    涨停板数据 (东方财富源)。
    如果东方财富源不可用,回退到新浪财经源涨停统计。
    """
    import akshare as ak

    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    result = {"date": date_str}

    # 优先: 东方财富涨停板
    try:
        df = ak.stock_zt_pool_em(date=date_str)
        if df is not None and not df.empty:
            result["source"] = "akshare_eastmoney"
            result["total_zt"] = len(df)

            # 涨停行业分布
            industry_counts = df["所属行业"].value_counts().head(10)
            result["industry_distribution"] = {
                ind: int(cnt) for ind, cnt in industry_counts.items()
            }

            # 连板统计
            df["涨停统计"] = df["涨停统计"].astype(str)
            connected = []
            for _, r in df.iterrows():
                ts = r["涨停统计"]
                if "/" in str(ts):
                    parts = str(ts).split("/")
                    if len(parts) == 2:
                        connected.append({
                            "code": r["代码"],
                            "name": r["名称"],
                            "connected": f"{parts[0]}/{parts[1]}",
                            "industry": r.get("所属行业", ""),
                            "turnover": round(float(r.get("换手率", 0)), 2),
                            "amount_亿": round(float(r.get("成交额", 0)) / 1e8, 1),
                        })
            connected.sort(key=lambda x: int(x["connected"].split("/")[0]), reverse=True)
            result["connected_stocks"] = connected[:20]

            # 首板详情
            first_board = df[df["涨停统计"].str.startswith("1/")].head(20)
            result["first_board_count"] = len(first_board)

            return result
    except Exception as e:
        result["eastmoney_error"] = str(e)

    # 降级: 从全市场数据中筛选涨停
    try:
        df = ak.stock_zh_a_spot()
        df["涨跌幅"] = df["涨跌幅"].astype(float)
        zt = df[df["涨跌幅"] >= 9.5]
        result["source"] = "akshare_sina_fallback"
        result["total_zt_fallback"] = len(zt)
        result["note"] = "东方财富涨停板API不可用,使用新浪源涨停统计降级"
    except Exception as e:
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# 连板股
# ---------------------------------------------------------------------------

def fetch_connected_stocks(date_str: str = None) -> dict:
    """连板梯队分析。"""
    import akshare as ak

    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    try:
        df = ak.stock_zt_pool_em(date=date_str)
        if df is None or df.empty:
            return {"error": "No data"}

        df["涨停统计"] = df["涨停统计"].astype(str)

        # 按连板数分组
        tiers = {}
        for _, r in df.iterrows():
            ts = r["涨停统计"]
            if "/" in str(ts):
                parts = str(ts).split("/")
                if len(parts) == 2:
                    level = int(parts[0])
                    if level not in tiers:
                        tiers[level] = []
                    tiers[level].append({
                        "code": r["代码"],
                        "name": r["名称"],
                        "industry": r.get("所属行业", ""),
                        "turnover": round(float(r.get("换手率", 0)), 2),
                        "amount_亿": round(float(r.get("成交额", 0)) / 1e8, 1),
                    })

        # 排序
        tier_list = []
        for level in sorted(tiers.keys(), reverse=True):
            tier_list.append({
                "level": level,
                "count": len(tiers[level]),
                "stocks": tiers[level][:10],  # 每层最多10只
            })

        return {"date": date_str, "tiers": tier_list, "source": "akshare_eastmoney"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 跌停板
# ---------------------------------------------------------------------------

def fetch_limit_down(date_str: str = None) -> dict:
    """跌停板数据。"""
    import akshare as ak

    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    try:
        df = ak.stock_zt_pool_dtgc_em(date=date_str)
        if df is not None and not df.empty:
            records = []
            for _, r in df.iterrows():
                records.append({
                    "code": r["代码"],
                    "name": r["名称"],
                    "change_pct": round(float(r["涨跌幅"]), 2),
                    "price": round(float(r["最新价"]), 2),
                    "industry": r.get("所属行业", ""),
                })
            return {"date": date_str, "limit_down": records, "total": len(records)}
    except Exception:
        pass

    return {"date": date_str, "limit_down": [], "total": 0, "note": "No limit down data"}


# ---------------------------------------------------------------------------
# 炸板股
# ---------------------------------------------------------------------------

def fetch_broken_board(date_str: str = None) -> dict:
    """炸板股数据。"""
    import akshare as ak

    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    try:
        df = ak.stock_zt_pool_zbgc_em(date=date_str)
        if df is not None and not df.empty:
            records = []
            for _, r in df.iterrows():
                records.append({
                    "code": r["代码"],
                    "name": r["名称"],
                    "change_pct": round(float(r["涨跌幅"]), 2),
                    "price": round(float(r["最新价"]), 2),
                    "industry": r.get("所属行业", ""),
                })
            return {"date": date_str, "broken": records, "total": len(records)}
    except Exception as e:
        return {"error": str(e)}

    return {"date": date_str, "broken": [], "total": 0}


# ---------------------------------------------------------------------------
# 行业板块 (新浪财经源)
# ---------------------------------------------------------------------------

def fetch_industry_board() -> dict:
    """
    行业板块排行。
    东方财富 push2 API 在沙箱中不可用,使用新浪全市场数据按行业分组统计。
    """
    import akshare as ak

    try:
        df = ak.stock_zh_a_spot()
        df["涨跌幅"] = df["涨跌幅"].astype(float)
        df["成交额"] = df["成交额"].astype(float)

        # 按行业分组统计
        industry_stats = {}
        for _, r in df.iterrows():
            ind = r.get("行业", "Unknown")
            if ind not in industry_stats:
                industry_stats[ind] = {"count": 0, "total_amount": 0, "max_change": -999, "stocks": []}
            industry_stats[ind]["count"] += 1
            industry_stats[ind]["total_amount"] += r["成交额"]
            if r["涨跌幅"] > industry_stats[ind]["max_change"]:
                industry_stats[ind]["max_change"] = r["涨跌幅"]
            if len(industry_stats[ind]["stocks"]) < 3:
                industry_stats[ind]["stocks"].append({
                    "code": r["代码"],
                    "name": r["名称"],
                    "change_pct": round(r["涨跌幅"], 2),
                })

        # 按平均涨幅排序 Top 20
        sorted_industries = sorted(
            industry_stats.items(),
            key=lambda x: x[1]["max_change"],
            reverse=True,
        )

        records = []
        for ind, stats in sorted_industries[:20]:
            records.append({
                "industry": ind,
                "stock_count": stats["count"],
                "max_change_pct": round(stats["max_change"], 2),
                "total_amount_亿": round(stats["total_amount"] / 1e8, 1),
                "leading_stocks": stats["stocks"],
            })

        return {"source": "akshare_sina_industry_group", "industries": records}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# 概念板块 (新浪财经源)
# ---------------------------------------------------------------------------

def fetch_concept_board() -> dict:
    """
    概念板块排行。
    从涨停板行业分布推断热门概念。
    """
    import akshare as ak

    try:
        df = ak.stock_zh_a_spot()
        df["涨跌幅"] = df["涨跌幅"].astype(float)

        # 筛选涨停和大涨股票
        hot = df[df["涨跌幅"] >= 9.5]

        # 按行业统计涨停数
        industry_zt = hot["行业"].value_counts().head(15)

        records = []
        for ind, cnt in industry_zt.items():
            ind_stocks = hot[hot["行业"] == ind][["代码", "名称", "涨跌幅", "成交额"]].head(5)
            stocks = [{
                "code": r["代码"],
                "name": r["名称"],
                "change_pct": round(r["涨跌幅"], 2),
            } for _, r in ind_stocks.iterrows()]

            records.append({
                "concept": ind,
                "zt_count": int(cnt),
                "leading_stocks": stocks,
            })

        return {"source": "akshare_sina_zt_inference", "concepts": records}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A-Share Sector & Board Data Fetcher"
    )
    parser.add_argument("--board-concept", action="store_true", help="Concept board ranking")
    parser.add_argument("--board-industry", action="store_true", help="Industry board ranking")
    parser.add_argument("--zt-pool", action="store_true", help="Limit-up stocks")
    parser.add_argument("--zt-industry", action="store_true", help="Limit-up industry distribution")
    parser.add_argument("--lt-pool", "--connected", action="store_true", help="Connected limit-up stocks")
    parser.add_argument("--dy-pool", action="store_true", help="Limit-down stocks")
    parser.add_argument("--broken-pool", action="store_true", help="Broken limit-up stocks")
    parser.add_argument("--top-volume", action="store_true", help="Top trading volume")
    parser.add_argument("--top-change", action="store_true", help="Top gainers")
    parser.add_argument("--market-overview", action="store_true", help="Market overview")
    parser.add_argument("--health", action="store_true", help="Data source health check")
    parser.add_argument("--date", type=str, default=None, help="Date string YYYYMMDD")
    args = parser.parse_args()

    try:
        if args.health:
            data = health_check()
        elif args.market_overview:
            data = fetch_market_overview()
        elif args.top_change:
            data = fetch_top_gainers()
        elif args.top_volume:
            data = fetch_top_volume()
        elif args.zt_pool or args.zt_industry:
            data = fetch_zt_pool(args.date)
            if args.zt_industry and "industry_distribution" in data:
                # 只输出行业分布
                data = {"industry_distribution": data.get("industry_distribution", {}),
                        "connected_stocks": data.get("connected_stocks", [])}
        elif args.lt_pool or args.connected:
            data = fetch_connected_stocks(args.date)
        elif args.dy_pool:
            data = fetch_limit_down(args.date)
        elif args.broken_pool:
            data = fetch_broken_board(args.date)
        elif args.board_concept:
            data = fetch_concept_board()
        elif args.board_industry:
            data = fetch_industry_board()
        else:
            # 默认输出市场概览 + 涨停板
            data = {
                "timestamp": datetime.now().isoformat(),
                "market_overview": fetch_market_overview(),
                "zt_pool": fetch_zt_pool(args.date),
            }

        output_json(data)

    except ImportError:
        error_exit("akshare is required. Install: pip install akshare")
    except Exception as e:
        error_exit(f"Error: {e}")


if __name__ == "__main__":
    main()
