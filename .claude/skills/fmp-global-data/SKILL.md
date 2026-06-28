---
name: fmp-global-data
description: >
  Fetch global financial market data from Financial Modeling Prep (FMP) API for investment analysis,
  market research, and data-driven decisions. Use this skill whenever the user asks to get stock quotes,
  financial statements (income/balance sheet/cashflow), key metrics, screeners, market movers,
  earnings calendars, analyst ratings, ESG data, crypto/forex/commodities quotes, economic indicators,
  IPO calendars, insider trading, or any global financial market data. Also trigger when the user
  mentions ticker symbols, stock analysis, market research, company fundamentals, valuation data,
  or financial data retrieval — even if they don't explicitly name FMP. This is your go-to skill for
  pulling real-time and historical financial data globally. If the user needs data for investing,
  trading, or financial analysis, use this skill.
---

## Overview

Fetch financial data from [Financial Modeling Prep (FMP)](https://site.financialmodelingprep.com/developer/docs) — a comprehensive API covering global stocks, ETFs, mutual funds, crypto, forex, commodities, indices, economics, and more.

## Authentication

All requests require the API key. Use it as a URL query parameter `&apikey=`.

```
API_KEY=kqrWZXH2XmAKrgYnrhYq8JKxu87TyQez
BASE_URL=https://financialmodelingprep.com/stable
```

## Quick Reference

### How to Call

Every endpoint follows this pattern:
```
https://financialmodelingprep.com/stable/<endpoint>?<params>&apikey=<API_KEY>
```

Use Python's `urllib.request` or `requests` library to make HTTP calls. Always set a `User-Agent` header. Parse JSON responses.

### Rate Limiting

Free tier: ~250 requests/day. Space out calls. If you get HTTP 403 or 429, wait a moment before retrying.

## API Categories

### 1. Search & Discovery

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `search-symbol` | Search by ticker symbol | `query` |
| `search-name` | Search by company name | `query` |
| `search-cik` | Search by CIK number | `cik` |
| `search-cusip` | Search by CUSIP | `cusip` |
| `search-isin` | Search by ISIN | `isin` |
| `search-exchange-variants` | Find all exchanges for a symbol | `symbol` |

### 2. Company Information

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `profile` | Full company profile | `symbol` |
| `profile-cik` | Profile by CIK | `cik` |
| `company-notes` | Analyst company notes | `symbol` |
| `employee-count` | Employee count history | `symbol` |
| `shares-float` | Float & liquidity data | `symbol` |
| `delisted-companies` | List of delisted companies | — |

### 3. Real-Time Quotes

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `quote` | Single stock quote | `symbol` |
| `quote-short` | Minimal quote | `symbol` |
| `batch-quote` | Multiple quotes at once | `symbols` (comma-separated) |

Quote response fields: `symbol`, `name`, `price`, `change`, `changePercentage`, `volume`, `dayLow`, `dayHigh`, `yearHigh`, `yearLow`, `marketCap`, `priceAvg50`, `priceAvg200`, `exchange`, `open`, `previousClose`, `timestamp`

### 4. Financial Statements

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `income-statement` | Income statement | `symbol`, `limit` |
| `balance-sheet-statement` | Balance sheet | `symbol`, `limit` |
| `cashflow-statement` | Cash flow statement | `symbol`, `limit` |

Each statement includes: `date`, `symbol`, `fiscalYear`, `period` (FY/QQ), `reportedCurrency`, `filingDate`, plus all line items (revenue, netIncome, operatingCashFlow, etc.)

### 5. Key Metrics & Scores

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `key-metrics` | Financial ratios & metrics | `symbol`, `limit` |
| `financial-scores` | Altman Z-Score, Piotroski | `symbol` |
| `owner-earnings` | Buffett owner earnings | `symbol` |
| `enterprise-values` | EV calculation breakdown | `symbol` |

Key metrics include: `marketCap`, `enterpriseValue`, `evToSales`, `evToEBITDA`, `netDebtToEBITDA`, `currentRatio`, `returnOnEquity`, `returnOnAssets`, `grahamNumber`, `freeCashFlowYield`, `earningsYield`, etc.

### 6. Stock Screener

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `company-screener` | Filter stocks by criteria | see filters below |

**Screener Filters** (combine freely):
- `marketCapMoreThan`, `marketCapLessThan` (in dollars)
- `priceMoreThan`, `priceLessThan`
- `volumeMoreThan`, `betaLower`, `betaUpper`
- `sector` (e.g., "Technology", "Healthcare", "Financial Services")
- `country` (e.g., "US", "CN", "JP")
- `exchangeShortName` (e.g., "NYSE", "NASDAQ")
- `isEtf`, `isFund`, `dividendMoreThan`
- `limit` (default 50)

### 7. Market Movers

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `biggest-gainers` | Top gainers today | `limit` |
| `biggest-losers` | Top losers today | `limit` |

### 8. Calendars & Events

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `earnings-calendar` | Upcoming/past earnings | `from`, `to` (YYYY-MM-DD) |
| `dividends-calendar` | Dividend events | `from`, `to` |
| `ipos-calendar` | IPO events | `from`, `to` |

Earnings fields: `symbol`, `date`, `epsActual`, `epsEstimated`, `revenueActual`, `revenueEstimated`

### 9. Analyst Data

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `ratings-snapshot` | Current analyst ratings | `symbol` |
| `grades` | Historical rating changes | `symbol`, `limit` |
| `price-target-summary` | Price target consensus | `symbol` |

Grades fields: `symbol`, `date`, `gradingCompany`, `previousGrade`, `newGrade`, `action`

### 10. Economic & Risk Data

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `treasury-rates` | US Treasury yield curve | — |
| `market-risk-premium` | Country risk premiums | — |
| `economics-indicators` | Economic data | varies |

### 11. Alternative Data

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `esg-ratings` | ESG scores | `symbol` |
| `senate-latest` | US Senate trading | — |

Senate fields: `symbol`, `firstName`, `lastName`, `office`, `assetDescription`, `assetType`, `type`, `amount`

### 12. Asset Lists

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `stock-list` | All listed stocks | `limit` |
| `financial-statement-symbol-list` | Stocks with financials | `limit` |
| `cik-list` | SEC CIK numbers | `page`, `limit` |
| `available-exchanges` | Global exchanges | — |
| `available-sectors` | Sector list | — |
| `available-countries` | Country list | — |
| `cryptocurrency-list` | All cryptos | `limit` |
| `forex-list` | Currency pairs | `limit` |
| `commodities-list` | Commodities | `limit` |

### 13. Financial Report Dates

| Endpoint | Purpose | Key Params |
|----------|---------|------------|
| `financial-reports-dates` | 10-K/10-Q filing links | `symbol` |

Returns `linkJson` and `linkXlsx` for each filing period.

## Common Workflow Patterns

### Pattern 1: Quick Stock Check
Get quote + profile + key metrics for a company:
```python
quote = api('quote', {'symbol': 'AAPL'})
profile = api('profile', {'symbol': 'AAPL'})
metrics = api('key-metrics', {'symbol': 'AAPL', 'limit': 4})
```

### Pattern 2: Fundamental Analysis
Pull all three statements + key metrics + scores:
```python
income = api('income-statement', {'symbol': 'AAPL', 'limit': 4})
balance = api('balance-sheet-statement', {'symbol': 'AAPL', 'limit': 4})
cashflow = api('cashflow-statement', {'symbol': 'AAPL', 'limit': 4})
metrics = api('key-metrics', {'symbol': 'AAPL', 'limit': 4})
scores = api('financial-scores', {'symbol': 'AAPL'})
```

### Pattern 3: Market Screening
Find undervalued tech stocks:
```python
stocks = api('company-screener', {
    'sector': 'Technology',
    'marketCapMoreThan': '1000000000',
    'betaLower': '0',
    'betaUpper': '2',
    'limit': '50'
})
```

### Pattern 4: Batch Quotes
Get quotes for multiple tickers at once:
```python
quotes = api('batch-quote', {'symbols': 'AAPL,MSFT,GOOGL,AMZN,TSLA'})
```

### Pattern 5: Earnings Season Watch
Check upcoming earnings:
```python
earnings = api('earnings-calendar', {
    'from': '2026-06-26',
    'to': '2026-07-03'
})
```

## Response Handling

All endpoints return JSON arrays or objects. Common patterns:
- Most endpoints return `[{...}, {...}]` — iterate with `for item in data:`
- Check `len(data)` to verify results exist before accessing
- Numeric values may be `null` — handle with `item.get('field') or 0`
- Dates are strings in `YYYY-MM-DD` format
- Financial values are in USD (unless `reportedCurrency` differs)
- Large numbers (market cap, revenue) are in raw units (not millions)

## Helper Script

Use the bundled `fmp_fetch.py` script for consistent API calls. See `scripts/fmp_fetch.py`.

## Notes

- The FMP API uses `/stable/` endpoints (not `/api/v3/` which is deprecated)
- Free tier provides ~47 working endpoints; some features require paid plans
- Some endpoints may return empty arrays (e.g., `search-symbol` with no match)
- For historical price data, you may need a paid plan — the free tier focuses on current/periodic data
- Combine with existing skills: `china-market-data` (A-share), `comps-analysis`, `dcf`, `earnings-analysis`, etc.
- When analyzing global stocks, cross-reference with `company-screener` filters for sector/country/industry grouping
