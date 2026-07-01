---
description: A股潜力股综合推荐 — 层层递进 × 五维咬合 × 融会贯通(执行 recommend_module_stocks.md)
argument-hint: "[可选:覆盖默认约束,如:资金2万 单股<60 风格中线]"
---

读取并严格执行 `../../recommend_module_stocks.md` 中的完整分析 prompt。将该文件内容视为本次要执行的指令框架,按其中"层层递进 × 五维咬合 × 融会贯通"方法论,调用项目已接入的 MCP 数据层(wind / ifind / akshare / china-news)与分析 skill,**实时获取当前A股行情数据**,从 L1 大盘定调开始,逐层深入、交叉印证,完成一次完整的潜力股综合推荐分析,并严格按该文件 §4 输出格式交付。

## 本地取数工具(scripts/,免密钥 HTTP,本机已验证 — MCP 兜底 + 交叉验证)

iFind/wind 仍为主力数据源;下列本地脚本在 MCP 字段缺失、SSL 失败或需交叉验证时启用——**不替代 MCP,而是补位与核对**。代码前缀:沪 `sh`、深 `sz`(如 `sh600519`、`sz300458`)。

| 用途 | 调用 | 用在哪(补位/交叉) |
|---|---|---|
| 全 A 排行 | `python scripts/cn_fetch.py rank changepercent 80` | L3 排行;与 ifind 板块成分股互核(sort=changepercent/amount/turnoverratio;自动过滤 ST/退市/北交所) |
| 个股短线因子 | `python scripts/cn_fetch.py factors sh600519 sz300458` | L3 技术面;ifind summary 缺字段时补位 |
| 个股当日快照 | `python scripts/cn_fetch.py quote sh600519,sz300458` | L3 估值+流动性;与 ifind 行情交叉验证 |
| 成交额精确快照 | `python scripts/cn_fetch.py squote sh600519,sz300458` | L3 流动性核验(新浪成交额=元最准,流动性以它为准) |
| 日 K 线(前复权) | `python scripts/cn_fetch.py kline sh600519 30` | L3 多周期;ifind K 线缺失时补位 |
| 龙虎榜价值挖掘 | `python scripts/hot_trend_dig.py` | L3 资金面;iFind 无专用龙虎榜工具,评估后以本地脚本为主、wind 龙虎榜为辅 |

> 取数原则:iFind/wind 先行 → 字段缺失或 SSL 失败时本地脚本补位 → 关键价位/成交额多源交叉,哪个准用哪个;板块行情与北向资金仍走 ifind/akshare MCP,新闻/情绪走 `ifind_search_news` / china-news MCP;某维度最终仍缺失标注"数据缺失",不编造。

执行硬性要求(摘自该文件,此处仅作强调,以该文件正文为准):
- **递进不跳层**:L1(大盘+政策)→ L2(板块+事件)→ L3(资金+基本面+技术+排行)→ 合成,上层未明确不下层;
- **咬合才下注**:每条信号必须在 §2.4 交叉校验表找到印证维度,单维信号只观察、不下注;
- **融会贯通**:最终推荐须四要素闭环(天时/地利/人和/节度),推荐语为一句完整闭环;
- **遵守 §1 投资约束**:约 1 万元、单股 <40 元、红线一票否决、单只 ≤40% 仓位、−8%~−10% 硬止损;
- **数据 soft-fail**:某 MCP 工具返回 error 时,按 §3 降级方案(换源或 curl 东方财富 push2 镜像/腾讯接口)继续,不中断整体分析。

附加指令(若提供,则覆盖 recommend_module_stocks.md §1 的默认约束;否则按默认约束执行):
$ARGUMENTS
