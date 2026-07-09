export const meta = {
  name: 'hot-trends',
  description: 'A股热门板块/潜力股推荐——情绪+资金主导:catalyst先识别主线→sector板块→tech∥fund并行→risk→对抗审查→governor。数据落盘不占上下文',
  phases: [
    {title: '热榜挖掘', detail: 'catalyst 识别主线'},
    {title: '板块成分', detail: 'sector 龙头+候选'},
    {title: '技术∥排雷', detail: 'technical + fundamentals 并行'},
    {title: '组合', detail: 'risk 配置'},
    {title: '对抗审查', detail: '矛盾检测'},
    {title: '综合落盘', detail: 'governor+历史对照'},
  ],
}

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const constraint=args.constraint||'热门板块潜力股综合推荐', topN=args.topN||8, acc=args.account||'1w', asOf=args.asOf||'YYYYMMDD'
const G='hot-trends', RD='data/runs/'+asOf+'_'+G
const goal='热门板块/潜力股: Top'+topN+' 约束['+constraint+'] 账户'+acc+' | 基准日'+asOf

let history = ''
try {
  const ix = JSON.parse(await Read('data/index.json') || '[]')
  const past = ix.filter(r => r.goal === G).slice(-3)
  if (past.length) history = '\n## 历史对照(最近 '+past.length+' 次运行)\n' + past.map(r => '- '+r.fetchedAt+' '+r.headline+' (置信度'+r.confidence+')').join('\n') + '\n'
} catch {}

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
const ap = (r, l) => r ? '\n【'+l+'】'+r.summary+' → '+r.path : '\n【'+l+'】⚠️ 数据缺失'

// ── Phase 0: 数据预取 + 持仓视图 ──
phase('数据预取')
const prefetchOut = await Bash('python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' --extra hot 2>&1')
const portfolioOut = await Bash('python scripts/portfolio_tracker.py update 2>&1')
const sharedCtx = '\n## 共享预取数据(指数/板块/涨停池/核心信号)\n'+prefetchOut+'\n\n'+portfolioOut+'\n\n> 详细数据含 radarSignals(核心信号:🔴关键/🟡重要/🟢一般) Read data/runs/'+asOf+'_'+G+'/_shared.json\n'
log('预取: ' + prefetchOut.slice(0, 120))

let ctx = ''

// ── Phase 1: 热榜挖掘 ──
phase('热榜挖掘')
const cat = await S('catalyst', () => agent(P('catalyst-scanner','多源挖掘今日主线:热榜+龙虎榜+涨停池+连板梯队+市场概览。',"用 ifind_search_news(必带time_start/end)+china-news+'PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python scripts/hot_trend_dig.py' (Step4-5涨停池+市场概览可用,Step1-3 SSL挂则curl龙虎榜)+cn_fetch.py rank。非结构化页面用 web-scraping fetch.py 抓取。输出主线主题+情绪(涨停/封板率/炸板率/连板高度)+资金方向。", ctx), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'热榜挖掘'}))
ctx = ap(cat,'主线/情绪') + sharedCtx

// ── Phase 2: 板块成分 ──
phase('板块成分')
const sector = await S('sector', () => agent(P('sector-analyst','承接主线,挖板块成分+龙头+候选池。','用 Read 读 '+cat.path+' 的 data.mainThemes;对主线用 ifind_sector_data(一次一板块)+cn_fetch.py rank 取成分+龙头+5日涨幅排名;候选优先<40元。cn_fetch 不覆盖的页面用 web-scraping fetch.py。', ctx), {agentType:'sector-analyst',schema:RET,label:'sector',phase:'板块成分'}))
ctx += ap(sector,'板块/候选')

// ── Phase 3: 技术∥排雷(并行) ──
phase('技术∥排雷')
const [tech, fund] = await parallel([
  () => S('tech', () => agent(P('technical-liquidity','对候选批量做流动性过滤+动量。','用 Read 读 '+sector.path+' 的 data.candidates;用 ifind_get_stock_summary 或 cn_fetch.py factors 批量算动量+流动性;硬门槛过滤(成交额>=1亿/换手1-7%/非ST非次新/近5-20日>30%透支剔除)。返pass/reject/factors。', ctx), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'技术∥排雷'})),
  () => S('fund', () => agent(P('fundamentals-analyst','对候选批量排雷(可不等技术过滤,对 sector 全候选做)。','用 Read 读 '+sector.path+' 的 data.candidates;用 ifind_get_stock_financials+ifind_get_stock_shareholders 批量排雷(商誉/质押/造假),硬雷点剔除。返每只 verdict。', ctx), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'技术∥排雷'})),
])
ctx += ap(tech,'技术') + ap(fund,'财务')

// ── Phase 4: 组合 ──
phase('组合')
const risk = await S('risk', () => agent(P('risk-portfolio','组合配置Top'+topN+'。','用 Read 读前序各 json;按情绪/资金主导(权重高于基本面)排Top'+topN+';组合分散(行业<=40%/催化同源<=50%);1w手数致分层建仓须标注。回测未背书不入TopN。', ctx), {agentType:'risk-portfolio',schema:RET,label:'risk',phase:'组合'}))
ctx += ap(risk,'组合')

// ── Phase 5: 对抗审查 ──
phase('对抗审查')
const review = await S('review', () => agent('你是对抗审查员,检测热门板块推荐中的结论矛盾。\n\n## 投资目标\n'+goal+'\n\n## 全链产出(用 Read 读各 json)\n'+ctx+'\n\n## 检查重点\n- 情绪高温但基本面排雷未通过的票是否仍在 TopN?\n- 板块主线强劲但个股流动性边缘?\n- 催化临近但已 price-in(近5日涨>15%)?\n- TopN 中催化同源是否超50%?\n\nWRITE '+RD+'/review.json(envelope,data 含 contradictions[],consistencyScore 0-100)\nschema 返回 {path,summary,keyFields:{contradictions,consistencyScore}}。', {agentType:'governor',schema:RET,label:'review',phase:'对抗审查'}))
ctx += ap(review,'对抗审查')

// ── Phase 6: 综合落盘 ──
phase('综合落盘')
const report = await S('governor', () => agent('综合全链写热门板块潜力股报告。\n\n## 投资目标\n'+goal+'\n\n## 全链产出(用 Read 读各 json)\n'+ctx+'\n'+history+'\n\n## 你的任务\n**对抗审查矛盾必须显式裁决**。用 MCP 只读工具抽查 TopN 中 1-2 只的关键数据(ROE/日K/催化)。\n1. WRITE output/'+asOf+'_热门板块潜力股综合推荐.md,governor 报告结构(结论先行→总体策略→各专项+逻辑关系→对抗审查结论→总督验证→操作→风险→免责),头一句话结论附情绪温度+置信度+回测达标。\n2. WRITE '+RD+'/final.json(envelope,data 含 oneLineConclusion/topN/totalPosition/confidence/keyRisks/contradictions/mainThemes/modules)。\n3. 更新 data/index.json(Read→push→Write)。\nschema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))

// ── Portfolio 记录推荐 ──
if (report?.topN?.length) {
  const recFile = RD+'/_rec.json'
  Write(recFile, JSON.stringify({topN: report.topN, confidence: report.confidence}))
  await Bash('python scripts/portfolio_tracker.py record --run-id '+asOf+'_'+G+' --json-file '+recFile+' 2>&1')
  log('portfolio: 已记录 '+report.topN.length+' 条推荐')
}
return report
