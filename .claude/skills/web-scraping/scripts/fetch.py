#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""金融网页抓取包装脚本——基于 Scrapling 的自动降级链。

作为命令行工具与可导入模块双重使用。默认针对金融站点优化：
verify=False（本地 SSL 常失败）、stealthy_headers=True、impersonate=chrome。

用法:
  python fetch.py URL [--channel auto|http|dynamic|stealthy] [--css SEL]
                      [-o FILE] [--no-verify] [--json] [--solve-cloudflare]
                      [--network-idle] [--impersonate chrome] [--timeout 30]

作为模块:
  from fetch import fetch_page
  page, meta = fetch_page("https://...", channel="auto")
  # page: scrapling Response/Selector；meta: dict(channel,status,length,elapsed,error)

注意: 降级链只在"抛异常"或"正文为空"时升级；status>=400 但有正文时照常返回
（meta 里如实标记 status，由调用方判断）。这处理了东方财富 push2his 返回 502
但 body 仍裹着 JSON 的真实怪象。
"""
import argparse
import json
import re
import sys
import time
import warnings

warnings.filterwarnings("ignore")

# Windows GBK 控制台直出 UTF-8 中文不乱码
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _fetch_http(url, **kw):
    from scrapling.fetchers import Fetcher
    return Fetcher.get(
        url,
        verify=kw.get("verify", False),
        stealthy_headers=True,
        impersonate=kw.get("impersonate", "chrome"),
        timeout=kw.get("timeout", 30),
    )


def _fetch_dynamic(url, **kw):
    from scrapling.fetchers import DynamicFetcher
    return DynamicFetcher.fetch(
        url,
        headless=kw.get("headless", True),
        network_idle=kw.get("network_idle", False),
        timeout=kw.get("timeout_ms", 30000),
    )


def _fetch_stealthy(url, **kw):
    from scrapling.fetchers import StealthyFetcher
    return StealthyFetcher.fetch(
        url,
        headless=kw.get("headless", True),
        network_idle=kw.get("network_idle", False),
        solve_cloudflare=kw.get("solve_cloudflare", False),
        timeout=kw.get("timeout_ms", 30000),
    )


_CHANNELS = {
    "http": _fetch_http,
    "dynamic": _fetch_dynamic,
    "stealthy": _fetch_stealthy,
}


def _html_str(page):
    if page is None:
        return ""
    v = getattr(page, "html_content", None)
    if v:
        return str(v)
    b = getattr(page, "body", None)
    if isinstance(b, (bytes, bytearray)):
        return b.decode("utf-8", "ignore")
    if b:
        return str(b)
    return ""


def _body_bytes(page):
    b = getattr(page, "body", None)
    if isinstance(b, (bytes, bytearray)):
        return bytes(b)
    return (_html_str(page) or "").encode("utf-8", "ignore")


def _strip_tags(html):
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _try_html2md(html):
    try:
        import html2text  # type: ignore
        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_links = False
        return h.handle(html)
    except Exception:
        return _strip_tags(html)


def _extract_json(text):
    """容错 JSON 提取：先整段 parse；失败则从首个 {/[ 到末尾 }/] 抽子串再 parse。
    用于东方财富等把 JSON 裹在 <html><body><p>...</p></body></html> 里的怪象。"""
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = -1
    for ch in ("{", "["):
        i = text.find(ch)
        if i != -1 and (start == -1 or i < start):
            start = i
    if start == -1:
        raise ValueError("正文里找不到 JSON 起始符 { 或 [")
    close = "}" if text[start] == "{" else "]"
    end = text.rfind(close)
    if end <= start:
        raise ValueError("找不到 JSON 结束符")
    return json.loads(text[start:end + 1])


def fetch_page(url, channel="auto", verify=False, timeout=30,
               network_idle=False, solve_cloudflare=False,
               impersonate="chrome", headless=True):
    """抓取 URL，返回 (page, meta)。

    channel='auto' 时按 http→dynamic→stealthy 降级：仅当某通道抛异常或正文为空时
    才升级。status>=400 但有正文时照常返回（meta 如实标记 status），让调用方据情判断——
    这处理了东方财富 502-带-body 的真实怪象。强制单通道时只跑该通道。
    """
    kw = dict(verify=verify, timeout=timeout, impersonate=impersonate,
              network_idle=network_idle, solve_cloudflare=solve_cloudflare,
              headless=headless, timeout_ms=timeout * 1000)
    chain = ["http", "dynamic", "stealthy"] if channel == "auto" else [channel]
    last_err = None
    for ch in chain:
        t0 = time.time()
        try:
            page = _CHANNELS[ch](url, **kw)
            status = int(getattr(page, "status", 200) or 200)
            body = _html_str(page)
            if not body:
                body = _body_bytes(page).decode("utf-8", "ignore")
            if len(body) == 0:
                raise RuntimeError(f"{ch} 返回空正文 status={status}")
            return page, {
                "channel": ch, "status": status, "length": len(body),
                "elapsed": round(time.time() - t0, 2), "url": url, "error": None,
            }
        except Exception as e:
            last_err = f"{ch}: {type(e).__name__}: {str(e)[:160]}"
            continue
    return None, {
        "channel": None, "status": None, "length": 0, "elapsed": 0,
        "url": url, "error": last_err,
    }


def _build_parser():
    p = argparse.ArgumentParser(
        description="Scrapling 金融抓取包装（自动降级链）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("url", help="目标 URL")
    p.add_argument("--channel", default="auto",
                   choices=["auto", "http", "dynamic", "stealthy"],
                   help="抓取通道（auto=自动降级，默认）")
    p.add_argument("-s", "--css", help="只提取匹配该 CSS 选择器的节点文本（省 token）")
    p.add_argument("-o", "--output", help="输出文件；扩展名决定格式：.md/.txt/.html")
    p.add_argument("--json", action="store_true", help="把响应当 JSON 解析后输出（容错提取）")
    p.add_argument("--no-verify", dest="verify", action="store_false", default=False,
                   help="关闭 SSL 校验（金融站点默认关）")
    p.add_argument("--verify", dest="verify", action="store_true",
                   help="强制开启 SSL 校验")
    p.add_argument("--network-idle", action="store_true", help="等网络空闲（dynamic/stealthy）")
    p.add_argument("--solve-cloudflare", action="store_true", help="stealthy 通道过 Cloudflare")
    p.add_argument("--impersonate", default="chrome", help="伪装的浏览器")
    p.add_argument("--timeout", type=int, default=30, help="超时秒数")
    p.add_argument("--no-headless", dest="headless", action="store_false", default=True,
                   help="显示浏览器窗口（调试用）")
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    page, meta = fetch_page(
        args.url, channel=args.channel, verify=args.verify, timeout=args.timeout,
        network_idle=args.network_idle, solve_cloudflare=args.solve_cloudflare,
        impersonate=args.impersonate, headless=args.headless,
    )
    sys.stderr.write(json.dumps(meta, ensure_ascii=False) + "\n")

    if page is None:
        sys.stderr.write("抓取失败，见上方 meta.error\n")
        return 2

    if args.json:
        raw = _body_bytes(page).decode("utf-8", "ignore") or _html_str(page)
        try:
            data = _extract_json(raw)
            content = json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e:
            sys.stderr.write(f"JSON 提取失败({e})，回退输出原始文本\n")
            content = _html_str(page) or raw
    elif args.css:
        nodes = page.css(args.css)
        parts = []
        for n in nodes:
            texts = n.css("::text").getall() if hasattr(n, "css") else [str(n)]
            parts.append("\n".join(texts))
        content = "\n---\n".join(parts)
    else:
        html = _html_str(page)
        if args.output and args.output.lower().endswith(".md"):
            content = _try_html2md(html)
        elif args.output and args.output.lower().endswith(".txt"):
            content = _strip_tags(html)
        else:
            content = html

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(content)
        sys.stderr.write(f"已写入 {args.output}（{len(content)} 字符）\n")
    else:
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
