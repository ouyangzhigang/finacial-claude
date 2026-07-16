export const meta = {
  name: 'hot-trends',
  description: 'A股热门板块/潜力股推荐——情绪+资金主导:catalyst先识别主线→sector板块→tech∥fund并行→risk→governor(审查+裁决+报告)。数据落盘不占上下文',
  phases: [
    {title: '热榜挖掘', detail: 'catalyst 识别主线(含 prefetch)'},
    {title: '板块成分', detail: 'sector 龙头+候选'},
    {title: '技术∥排雷', detail: 'technical + fundamentals 并行'},
    {title: '组合', detail: 'risk 配置'},
    {title: '综合落盘', detail: 'governor 审查+裁决+报告+portfolio+notify'},
  ],
}

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const constraint=args.constraint||'热门板块潜力股综合推荐', topN=args.topN||8, acc=args.account||'1w', asOf=args.asOf||'YYYYMMDD'
const G='hot-trends', RD='data/runs/'+asOf+'_'+G
const goal='热门板块/潜力股: Top'+topN+' 约束['+constraint+'] 账户'+acc+' | 基准日'+asOf
const history = args.history || ''
let SHARED = 'data/runs/'+asOf+'_'+G+'/_shared.json'
const startTime = Date.now()

// ── 预取指令(仅 catalyst agent 执行) ──
let PREFETCH = '⚠️ 前置步骤(必须在分析之前完成):\n1. 运行 Bash: python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' --extra hot 2>&1\n2. 运行 Bash: python scripts/portfolio_tracker.py update 2>&1\n3. Read '+SHARED+' 获取共享数据(板块/涨停池/核心信号🔴🟡🟢)\n完成后再进入下方分析任务。\n\n'

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
const P = (ag, task, extra, ctx) => task+'\n\n## 投资目标\n'+goal+'\n\n## 前序环节产出\n'+(ctx||'(本环节为起点,无前序)')+'\n\n## 你的任务\n'+extra+'\n\n## 数据落盘\n完整输出 WRITE 到 '+RD+'/'+ag+'.json,envelope:{"runId":"'+asOf+'_'+G+'","asOf":"'+asOf+'","goal":"'+G+'","agent":"'+ag+'","fetchedAt":"'+asOf+'","data":{完整输出},"summary":"一句话","keyFields":{小摘录}}\nschema 只返回 {path,summary,keyFields}。'
const ap = (r, l) => {
  if (!r) return '\n【'+l+'】⚠️ 数据缺失'
  const pathInfo = r.path ? ' → '+r.path : ''
  return '\n【'+l+'】'+r.summary+pathInfo
}

let ctx = ''

// ── Phase 1: 热榜挖掘(含 prefetch) ──
phase('热榜挖掘')
log('🔄 启动热榜挖掘 — agent: catalyst-scanner')
const catStart = Date.now()
const cat = await S('catalyst', () => agent(PREFETCH+P('catalyst-scanner','多源挖掘今日主线:热榜+龙虎榜+涨停池+连板梯队+市场概览。',"用 ifind_search_news(必带time_start/end)+china-news+'PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python scripts/hot_trend_dig.py' (Step4-5涨停池+市场概览可用,Step1-3 SSL挂则curl龙虎榜)+cn_fetch.py rank。非结构化页面用 web-scraping fetch.py 抓取。输出主线主题+情绪(涨停/封板率/炸板率/连板高度)+资金方向。", ctx), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'热榜挖掘'}))
ctx = ap(cat,'主线/情绪')
const catTime = Math.round((Date.now() - catStart) / 1000)
log('✅ 热榜挖掘完成 ('+catTime+'s) — ' + (cat?.summary || '空'))

// ── Phase 2: 板块成分(承接主线主题) ──
phase('板块成分')
log('🔄 启动板块成分 — agent: sector-analyst')
const sectorStart = Date.now()
const sector = await S('sector', () => agent(P('sector-analyst','承接主线,挖板块成分+龙头+候选池。','用 Read 读 '+cat.path+' 的 data.mainThemes 确定主线方向;对主线用 ifind_sector_data(一次一板块)+cn_fetch.py rank 取成分+龙头+5日涨幅排名;候选优先<40元。cn_fetch 不覆盖的页面用 web-scraping fetch.py。', ctx), {agentType:'sector-analyst',schema:RET,label:'sector',phase:'板块成分'}))
ctx += ap(sector,'板块/候选')
const sectorTime = Math.round((Date.now() - sectorStart) / 1000)
log('✅ 板块成分完成 ('+sectorTime+'s) — ' + (sector?.summary || '空'))

// ── Phase 3: 技术∥排雷(并行,都读 sector 候选) ──
phase('技术∥排雷')
log('🔄 启动技术∥排雷 — technical-liquidity ∥ fundamentals-analyst')
const parallelStart = Date.now()
const [tech, fund] = await parallel([
  () => S('tech', () => agent(P('technical-liquidity','对候选批量做流动性过滤+动量。','用 Read 读 '+sector.path+' 的 data.candidates 获取候选清单;用 ifind_get_stock_summary 或 cn_fetch.py factors 批量算动量+流动性;硬门槛过滤(成交额>=1亿/换手1-7%/非ST非次新/近5-20日>30%透支剔除)。返pass/reject/factors。', ctx), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'技术∥排雷'})),
  () => S('fund', () => agent(P('fundamentals-analyst','对候选批量排雷(对 sector 全候选做)。','用 Read 读 '+sector.path+' 的 data.candidates 获取候选清单;用 ifind_get_stock_financials+ifind_get_stock_shareholders 批量排雷(商誉/质押/造假),硬雷点剔除。返每只 verdict。', ctx), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'技术∥排雷'})),
])
ctx += ap(tech,'技术') + ap(fund,'财务')
const parallelTime = Math.round((Date.now() - parallelStart) / 1000)
log('✅ 技术∥排雷完成 ('+parallelTime+'s)')
log('  技术: ' + (tech?.summary || '空'))
log('  财务: ' + (fund?.summary || '空'))

// ── Phase 4: 组合(综合全链) ──
phase('组合')
log('🔄 启动组合配置 — agent: risk-portfolio')
const riskStart = Date.now()
const risk = await S('risk', () => agent(P('risk-portfolio','组合配置Top'+topN+'。','Read 全链 json(主线方向+候选+技术因子+排雷结论);按情绪/资金主导(权重高于基本面)排Top'+topN+';组合分散(行业<=40%/催化同源<=50%);1w手数致分层建仓须标注。回测未背书不入TopN。', ctx), {agentType:'risk-portfolio',schema:RET,label:'risk',phase:'组合'}))
ctx += ap(risk,'组合')
const riskTime = Math.round((Date.now() - riskStart) / 1000)
log('✅ 组合配置完成 ('+riskTime+'s) — ' + (risk?.summary || '空'))

// ── Phase 5: 综合落盘 ──
phase('综合落盘')
log('🔄 启动综合落盘 — agent: governor (对抗审查+裁决+报告)')
const govStart = Date.now()
const report = await S('governor', () => agent('综合全链写热门板块潜力股报告。\n\n## 投资目标\n'+goal+'\n\n## 全链产出(用 Read 读各 json)\n'+ctx+'\n'+history+'\n\n## 你的任务\n### 0. 收尾脚本(先跑)\nBash: python scripts/portfolio_tracker.py update 2>&1\n\n### 1. 对抗审查\n检测矛盾并用 MCP 只读工具抽查验证:\n- 情绪高温但基本面排雷未通过的票是否仍在 TopN?\n- 板块主线强劲但个股流动性边缘?\n- 催化临近但已 price-in?(查近5日涨幅)\n- TopN 中催化同源是否超50%?\n对每对矛盾用 ifind 抽查关键数据,标注 ✅核实/⚠️偏差/❌矛盾。\n\n### 2. 报告输出\n1. WRITE output/'+asOf+'_热门板块潜力股综合推荐.md,governor 报告结构(结论先行→总体策略→各专项+逻辑关系→对抗审查结论+总督验证→操作→风险→免责),头一句话结论附情绪温度+置信度+回测达标。\n2. WRITE '+RD+'/final.json(envelope,data 含 oneLineConclusion/topN/totalPosition/confidence/keyRisks/contradictions/mainThemes/modules)。\n3. 更新 data/index.json(Read→push→Write)。\n4. 如果有 topN 推荐:WRITE '+RD+'/_rec.json 含 {topN, confidence},然后 Bash: python scripts/portfolio_tracker.py record --run-id '+asOf+'_'+G+' --json-file '+RD+'/_rec.json 2>&1\n\n### 3. 邮件通知\nBash: python scripts/notify_email.py --run-id '+asOf+'_'+G+' 2>&1\n(失败不影响返回)\n\nschema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
const govTime = Math.round((Date.now() - govStart) / 1000)
const totalTime = Math.round((Date.now() - startTime) / 1000)
log('✅ 综合落盘完成 ('+govTime+'s)')
log('🎉 Workflow 全部完成! 总耗时 '+Math.floor(totalTime/60)+'min '+(totalTime%60)+'s')
if (report?.path) {
  log('📄 报告: '+report.path)
}
if (report?.topN?.length) {
  log('📊 Top'+report.topN.length+': '+report.topN.map(t => t.code+' '+t.name).join(', '))
}

return report
