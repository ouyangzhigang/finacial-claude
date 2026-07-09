export const meta = {
  name: 'single-stock-deep',
  description: 'A股单股深度分析——并行4维(macro∥fundamentals∥technical∥catalyst)→sector→risk→对抗审查→governor报告。数据落盘不占上下文',
  phases: [
    {title: '独立分析', detail: 'macro∥fundamentals∥technical∥catalyst 并行'},
    {title: '行业定位', detail: 'sector 承接宏观'},
    {title: '风险估值', detail: 'risk 综合+情景'},
    {title: '对抗审查', detail: '矛盾检测+裁决'},
    {title: '综合落盘', detail: 'governor+历史对照'},
  ],
}

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const tk = args.ticker||'', nm = args.name||'', ac = args.account||'1w', hz = args.horizon||'波段', rp = args.riskPref||'稳健', ps = args.position||'无持仓', asOf = args.asOf||'YYYYMMDD'
const G='single-stock-deep', RD='data/runs/'+asOf+'_'+G
const goal='单股深评: '+tk+' '+nm+' | 账户'+ac+' 周期'+hz+' 风险'+rp+' 持仓'+ps+' | 基准日'+asOf

// ── 历史运行(供 governor 对照) ──
let history = ''
try {
  const ix = JSON.parse(await Read('data/index.json') || '[]')
  const past = ix.filter(r => r.goal === G || (r.headline||'').includes(tk)).slice(-3)
  if (past.length) history = '\n## 历史对照(最近 '+past.length+' 次运行)\n' + past.map(r => '- '+r.fetchedAt+' '+r.headline+' (置信度'+r.confidence+')').join('\n') + '\n'
} catch {}

// ── 通用 helper ──
const S = async (name, fn) => {
  const ep = RD+'/'+name+'_degraded.json'
  try {
    const r = await fn()
    if (r) return r
  } catch (e) {
    const msg = (e?.message||String(e)).slice(0,200)
    try { Write(ep, JSON.stringify({runId:asOf+'_'+G,asOf,goal:G,agent:name,fetchedAt:asOf,data:{},summary:name+' 失败: '+msg,keyFields:{_error:true}},null,2)) } catch {}
    return {path:ep,summary:name+' 失败(降级): '+msg,keyFields:{_error:true}}
  }
  return {path:ep,summary:name+' 返回空',keyFields:{_error:'empty'}}
}
const P = (ag, task, extra, ctx) => task+'\n\n## 投资目标\n'+goal+'\n\n## 前序环节产出\n'+(ctx||'(本环节为起点,无前序)')+'\n\n## 你的任务\n'+extra+'\n\n## 数据落盘\n完整输出 WRITE 到 '+RD+'/'+ag+'.json,envelope:{"runId":"'+asOf+'_'+G+'","asOf":"'+asOf+'","goal":"'+G+'","agent":"'+ag+'","fetchedAt":"'+asOf+'","data":{完整输出},"summary":"一句话","keyFields":{小摘录}}\nschema 只返回 {path,summary,keyFields}。'
const ap = (r, l) => r ? '\n【'+l+'】'+r.summary+' → '+r.path : '\n【'+l+'】⚠️ 数据缺失(agent 失败)'

// ── Phase 0: 数据预取 + 持仓视图 ──
phase('数据预取')
const prefetchOut = await Bash('python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' --ticker '+tk+' 2>&1')
const portfolioOut = await Bash('python scripts/portfolio_tracker.py update 2>&1')
const sharedCtx = '\n## 共享预取数据(含核心信号)\n'+prefetchOut+'\n\n'+portfolioOut+'\n\n> radarSignals 含市场核心信号(🔴关键/🟡重要/🟢一般) Read data/runs/'+asOf+'_'+G+'/_shared.json\n'
log('预取: ' + prefetchOut.slice(0, 120))

// ── Phase 1: 4 维独立分析(并行,互不依赖) ──
phase('独立分析')
const [macro, fund, tech, cat] = await parallel([
  () => S('macro', () => agent(P('macro-strategist','对 '+tk+'('+nm+') 所属行业做"天时"五维定调。','用工具链取该股所属行业宏观读数+政策节点+情绪,输出顺风方向2-3+占优风格。', ''), {agentType:'macro-strategist',schema:RET,label:'macro',phase:'独立分析'})),
  () => S('fund', () => agent(P('fundamentals-analyst',tk+'('+nm+') 财务画像+估值锚+排雷。','用 ifind_get_stock_financials(年报日期优先)+ifind_get_stock_summary+ifind_get_stock_shareholders 取财务+估值分位+排雷,硬雷点一票否决。', ''), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'独立分析'})),
  () => S('tech', () => agent(P('technical-liquidity',tk+'('+nm+') 流动性硬门槛+短线因子+技术位。','用 ifind_get_stock_summary 取近1月日K算5/10/20日动量+MA20+量价突破;流动性硬门槛(成交额>=1亿/换手1-7%/市值>=30亿)不过关直接标注。盘中价须收盘复核。', ''), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'独立分析'})),
  () => S('cat', () => agent(P('catalyst-scanner',tk+'('+nm+') 催化日历+兑现度+情绪+资金。','用 ifind_search_news(必带time_start/end)+china-news get_stock_news 取催化+情绪+资金,判断兑现度(近5日涨>15%半兑现/>30%透支)。非结构化新闻/公告页用 web-scraping fetch.py 抓取。', ''), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'独立分析'})),
])

let ctx = ap(macro,'宏观') + ap(fund,'财务') + ap(tech,'技术') + ap(cat,'催化') + sharedCtx

// ── Phase 2: 行业定位(需宏观顺风方向) ──
phase('行业定位')
const sector = await S('sector', () => agent(P('sector-analyst','分析 '+tk+'('+nm+') 的行业地位、同业竞争、板块强度。','承接宏观顺风方向,定位该股在所属板块的龙头/跟风/边缘角色,列同业可比3-5只。', ctx), {agentType:'sector-analyst',schema:RET,label:'sector',phase:'行业定位'}))
ctx += ap(sector,'行业')

// ── Phase 3: 风险估值 ──
phase('风险估值')
const risk = await S('risk', () => agent(P('risk-portfolio',tk+'('+nm+') 估值区间+情景预演。','综合前序模块(用 Read 读各 json 取细节),给估值区间(低/中/高)+突破/震荡/破位三情景应对+操作区间。单股深评不需 TopN,但需操作区间。', ctx), {agentType:'risk-portfolio',schema:RET,label:'risk',phase:'风险估值'}))
ctx += ap(risk,'风险估值')

// ── Phase 4: 对抗审查(矛盾检测) ──
phase('对抗审查')
const review = await S('review', () => agent('你是对抗审查员,专门检测各分析维度之间的结论矛盾。\n\n## 投资目标\n'+goal+'\n\n## 全链产出(用 Read 读各 json 的 data 取细节)\n'+ctx+'\n\n## 你的任务\n逐对检查:\n- 技术看多 vs 基本面看空?(动量强劲但财务红旗)\n- 催化强劲 vs 已 price-in?(近5日涨>15%)\n- 行业顺风 vs 个股边缘?(板块强但该股是跟风)\n- 估值高 vs 动量强?(追高风险)\n\n对每对矛盾给出:双方 agent 路径+数据+你的裁决。\n无矛盾→确认一致性。\n\nWRITE '+RD+'/review.json(envelope,data 含 contradictions[],consistencyScore 0-100)\nschema 返回 {path,summary,keyFields:{contradictions,consistencyScore}}。', {agentType:'governor',schema:RET,label:'review',phase:'对抗审查'}))
ctx += ap(review,'对抗审查')

// ── Phase 5: 综合落盘 ──
phase('综合落盘')
const report = await S('governor', () => agent('综合全链产出写单股深评报告。\n\n## 投资目标\n'+goal+'\n\n## 全链产出(用 Read 读各 json 的 data 取细节)\n'+ctx+'\n'+history+'\n\n## 你的任务\n按矛盾调和矩阵综合六模块。**对抗审查发现的矛盾必须显式裁决**,不得两边都引用不表态。若多环红(技术+资金双红)不得给建仓价位只给观望+触发条件。\n\n1. WRITE 报告到 output/'+tk+'_'+asOf+'_深度分析报告.md(目录不存在先创建),按 governor 报告结构(结论先行→总体策略→各专项+逻辑关系→对抗审查结论→操作→风险→免责),头一句话结论附核心假设置信度。\n2. WRITE 结构化最终到 '+RD+'/final.json(envelope,data 含 oneLineConclusion/topN/totalPosition/confidence/keyRisks/contradictions/modules)。\n3. 更新 data/index.json(Read→push→Write)。\nschema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
return report
