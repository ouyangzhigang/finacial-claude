export const meta = {
  name: 'single-stock-deep',
  description: 'A股单股深度分析——并行4维(macro∥fundamentals∥technical∥catalyst)→sector→risk→governor(审查+裁决+报告)。数据落盘不占上下文',
  phases: [
    {title: '独立分析', detail: 'macro(含prefetch)∥fundamentals∥technical∥catalyst 并行'},
    {title: '行业定位', detail: 'sector 承接宏观'},
    {title: '风险估值', detail: 'risk 综合+情景'},
    {title: '综合落盘', detail: 'governor 审查+裁决+报告+portfolio+notify'},
  ],
}

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const tk = args.ticker||'', nm = args.name||'', ac = args.account||'1w', hz = args.horizon||'波段', rp = args.riskPref||'稳健', ps = args.position||'无持仓', asOf = args.asOf||'YYYYMMDD'
const G='single-stock-deep', RD='data/runs/'+asOf+'_'+G
const goal='单股深评: '+tk+' '+nm+' | 账户'+ac+' 周期'+hz+' 风险'+rp+' 持仓'+ps+' | 基准日'+asOf
const history = args.history || ''
let SHARED = 'data/runs/'+asOf+'_'+G+'/_shared.json'
const startTime = Date.now()

// ── 预取指令(仅 macro agent 执行,创建 _shared.json) ──
let PREFETCH = '⚠️ 前置步骤(必须在分析之前完成):\n1. 运行 Bash: python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' --ticker '+tk+' 2>&1\n2. 运行 Bash: python scripts/portfolio_tracker.py update 2>&1\n3. Read '+SHARED+' 获取共享市场数据(核心信号🔴🟡🟢)\n完成后再进入下方分析任务。\n\n'

// ── 通用 helper ──
const S = async (name, fn) => {
  try {
    const r = await fn()
    if (r) return r
  } catch (e) {
    const msg = (e?.message||String(e)).slice(0,200)
    return {path:'',summary:name+' 失败(降级): '+msg,keyFields:{_error:true}}
  }
  return {path:'',summary:name+' 返回空',keyFields:{_error:'empty'}}
}

// P() 构建 agent prompt; target 参数生成「目标标的」段(非单股深评时不传)
const P = (ag, task, extra, ctx, target) => {
  const targetSec = target ? '\n\n## 目标标的\n'+target : ''
  return task+'\n\n## 投资目标\n'+goal+targetSec+'\n\n## 前序环节产出\n'+(ctx||'(本环节为起点,无前序)')+'\n\n## 你的任务\n'+extra+'\n\n## 数据落盘\n完整输出 WRITE 到 '+RD+'/'+ag+'.json,envelope:{"runId":"'+asOf+'_'+G+'","asOf":"'+asOf+'","goal":"'+G+'","agent":"'+ag+'","fetchedAt":"'+asOf+'","data":{完整输出},"summary":"一句话","keyFields":{小摘录}}\nschema 只返回 {path,summary,keyFields}。'
}
const ap = (r, l) => {
  if (!r) return '\n【'+l+'】⚠️ 数据缺失(agent 失败)'
  const pathInfo = r.path ? ' → '+r.path : ''
  return '\n【'+l+'】'+r.summary+pathInfo
}

// 目标标的字符串(传给每个 agent 的 P() 第5参数)
const TGT = tk+' '+nm+' — 你分析的正是这只股票,所有数据查询和结论都围绕它展开。'

// ── Phase 1: 4 维独立分析(并行,macro 含 prefetch,其他读 _shared.json) ──
phase('独立分析')
log('🔄 启动4维并行分析 — macro∥fundamentals∥technical∥catalyst')
const parallelStart = Date.now()
const [macro, fund, tech, cat] = await parallel([
  () => S('macro', () => agent(PREFETCH+P('macro-strategist','对目标标的所属行业做"天时"五维定调。','用工具链取该股所属行业宏观读数+政策节点+情绪,输出顺风方向2-3+占优风格。判断目标标的所属方向是否落在顺风区。', '', TGT), {agentType:'macro-strategist',schema:RET,label:'macro',phase:'独立分析'})),
  () => S('fund', () => agent(P('fundamentals-analyst','对目标标的做财务画像+估值锚+排雷。','Read '+SHARED+' 获取市场背景。用 ifind_get_stock_financials(年报日期优先)+ifind_get_stock_summary+ifind_get_stock_shareholders 取财务+估值分位+排雷,硬雷点一票否决。', '', TGT), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'独立分析'})),
  () => S('tech', () => agent(P('technical-liquidity','对目标标的做流动性硬门槛+短线因子+技术位。','Read '+SHARED+' 获取市场背景。用 ifind_get_stock_summary 取近1月日K算5/10/20日动量+MA20+量价突破;流动性硬门槛(成交额>=1亿/换手1-7%/市值>=30亿)不过关直接标注。盘中价须收盘复核。', '', TGT), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'独立分析'})),
  () => S('cat', () => agent(P('catalyst-scanner','对目标标的做催化日历+兑现度+情绪+资金分析。','Read '+SHARED+' 获取市场背景。用 ifind_search_news(必带time_start/end)+china-news get_stock_news 取催化+情绪+资金,判断兑现度(近5日涨>15%半兑现/>30%透支)。非结构化新闻/公告页用 web-scraping fetch.py 抓取。', '', TGT), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'独立分析'})),
])

let ctx = ap(macro,'宏观') + ap(fund,'财务') + ap(tech,'技术') + ap(cat,'催化')
const parallelTime = Math.round((Date.now() - parallelStart) / 1000)
log('✅ 4维并行分析完成 ('+parallelTime+'s)')
log('  宏观: ' + (macro?.summary || '空'))
log('  财务: ' + (fund?.summary || '空'))
log('  技术: ' + (tech?.summary || '空'))
log('  催化: ' + (cat?.summary || '空'))

// ── Phase 2: 行业定位(承接宏观顺风方向+所有 Phase 1 产出) ──
phase('行业定位')
log('🔄 启动行业定位 — agent: sector-analyst')
const sectorStart = Date.now()
const sector = await S('sector', () => agent(P('sector-analyst','分析目标标的的行业地位、同业竞争、板块强度。','承接宏观顺风方向(Read '+macro.path+' 的 data.tailwinds),定位该股在所属板块的龙头/跟风/边缘角色。参考技术信号(Read '+tech.path+')和催化主线(Read '+cat.path+'),列同业可比3-5只并对比。', ctx, TGT), {agentType:'sector-analyst',schema:RET,label:'sector',phase:'行业定位'}))
ctx += ap(sector,'行业')
const sectorTime = Math.round((Date.now() - sectorStart) / 1000)
log('✅ 行业定位完成 ('+sectorTime+'s) — ' + (sector?.summary || '空'))

// ── Phase 3: 风险估值(综合全链) ──
phase('风险估值')
log('🔄 启动风险估值 — agent: risk-portfolio')
const riskStart = Date.now()
const risk = await S('risk', () => agent(P('risk-portfolio','对目标标的做估值区间+情景预演。','综合全链模块(Read 各 json 取细节):宏观顺风度+财务排雷+技术动量+催化强度+行业地位。给估值区间(低/中/高)+突破/震荡/破位三情景应对+操作区间。', ctx, TGT), {agentType:'risk-portfolio',schema:RET,label:'risk',phase:'风险估值'}))
ctx += ap(risk,'风险估值')
const riskTime = Math.round((Date.now() - riskStart) / 1000)
log('✅ 风险估值完成 ('+riskTime+'s) — ' + (risk?.summary || '空'))

// ── Phase 4: 综合落盘(含对抗审查+裁决+portfolio+notify) ──
phase('综合落盘')
log('🔄 启动综合落盘 — agent: governor (对抗审查+裁决+报告)')
const govStart = Date.now()
const report = await S('governor', () => agent('综合全链产出写单股深评报告。\n\n## 投资目标\n'+goal+'\n\n## 目标标的\n'+TGT+'\n\n## 全链产出(用 Read 读各 json 的 data 取细节)\n'+ctx+'\n'+history+'\n\n## 你的任务\n### 0. 收尾脚本(先跑)\nBash: python scripts/portfolio_tracker.py update 2>&1\n\n### 1. 对抗审查(核心职责)\n逐对检测矛盾并用 MCP 只读工具抽查验证:\n- 技术看多 vs 基本面看空?(动量强劲但财务红旗)\n- 催化强劲 vs 已 price-in?(查近5日涨幅)\n- 行业顺风 vs 个股边缘?(板块强但该股是跟风)\n- 估值高 vs 动量强?(追高风险)\n- 任一环节标记了 ⚠️ 或 ❌ 时,交叉验证其他环节是否一致\n对每对矛盾用 ifind 抽查关键数据(ROE/日K/催化),标注 ✅核实/⚠️偏差/❌矛盾。\n若多环红(技术+资金双红)不得给建仓价位只给观望+触发条件。\n\n### 2. 报告输出\n1. WRITE 报告到 output/'+tk+'_'+asOf+'_深度分析报告.md(目录不存在先创建),按 governor 报告结构(结论先行→总体策略→各专项+逻辑关系→对抗审查结论+总督验证→操作→风险→免责),头一句话结论附核心假设置信度。\n2. WRITE 结构化最终到 '+RD+'/final.json(envelope,data 含 oneLineConclusion/topN/totalPosition/confidence/keyRisks/contradictions/modules)。\n3. 更新 data/index.json(Read→push→Write)。\n\n### 3. 邮件通知\nBash: python scripts/notify_email.py --run-id '+asOf+'_'+G+' 2>&1\n(失败不影响返回)\n\nschema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
const govTime = Math.round((Date.now() - govStart) / 1000)
const totalTime = Math.round((Date.now() - startTime) / 1000)
log('✅ 综合落盘完成 ('+govTime+'s)')
log('🎉 Workflow 全部完成! 总耗时 '+Math.floor(totalTime/60)+'min '+(totalTime%60)+'s')
if (report?.path) {
  log('📄 报告: '+report.path)
}

return report
