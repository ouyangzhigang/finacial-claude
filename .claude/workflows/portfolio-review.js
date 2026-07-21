export const meta = {
  name: 'portfolio-review',
  description: 'A股组合体检——risk主导(相关性/集中度)→fund∥tech∥cat并行评持仓→macro→governor(审查+裁决+体检报告+换仓)',
  phases: [
    {title: '组合体检', detail: 'risk 相关性+集中度+因子暴露(含 prefetch)'},
    {title: '持仓深评', detail: 'fundamentals∥technical∥catalyst 并行'},
    {title: '顺风逆风', detail: 'macro 持仓方向变化'},
    {title: '综合落盘', detail: 'governor 审查+裁决+报告+notify'},
  ],
}

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const holdings=args.holdings||[], acc=args.account||'1w', asOf=args.asOf||'YYYYMMDD'
const G='portfolio-review', RD='data/runs/'+asOf+'_'+G
const holdingsStr=holdings.map(h=>h.code+(h.name?'('+h.name+')':'')+' '+(h.shares||'?')+'股@'+(h.cost||'?')).join(', ')
const goal='组合体检: 持仓['+holdingsStr+'] 账户'+acc+' | 基准日'+asOf
const history = args.history || ''
const SHARED = 'data/runs/'+asOf+'_'+G+'/_shared.json'

// ── 预取指令(仅 risk agent 执行) ──
const PREFETCH = '⚠️ 前置步骤(必须在分析之前完成):\n1. 运行 Bash: python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' 2>&1\n2. 运行 Bash: python scripts/portfolio_tracker.py update 2>&1\n3. 运行 Bash: python scripts/portfolio_tracker.py summary 2>&1\n4. Read '+SHARED+' 获取共享数据(核心信号🔴🟡🟢)\n完成后再进入下方分析任务。\n\n'

const S = async (name, fn) => {
  try { const r = await fn(); if (r) return r } catch (e) {
    const msg = (e?.message||String(e)).slice(0,200)
    return {path:'',summary:name+' 失败(降级): '+msg,keyFields:{_error:true}}
  }
  return {path:'',summary:name+' 返回空',keyFields:{_error:'empty'}}
}
// 压缩版P/O模板: 数据落盘格式提取为O(), 减少~60%模板字符
const O = (ag) => `\nWRITE ${RD}/${ag}.json; envelope:{"agent":"${ag}","asOf":"${asOf}","data":{...}}; schema→{path,summary,keyFields}`
const P = (ag, task, extra, ctx) => `${task}\n# 目标\n${goal}\n# 前序\n${ctx||'(起点)'}\n# 任务\n${extra}${O(ag)}`
const ap = (r, l) => r ? '\n【'+l+'】'+r.summary+(r.path?' → '+r.path:'') : '\n【'+l+'】⚠️ 数据缺失'

// ── 空持仓早退 ──
if (!holdings.length) {
  phase('综合落盘')
  const report = await S('governor', () => agent('持仓清单为空,无法体检。\n## 投资目标\n'+goal+'\n## 你的任务\n提示用户"组合体检需提供持仓清单(代码/股数/成本)"。\n1. WRITE '+RD+'/final.json(envelope,data含verdict:"持仓为空",reason)。\n2. 更新 data/index.json(Read→push→Write)。\nschema 返回 {path:"",dataPath:"'+RD+'/final.json",oneLineConclusion:"持仓为空,无法体检",confidence:"低",keyRisks:["无持仓输入"]}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
  return report
}

let ctx = ''

// ── Phase 1: 组合体检(含 prefetch) ──
phase('组合体检')
log('🔄 启动组合体检 — agent: risk-portfolio')
const risk = await S('risk', () => agent(PREFETCH+P('risk-portfolio','对持仓做组合层体检:相关性+集中度+因子暴露+隐性偏移。','持仓清单: '+holdingsStr+'。⚠️ 不要用 MCP。用 cn_fetch.py kline 取近20日K线算持仓间相关性+行业集中度+风格暴露。识别"同涨同跌"对与隐性偏移。对每只给初步信号衰减判断。', ctx), {agentType:'risk-portfolio',schema:RET,label:'risk',phase:'组合体检'}))
ctx = ap(risk,'组合体检')
log('✅ 组合体检完成 — ' + (risk?.summary || '空'))

// ── Phase 2: 持仓深评(3 并行,都读 risk 的持仓评估) ──
phase('持仓深评')
log('🔄 启动持仓深评 — fundamentals∥technical∥catalyst')
const [fund, tech, cat] = await parallel([
  () => S('fund', () => agent(P('fundamentals-analyst','对持仓批量做基本面变化复查。','用 Read 读 '+risk.path+' 的 data.holdingsAssessment 获取持仓清单;检查持仓最新财报 vs 建仓时变化(业绩拐点/新红旗/股东变化)。返每只 verdict+earningsChange。', ctx), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'持仓深评'})),
  () => S('tech', () => agent(P('technical-liquidity','对持仓批量做技术信号衰减检查。','用 Read 读 '+risk.path+' 的 data.holdingsAssessment 获取持仓清单;检查每只:近5日动量转负?跌破MA5/MA20?量能萎缩?返每只 signalDecay+action(持有/减仓/换仓)。', ctx), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'持仓深评'})),
  () => S('cat', () => agent(P('catalyst-scanner','对持仓批量做催化兑现/落空检查。','用 Read 读 '+risk.path+' 的 data.holdingsAssessment 获取持仓清单。⚠️ 不要用 MCP。用 python scripts/cn_fetch.py --keyword <股票名> 取新浪/腾讯资讯 + astock_data.py 取资金流。检查每只:原催化已兑现/落空?新催化临近?返每只 catalystFulfilled+upcoming+action。', ctx), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'持仓深评'})),
])
ctx += ap(fund,'基本面') + ap(tech,'技术') + ap(cat,'催化')
log('✅ 持仓深评完成')
log('  基本面: ' + (fund?.summary || '空'))
log('  技术: ' + (tech?.summary || '空'))
log('  催化: ' + (cat?.summary || '空'))

// ── Phase 3: 顺风逆风(读全链) ──
phase('顺风逆风')
log('🔄 启动顺风逆风分析 — agent: macro-strategist')
const macro = await S('macro', () => agent(P('macro-strategist','检查持仓方向相对宏观的顺风/逆风变化。','Read 全链 json(组合体检+基本面+技术+催化);判断持仓所属方向的宏观顺风/逆风变化(相比建仓时),输出顺风/逆风+风格切换。', ctx), {agentType:'macro-strategist',schema:RET,label:'macro',phase:'顺风逆风'}))
ctx += ap(macro,'顺风逆风')
log('✅ 顺风逆风完成 — ' + (macro?.summary || '空'))

// ── Phase 4: 综合落盘 ──
phase('综合落盘')
log('🔄 启动综合落盘 — agent: governor (对抗审查+裁决+体检报告)')
const report = await S('governor', () => agent('综合全链写组合体检报告+换仓建议。\n\n## 投资目标\n'+goal+'\n\n## 全链产出(用 Read 读各 json)\n'+ctx+'\n'+history+'\n\n## 你的任务\n### 0. 收尾脚本(先跑)\nBash: python scripts/portfolio_tracker.py update 2>&1\n\n### 1. 对抗审查\n检测矛盾并用 MCP 只读工具抽查验证:\n- 技术信号衰减(减仓)但催化即将兑现(加仓)?\n- 基本面改善但组合相关性过高(同涨同跌)?\n- 宏观从顺风转逆风但持仓未调整?\n- 某只持仓基本面+技术+催化三方矛盾?\n对关键矛盾用 ifind 抽查持仓数据,标注 ✅核实/⚠️偏差/❌矛盾。\n\n### 2. 报告输出\n换仓建议具体到哪只减/换/加(引用各agent的action)。\n1. WRITE output/'+asOf+'_组合体检报告.md(结论先行→总体策略→各专项+逻辑关系→对抗审查结论+总督验证→换仓操作→风险→免责),头一句话附组合健康度+置信度。\n2. WRITE '+RD+'/final.json(envelope,data 含 oneLineConclusion/rebalanceActions/topN/totalPosition/confidence/keyRisks/contradictions/modules)。\n3. 更新 data/index.json(Read→push→Write)。\n\n### 3. 邮件通知\nBash: python scripts/notify_email.py --run-id '+asOf+'_'+G+' 2>&1\n(失败不影响返回)\n\nschema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
log('✅ 综合落盘完成')
log('🎉 Workflow 全部完成!')
if (report?.path) {
  log('📄 报告: '+report.path)
}

return report
