---
description: 多agent投资研究编排入口——解析投资目标关键词,调用对应workflow(单股深评/短周期选股/热门板块/组合体检/舆情趋势预判),由governor+6专精agent协作输出报告
argument-hint: "[目标关键词+参数,如:短周期 2周 账户1w | 600519 深评 | 热门板块 | 体检 600519 100股@1700 | 舆情 AI算力]"
---

## 多 Agent 投资研究架构(.claude/agents + .claude/workflows)

本命令是多 agent 编排入口:解析 `$ARGUMENTS` 首关键词 → 映射到 `.claude/workflows/<goal>.js` → 用 Workflow 工具执行(内部 governor + 6 专精 agent 协作,上下文接力)→ 返回报告路径+结论。

## 第一步:解析 `$ARGUMENTS` 映射目标

**原始入参**:`$ARGUMENTS`

按下表匹配首关键词(允许多关键词命中,取最先匹配项):

| 目标关键词 | workflow 名 | 必填参数 | 可选参数 |
|---|---|---|---|
| 深评/深度/单股/<6位代码> | `single-stock-deep` | ticker(6位代码), name | account, horizon, riskPref, position |
| 短周期/选股/2周/推荐 | `short-term-picks` | — | topN, period, account, riskPref, position |
| 超短/1日/隔日/次日/打板/涨停/尾盘 | `ultra-short-picks` | — | topN, account, riskPref |
| 热门/板块/热点/潜力 | `hot-trends` | — | constraint, topN, account |
| 体检/复盘/持仓 | `portfolio-review` | holdings:[{code,shares,cost}] | account |
| 舆情/趋势/预判 | `sentiment-trend-picks` | keyword 或 trend | topN, account |
| **未来/预判/短线/波段/中线/预测** | `future-picks` | — | topN, account, horizon(短线/波段/中线), riskPref, position |

> ⭐ **future-picks 是全新预判型工作流**(2026-07-31 新建):不是当日排行榜,是"今天分析→预测未来N天将涨"的票,推理链驱动(因为A→B→C→D→预判E将涨),含未来催化日历+板块轮动接力+操作卡+跟踪兑现。**用户要"涨幅最高/最具潜力/未来"时优先用这个**,而非旧的 short-term-picks(当日选股)。

> ⚠️ **周期下限硬约束**:短周期目标解析出投资周期 < 5 个交易日(2日/3日/隔日)时,workflow 内会拒绝选股,降级日内跟踪简报(只给观察位,不给买入区间/仓位)。
> ⚠️ **缺失必填参数**(如单股的 ticker、体检的 holdings)→ 先向用户追问,不臆测。

## 第二步:构建 args 对象

按目标 workflow 的 args schema 构建,务必包含:
- `asOf`: 今天日期 YYYYMMDD 格式(用于报告命名,**从当前会话上下文取今天日期,不要硬编码**)
- 各目标必填/可选参数(从 `$ARGUMENTS` 解析,缺失用默认)

**参数解析示例**:
- `短周期 2周 账户1w` → `{asOf:"<今天>", topN:5, period:"2周", account:"1w", riskPref:"稳健偏积极", position:"无持仓"}`
- `600519 深评 账户1w 波段 稳健` → `{asOf:"<今天>", ticker:"600519", name:"贵州茅台", account:"1w", horizon:"波段", riskPref:"稳健", position:"无持仓"}`
- `体检 600519 100股@1700 000858 200股@145` → `{asOf:"<今天>", holdings:[{code:"600519",shares:100,cost:1700},{code:"000858",shares:200,cost:145}], account:"1w"}`
- `舆情 AI算力` → `{asOf:"<今天>", keyword:"AI算力", topN:5, account:"1w"}`
- `热门板块 Top8` → `{asOf:"<今天>", constraint:"热门板块潜力股综合推荐", topN:8, account:"1w"}`
- `超短 1日 打板 账户1w` → `{asOf:"<今天>", topN:3, account:"1w", riskPref:"积极"}`
- `未来 波段 账户1w` → `{asOf:"<今天>", topN:5, account:"1w", horizon:"波段", riskPref:"稳健偏积极", position:"无持仓"}`
- `短线 预判 Top3` → `{asOf:"<今天>", topN:3, account:"1w", horizon:"短线", riskPref:"积极", position:"无持仓"}`
- `中线 预测 账户1w` → `{asOf:"<今天>", topN:5, account:"1w", horizon:"中线", riskPref:"稳健", position:"无持仓"}`

> ⭐ **future-picks 调用优先用 `scriptPath` 指向源脚本**(避免 name 模式缓存):`Workflow({scriptPath:"E:/finacial-invest/.claude/workflows/future-picks.js", args:{...}})`。args 会被序列化成字符串,脚本顶部已加 `if(typeof args==='string') args=JSON.parse(args)` 兼容层。

> ⚠️ **超短周期特殊约束**: 超短选股仅适用于交易时段(09:30-15:00)。尾盘(14:30-15:00)买入封板票, 次日开盘冲高出。市场温度<30°时拒绝选股。不看基本面, 核心看封板质量+资金流+舆情+龙虎榜。

## 第三步:调用 Workflow 执行

调用 `Workflow({name: "<映射出的workflow名>", args: <第二步构建的args对象>})`。

- workflow 在后台运行(governor + 6 专精 agent 按流程协作,每步 agent 的 prompt 内嵌前序产出做上下文接力),完成后返回 `{path, oneLineConclusion, topN, totalPosition, confidence, keyRisks}`。
- 若 workflow 失败或数据源大面积挂(iFind/wind/akshare 全挂),向用户如实报告数据缺口,不编造。
- **不要在对话中重复输出完整报告**——报告已由 governor 写入 `output/`,对话只回显结论。

## 第四步:对话回报

收到 workflow 返回后,在对话中回显:
- 报告相对路径(`output/...`)
- 一句话结论(含核心假设置信度)
- Top N 代码清单(代码/名称/角色/仓位)
- 总仓位
- 关键风险(1-3 条)

---

## 架构速查(供调试理解)

- **专精层 7 agent**(`.claude/agents/`):governor(综合落盘+对抗审查+MCP抽查)、macro-strategist(天时)、sector-analyst(撒网)、fundamentals-analyst(排雷+估值)、technical-liquidity(过关+动量)、catalyst-scanner(催化+情绪)、risk-portfolio(组合+回测)
- **编排层 5 workflow**(`.claude/workflows/`):single-stock-deep / short-term-picks / hot-trends / portfolio-review / sentiment-trend-picks
- **Phase 0 预取**:每个 workflow 启动时运行 `prefetch_shared.py`(指数/榜单/板块/市场雷达核心信号)+ `portfolio_tracker.py`(活跃推荐行情更新),合并单次 Bash 调用,结果写入 `_shared.json` 注入全部 agent 的 sharedCtx
- **数据源 soft-fail**:iFind 主→wind(WIND_SSL_NO_VERIFY)→akshare/cn_fetch.py→web-scraping fetch.py(Scrapling,JS渲染/反爬)→curl -k→标缺失
- **市场雷达**:`scripts/market_radar.py`(7通道:新浪7x24+腾讯指数+东方财富板块/涨停/龙虎榜/资金流),核心信号自动提取(🔴critical/🟡important/🟢normal)
- **对抗审查已合并入 governor**:governor 先做矛盾检测+MCP抽查验证(≤3次),再裁决+写报告,不再单独 review agent
- **组合追踪**:`scripts/portfolio_tracker.py`(record/update/summary),workflow 结束时自动 record 推荐,启动时 update 行情
- **上下文接力**:workflow 维护 ctx 字符串,每步 agent prompt 内嵌「前序环节产出」块,schema 强结构输出
- **回测纪律**:回测3项全不达标标的不得入TopN(驰宏锌锗教训),Top1须回测相对最优且非高位回调者
- **盘中纪律**:数据若为盘中,操作卡价位为触发观察位,须收盘复核方为有效买入区间

---

现在开始:先解析 `$ARGUMENTS` 映射目标+构建 args(含 asOf=今天),缺失必填参数则向用户追问;再调用 Workflow 执行;最后回显报告路径+结论+TopN+仓位+风险。
