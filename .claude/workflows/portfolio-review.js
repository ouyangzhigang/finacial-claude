export const meta = {
  name: 'portfolio-review',
  description: 'A股组合体检——risk主导(相关性/集中度)→fund∥tech∥cat并行评持仓→macro→对抗审查→governor体检报告+换仓',
  phases: [
    {title: '组合体检', detail: 'risk 相关性+集中度+因子暴露'},
    {title: '持仓深评', detail: 'fundamentals∥technical∥catalyst 并行'},
    {title: '顺风逆风', detail: 'macro 持仓方向变化'},
    {title: '对抗审查', detail: '矛盾检测'},
    {title: '综合落盘', detail: 'governor+历史对照'},
  ],
}

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const holdings=args.holdings||[], acc=args.account||'1w', asOf=args.asOf||'YYYYMMDD'
const G='portfolio-review', RD='data/runs/'+asOf+'_'+G
const holdingsStr=holdings.map(h=>h.code+(h.name?'('+h.name+')':'')+' '+(h.shares||'?')+'股@'+(h.cost||'?')).join(', ')
const goal='组合体检: 持仓['+holdingsStr+'] 账户'+acc+' | 基准日'+asOf

let history = ''
try {
  const ix = JSON.parse(await Read('data/index.json') || '[]')
  const past = ix.filter(r => r.goal === G).slice(-3)
  if (past.length) history = '\n## 历史对照\n' + past.map(r => '- '+r.fetchedAt+' '+r.headline+' ('+r.confidence+')').join('\n') + '\n'
} catch {}

const S = async (name, fn) => {
  const ep = RD+'/'+name+'_degraded.json'
  try { const r = await fn(); if (r) return r } catch (e) {
    const msg = (e?.message||String(e)).slice(0,200)
    try { Write(ep, JSON.stringify({runId:asOf+'_'+G,asOf,goal:G,agent:name,fetchedAt:asOf,data:{},summary:name+' 失败: '+msg,keyFields:{_error:true}},null,2)) } catch {}
    return {path:ep,summary:name+' 失败(降级): '+msg,keyFields:{_error:true}}
  }
  return {path:ep,summary:name+' 返回空',keyFields:{_error:'empty'}}
}
const P = (ag, task, extra, ctx) => task+'\n\n## 投资目标\n'+goal+'\n\n## 前序环节产出\n'+(ctx||'(本环节为起点,无前序)')+'\n\n## 你的任务\n'+extra+'\n\n## 数据落盘\n完整输出 WRITE 到 '+RD+'/'+ag+'.json,envelope:{"runId":"'+asOf+'_'+G+'","asOf":"'+asOf+'","goal":"'+G+'","agent":"'+ag+'","fetchedAt":"'+asOf+'","data":{完整输出},"summary":"一句话","keyFields":{小摘录}}\nschema 只返回 {path,summary,keyFields}。'
const ap = (r, l) => r ? '\n【'+l+'】'+r.summary+' → '+r.path : '\n【'+l+'】⚠️ 数据缺失'

// ── Phase 0: 数据预取 + 持仓视图 ──
phase('数据预取')
const prefetchOut = await Bash('python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' 2>&1')
const portfolioOut = await Bash('python scripts/portfolio_tracker.py update 2>&1; echo "---"; python scripts/portfolio_tracker.py summary 2>&1')
const sharedCtx = '\n## 共享预取数据+持仓视图(含核心信号)\n'+prefetchOut+'\n\n'+portfolioOut+'\n\n> radarSignals 含市场核心信号(🔴关键/🟡重要/🟢一般) Read data/runs/'+asOf+'_'+G+'/_shared.json\n'
log('预取: ' + prefetchOut.slice(0, 120))

// ── 空持仓早退 ──
if (!holdings.length) {
  phase('综合落盘')
  const report = await S('governor', () => agent('持仓清单为空,无法体检。\n## 投资目标\n'+goal+'\n## 你的任务\n提示用户"组合体检需提供持仓清单(代码/股数/成本)"。\n1. WRITE '+RD+'/final.json(envelope,data含verdict:"持仓为空",reason)。\n2. 更新 data/index.json(Read→push→Write)。\nschema 返回 {path:"",dataPath:"'+RD+'/final.json",oneLineConclusion:"持仓为空,无法体检",confidence:"低",keyRisks:["无持仓输入"]}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
  return report
}

let ctx = ''

// ── Phase 1: 组合体检 ──
phase('组合体检')
const risk = await S('risk', () => agent(P('risk-portfolio','对持仓做组合层体检:相关性+集中度+因子暴露+隐性偏移。','用 ifind_get_stock_summary日K算持仓间相关性(近20日收益相关)+行业集中度+风格暴露+催化同源。识别"同涨同跌"对与隐性偏移。对每只给初步信号衰减判断。', ctx), {agentType:'risk-portfolio',schema:RET,label:'risk',phase:'组合体检'}))
ctx = ap(risk,'组合体检')

// ── Phase 2: 持仓深评(3 并行) ──
phase('持仓深评')
const [fund, tech, cat] = await parallel([
  () => S('fund', () => agent(P('fundamentals-analyst','对持仓批量做基本面变化复查。','用 Read 读 '+risk.path+' 的 data.holdingsAssessment;检查持仓最新财报 vs 建仓时变化(业绩拐点/新红旗/股东变化)。返每只 verdict+earningsChange。', ctx), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'持仓深评'})),
  () => S('tech', () => agent(P('technical-liquidity','对持仓批量做技术信号衰减检查。','用 Read 读 '+risk.path+' 的 data.holdingsAssessment;检查每只:近5日动量转负?跌破MA5/MA20?量能萎缩?返每只 signalDecay+action(持有/减仓/换仓)。', ctx), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'持仓深评'})),
  () => S('cat', () => agent(P('catalyst-scanner','对持仓批量做催化兑现/落空检查。','用 Read 读 '+risk.path+' 的 data.holdingsAssessment;用 ifind_search_news+china-news get_stock_news+ifind_get_stock_events 检查每只:原催化已兑现/落空?新催化临近?返每只 catalystFulfilled+upcoming+action。非结构化页面用 web-scraping fetch.py。', ctx), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'持仓深评'})),
])
ctx += ap(fund,'基本面') + ap(tech,'技术') + ap(cat,'催化')

// ── Phase 3: 顺风逆风 ──
phase('顺风逆风')
const macro = await S('macro', () => agent(P('macro-strategist','检查持仓方向相对宏观的顺风/逆风变化。','用 Read 读前序各 json;判断持仓所属方向的宏观顺风/逆风变化(相比建仓时),输出顺风/逆风+风格切换。', ctx), {agentType:'macro-strategist',schema:RET,label:'macro',phase:'顺风逆风'}))
ctx += ap(macro,'顺风逆风')

// ── Phase 4: 对抗审查 ──
phase('对抗审查')
const review = await S('review', () => agent('你是对抗审查员,检测组合体检中的结论矛盾。\n\n## 投资目标\n'+goal+'\n\n## 全链产出(用 Read 读各 json)\n'+ctx+'\n\n## 检查重点\n- 技术信号衰减(减仓)但催化即将兑现(加仓)?\n- 基本面改善但组合相关性过高(同涨同跌)?\n- 宏观从顺风转逆风但持仓未调整?\n- 某只持仓基本面+技术+催化三方矛盾?\n\nWRITE '+RD+'/review.json(envelope,data 含 contradictions[],consistencyScore 0-100)\nschema 返回 {path,summary,keyFields:{contradictions,consistencyScore}}。', {agentType:'governor',schema:RET,label:'review',phase:'对抗审查'}))
ctx += ap(review,'对抗审查')

// ── Phase 5: 综合落盘 ──
phase('综合落盘')
const report = await S('governor', () => agent('综合全链写组合体检报告+换仓建议。\n\n## 投资目标\n'+goal+'\n\n## 全链产出(用 Read 读各 json)\n'+ctx+'\n'+history+'\n\n## 你的任务\n**对抗审查矛盾必须显式裁决**。换仓建议具体到哪只减/换/加(引用各agent的action)。\n1. WRITE output/'+asOf+'_组合体检报告.md(结论先行→总体策略→各专项+逻辑关系→对抗审查结论→换仓操作→风险→免责),头一句话附组合健康度+置信度。\n2. WRITE '+RD+'/final.json(envelope,data 含 oneLineConclusion/rebalanceActions/topN/totalPosition/confidence/keyRisks/contradictions/modules)。\n3. 更新 data/index.json(Read→push→Write)。\nschema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
return report
