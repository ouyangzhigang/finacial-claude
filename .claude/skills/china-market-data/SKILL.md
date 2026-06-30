---
name: china-market-data
description: Query A-share and Chinese financial market data via multiple data sources. Six-tier architecture: Tier-0 Wind, Tier-1 iFind, Tier-2 Tushare/AkShare MCP, Tier-2.5 East Money push2 API (direct JSON), Tier-3 BaoStock (stable server-side data), Tier-4 FMP (global), Tier-5 Scrapling (web scraping fallback). Use whenever the agent needs Chinese financial data — compatible with 沪深 A 股, 科创板, 创业板, 北交所, and 港股通 stocks.
---

# china-market-data

## Architecture overview

Six complementary data acquisition layers, escalating from structured MCP tools to adaptive web scraping:

| Tier | Source | Type | Cost | Speed | Coverage | When to use |
|------|--------|------|------|-------|----------|-------------|
| **0** | Wind (万得) | MCP structured | Paid | ★★★★★ | ★★★★★ | Default for all structured financial data |
| **1** | iFind (同花顺) | MCP structured | Paid | ★★★★★ | ★★★★☆ | Precise financials, ESG, bonds, macro |
| **2** | Tushare MCP + AkShare MCP | MCP structured | Free | ★★★★☆ | ★★★★☆ | Primary free source:行情/财报/行业/指数/宏观/龙虎榜 |
| **2.5** | East Money push2 API | Direct HTTP JSON | Free | ★★★★★ | ★★★☆ | Real-time quotes, PE/PB, market cap — zero scraping |
| **3** | BaoStock | Python library (server-side) | Free | ★★★★☆ | ★★★☆ | Stable historical K-line, 5min/60min bars, financials |
| **4** | FMP (全球数据) | REST API | Freemium | ★★★★☆ | ★★★★★ | Global stocks, ETFs, crypto, forex, commodities |
| **5** | Scrapling | Web scraping | Free | ★★★☆☆ | ★★★★★ | Unstructured web data, news, regulatory filings, protected sites |

**Escalation principle**: Always start with the most structured, lowest-latency source (Wind → iFind → Tushare/AkShare MCP → push2 API → BaoStock). Only escalate to Scrapling when:
- No MCP tool covers the needed data
- The data lives on a website not exposed via API
- You need to scrape content behind anti-bot protection (Cloudflare, etc.)
- MCP tools are unavailable or rate-limited

---

## Tier 0 — Wind (万得)

- 覆盖：A股/港美股/基金/指数/债券/宏观/研报/分析（44个工具）
- MCP 服务：`wind-mcp`（需 `WIND_API_KEY` 密钥，以 `ak_` 开头）
- 优势：全市场覆盖面最广、数据最全面、包含研报和量化分析
- 密钥申请：https://aifinmarket.wind.com.cn/#/home

## Tier 1 — iFind (同花顺)

- 覆盖：股票、基金、宏观经济、新闻公告、债券、港美股、指数板块
- MCP 服务：`ifind-mcp`（需 `IFIND_AUTH_TOKEN` 密钥）
- 优势：精确财务数据、一致预期、ESG评级、债券详情、港美股、宏观行业指标
- 并发限制：免费版 2/s，个人版 5/s，企业版 10/s

### 股票服务

| Tool | Purpose |
|------|---------|
| `ifind_search_stocks` | 自然语言智能选股 |
| `ifind_get_stock_summary` | 股票信息摘要 |
| `ifind_get_stock_info` | 基本资料 / 日频行情 / 技术指标 |
| `ifind_get_stock_shareholders` | 股本结构与股东 |
| `ifind_get_stock_financials` | 财务数据与指标 |
| `ifind_get_risk_indicators` | 风险定量指标 |
| `ifind_get_stock_events` | 上市公司重大事件 |
| `ifind_get_esg_data` | ESG 评级数据 |

### 基金服务

| Tool | Purpose |
|------|---------|
| `ifind_search_funds` | 基金搜索 |
| `ifind_get_fund_profile` | 基金基本资料 |
| `ifind_get_fund_market_performance` | 基金行情与业绩 |
| `ifind_get_fund_ownership` | 基金份额与持有人 |
| `ifind_get_fund_portfolio` | 基金持仓明细 |
| `ifind_get_fund_financials` | 基金财务指标 |
| `ifind_get_fund_company_info` | 基金公司信息 |

### 宏观经济 / 行业经济指标

| Tool | Purpose |
|------|---------|
| `ifind_search_edb` | 指标模糊搜索（先搜再查） |
| `ifind_get_edb_data` | 指标数据查询 |

### 新闻公告

| Tool | Purpose |
|------|---------|
| `ifind_search_news` | 新闻资讯语义检索 |
| `ifind_search_notice` | 上市公司公告语义检索 |
| `ifind_search_trending_news` | 热点事件资讯 |

### 债券

| Tool | Purpose |
|------|---------|
| `ifind_bond_basic_info` | 债券基本信息 |
| `ifind_bond_market_data` | 债券行情与估值 |
| `ifind_bond_financial_data` | 发债主体财务 |
| `ifind_bond_special_data` | 可转债/信用债特殊条款 |

### 港美股

| Tool | Purpose |
|------|---------|
| `ifind_search_global_stocks` | 港美股智能选股 |
| `ifind_global_stock_profile` | 港美股基本资料 |
| `ifind_global_stock_quotes` | 港美股行情 |
| `ifind_global_stock_financial` | 港美股财务 |
| `ifind_global_stock_events` | 港美股公告事件 |

### 指数板块

| Tool | Purpose |
|------|---------|
| `ifind_index_data` | 指数行情 / 技术指标 / 估值 |
| `ifind_sector_data` | 板块行情 / 成分股分析 |

## Tier 2 — Tushare MCP + AkShare MCP (免费)

### Tushare MCP（推荐作为免费首选）

- MCP 服务：`tushareMcp`（无需密钥即可使用基础工具）
- 覆盖：400+ 工具，涵盖 A 股行情、财报、资金流、龙虎榜、涨跌停、概念板块、宏观数据等
- 优势：结构化数据、无需爬虫、覆盖极广

**核心工具速查**：

| 数据类型 | Tushare MCP 工具 |
|----------|-----------------|
| 日线行情 | `mcp__tushareMcp__daily` |
| 分钟线 | `mcp__tushareMcp__stk_mins` |
| 利润表 | `mcp__tushareMcp__income` |
| 资产负债表 | `mcp__tushareMcp__balancesheet` |
| 现金流量表 | `mcp__tushareMcp__cashflow` |
| 财务指标 | `mcp__tushareMcp__fina_indicator` |
| 每日指标 | `mcp__tushareMcp__daily_basic` |
| 个股资金流 | `mcp__tushareMcp__moneyflow` |
| 沪深港通 | `mcp__tushareMcp__moneyflow_hsgt` |
| 涨跌停 | `mcp__tushareMcp__limit_list` / `limit_list_ths` |
| 龙虎榜 | `mcp__tushareMcp__top_list` / `top_inst` |
| 概念板块 | `mcp__tushareMcp__dc_daily` / `cls_daily` |
| 宏观 GDP | `mcp__tushareMcp__cn_gdp` |
| 宏观 CPI | `mcp__tushareMcp__cn_cpi` |
| 宏观 PMI | `mcp__tushareMcp__cn_pmi` |
| 货币供应 | `mcp__tushareMcp__cn_m` |
| 社融 | `mcp__tushareMcp__sf_month` |
| 公告 | `mcp__tushareMcp__anns_d` |
| 新闻 | `mcp__tushareMcp__major_news` |
| 美股行情 | `mcp__tushareMcp__us_daily` |

### AkShare MCP

- MCP 服务：`akshare-mcp`（无需密钥，直接启动）
- 覆盖：A 股行情、财报、行业分类、指数
- 优势：无并发限制，适合高频批量查询

| Tool | Purpose |
|------|---------|
| `search_stock` | Search A-share stocks by code or name |
| `get_quote` | Real-time quote (price, PE, PB, market cap) |
| `get_historical_data` | OHLCV history (daily/weekly/monthly), forward-adjusted |
| `get_financials` | 利润表/资产负债表/现金流量表 |
| `get_industry_stocks` | 行业分类 & 成分股 (东方财富行业) |
| `get_index_data` | 指数行情 (上证/深证/创业板/科创50) |
| `get_stock_info` | 公司基本信息 & 业务范围 |
| `get_market_overview` | 涨幅榜/跌幅榜/成交额榜 |
| `get_fund_data` | 公募基金/ETF 行情 |

## Tier 2.5 — 东方财富 push2 API（直连 HTTP JSON）

东方财富 push2 API 返回原生 JSON，**无需爬虫、无需浏览器渲染**。

```python
import requests

# 实时行情 + 估值（600519 贵州茅台）
suffix = "1"  # 1=沪市, 0=深市
url = (
    f"https://push2.eastmoney.com/api/qt/stock/get"
    f"?secid={suffix}.600519"
    f"&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170"
)
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
data = resp.json()["data"]
# f43=最新价(分), f169=PE-TTM, f170=PB, f60=总市值
```

| 字段 | 含义 | 单位 |
|------|------|------|
| f43 | 最新价 | 分（÷100） |
| f44 | 涨跌幅 | ‱（÷100） |
| f45 | 振幅 | ‱（÷100） |
| f47 | 成交量 | 手 |
| f48 | 成交额 | 元 |
| f57 | 流通市值 | 万元 |
| f58 | 股票简称 | 文本 |
| f60 | 总市值 | 万元 |
| f169 | PE-TTM | ‱（÷100） |
| f170 | PB | ‱（÷100） |
| f171 | 换手率 | ‱（÷100） |

## Tier 3 — BaoStock（稳定历史 K 线）

- 免费 Python 库，自有服务端基础设施
- 不依赖上游网页接口（AkShare 依赖东方财富/新浪前端 API，可能因改版挂掉）
- 提供 5 分钟/60 分钟 K 线，比 AkShare 更稳定

```python
import baostock as bs
bs.login()
rs = bs.query_history_k_data_plus(
    "sh.600519",
    "date,open,high,low,close,volume,amount,pctChg",
    start_date="2025-01-01", end_date="2025-12-31",
    frequency="d", adjustflag="2"  # 2=前复权
)
while rs.next():
    row = rs.get_row_data()
    # 0=date, 1=code, 2=open, 3=high, 4=low, 5=close, 6=volume, 7=amount, 8=pctChg
```

## Tier 4 — FMP（全球数据）

- 覆盖：全球股票、ETF、加密货币、外汇、商品、分析师评级、宏观
- REST API，需 API Key

## Tier 5 — Scrapling（网页抓取兜底）

当所有 MCP 数据源都无法获取所需信息时，使用 Scrapling 进行网页抓取。Scrapling 是一个自适应 Web 抓取框架，具备以下核心能力：

### 核心优势

1. **反爬虫绕过**：内置 Cloudflare Turnstile/Interstitial 自动求解，无需第三方服务
2. **三层抓取器**：
   - `Fetcher` — 高速 HTTP 请求（TLS 指纹伪装，如真实浏览器）
   - `DynamicFetcher` — 浏览器渲染（Playwright，支持 JS 执行）
   - `StealthyFetcher` — 高级隐身模式（反指纹、Canvas 噪声、WebRTC 泄漏防护）
3. **智能选择器**：CSS / XPath / BeautifulSoup 风格 / 文本匹配 / 正则提取 / 相似元素发现
4. **Spider 框架**：Scrapy 风格的并发爬虫，支持断点续爬、代理轮换
5. **MCP 工具集成**：10 个 MCP 工具，支持持久化浏览器会话管理
6. **内容净化**：自动去除广告、隐藏元素、提示注入攻击

### 数据源优先级

| 数据类型 | 首选方案 | 备选方案 |
|----------|----------|----------|
| 结构化财务数据 | Wind/iFind/Tushare MCP | — |
| 实时行情快照 | 东方财富 push2 API / AkShare MCP | Scrapling `Fetcher` |
| 历史 K 线 | Tushare MCP `daily` / BaoStock | AkShare |
| 公司公告原文 | Tushare MCP `anns_d` | Scrapling `StealthyFetcher` 抓巨潮 |
| 个股新闻 | Tushare MCP `major_news` | Scrapling `Fetcher` 抓东财 |
| 行业研报 | Wind MCP | Scrapling `DynamicFetcher` 抓慧博/投研论坛 |
| 宏观经济数据 | Tushare MCP `cn_gdp/cn_cpi/cn_ppi` | AkShare MCP |
| 港股/美股行情 | iFind 全球股票 / Tushare `us_daily` | FMP |
| 交易所公告/规则 | — | Scrapling `StealthyFetcher` 抓上交所/深交所 |
| 东方财富/雪球社区 | — | Scrapling `DynamicFetcher` / `StealthyFetcher` |
| 任何未覆盖的网站 | — | Scrapling（最后一道防线） |

### 抓取器选择指南

```
需要抓取网站数据？
│
├─ 静态页面，无反爬？ ──→ Fetcher (最快，TLS 指纹伪装)
│   例：国家统计局公开数据页、证监会公告
│
├─ 需要 JS 渲染，无强反爬？ ──→ DynamicFetcher
│   例：东方财富行情页、新浪财经、Yahoo Finance
│
└─ 有 Cloudflare/反爬保护？ ──→ StealthyFetcher
    例：巨潮资讯网、上交所/深交所、部分券商网站
```

### 常用 A 股数据抓取场景

#### 1. 从巨潮资讯网抓取公司公告原文

```python
from scrapling.fetchers import StealthyFetcher

page = StealthyFetcher.fetch(
    'http://www.cninfo.com.cn/new/fulltextSearch/full?searchkey=贵州茅台&isfulltext=false&sortName=pubdate&sortType=desc&pageNum=1&pageSize=10',
    solve_cloudflare=True,
    timeout=60000,
    wait_selector='.news-result-item'
)
titles = page.css('.news-result-item .title::text').getall()
```

#### 2. 从雪球获取个股讨论与舆情

```python
from scrapling.fetchers import DynamicFetcher

page = DynamicFetcher.fetch(
    'https://xueqiu.com/v4/statuses/public_timeline_by_category.json?since_id=-1&max_id=-1&count=20&category=1111',
    wait=2000,
    disable_resources=True
)
```

#### 3. 批量抓取多个股票的基本信息

```python
from scrapling.fetchers import FetcherSession

tickers = ['600519', '000858', '601318']

with FetcherSession(impersonate='chrome', timeout=30) as session:
    for ticker in tickers:
        page = session.get(f'https://push2.eastmoney.com/api/qt/stock/get?secid=1.{ticker}')
        info = page.json()
        print(f"{ticker}: {info.get('data', {}).get('f58', '')}")
```

### MCP 工具（Scrapling MCP Server）

启动 `scrapling mcp` 后，提供以下工具：

| 工具 | 用途 |
|------|------|
| `get` | HTTP GET 请求（静态页面，最快） |
| `bulk_get` | 并发 GET 多个静态页面 |
| `fetch` | 浏览器渲染抓取（JS 动态页面） |
| `bulk_fetch` | 并发浏览器抓取 |
| `stealthy_fetch` | 隐身模式抓取（反 Cloudflare） |
| `bulk_stealthy_fetch` | 并发隐身抓取 |
| `open_session` | 创建持久化浏览器会话 |
| `close_session` | 关闭会话 |
| `list_sessions` | 列出活跃会话 |
| `screenshot` | 页面截图 |

**工具选择策略**：
- 优先用 `get`（HTTP 请求最快）
- `get` 返回空内容 → 升级到 `fetch`（浏览器渲染）
- `fetch` 被拦截 → 升级到 `stealthy_fetch`（反爬虫绕过）
- 同一站点多次抓取 → `open_session` + `session_id` 复用

### 解析技巧

Scrapling 返回的 `Response` 对象支持多种选择器：

```python
# CSS 选择器
page.css('.quote .text::text').getall()

# XPath
page.xpath('//div[@class="quote"]//span[@class="text"]/text()').getall()

# BeautifulSoup 风格
page.find_all('div', class_='quote')

# 文本匹配
page.find_by_text('净利润')

# 正则提取
page.css('.price::text').re_first(r'\d+\.?\d*')

# 相似元素发现
first_item.find_similar()  # 找到所有同类元素
```

### 注意事项

1. **遵守 robots.txt**：Spider 设置 `robots_txt_obey = True`
2. **控制频率**：批量抓取加延时 `download_delay`，避免被封
3. **输出格式**：优先 `.md` 输出可读性；抓取 API 接口用 `.json`
4. **CSS 选择器**：始终用 `-s` / `css_selector` 缩小提取范围，节省 token
5. **临时文件清理**：抓取后及时删除临时文件
6. **Cloudflare 求解**：设置 `timeout >= 60000ms` 给足挑战求解时间
7. **广告拦截**：浏览器工具默认拦截 ~3,500 个广告域名，节省 token

---

## 数据源模式切换

> **env var `IFIND_DATA_SOURCE_MODE`**:
> - `wind-only` (strict): 仅 Wind，不可用时报错
> - `wind-fallback` (recommended): Wind 首选，回退 iFind → Tushare → AkShare
> - `ifind-only` (strict): 仅 iFind，不可用时报错
> - `ifind-fallback` (default): iFind 首选，回退 Tushare/AkShare
> - `akshare-only`: 仅 AkShare，跳过 Wind/iFind
> - `scrapling-only`: 仅 Scrapling 网页抓取
>
> Usage: `export IFIND_DATA_SOURCE_MODE=ifind-only`

---

## 工作流

### Step 1: 识别标的

```python
# Tushare MCP — 股票列表
mcp__tushareMcp__stock_basic(ts_code="600519.SH")

# iFind — 自然语言选股
ifind_search_stocks(query="电子行业市值大于100亿")

# AkShare — 关键词搜索
search_stock(keyword="茅台")
```

### Step 2: 获取行情与财务数据

```python
# Tushare MCP — 日线行情
mcp__tushareMcp__daily(ts_code="600519.SH", start_date="20250101", end_date="20251231")

# 东方财富 push2 API — 实时行情（零爬虫）
requests.get("https://push2.eastmoney.com/api/qt/stock/get?secid=1.600519&fields=f43,f169,f170")

# BaoStock — 历史 K 线（稳定服务端）
bs.query_history_k_data_plus("sh.600519", "date,open,high,low,close,volume", ...)

# AkShare MCP — 财务报表
get_financials(ticker="600519")
```

### Step 3: 行业 / 板块上下文

```python
# Tushare MCP — 概念板块
mcp__tushareMcp__dc_daily(trade_date="20260628", idx_type="概念板块")

# iFind — 板块分析
ifind_sector_data(query="白酒板块的成分股个数及过去5日平均涨跌幅")

# AkShare — 行业成分
get_industry_stocks(industry="白酒")
```

### Step 4: 宏观指标

```python
# Tushare MCP — 宏观数据（推荐）
mcp__tushareMcp__cn_gdp(start_q="2024Q1", end_q="2025Q4")
mcp__tushareMcp__cn_cpi(start_m="202501", end_m="202512")
mcp__tushareMcp__cn_pmi(m="202506")

# iFind — 先搜索再取数
ifind_search_edb(query="新能源汽车产量相关指标")
ifind_get_edb_data(query="新能源汽车产量当月值（202301-202506）")
```

### Step 5: 新闻与舆情

```python
# Tushare MCP — 新闻舆情
mcp__tushareMcp__major_news(src="财联社", start_date="2025-01-01 00:00:00", end_date="2025-01-02 00:00:00")

# iFind — 公告语义检索
ifind_search_notice(query="贵州茅台2024年年度报告 分红", time_start="2025-01-01", time_end="2025-12-31", size=5)

# AkShare — 个股新闻
get_stock_news(ticker="600519")

# Scrapling — 巨潮资讯公告原文（MCP 不可用时）
StealthyFetcher.fetch('http://www.cninfo.com.cn/new/fulltextSearch/full?searchkey=贵州茅台')

# Scrapling — 东方财富股吧舆情
DynamicFetcher.fetch('https://guba.eastmoney.com/list,600519.html')
```

---

## 数据覆盖说明

- **A 股**: Wind/iFind/Tushare/AkShare/BaoStock 全覆盖（SH, SZ, BJ, STAR, ChiNext），Scrapling 可抓东方财富/新浪/腾讯行情
- **港股**: iFind 完整覆盖；AkShare 部分覆盖；Scrapling 可抓 Yahoo Finance HK
- **美股中概**: iFind 通过 `ifind_global_stock_*` 覆盖；Tushare `us_daily`；Scrapling 可抓 Yahoo Finance
- **基金**: iFind 完整覆盖（资料/行情/持仓/持有人）；AkShare 仅 ETF 行情
- **债券**: iFind 覆盖信用债/可转债/回购；Tushare MCP 也有债券工具
- **ESG**: 仅 iFind 提供
- **宏观经济**: Tushare MCP 覆盖最广（GDP/CPI/PPI/PMI/M2/社融）；AkShare 有基础宏观数据
- **新闻/公告**: Tushare MCP `major_news` / `anns_d`；iFind 语义检索最强；Scrapling 可抓巨潮/交易所原文
- **研报**: Wind 独有（44 个工具）；Scrapling 可抓慧博/投研论坛
- **社区舆情**: Scrapling 可抓雪球/东方财富股吧
- **未覆盖数据源**: Scrapling 是最后一道防线，几乎可以抓任何公开网页

---

## 快速参考矩阵

| 场景 | 首选 | 备选 1 | 备选 2 | 兜底 |
|------|------|--------|--------|------|
| 财务报表 | Tushare MCP | iFind | AkShare | — |
| 实时行情 | 东方财富 push2 API | Tushare MCP | AkShare | — |
| K 线历史 | Tushare MCP | BaoStock | AkShare | — |
| 股东结构 | Wind | iFind | — | — |
| ESG 评级 | iFind | — | — | — |
| 宏观数据 | Tushare MCP | AkShare MCP | — | — |
| 公告原文 | Tushare MCP `anns_d` | iFind | Scrapling 巨潮 | — |
| 个股新闻 | Tushare MCP `major_news` | AkShare | Scrapling 东财 | — |
| 行业研报 | Wind | Scrapling 慧博 | — | — |
| 社区舆情 | — | — | — | Scrapling 雪球/东财 |
| 港股行情 | iFind | — | Scrapling Yahoo | — |
| 美股行情 | Tushare `us_daily` | iFind | FMP | — |
