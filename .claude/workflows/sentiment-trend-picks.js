export const meta = {
  name: 'sentiment-trend-picks',
  description: 'A股舆情趋势预判选股——catalyst舆情→macro验证→sector→tech∥fund并行→risk→governor(审查+裁决+报告)。防纯炒作空气票',
  phases: [
    {title: '舆情挖掘', detail: 'catalyst 识别趋势+候选(含 prefetch)'},
    {title: '趋势验证', detail: 'macro 趋势是否顺风'},
    {title: '板块候选', detail: 'sector 趋势板块+候选'},
    {title: '技术∥排雷', detail: 'technical + fundamentals 并行'},
    {title: '组合回测', detail: 'risk 组合+回测'},
    {title: '综合落盘', detail: 'governor 审查+裁决+报告+portfolio+notify'},
  ],
}

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const keyword=args.keyword||'', trend=args.trend||'', topN=args.topN||5, acc=args.account||'1w', asOf=args.asOf||'YYYYMMDD'
const G='sentiment-trend-picks', RD='data/runs/'+asOf+'_'+G
const focus=keyword||trend||'近期舆情热点'
const goal='舆情趋势预判选股: 关键词['+focus+'] Top'+topN+' 账户'+acc+' | 基准日'+asOf
const history = args.history || ''
const SHARED = 'data/runs/'+asOf+'_'+G+'/_shared.json'

// ── 预取指令(仅 catalyst agent 执行) ──
const PREFETCH = '⚠️ 前置步骤(必须在分析之前完成):\n1. 运行 Bash: python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' 2>&1\n2. 运行 Bash: python scripts/portfolio_tracker.py update 2>&1\n3. Read '+SHARED+' 获取共享数据(核心信号🔴🟡🟢)\n完成后再进入下方分析任务。\n\n'

const S = async (name, fn) => {
  try { const r = await fn(); if (r) return r } catch (e) {
    const msg = (e?.message||String(e)).slice(0,200)
    return {path:'',summary:name+' 失败(降级): '+msg,keyFields:{_error:true}}
  }
  return {path:'',summary:name+' 返回空',keyFields:{_error:'empty'}}
}
const P = (ag, task, extra, ctx) => task+'\n\n## 投资目标\n'+goal+'\n\n## 前序环节产出\n'+(ctx||'(本环节为起点,无前序)')+'\n\n## 你的任务\n'+extra+'\n\n## 数据落盘\n完整输出 WRITE 到 '+RD+'/'+ag+'.json,envelope:{"runId":"'+asOf+'_'+G+'","asOf":"'+asOf+'","goal":"'+G+'","agent":"'+ag+'","fetchedAt":"'+asOf+'","data":{完整输出},"summary":"一句话","keyFields":{小摘录}}\nschema 只返回 {path,summary,keyFields}。'
const ap = (r, l) => r ? '\n【'+l+'】'+r.summary+(r.path?' → '+r.path:'') : '\n【'+l+'】⚠️ 数据缺失'

let ctx = ''

// ── Phase 1: 舆情挖掘(含 prefetch) ──
phase('舆情挖掘')
const cat = await S('catalyst', () => agent(PREFETCH+P('catalyst-scanner','舆情挖掘:从新闻语义+热榜+社交情绪识别趋势+候选股。','用 ifind_search_news(必带time_start/end,query含"'+focus+'")+china-news+hot_trend_dig.py 识别2-3个趋势主题,给信号强度+信息源+候选代码。非结构化页面用 web-scraping fetch.py。警惕纯炒作,给情绪温度+市场怀疑度。', ctx), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'舆情挖掘'}))
ctx = ap(cat,'舆情趋势')

// ── Phase 2: 趋势验证(读 catalyst 的趋势主题) ──
phase('趋势验证')
const macro = await S('macro', () => agent(P('macro-strategist','验证舆情趋势是否与宏观顺风方向一致。','用 Read 读 '+cat.path+' 的 data.trends 获取舆情趋势;用 ifind_index_data+ifind_search_news+ifind_get_edb_data 判断趋势是否落在宏观顺风方向。trendAligned=true 才继续,false 则降权。', ctx), {agentType:'macro-strategist',schema:RET,label:'macro',phase:'趋势验证'}))
ctx += ap(macro,'趋势验证')

// ── Phase 3: 板块候选(读 catalyst + macro) ──
phase('板块候选')
const sector = await S('sector', () => agent(P('sector-analyst','承接趋势,挖对应板块+候选池。','用 Read 读 '+cat.path+' 和 '+macro.path+';对验证通过的趋势(trendAligned=true),用 ifind_sector_data+ifind_search_stocks+手动龙头 取板块成分+候选,优先<40元。合并去重。', ctx), {agentType:'sector-analyst',schema:RET,label:'sector',phase:'板块候选'}))
ctx += ap(sector,'候选')

// ── Phase 4: 技术∥排雷(并行,都读 sector 候选) ──
phase('技术∥排雷')
const [tech, fund] = await parallel([
  () => S('tech', () => agent(P('technical-liquidity','对候选批量做流动性过滤+动量(趋势启动信号)。','用 Read 读 '+sector.path+' 的 data.candidates 获取候选清单;批量算动量+流动性;硬门槛过滤;重点识别趋势启动特征(站上MA20+放量突破+m5正但未透支)。返pass/reject/factors。', ctx), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'技术∥排雷'})),
  () => S('fund', () => agent(P('fundamentals-analyst','对候选批量排雷(防空气票)。','用 Read 读 '+sector.path+' 的 data.candidates 获取候选清单;批量排雷;重点:纯炒作票(无业绩+高估值+无机构持仓)直接剔除。返每只 verdict。', ctx), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'技术∥排雷'})),
])
ctx += ap(tech,'技术') + ap(fund,'排雷')

// ── Phase 5: 组合回测(综合全链) ──
phase('组合回测')
const risk = await S('risk', () => agent(P('risk-portfolio','组合配置+回测验证。','Read 全链 json(舆情趋势+宏观验证+候选+技术因子+排雷);排Top'+topN+'(趋势强度+技术启动+排雷通过);5日窗口回测(胜率>=55%/均收>=3%/回撤<=8%);3项全不达标一票否决;组合分散(行业<=40%/催化同源<=50%)。', ctx), {agentType:'risk-portfolio',schema:RET,label:'risk',phase:'组合回测'}))
ctx += ap(risk,'组合')

// ── Phase 6: 综合落盘 ──
phase('综合落盘')
const report = await S('governor', () => agent('综合全链写舆情趋势预判选股报告。\n\n## 投资目标\n'+goal+'\n\n## 全链产出(用 Read 读各 json)\n'+ctx+'\n'+history+'\n\n## 你的任务\n### 0. 收尾脚本(先跑)\nBash: python scripts/portfolio_tracker.py update 2>&1\n\n### 1. 对抗审查\n检测矛盾并用 MCP 只读工具抽查验证:\n- 舆情热度高但宏观逆风?(逆风炒作风险)\n- 趋势强度强但基本面空气?(无业绩支撑)\n- 技术启动但催化已price-in?(查近5日涨幅)\n- 排雷通过但回测未背书?\n对每对矛盾用 ifind 抽查关键数据,标注 ✅核实/⚠️偏差/❌矛盾。\n\n### 2. 报告输出\n预判置信度基于趋势强度+宏观对齐+回测达标。\n1. WRITE output/'+asOf+'_舆情趋势预判选股.md(结论先行→总体策略→各专项+逻辑关系→对抗审查结论+总督验证→操作→风险→免责),风险含趋势证伪触发条件。\n2. WRITE '+RD+'/final.json(envelope,data 含 oneLineConclusion/topN/totalPosition/confidence/keyRisks/contradictions/trends/modules)。\n3. 更新 data/index.json(Read→push→Write)。\n4. 如果有 topN 推荐:WRITE '+RD+'/_rec.json 含 {topN, confidence},然后 Bash: python scripts/portfolio_tracker.py record --run-id '+asOf+'_'+G+' --json-file '+RD+'/_rec.json 2>&1\n\n### 3. 邮件通知\nBash: python scripts/notify_email.py --run-id '+asOf+'_'+G+' 2>&1\n(失败不影响返回)\n\nschema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))

return report
