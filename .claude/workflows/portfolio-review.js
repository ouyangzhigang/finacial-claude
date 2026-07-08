export const meta = {
  name: 'portfolio-review',
  description: 'A股组合健康检查/复盘——risk主导(相关性/集中度/因子暴露)→fundamentals+technical+catalyst并行评持仓→macro顺风逆风变化→governor体检报告+换仓。数据落盘data/不占上下文',
  phases: [
    {title: '组合体检', detail: 'risk 相关性+集中度+因子暴露'},
    {title: '持仓深评', detail: 'fundamentals+technical+catalyst 并行'},
    {title: '顺风逆风', detail: 'macro 持仓方向变化'},
    {title: '综合落盘', detail: 'governor 体检报告+换仓+final.json'},
  ],
}

const RET = {type: 'object', properties: {path: {type: 'string'}, summary: {type: 'string'}, keyFields: {type: 'object'}}, required: ['path', 'summary']}
const GOV_RET = {type: 'object', properties: {path: {type: 'string'}, dataPath: {type: 'string'}, oneLineConclusion: {type: 'string'}, topN: {type: 'array', items: {type: 'object'}}, totalPosition: {type: 'string'}, confidence: {type: 'string'}, keyRisks: {type: 'array', items: {type: 'string'}}}, required: ['path', 'oneLineConclusion', 'confidence']}

const holdings = args.holdings || [], acc = args.account || '1w', asOf = args.asOf || 'YYYYMMDD'
const G = 'portfolio-review', RD = 'data/runs/' + asOf + '_' + G
const holdingsStr = holdings.map(h => h.code + (h.name ? '(' + h.name + ')' : '') + ' ' + (h.shares || '?') + '股@' + (h.cost || '?')).join(', ')
const goal = '组合体检: 持仓[' + holdingsStr + '] 账户' + acc + ' | 基准日' + asOf

const P = (agent, task, extra, ctx) => task + '\n\n## 投资目标\n' + goal + '\n\n## 前序环节产出(承接,勿无视;如需细节用 Read 读对应 json 的 data 字段)\n' + (ctx || '(本环节为起点,无前序)') + '\n\n## 你的任务\n' + extra + '\n\n## 数据落盘(节约上下文,必须)\n把完整结构化输出 WRITE 到 ' + RD + '/' + agent + '.json(目录不存在先创建),envelope:{"runId":"' + asOf + '_' + G + '","asOf":"' + asOf + '","goal":"' + G + '","agent":"' + agent + '","fetchedAt":"' + asOf + '","data":{完整输出},"summary":"一句话","keyFields":{小摘录如 codes/actions}}\nschema 只返回 {path, summary, keyFields},勿把完整 data 塞进返回值。'

if (!holdings.length) {
  phase('综合落盘')
  const report = await agent('持仓清单为空,无法体检。\n## 投资目标\n' + goal + '\n## 你的任务\n提示用户"组合体检需提供持仓清单(代码/股数/成本),如:600519 100股@1700 000858 200股@145"。\n1. WRITE ' + RD + '/final.json(envelope,data含verdict:"持仓为空",reason)。\n2. 更新 data/index.json(数组push {runId,asOf,goal,path:dataPath,headline:"持仓为空,无法体检",confidence:"低",fetchedAt})。\nschema 返回 {path:"", dataPath:"' + RD + '/final.json", oneLineConclusion:"持仓为空,无法体检", confidence:"低", keyRisks:["无持仓输入"]}。', {agentType: 'governor', schema: GOV_RET, label: 'governor', phase: '综合落盘'})
  return report
}

let ctx = ''

phase('组合体检')
const risk = await agent(P('risk-portfolio', '对持仓做组合层体检:相关性+集中度+因子暴露+隐性偏移。', '用 ifind_get_stock_summary日K算持仓间相关性(近20日收益相关)+行业集中度+风格暴露(价值/成长/红利/题材)+催化同源(同一政策/事件源合计仓位)。识别"同涨同跌"对与隐性偏移。对每只持仓给初步信号衰减判断(基于近5日动量)。', ctx), {agentType: 'risk-portfolio', schema: RET, label: 'risk', phase: '组合体检'})
ctx = '【组合体检】' + risk.summary + ' → ' + risk.path

phase('持仓深评')
const [fund, tech, cat] = await parallel([
  () => agent(P('fundamentals-analyst', '对持仓批量做基本面变化复查。', '用 Read 读 ' + risk.path + ' 的 data.holdingsAssessment 取持仓清单;用 ifind_get_stock_financials+ifind_get_stock_shareholders 检查持仓最新财报 vs 建仓时变化(业绩拐点/新红旗/股东变化)。返每只verdict+earningsChange。', ctx), {agentType: 'fundamentals-analyst', schema: RET, label: 'fundamentals', phase: '持仓深评'}),
  () => agent(P('technical-liquidity', '对持仓批量做技术信号衰减检查。', '用 Read 读 ' + risk.path + ' 的 data.holdingsAssessment 取持仓清单;用 ifind_get_stock_summary日K 检查每只:近5日动量转负?跌破5日线/MA20?量能萎缩?返每只signalDecay+action(持有/减仓/换仓)。', ctx), {agentType: 'technical-liquidity', schema: RET, label: 'technical', phase: '持仓深评'}),
  () => agent(P('catalyst-scanner', '对持仓批量做催化兑现/落空检查。', '用 Read 读 ' + risk.path + ' 的 data.holdingsAssessment 取持仓清单;用 ifind_search_news+china-news get_stock_news+ifind_get_stock_events 检查每只:原催化已兑现/落空?新催化临近?返每只catalystFulfilled+upcoming+action。', ctx), {agentType: 'catalyst-scanner', schema: RET, label: 'catalyst', phase: '持仓深评'}),
])
ctx += '\n【基本面变化】' + fund.summary + ' → ' + fund.path
ctx += '\n【技术信号】' + tech.summary + ' → ' + tech.path
ctx += '\n【催化兑现】' + cat.summary + ' → ' + cat.path

phase('顺风逆风')
const macro = await agent(P('macro-strategist', '检查持仓方向相对宏观的顺风/逆风变化。', '用 Read 读前序各 json 取持仓所属方向;用 ifind_index_data+ifind_search_news+ifind_sector_data 判断持仓所属方向的宏观顺风/逆风变化(相比建仓时),输出顺风/逆风+风格切换。', ctx), {agentType: 'macro-strategist', schema: RET, label: 'macro', phase: '顺风逆风'})
ctx += '\n【顺风逆风】' + macro.summary + ' → ' + macro.path

phase('综合落盘')
const report = await agent('综合全链写组合体检报告+换仓建议。\n\n## 投资目标\n' + goal + '\n\n## 全链产出(承接,勿无视;用 Read 读各 json 的 data 取细节)\n' + ctx + '\n\n## 你的任务\n1. WRITE 报告到 output/' + asOf + '_组合体检报告.md(目录不存在先创建),按 governor 报告结构与命名规范(结论先行→总体策略→各专项核心细节+逻辑关系→专业知识点→操作→风险情景→免责)写,换仓建议具体到哪只减/换/加(引用各agent的action)。报告头一句话结论附组合健康度+置信度。\n2. WRITE 结构化最终到 ' + RD + '/final.json(envelope,data含oneLineConclusion/rebalanceActions/topN/totalPosition/confidence/keyRisks/modules各环节path)。\n3. 更新 data/index.json(数组push {runId,asOf,goal,path:dataPath,headline,confidence,fetchedAt})。\nschema 返回 {path, dataPath, oneLineConclusion, topN(换仓建议), totalPosition, confidence, keyRisks}。', {agentType: 'governor', schema: GOV_RET, label: 'governor', phase: '综合落盘'})
return report
