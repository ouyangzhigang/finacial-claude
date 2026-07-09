# data/ — 多 Agent 投资研究数据落盘目录

多 agent workflow 执行时,各专精 agent 把**全量结构化产出**写入此目录,**不塞进对话上下文**;governor 综合时读盘取细节。下次研究/其它 agent 可复用历史数据,无需重跑取数。

## 目录结构

```
data/
  index.json                          # 全局运行索引(数组,所有 run 的目录)
  runs/
    {asOf}_{goal}/                    # 一次运行,如 20260703_short-term-picks/
      macro-strategist.json           # 各专精 agent 全量产出(envelope)
      sector-analyst.json
      technical-liquidity.json
      catalyst-scanner.json
      fundamentals-analyst.json
      risk-portfolio.json
      final.json                      # governor 结构化最终结论
  # 人类可读报告仍在 output/{name}.md(不在此目录)
```

`{asOf}` = 基准日 YYYYMMDD;`{goal}` = workflow 名(single-stock-deep / short-term-picks / hot-trends / portfolio-review / sentiment-trend-picks)。

## envelope 格式(所有 json 统一)

```json
{
  "runId": "20260703_short-term-picks",
  "asOf": "20260703",
  "goal": "short-term-picks",
  "agent": "macro-strategist",
  "fetchedAt": "20260703",
  "data": { },
  "summary": "一句话摘要",
  "keyFields": { }
}
```

- `data`:该 agent 的**完整结构化输出**(领域全量数据,如候选池/评分表/回测/财务画像)
- `summary`:一句话(进 workflow ctx,承接用)
- `keyFields`:小摘录(如 codes/verdicts/tailwinds,进 ctx 供下游快速判断)

下游 agent 需要细节时,用 `Read` 读对应 json 的 `data` 字段,不全量进 prompt。

## index.json 格式

```json
[
  {
    "runId": "20260703_short-term-picks",
    "asOf": "20260703",
    "goal": "short-term-picks",
    "path": "data/runs/20260703_short-term-picks/final.json",
    "headline": "Top1 康龙化成 回测全达标 总仓位55.5%",
    "confidence": "中",
    "fetchedAt": "20260703"
  }
]
```

governor 每次运行结束追加(append)一条。可按 `goal` / `asOf` 检索历史运行。

## 复用方式

- **下次同目标研究**:Read `data/runs/{prev}_{goal}/final.json` 对比上次结论演化
- **跨 agent 复用**:如单股深评已取 600519 的 technical-liquidity.json,短周期选股若含 600519 可读该 json 复用(注意 `fetchedAt` 时效)
- **复盘**:Read `data/index.json` 看历史 run 清单,挑相关 run 读 final.json

## 时效与清理

- `fetchedAt` 标注取数日;短线数据(行情/资金)超 3 交易日视陈旧,需重取
- 财报/估值分位按季陈旧;宏观按月
- 目录可定期归档/清理旧 run(本目录不进 git,见 .gitignore)

## 不进 git

`data/` 含运行产物与可能的原始行情,体积大且时效敏感,加入 `.gitignore`(与 `output/` 同处理)。
