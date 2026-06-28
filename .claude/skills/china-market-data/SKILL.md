---
name: china-market-data
description: Query A-share and Chinese financial market data via multiple data sources. Four-tier architecture: Tier-0 Wind (most comprehensive paid), Tier-1 iFind (precise financials), Tier-2 AkShare (free open-source), Tier-3 Scrapling (web scraping for sites not covered by MCP). Use whenever the agent needs Chinese financial data — compatible with 沪深 A 股, 科创板, 创业板, 北交所, and 港股通 stocks.
---

# china-market-data

## Architecture overview

Four complementary data acquisition layers, escalating from structured MCP tools to adaptive web scraping:

| Tier | Source | Type | Cost | Speed | Coverage | When to use |
|------|--------|------|------|-------|----------|-------------|
| **0** | Wind (万得) | MCP structured | Paid | ★★★★★ | ★★★★★ | Default for all structured financial data |
| **1** | iFind (同花顺) | MCP structured | Paid | ★★★★★ | ★★★★☆ | Precise financials, ESG, bonds, macro |
| **2** | AkShare | MCP structured | Free | ★★★★☆ | ★★★☆☆ | Quick free data, batch queries, no API key |
| **3** | Scrapling | Web scraping | Free | ★★★☆☆ | ★★★★★ | Unstructured web data, news, regulatory filings, protected sites |

**Escalation principle**: Always start with the most structured, lowest-latency source (Wind → iFind → AkShare). Only escalate to Scrapling when:
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

## Tier 2 — AkShare (免费开源)

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

## Tier 3 — 新闻公告 (免费)

- MCP 服务：`china-news-mcp`
- 覆盖：个股新闻、市场头条

| Tool | Purpose |
|------|---------|
| `get_stock_news` | 个股新闻 |
| `get_market_headlines` | 市场头条 |

---

## Tier 4 — Scrapling (网页抓取兜底)

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
| 结构化财务数据 | Wind/iFind/AkShare MCP | — |
| 实时行情快照 | AkShare `get_quote` | Scrapling `Fetcher` 抓东方财富/新浪财经 |
| 历史 K 线 | AkShare `get_historical_data` | Scrapling `DynamicFetcher` 抓腾讯/新浪行情 |
| 公司公告原文 | iFind `ifind_search_notice` | Scrapling `StealthyFetcher` 抓巨潮资讯网 |
| 个股新闻 | AkShare `get_stock_news` | Scrapling `Fetcher` 抓东方财富股吧 |
| 行业研报 | Wind `wind_search_research` | Scrapling `DynamicFetcher` 抓慧博/投研论坛 |
| 宏观经济数据 | iFind EDB | Scrapling `Fetcher` 抓国家统计局 |
| 港股/美股行情 | iFind 全球股票 | Scrapling `DynamicFetcher` 抓 Yahoo Finance |
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

#### 1. 从东方财富获取实时行情

```python
from scrapling.fetchers import DynamicFetcher

page = DynamicFetcher.fetch(
    'https://push2.eastmoney.com/api/qt/stock/get?secid=1.600519&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f169,f170',
    disable_resources=True,  # 只抓数据接口
    network_idle=True
)
data = page.json()
```

#### 2. 从巨潮资讯网抓取公司公告原文

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

#### 3. 从新浪财经获取 K 线历史数据

```python
from scrapling.fetchers import DynamicFetcher

page = DynamicFetcher.fetch(
    'https://quotes.sina.cn/cn/api/jsonp.php/var%20CB_list=null/IB_CallerServlet?domain=cb.eastmoney.com&code=SH600519&type=history&count=100',
    disable_resources=True,
    network_idle=True
)
data = page.json()
```

#### 4. 从雪球获取个股讨论与舆情

```python
from scrapling.fetchers import DynamicFetcher

page = DynamicFetcher.fetch(
    'https://xueqiu.com/v4/statuses/public_timeline_by_category.json?since_id=-1&max_id=-1&count=20&category=1111',
    wait=2000,
    disable_resources=True
)
```

#### 5. 批量抓取多个股票的基本信息

```python
from scrapling.fetchers import FetcherSession

tickers = ['600519', '000858', '601318']

with FetcherSession(impersonate='chrome', timeout=30) as session:
    for ticker in tickers:
        page = session.get(f'https://push2.eastmoney.com/api/qt/stock/get?secid=1.{ticker}')
        info = page.json()
        print(f"{ticker}: {info.get('name')}")
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
> - `wind-fallback` (recommended): Wind 首选，回退 iFind → AkShare
> - `ifind-only` (strict): 仅 iFind，不可用时报错
> - `ifind-fallback` (default): iFind 首选，回退 AkShare
> - `akshare-only`: 仅 AkShare，跳过 Wind/iFind
> - `scrapling-only`: 仅 Scrapling 网页抓取
>
> Usage: `export IFIND_DATA_SOURCE_MODE=ifind-only`

---

## 工作流

### Step 1: 识别标的

```python
# iFind — 自然语言选股
ifind_search_stocks(query="电子行业市值大于100亿")

# AkShare — 关键词搜索
search_stock(keyword="茅台")

# Scrapling — 从网站搜索
Fetcher.get('https://so.eastmoney.com/news/s?keyword=贵州茅台')
```

### Step 2: 获取行情与财务数据

```python
# iFind — 精确财务
ifind_get_stock_financials(query="贵州茅台2024年年报的ROE、ROA、净利润增速")

# AkShare — 历史行情
get_historical_data(ticker="600519", start_date="20240101", end_date="20241231", frequency="daily")

# AkShare — 财务报表
get_financials(ticker="600519", statement_type="income", period="annual")

# Scrapling — 东方财富实时行情（MCP 不可用时）
DynamicFetcher.fetch('https://push2.eastmoney.com/api/qt/stock/get?secid=1.600519')
```

### Step 3: 行业 / 板块上下文

```python
# iFind — 板块分析
ifind_sector_data(query="白酒板块的成分股个数及过去5日平均涨跌幅")

# AkShare — 行业成分
get_industry_stocks(industry="白酒")

# Scrapling — 行业排行
Fetcher.get('https://data.eastmoney.com/bkzj/hy.html')
```

### Step 4: 宏观指标

```python
# iFind — 先搜索再取数
ifind_search_edb(query="新能源汽车产量相关指标")
ifind_get_edb_data(query="新能源汽车产量当月值（202301-202506）")

# Scrapling — 国家统计局
Fetcher.get('https://data.stats.gov.cn/easyquery.htm?cn=C01')
```

### Step 5: 新闻与舆情

```python
# iFind — 公告语义检索
ifind_search_notice(query="贵州茅台2024年年度报告 分红", time_start="2025-01-01", time_end="2025-12-31", size=5)

# AkShare — 个股新闻
get_stock_news(ticker="600519")

# Scrapling — 巨潮资讯公告原文
StealthyFetcher.fetch('http://www.cninfo.com.cn/new/fulltextSearch/full?searchkey=贵州茅台')

# Scrapling — 东方财富股吧舆情
DynamicFetcher.fetch('https://guba.eastmoney.com/list,600519.html')
```

---

## 数据覆盖说明

- **A 股**: Wind/iFind/AkShare 全覆盖（SH, SZ, BJ, STAR, ChiNext），Scrapling 可抓东方财富/新浪/腾讯行情
- **港股**: iFind 完整覆盖；AkShare 部分覆盖；Scrapling 可抓 Yahoo Finance HK
- **美股中概**: iFind 通过 `ifind_global_stock_*` 覆盖；Scrapling 可抓 Yahoo Finance
- **基金**: iFind 完整覆盖（资料/行情/持仓/持有人）；AkShare 仅 ETF 行情
- **债券**: iFind 覆盖信用债/可转债/回购；AkShare 需扩展
- **ESG**: 仅 iFind 提供
- **宏观经济**: iFind EDB 覆盖最广；AkShare 有基础宏观数据；Scrapling 可抓统计局
- **新闻/公告**: iFind 语义检索最强；Scrapling 可抓巨潮/交易所原文
- **研报**: Wind 独有（44 个工具）；Scrapling 可抓慧博/投研论坛
- **社区舆情**: Scrapling 可抓雪球/东方财富股吧
- **未覆盖数据源**: Scrapling 是最后一道防线，几乎可以抓任何公开网页

---

## 快速参考矩阵

| 场景 | 首选 | 备选 1 | 备选 2 | 兜底 |
|------|------|--------|--------|------|
| 财务报表 | Wind | iFind | AkShare | — |
| 实时行情 | iFind | AkShare | Scrapling 东方财富 | — |
| K 线历史 | AkShare | Scrapling 新浪/腾讯 | — | — |
| 股东结构 | Wind | iFind | — | — |
| ESG 评级 | iFind | — | — | — |
| 宏观数据 | iFind | AkShare | Scrapling 统计局 | — |
| 公告原文 | iFind | Wind | Scrapling 巨潮 | — |
| 个股新闻 | AkShare | iFind | Scrapling 东财 | — |
| 行业研报 | Wind | Scrapling 慧博 | — | — |
| 社区舆情 | — | — | — | Scrapling 雪球/东财 |
| 港股行情 | iFind | — | Scrapling Yahoo | — |
| 美股行情 | iFind | — | Scrapling Yahoo | — |
