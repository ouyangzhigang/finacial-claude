# A股金融抓取配方（本地实测 2026-07-08）

配合 `scripts/fetch.py` 或 `scrapling extract`。完整站点速查见 `config/finance_sites.yaml`。

## 东方财富 push2his K线/行情 JSON

```bash
python ../scripts/fetch.py \
  "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600519&fields1=f1&fields2=f51,f52,f53,f54,f55,f56&klt=101&fqt=1&beg=20260701&end=20260708" \
  --no-verify --json
```

- 参数：`secid`（沪=1.代码 深=0.代码）、`klt`（101日/102周/103月）、`fqt`（0不复权1前复权）
- 解析：`json.loads(page.body)['data']['klines']`，每项 `"日期,开,收,高,低,量,..."`
- **flaky**：实测可能 200纯JSON / 502裹HTML-JSON / curl(56)连接断。fetch.py 的 auto 链 + `_extract_json` 容错 + 重试通常能拿到。失败重试 1-2 次。
- 实测结果：6 根日K，首根 `2026-07-01,1180.10,1193.01,1196.80,1166.33,42474`

## 东方财富 datacenter JSON（龙虎榜/涨停板/融资融券）

```bash
python ../scripts/fetch.py \
  "https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LHBSTKDETAIL&pageSize=50&pageNumber=1" \
  --no-verify --json
```

解析：`json.loads(page.body)['result']['data']` 为行列表。

## 雪球 xueqiu 个股页（强反爬，必须 stealthy）

```bash
python ../scripts/fetch.py "https://xueqiu.com/S/SH600519" --channel stealthy --no-verify
```

- 实测：**http 返回 85KB 无 title 的 JS 外壳**；**DynamicFetcher 触发"滑动验证页面"**；**StealthyFetcher 成功**（145KB，title="贵州茅台(SH600519)股票股价_股价行情_财报_数据报告 - 雪球"）
- 选择器：`page.css("title::text").get()`；正文数据在 JS 渲染后的 DOM 里，按需 `page.css(SEL, adaptive=True)`
- URL 模板：`https://xueqiu.com/S/{SH或SZ}{code}`

## 同花顺 10jqka 个股页

```bash
python ../scripts/fetch.py "https://stockpage.10jqka.com.cn/600519/" --no-verify
```

未本地实测选择器；抓回后用 `page.css` 探查，失效用 `adaptive=True`。

## 新浪财经（GBK）

```bash
python ../scripts/fetch.py "URL" --no-verify
```

新浪部分接口 GBK；scrapling 按响应头解码，若乱码：`page.body.decode('gbk')`。
**优先用项目 `scripts/cn_fetch.py`**（已内置 GBK+SSL 处理，更稳）。

## 受 Cloudflare 保护的站点

```bash
python ../scripts/fetch.py "URL" --channel stealthy --solve-cloudflare --no-verify
```

Cloudflare 挑战由 Scrapling 自动化处理，无需打码或凭证。

## 通用流程

1. 先 MCP 数据层（wind/ifind/akshare）取结构化字段——最准。
2. MCP 缺字段或要非结构化页面 → 本技能：`fetch.py URL --no-verify` 起步。
3. http 拿到外壳（缺关键内容/title）→ 升 `--channel dynamic`，仍不行 → `--channel stealthy`。
4. JSON 响应加 `--json`（容错提取，处理 502-裹-HTML-JSON）。
5. 只取片段加 `-s "CSS选择器"` 省 token。
6. 命令行直接抓用 `scrapling extract ... --ai-targeted -s SEL`。
