# Fetchers 深度参考

Scrapling 提供 4 个 fetcher + 对应 session 类。本机实测（2026-07-08）Fetcher / DynamicFetcher / StealthyFetcher 三条通道均可用。

## 通道选型

| Fetcher | 底层 | 适合 | 本机状态 |
|---------|------|------|----------|
| `Fetcher` / `AsyncFetcher` | curl_cffi（HTTP，TLS 指纹伪装） | 静态页、JSON API、博客新闻 | 可用 |
| `DynamicFetcher` | Playwright Chromium | SPA、JS 渲染、等接口返回 | 可用 |
| `StealthyFetcher` | 指纹伪装（camoufox 可选） | 反爬、Cloudflare Turnstile | 可用（camoufox 未装仍可降级） |

升级链：Fetcher → DynamicFetcher → StealthyFetcher。仅在异常或正文为空时升级。
盲区：JS 重站点 http 返回 200+非空外壳不会自动升级，须显式指定通道。

## Fetcher（HTTP）

```python
from scrapling.fetchers import Fetcher, FetcherSession
page = Fetcher.get(url, verify=False, stealthy_headers=True, impersonate='chrome', timeout=30)
with FetcherSession(impersonate='chrome') as s:
    p1 = s.get(url1, stealthy_headers=True)
    p2 = s.get(url2, impersonate='firefox135')
```

关键参数：`verify`（SSL，金融站点常需 False）、`stealthy_headers`、`impersonate`（chrome/firefox/safari，可逗号随机）、`http3`（FetcherSession）、`timeout`（秒）、`proxy`。

## DynamicFetcher（Playwright JS 渲染）

```python
from scrapling.fetchers import DynamicFetcher
page = DynamicFetcher.fetch(url, headless=True, network_idle=True, timeout=30000)
```

关键参数：`headless`、`network_idle`（等接口跑完）、`disable_resources`（提速）、`wait_selector`、`real_chrome`、`block_ads`、`timeout`（毫秒）、`capture_xhr`（正则，`page.captured_xhr`）。

## StealthyFetcher（反爬）

```python
from scrapling.fetchers import StealthyFetcher
page = StealthyFetcher.fetch(url, headless=True, solve_cloudflare=True, timeout=30000)
```

关键参数（在 dynamic 基础上）：`solve_cloudflare`（过 Turnstile，无需打码/凭证）、`block_webrtc`/`allow_webgl`/`hide_canvas`（指纹）、`dns_over_https`（用代理时防 DNS 泄漏）。

## 代理轮换

所有 session 类支持 proxy 列表轮换（cyclic 或自定义策略），详见 `spiders.md`。

## page 对象属性（实测 Response）

- `page.status`：int（HTTP 状态码）
- `page.body`：bytes（原始响应体；JSON 用 `.decode()`）
- `page.html_content`：str（HTML 文本，用于 Selector 解析）
- `page.css(sel)` / `page.xpath(sel)` / `page.find_all(...)`
- `page.css(sel, adaptive=True)` / `auto_save=True`：自适应定位

> JSON API 响应 `body` 可能裹在 `<html><body><p>{...}</p></body></html>` 里（东方财富 502 怪象），用容错提取（见 `scripts/fetch.py` 的 `_extract_json`）。
