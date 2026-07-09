#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""金融网页抓取包装脚本——基于 Scrapling 的自动降级链 + 重试。

作为命令行工具与可导入模块双重使用。默认针对金融站点优化：
verify=False（本地 SSL 常失败）、stealthy_headers=True、impersonate=chrome。

用法:
  python fetch.py URL [--channel auto|http|dynamic|stealthy] [--css SEL]
                      [-o FILE] [--no-verify] [--json] [--solve-cloudflare]
                      [--network-idle] [--impersonate chrome] [--timeout 30]
                      [--retry N] [--urls-file FILE]

批量:
  python fetch.py --urls-file urls.txt -o out/ --json     # 每 URL 一个文件
  python fetch.py --urls-file urls.txt --json              # 逐条输出到 stdout

作为模块:
  from fetch import fetch_page
  page, meta = fetch_page("https://...", channel="auto", retries=2)
  # page: scrapling Response/Selector；meta: dict(channel,status,length,elapsed,attempts,error)

注意: 降级链只在"抛异常"或"正文为空"时升级；status>=400 但有正文时照常返回
（meta 里如实标记 status，由调用方判断）。这处理了东方财富 push2his 返回 502
但 body 仍裹着 JSON 的真实怪象。
"""
import argparse
import json
import os
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


def _slugify_url(url):
    """URL → 安全文件名（批量输出时用）。"""
    s = re.sub(r"https?://", "", url)
    s = re.sub(r"[?#].*", "", s)
    s = re.sub(r"[/:]+", "_", s)
    s = re.sub(r"[^\w.\-]", "_", s)
    return s[:120] or "index"


def fetch_page(url, channel="auto", verify=False, timeout=30,
               network_idle=False, solve_cloudflare=False,
               impersonate="chrome", headless=True, retries=2):
    """抓取 URL，返回 (page, meta)。

    channel='auto' 时按 http→dynamic→stealthy 降级：仅当某通道抛异常或正文为空时
    才升级。status>=400 但有正文时照常返回（meta 如实标记 status），让调用方据情判断——
    这处理了东方财富 502-带-body 的真实怪象。

    retries: 整条降级链跑完后仍失败（异常或空正文）时，重试整条链的次数（默认 2）。
    金融站点 flaky（东方财富 push2his 偶发 502/空回复），重试常能拿到。
    """
    kw = {"verify": verify, "timeout": timeout, "impersonate": impersonate,
          "network_idle": network_idle, "solve_cloudflare": solve_cloudflare,
          "headless": headless, "timeout_ms": timeout * 1000}
    chain = ["http", "dynamic", "stealthy"] if channel == "auto" else [channel]
    all_attempts = []

    for attempt in range(1, retries + 2):  # retries=2 → 最多跑 3 轮
        last_err = None
        for ch in chain:
            t0 = time.time()
            try:
                page = _CHANNELS[ch](url, **kw)
                status = int(getattr(page, "status", 200) or 200)
                body = _html_str(page)
                if not body:
                    body = _body_bytes(page).decode("utf-8", "ignore")
                elapsed = round(time.time() - t0, 2)
                if len(body) == 0:
                    err = f"{ch} 返回空正文 status={status}"
                    all_attempts.append({"channel": ch, "status": status, "length": 0,
                                         "elapsed": elapsed, "error": err})
                    last_err = err
                    continue
                return page, {
                    "channel": ch, "status": status, "length": len(body),
                    "elapsed": elapsed, "url": url, "error": None,
                    "attempt": attempt, "attempts": all_attempts,
                }
            except Exception as e:
                elapsed = round(time.time() - t0, 2)
                err = f"{ch}: {type(e).__name__}: {str(e)[:160]}"
                all_attempts.append({"channel": ch, "status": None, "length": 0,
                                     "elapsed": elapsed, "error": err})
                last_err = err
                continue

        # 整条链跑完仍失败，若还有重试额度，等 0.5s 再来一轮
        if attempt <= retries:
            time.sleep(0.5)

    return None, {
        "channel": None, "status": None, "length": 0, "elapsed": 0,
        "url": url, "error": last_err, "attempt": retries + 1,
        "attempts": all_attempts,
    }


def _process_one(url, args, out_dir=None):
    """处理单个 URL，返回 (content, meta)。"""
    page, meta = fetch_page(
        url, channel=args.channel, verify=args.verify, timeout=args.timeout,
        network_idle=args.network_idle, solve_cloudflare=args.solve_cloudflare,
        impersonate=args.impersonate, headless=args.headless,
        retries=args.retry,
    )
    # stderr 始终输出 meta（批量时也如此，便于监控）
    sys.stderr.write(json.dumps(meta, ensure_ascii=False) + "\n")

    if page is None:
        return None, meta

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
        ext = (args.output or "").lower()
        if out_dir:
            ext = ".json" if args.json else ".md"
        if ext.endswith(".md"):
            content = _try_html2md(html)
        elif ext.endswith(".txt"):
            content = _strip_tags(html)
        else:
            content = html

    return content, meta


def _build_parser():
    p = argparse.ArgumentParser(
        description="Scrapling 金融抓取包装（自动降级链 + 重试）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("url", nargs="?", help="目标 URL（--urls-file 时忽略）")
    p.add_argument("--channel", default="auto",
                   choices=["auto", "http", "dynamic", "stealthy"],
                   help="抓取通道（auto=自动降级，默认）")
    p.add_argument("-s", "--css", help="只提取匹配该 CSS 选择器的节点文本（省 token）")
    p.add_argument("-o", "--output", help="输出文件（单 URL）或目录（批量）；扩展名决定格式：.md/.txt/.html")
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
    p.add_argument("--retry", type=int, default=2,
                   help="整条降级链失败后重试次数（默认 2，金融站点 flaky 时常需重试）")
    p.add_argument("--urls-file", help="批量模式：从文件读取 URL（每行一个），-o 指定输出目录")
    return p


def _run_batch(args):
    """批量模式：从 urls-file 逐条抓取，输出到目录。"""
    with open(args.urls_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    if not urls:
        sys.stderr.write("urls-file 为空\n")
        return 2

    out_dir = args.output or "."
    os.makedirs(out_dir, exist_ok=True)
    results = {"total": len(urls), "ok": 0, "fail": 0, "items": []}

    for i, url in enumerate(urls, 1):
        sys.stderr.write(f"[{i}/{len(urls)}] {url}\n")
        content, meta = _process_one(url, args, out_dir=out_dir)
        if content is not None:
            fname = _slugify_url(url) + (".json" if args.json else ".md")
            out_path = os.path.join(out_dir, fname)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            results["ok"] += 1
            results["items"].append({"url": url, "file": out_path, "status": meta["status"]})
            sys.stderr.write(f"  → {out_path} ({len(content)} 字符)\n")
        else:
            results["fail"] += 1
            results["items"].append({"url": url, "error": meta["error"]})
            sys.stderr.write(f"  → 失败: {meta['error']}\n")

    summary = json.dumps(results, ensure_ascii=False, indent=2)
    sys.stdout.write(summary + "\n")
    return 0 if results["fail"] == 0 else 1


def _run_single(args):
    """单 URL 模式。"""
    if not args.url:
        sys.stderr.write("错误：需提供 URL 或 --urls-file\n")
        return 2

    content, meta = _process_one(args.url, args)
    if content is None:
        sys.stderr.write("抓取失败，见上方 meta.error\n")
        return 2

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(content)
        sys.stderr.write(f"已写入 {args.output}（{len(content)} 字符）\n")
    else:
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.urls_file:
        return _run_batch(args)
    return _run_single(args)


if __name__ == "__main__":
    raise SystemExit(main())
