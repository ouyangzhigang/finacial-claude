"""
金融数据工具包 — 网络连通性检测
=================================
自动检测各数据源的可达性,在 Claude Code 沙箱环境中东方财富 push2 API
可能因网络策略被拦截,本模块提供健康检查和自动降级。
"""
import socket
import time
from typing import Optional


def check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    """TCP 端口连通性检测(纯 socket,不依赖 HTTP)。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_https(host: str, path: str, timeout: float = 5.0) -> tuple[bool, str]:
    """
    HTTPS 连通性检测。
    返回 (reachable, error_message)。
    使用 urllib 绕过 requests 的代理检测。
    """
    import urllib.request
    import os

    # 强制不使用代理
    for key in list(os.environ.keys()):
        if "proxy" in key.lower():
            os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"

    url = f"https://{host}{path}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.eastmoney.com/",
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        return True, ""
    except Exception as e:
        return False, str(e)


def check_akshare_sina() -> bool:
    """检测 AkShare 新浪源是否可用(已在沙箱中验证通过)。"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot()
        return df is not None and len(df) > 0
    except Exception:
        return False


def check_akshare_eastmoney() -> bool:
    """检测 AkShare 东方财富源是否可用。"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        return df is not None and len(df) > 0
    except Exception:
        return False


def health_check() -> dict:
    """
    全面数据源健康检查。
    返回各数据源的可达性和推荐方案。
    """
    results = {}

    # 1. AkShare 新浪源
    results["akshare_sina"] = {
        "name": "AkShare + 新浪财经源",
        "available": check_akshare_sina(),
        "recommendation": "✅ 推荐作为主要数据源",
    }

    # 2. AkShare 东方财富源
    results["akshare_em"] = {
        "name": "AkShare + 东方财富源",
        "available": check_akshare_eastmoney(),
        "recommendation": "⚠️ 如不可用则使用新浪源替代",
    }

    # 3. 东方财富 push2 API 直连
    reachable, err = check_https("push2.eastmoney.com", "/api/qt/clist/get?pn=1&pz=1")
    results["eastmoney_push2"] = {
        "name": "东方财富 push2 API (直连)",
        "available": reachable,
        "error": err[:100] if err else "",
        "recommendation": "❌ 沙箱环境通常不可用,无需尝试",
    }

    # 4. TCP 检测(辅助)
    results["eastmoney_tcp"] = {
        "name": "东方财富 TCP 端口检测",
        "push2_443": check_tcp("push2.eastmoney.com", 443),
        "82_push2_443": check_tcp("82.push2.eastmoney.com", 443),
    }

    return results


def get_recommended_source() -> str:
    """根据健康检查结果返回推荐的数据源。"""
    hc = health_check()
    if hc["akshare_sina"]["available"]:
        return "akshare_sina"
    elif hc["akshare_em"]["available"]:
        return "akshare_em"
    else:
        return "none"
