# A 股专精 Agent 工具与 Skill 速查表

> **用途**:7 个专精 agent 的共享参考。各 agent body 只内化**高频口径**(本文件不重复),全口径/CLI 参数/skill 完整阈值/脚本路径按需 **Read 本文件**。
> **不强制加载**:agent body 已内化高频部分;仅当口径不确定、CLI 参数忘、脚本路径找不到时才 Read 此文件。

---

## 1. MCP 工具速查(本机实测状态)

### iFind MCP(Tier-1 主力,全链路可用)
| 工具 | query 格式 / 关键参数 | 本机坑 |
|---|---|---|
| `ifind_get_stock_financials` | `"股票+年份+ROE等"`,max 5 主体 | **MRQ(最新一期)大量返空→用年报日期 20241231/20251231**;单季用"2025年第三季度" |
| `ifind_get_stock_summary` | `"简称+查询内容"`(近1月日K/最新财报/成长/估值/公司信息) | MRQ 口径,一个调用拿全;近1月日K返每日 OHLCV+换手+涨跌 |
| `ifind_get_stock_info` | `"简称+指标+时间"`(快照:最新价/近5日涨跌/换手/成交额/主力净流入/MACD/均线) | — |
| `ifind_get_stock_shareholders` | `"简称+指标"`(十大流通股东+集中度+质押+流通占比) | — |
| `ifind_get_stock_events` | `"股票+事件指标"`(分红/回购/增持/重组) | **不返订单/业绩预告类** |
| `ifind_search_news` | 语义新闻检索,返段落 | **必带 time_start/time_end,格式 YYYY-MM-DD** |
| `ifind_search_trending_news` | 热点事件 | **未授权,改用 ifind_search_news** |
| `ifind_search_stocks` | NL 选股"半导体设备板块流通市值50-500亿..." | **医药/创新药/CXO 类返空→手动龙头** |
| `ifind_sector_data` | `"板块名称+指标+时间"`,**一次一板块** | "涨幅前N概念板块排名"做不了;多板块分调用 |
| `ifind_index_data` | `"指数名称+时间+指标"`(上证/深成/创业板/科创50 收盘+涨跌+MACD/RSI/MA) | — |
| `ifind_get_edb_data` | `"指标名称+时间范围"`(GDP/PMI/CPI/PPI/M2/M1/社融/LPR) | 一次多指标只返第一个,需分查;先用 ifind_search_edb 确认指标名 |

### wind MCP(Tier-0 补充,需 `WIND_SSL_NO_VERIFY=1`,常全挂)
- `wind_get_stock_fundamentals` / `wind_get_stock_kline` / `wind_get_stock_technicals` / `wind_get_economic_data` / `wind_get_financial_news` / `wind_get_stock_events`
- 报"无法连接服务"则跳过(本机常全挂)

### akshare MCP(Tier-2 兜底,SSL 常挂)
- `get_financials` / `get_historical_data` / `get_index_data` / `get_industry_stocks` / `get_market_overview` / `get_quote` / `get_stock_info`
- SSL `CERTIFICATE_VERIFY_FAILED` 常发;挂则走 cn_fetch.py / curl

### china-news MCP(Tier-3,SSL 易挂)
- `get_stock_news`(个股新闻,含龙虎榜/公告/业绩预告,极有用)、`get_market_headlines`(SSL 常挂)

---

## 2. CLI 脚本速查(免密钥 HTTP 通道,soft-fail 兜底主力)

### `scripts/cn_fetch.py`(repo root,CLI 子命令)
| 子命令 | 用途 | 输出 |
|---|---|---|
| `python scripts/cn_fetch.py rank [sort] [num]` | 新浪榜单(sort=changepercent/amount/turnoverratio,num 默认80) | TSV: code\tname\tprice\tpct\tamount_yi\tturnover\tmktcap\tpe\tpb(自动滤 ST/退/北交所) |
| `python scripts/cn_fetch.py factors sym1 sym2 ...` | 批量短线因子 | 每只 JSON: m5/m10/m20/ma5/ma10/ma20/above_ma20/above_ma5/breakout/amt20_yi/last/date |
| `python scripts/cn_fetch.py kline sym [n]` | 腾讯前复权日K(n 默认10) | JSON: [[date,open,close,high,low,vol],...] |
| `python scripts/cn_fetch.py quote sym1,sym2` | 腾讯批量快照(GBK) | JSON: {code:{price,pct,amount_yi,turnover,pe_ttm,mktcap_yi,float_mktcap_yi,...}}(PE/市值空填 None 非 0) |
| `python scripts/cn_fetch.py squote sym1,sym2` | 新浪批量报价(成交额单位=元,最准) | JSON: {code:{price,open,high,low,vol_hand,amount_yuan,date,time}} |

- SSL 自处理(`CN_FETCH_SSL_NO_VERIFY=1` 默认);腾讯 GBK 自动解码;UA 自带。

### `scripts/hot_trend_dig.py`(repo root)
```
python scripts/hot_trend_dig.py                 # 默认今天/最近交易日,Top15
python scripts/hot_trend_dig.py --date 20260630 # 指定日期
python scripts/hot_trend_dig.py --top 20        # 展示 Top N
```
- 内部 subprocess 封装 `sector_data.py`(涨停池/连板/市场概览自动降级新浪源)。
- akshare 龙虎榜/热榜/飙升榜经新浪源。Step1-3(龙虎榜/热榜/飙升)SSL 常挂→curl 龙虎榜 `RPT_DAILYBILLBOARD_DETAILS`;Step4-5(涨停池/市场概览)经 sector_data.py 可用。
- 输出:龙虎榜明细+热榜+飙升榜+涨停池+连板梯队+市场概览。

### findata-toolkit-cn 脚本(免费+自动降级,**路径在 skill 内非 root**)
**路径坑**:三个脚本在 `.claude/skills/findata-toolkit-cn/scripts/`,**不在 repo root `scripts/`**。
**正确调用**(从 repo root):
```bash
# 方式1:cd 到 skill 根(SKILL.md 原生命令,config 路径才对)
cd .claude/skills/findata-toolkit-cn && python scripts/macro_data.py --dashboard

# 方式2:import 模式(参考 hot_trend_dig.py:84-104)
python -c "import sys,json; sys.path.insert(0,'.claude/skills/findata-toolkit-cn'); from scripts.sector_data import fetch_zt_pool; print(json.dumps(fetch_zt_pool(),ensure_ascii=False,default=str))"
```
| 脚本 | 命令 | 用途 |
|---|---|---|
| `stock_data.py` | `600519` / `--metrics` / `--history` / `--financials` / `--insider` / `--northbound` / `--screen` | 个股基本面/行情/财务/董监高增减持/北向 |
| `sector_data.py` | `--market-overview` / `--top-change` / `--top-volume` / `--zt-pool` / `--zt-industry` / `--lt-pool` / `--dy-pool` / `--broken-pool` / `--board-concept` / `--board-industry` / `--health` | 板块排行/涨停/连板/炸板/市场概览(东方财富挂自动降级新浪) |
| `macro_data.py` | `--dashboard` / `--rates` / `--inflation` / `--pmi` / `--social-financing` / `--cycle` | LPR/Shibor/CPI/PPI/PMI/社融/M2/周期判断 |

- 依赖:`pip install -r .claude/skills/findata-toolkit-cn/requirements.txt`(akshare)。
- 北向资金 API 变更,用 `stock_hsgt_` 系列替代(2024-08 起实时披露停)。

---

## 3. Soft-Fail 数据链(5 层,连续 2 层挂→标"数据缺失")

```
iFind MCP(主) → wind MCP(WIND_SSL_NO_VERIFY=1,常挂) → akshare MCP/cn_fetch.py(SSL 自处理) → curl -k 东方财富 push2 镜像(19/29.push2)/腾讯 qt.gtimg.cn → 标注"数据缺失"+评估对漏斗影响
```
- 东方财富 push2his K线加 UA 可用(secid 沪1深0);push2 实时盘口/资金流常挂。
- 腾讯 `qt.gtimg.cn` / `web.ifzq.gtimg.cn` GBK + Windows SSL 自处理(cn_fetch.py 已封装)。
- 连续 2 层挂→该 agent 输出显式标注影响面,不编造。

---

## 4. Skill 关键口径速查(被 agent 引用的 7 个)

> 子 agent(agentType)有独立系统提示,**通常不能触发主对话 skill progressive-disclosure**——只能看到自己的 agent body + workflow prompt。故 agent body 须内化高频口径(各 agent body 已内化),此节供全口径按需查。

### undervalued-stock-screener(低估值筛选,sector/risk 用)
- PE<申万行业中位数、PB<行业中位数(配合ROE)、营收/归母净利 3-5年 CAGR 正、资产负债率<行业中位数、自由现金流正且3年累计正、ROE高于行业均值
- 自动排除:ST、上市<2年、近12月净利为负
- A股特殊:**行业相对估值法**(A股 PE 中枢高于成熟市场)、**扣非净利润**(排除政府补贴/投资收益/资产处置)

### small-cap-growth-identifier(小盘成长,sector 用)
- 市值 20-200亿、营收 3年 CAGR>20%(或2年>25%)、毛利率/营业利润率扩大或稳定、实控人持股≥15%、机构持仓<10%
- 自动排除:ST、上市<1年、近12月亏损无改善、**商誉占净资产>30%**
- 专精特新标签:工信部小巨人/细分市场份额前三/技术壁垒/客户黏性

### event-driven-detector(事件驱动,sector/catalyst 用)
- 事件类别:并购重组/资产注入/回购增持/国企改革/指数调整/管理层变更/分拆上市/解禁减持
- 每事件:价差/机会量化、完成概率、时间线、风险收益比(年化收益 vs 概率加权下行)
- 风险评估:监管审批/资金对价/股东审议/市场敏感/时间占用/下行回归/信息不对称(内幕已 price-in 风险)

### sentiment-reality-gap(情绪-基本面偏差,sector/risk 用)
- 负面信号:近6月跌≥20%或跑输行业、分析师下调、**北向(2024-08停披露,改融资余额/主力净流入)**、融资余额降、媒体负面、机构连续两季减持
- 基本面验证:营收增速正或企稳、扣非净利正、经营现金流正、资产负债率可控、行业地位稳定、护城河未削弱
- **问题性质分类(关键)**:暂时性(单季波动/政策扰动/周期底部→买入机会) vs 结构性(技术淘汰/商业模式瓦解→回避) vs 不确定(观察)
- 估值差距:当前 PE/PB vs 自身5年中位数偏离、vs 行业中位数折价、隐含增长率、安全边际

### china-catalyst-calendar(催化日历,catalyst 用)
- 财报:业绩预告(变动>50%强制披露)/季报(季末1月内)/中报(8月底)/年报(4月底)/业绩说明会(上证e互动/深交所互动易)
- 监管:MLF/LPR(15号)/降准降息(国新办)/国常会/部委政策/集采
- 公司:解禁/增减持(5%触发披露)/回购/并购/增发/可转债
- 行业:展会/研讨会/协会月度数据
- 宏观:PMI(1号)/CPI PPI(9-10号)/社融M2(10-15号)

### quant-factor-screener(多因子,**中长期口径,短线不套用**)
- 6 因子等权:价值(盈利收益率/PB倒数/FCF收益率/EV-EBITDA)/动量(**12-1月**价格动量)/质量(ROE/稳定性/低杠杆/应计)/低波动(1年波动率/Beta/下行)/规模(越小越高)/成长(营收/盈利增速/利润率扩张)
- **短线 agent 不得用其动量/低波动口径**(12-1月 vs 短线5/10/20日;低波动 vs 短线高换手有人气)
- **可用其价值因子**做 risk 估值维交叉验证(盈利收益率/PB倒数/FCF收益率)

### china-break-trace(财务排雷,fundamentals 用,body 已内化收入质量,补利润质量)
- **收入质量**:AR/Revenue>40%或快升、AR增速>>收入增速、OCF/NI<0.5或负、收入确认激进、客户集中度>30%、关联交易高
- **利润质量(补)**:营业利润 vs 净利润 gap 大、**非经常性损益>20%**、毛利率异常波动、税率异常
- **资产负债**:存贷双高、商誉/净资产高、应收/存货异常
- **现金流**:OCF 持续为负、自由现金流恶化
- **红旗信号**:审计意见非标、关联交易>30%、变更会计政策、董秘/财务总监离职

---

## 5. 数据时效与 A 股交易约束

- **时效**:短线数据(行情/资金/情绪)超 3 交易日陈旧;财报按季;宏观按月。盘中价不作买入依据,须收盘复核。
- **T+1**:当日买入次日方可卖;涨跌停板(主板±10%/创业板科创板±20%/ST±5%);100 股最小手数(1w 账户仓位受手数硬约束,股价<40元方可分散)。
- **北向资金**:2024-08 起实时披露停,资金维用主力净流入+龙虎榜+融资余额替代。
- **secid 规则**:东方财富 push2 沪市 `1.{code}`、深市 `0.{code}`、北交所 `0.{code}`(bj 开头 cn_fetch 已滤)。
