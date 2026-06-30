---
name: findata-toolkit-cn
description: A股金融数据工具包。提供脚本获取A股实时行情、财务指标、董监高增减持、北向资金、宏观经济数据（LPR、CPI/PPI、PMI、社融、M2）。数据源：东方财富 push2 API（直连JSON）+ AkShare + BaoStock。所有数据源免费，无需API密钥。
license: Apache-2.0
---

# 金融数据工具包 — A股市场

自包含的数据工具包，提供A股市场实时金融数据和定量计算。所有数据源**免费**，**无需API密钥**。

## 安装

安装依赖（一次性）：

```bash
pip3 install -r requirements.txt
```

## 可用工具

所有脚本位于 `scripts/` 目录。从技能根目录运行。

### 1. A股数据 (`scripts/stock_data.py`)

通过东方财富 push2 API（直连JSON）+ AkShare + BaoStock 获取A股数据。

| 命令 | 用途 |
|------|------|
| `python3 scripts/stock_data.py 600519` | 基本信息（贵州茅台） |
| `python3 scripts/stock_data.py 600519 --metrics` | 完整财务指标（估值、盈利、杠杆、增长） |
| `python3 scripts/stock_data.py 600519 --history` | 历史OHLCV行情（AkShare首选，BaoStock兜底） |
| `python3 scripts/stock_data.py 600519 --history --source baostock` | 强制用BaoStock获取历史K线 |
| `python3 scripts/stock_data.py 600519 --financials` | 利润表、资产负债表、现金流量表 |
| `python3 scripts/stock_data.py 600519 --insider` | 董监高增减持数据 |
| `python3 scripts/stock_data.py --northbound` | 北向资金流向（沪股通/深股通） |
| `python3 scripts/stock_data.py 600519 000858 --screen` | 批量筛选 |
| `python3 scripts/stock_data.py --clear-cache` | 清除所有缓存 |

### 2. 宏观数据 (`scripts/macro_data.py`)

通过 AkShare 获取中国宏观经济指标。

| 命令 | 用途 |
|------|------|
| `python3 scripts/macro_data.py --dashboard` | 完整宏观仪表盘 |
| `python3 scripts/macro_data.py --rates` | 利率数据（LPR、Shibor） |
| `python3 scripts/macro_data.py --inflation` | CPI/PPI数据 |
| `python3 scripts/macro_data.py --pmi` | PMI数据（制造业/非制造业） |
| `python3 scripts/macro_data.py --social-financing` | 社会融资规模 + M2 |
| `python3 scripts/macro_data.py --cycle` | 经济周期阶段判断 |

## 数据来源

| 来源 | 数据内容 | 方式 |
|------|----------|------|
| 东方财富 push2 API | 实时行情、估值、基本信息 | 直接 HTTP GET JSON，非爬虫 |
| AKShare | 财务指标、财务报表、宏观数据、北向资金 | Python 库 |
| BaoStock | 历史K线（稳定服务端数据） | Python 库，零依赖上游网页 |

## 缓存机制

所有数据获取函数自动使用 SQLite 本地缓存：
- 实时行情：交易时段 30 秒，非交易时段 5 分钟
- 历史 K 线：1 小时
- 财务数据：24 小时
- 宏观数据：7 天

缓存数据库位置：`./cache/data_cache.db`（项目目录内）
清除缓存：`python3 scripts/stock_data.py --clear-cache`

## 输出格式

所有脚本以 **JSON** 输出到标准输出，便于解析。错误信息输出到标准错误。

## 配置

可选：编辑 `config/data_sources.yaml` 自定义速率限制或添加付费数据源API密钥。
