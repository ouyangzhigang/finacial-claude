// future-picks.js — 全新预判型工作流:找未来时间段有潜力上涨的票
// 宗旨:不是当日排行榜,不是数据堆砌——是"今天分析→预测未来N天将涨"+完整推理链
// 与 short-term-picks 区别:旧=当日选股(回看已涨);新=未来预判(将涨信号)
// 全周期分层:短线1-5日 / 波段1-2周 / 中线1-3月

export const meta = {
  name: 'future-picks',
  description: 'A股未来预判——推理链5阶段(预判假设→证据收集→推理验证→潜力锁定→跟踪兑现),找未来有潜力上涨的票,非当日排行榜',
  phases: [
    {title: '预判假设', detail: 'macro定方向+板块轮动接力预判'},
    {title: '证据收集', detail: 'sector∥technical∥catalyst∥fundamentals 找将涨信号'},
    {title: '推理验证', detail: 'governor综合演绎:因为A→B→C→预判D将涨'},
    {title: '潜力锁定', detail: 'TopN+操作卡(触发窗+买入区间+止损)'},
    {title: '跟踪兑现', detail: 'record预测+命中率反馈'},
  ],
}

// ── args 兼容层(Workflow会序列化args成字符串) ──
if (typeof args === 'string') { try { args = JSON.parse(args); } catch (e) { args = {}; } }
log('🔍 DEBUG args: typeof='+typeof args+' asOf='+(args&&args.asOf)+' horizon='+(args&&args.horizon))

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const topN=args.topN||5, acc=args.account||'1w', rp=args.riskPref||'稳健偏积极', pos=args.position||'无持仓', asOf=args.asOf||'YYYYMMDD'
// horizon: 短线(1-5日)/波段(1-2周)/中线(1-3月) —— 决定预判周期+主因子
const horizon=args.horizon||'波段'
const HOR_MAP = {'短线':'1-5日','波段':'1-2周','中线':'1-3月'}
const horDays = HOR_MAP[horizon] || horizon
const G='future-picks', RD='data/runs/'+asOf+'_'+G+'_'+horizon
const goal='未来预判('+horizon+horDays+'): 找未来'+horDays+'有潜力上涨的Top'+topN+' | 账户'+acc+' 风险'+rp+' 持仓'+pos+' | 基准日'+asOf
const SHARED = 'data/runs/'+asOf+'_'+G+'_'+horizon+'/_shared.json'

// ── helper(复用_lib机制) ──
const S = async (name, fn) => {
  try { const r = await fn(); if (r) return r } catch (e) {
    const msg = (e?.message||String(e)).slice(0,200)
    return {path:'',summary:name+' 失败: '+msg,keyFields:{_error:true}}
  }
  return {path:'',summary:name+' 返回空',keyFields:{_error:'empty'}}
}
const O = (ag) => '\nWRITE '+RD+'/'+ag+'.json; envelope:{"agent":"'+ag+'","asOf":"'+asOf+'","horizon":"'+horizon+'","data":{...}}; schema→{path,summary,keyFields}'
// P() 改造:强制agent输出"推理链+预判",而非纯数据打分
const P = (ag, task, extra, ctx) => task+'\n# 目标\n'+goal+'\n# 前序推理\n'+(ctx||'(起点,无前序)')+'\n# 你的任务\n'+extra+'\n\n⚠️ 推理链要求:输出必须含"因为X→预判Y"的演绎,不只输出分数。keyFields须含reasoningChain字段(数组,每条=一个推理步骤)。'+O(ag)
const ap = (r, l) => r ? '\n【'+l+'】'+r.summary+(r.path?' → '+r.path:'') : '\n【'+l+'】⚠️ 数据缺失'

// 周期因子导向(不同周期看不同将涨信号)
const HORIZON_FOCUS = {
  '短线': '短线(1-5日)重点看:主力净流入未拉升(market_radar fetch_capital_flow)+龙虎榜机构建仓(hot_trend_dig)+形态突破前夜(区间收敛)+次催化(近1-5日事件)。找"资金已进场但当日未大涨"的票。',
  '波段': '波段(1-2周)重点看:板块轮动接力(sector-rotation)+未来催化日历(china-catalyst-calendar)+回踩缩量买点(setup_score回踩企稳)+主力建仓未拉升。找"板块将接力+形态回踩+催化将兑现"的票。',
  '中线': '中线(1-3月)重点看:宏观周期定位(sector-rotation-detector)+业绩预增(中报/年报预览)+产业趋势+估值修复(超跌低估)。找"周期顺风+业绩将释放+估值将修复"的票。',
}
const FOCUS = HORIZON_FOCUS[horizon] || HORIZON_FOCUS['波段']

const PREFETCH = '⚠️ 前置步骤(一条Bash并行):\n1. Bash: python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+'_'+horizon+' --extra hot 2>&1 & python scripts/market_radar.py 2>&1 > '+RD+'/market_radar.json & wait\n  (prefetch_shared 已内置 global_snapshot:美股三大指数+大宗+传导路径,会合并进 _shared.json 的 globalSnapshot 字段)\n2. Read '+SHARED+' 获取市场雷达核心信号(板块/涨停/龙虎榜/资金流)+ globalSnapshot(隔夜美股+大宗实证)\n3. Read '+RD+'/market_radar.json 获取7通道信号(若生成)\n完成后再分析。\n\n'

let ctx = ''

// ════════════════════════════════════════
// 阶段1: 预判假设 —— 定方向(不是"今天涨什么",是"未来N天哪个板块将接力占优")
// ════════════════════════════════════════
phase('预判假设')
log('🔄 预判假设 — macro定方向+板块轮动接力预判')
const macro = await S('macro', () => agent(PREFETCH+P('macro-strategist',
  '做未来'+horDays+'天时定调+板块轮动接力预判。复用 sector-rotation-detector 技能思维(宏观周期→行业跑赢/跑输)。',
  '1. Read '+SHARED+' 取regime+核心信号+globalSnapshot(隔夜美股三大指数+大宗实证,在_shared.json的globalSnapshot字段)\n2. 据globalSnapshot的隔夜美股道指/纳指涨跌+原油/黄金/铜涨跌,判断对A股的外部冲击路径(美股跌→科技承压/原油涨→资源股催化等),用实证数字不空谈\n3. 判断当前宏观周期阶段(复苏/扩张/滞胀/衰退)+方向\n4. ⭐ 核心:预判未来'+horDays+'占优风格 + 顺风板块2-3个 + 下个接力方向(不是今天涨的,是明天/下周/下月将接力的)\n5. 输出keyFields: {regime, cyclePhase, tailwinds:[板块], nextRotation:[接力方向预判], internationalPath:"基于globalSnapshot实证的传导判断(带具体数字)", reasoningChain:[推理链]}\n\n'+FOCUS, ctx), {agentType:'macro-strategist',schema:RET,label:'macro',phase:'预判假设'}))
ctx = ap(macro,'预判假设')
log('✅ 预判假设完成: ' + (macro?.summary || '空'))

// ════════════════════════════════════════
// 阶段2: 证据收集 —— 4路并行找"将涨信号"(非已涨数据)
// ════════════════════════════════════════
phase('证据收集')
log('🔄 证据收集 — 4路并行找将涨信号')
const [sector, tech, cat, fund] = await parallel([
  // 2a. 板块轮动接力 + 跟风补涨票
  () => S('sector', () => agent(P('sector-analyst',
    '找板块轮动接力的跟风补涨票(龙头已涨→今天没涨的跟风票将补涨)。复用 sector-rotation-detector 思维。',
    '1. Read '+macro.path+' 的 data.nextRotation 获取接力方向预判\n2. 用 market_radar fetch_sector_ranking 找今日强势板块,预判下个接力板块\n3. ⭐ 核心:找龙头今日涨停/大涨的板块里,今天【没涨】的跟风票(将补涨)\n4. ⭐ 用 ifind_search_stocks 自然语言筛\"主线板块里近20日跌>5%+PE<30+未涨停\"的跟风补涨票(全市场未涨来源,补 cn_fetch.py rank=已涨榜单的滞后) + cn_fetch.py rank 补充龙头已涨信号; 汇总候选20-30只\n5. 输出keyFields: {candidates:[{code,name,sector,relaySignal(接力信号),reasoningChain}], nextSector(下个接力板块)}\n\n'+FOCUS, ctx), {agentType:'sector-analyst',schema:RET,label:'sector',phase:'证据收集'})),
  // 2b. 技术形态将涨信号(回踩企稳/区间收敛/底部结构)——用setup_score
  // ⚠️ 本路与2a sector并行,不能引用sector结果(TDZ),用阶段1已完成的macro.path
  () => S('technical', () => agent(P('technical-liquidity',
    '找技术形态"将涨信号"的票(回踩缩量企稳/区间收敛待变盘/底部结构/蓄势待突破)。复用 factor_engine setup_score。',
    '1. Read '+macro.path+' 取顺风方向+候选线索(本路与sector并行,sector结果未就绪,勿引用)\n2. Bash: PYTHONIOENCODING=utf-8 python scripts/factor_engine.py --codes <从macro顺风方向自选候选> --output '+RD+'/factor_scores.json 2>&1\n3. Read '+RD+'/factor_scores.json 重点看 setup_score + setup_signals + range_contraction\n4. ⭐ 核心:挑 setup_score 高 + setup_signals 含"回踩企稳/区间收敛/底部结构"的票(非已突破的m5高)\n5. 输出keyFields: {setupCandidates:[{code,setup_score,setup_signals,reasoningChain}], passCodes}\n\n⚠️ 流动性硬门槛仍过滤(成交额>=1亿/换手1-7%/市值>=30亿/非ST)', ctx), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'证据收集'})),
  // 2c. 催化将兑现 + 主力建仓未拉升
  () => S('catalyst', () => agent(P('catalyst-scanner',
    '找催化将兑现+主力建仓未拉升的票。复用 event-driven-detector + china-catalyst-calendar 思维。',
    '1. Read '+SHARED+' 取龙虎榜+资金流信号\n2. Bash: python scripts/hot_trend_dig.py 2>&1 取龙虎榜机构建仓\n3. 用 market_radar fetch_capital_flow 找主力净流入为正但当日未大涨的票(建仓未拉升)\n4. ⭐ 核心:找有未来催化(财报/政策/会议)+主力已进场但未拉升的票\n5. 输出keyFields: {catalystCandidates:[{code,catalyst(未来事件),capitalSignal(建仓信号),reasoningChain}]}\n\n'+FOCUS, ctx), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'证据收集'})),
  // 2d. 估值修复 + 业绩预增
  () => S('fundamentals', () => agent(P('fundamentals-analyst',
    '找估值修复+业绩预增的票(超跌低估值+基本面反转)。复用 sentiment-reality-gap + undervalued 思维。',
    '1. Read '+SHARED+' 或候选清单\n2. ⭐ 用 ifind_search_stocks 自然语言筛\"近20日跌>10%+PE<30+归母净利同比>0的非ST股票\"(全市场超跌低估未涨票,补\"龙虎榜/涨停池=已动\"滞后来源) + astock_data.py tencent_quote 取PE分位/PB/市值 + mootdx财务复核\n3. ⭐ 核心:找超跌(近20日跌>15%)+估值低(PE分位<30%)+业绩预增/扭转的票(将修复)\n4. 硬雷排雷(商誉>30%/质押>50%一票否决)\n5. 输出keyFields: {valueCandidates:[{code,pe,pb,pullback(超跌深度),earningsSignal(业绩信号),reasoningChain}]}\n\n⚠️ 中线周期重点看这路,短线可降权', ctx), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'证据收集'})),
])
ctx += ap(sector,'板块接力') + ap(tech,'形态将涨') + ap(cat,'催化建仓') + ap(fund,'估值修复')
log('✅ 证据收集完成')

// ════════════════════════════════════════
// 阶段3: 推理验证 —— governor综合演绎(因为A→B→C→D→预判E将涨)
// ════════════════════════════════════════
phase('推理验证')
log('🔄 推理验证 — governor综合演绎')
const reasoning = await S('reasoning', () => agent(P('governor',
  '综合4路证据+宏观预判,做推理演绎:哪些票未来'+horDays+'有上涨潜力,且说清为什么。',
  '1. Read全部证据: '+sector.path+' '+tech.path+' '+cat.path+' '+fund.path+' '+macro.path+'\n2. ⭐ 核心:对每只候选票,综合多路信号形成完整推理链\n   模板:因为[板块轮动A]+[资金建仓B]+[形态回踩C]+[催化将兑现D]→预判[票E]未来'+horDays+'有上涨潜力\n3. 剔除只有单一信号(无共振)的票——需≥2路信号共振才入选\n4. 输出keyFields: {reasonedPicks:[{code,name,signals:[信号清单],reasoningChain:[A→B→C→D→E],potentialScore,triggerWindow(触发时间窗)}]}\n\n⚠️ 这是核心环节:你的价值在"综合推理预判",不是拼数据。每只票必须说清"为什么预判它将涨"。', ctx), {agentType:'governor',schema:RET,label:'reasoning',phase:'推理验证'}))
ctx += ap(reasoning,'推理验证')
log('✅ 推理验证完成: ' + (reasoning?.summary || '空'))

// ════════════════════════════════════════
// 阶段4: 潜力锁定 —— TopN+操作卡(不再回测证伪踢出,用预判强度+风险收益比)
// ════════════════════════════════════════
phase('潜力锁定')
log('🔄 潜力锁定 — governor/risk 选TopN+操作卡')
const report = await S('governor', () => agent(P('risk-portfolio',
  '基于推理验证结果,锁定Top'+topN+'潜力票+操作卡。复用 risk-adjusted-return-optimizer 思维。',
  '1. Read '+reasoning.path+' 取reasonedPicks\n2. 按 potentialScore(多信号共振强度)+风险收益比排序选Top'+topN+'\n3. ⭐ 输出每只票的操作卡:触发时间窗+买入区间+止损+止盈\n4. 仓位配置(组合分散:行业<=40%/催化同源<=50%/单票<=25%)\n5. 不再回测证伪踢出——回测只作风险参考(标注),不否决预判\n5b. ⚠️估值/业绩硬约束(future-picks不跑hard_gate.py,由你代码级执行,不可override):Read '+RD+'/fundamentals.json取每只票pePercentile+netProfitGrowthPct;pePercentile>80%→降级观察仓不入TopN(标估值已贵·位置不佳);pePercentile>95%→不得排Top1;netProfitGrowthPct<-30%→不得排Top1/3(业绩雷标低置信).病根:凯美PE分位100%/许继Q1-46%这类估值天花板+业绩雷票不该推给用户.\n6. WRITE output/'+asOf+'_未来潜力预判_'+horizon+'.md 报告结构:\n   一、预判方向(未来'+horDays+'占优风格/顺风板块/接力方向+宏观推理)\n   二、潜力票清单(每只附完整推理链A→B→C→D→E)\n   三、未来催化日历(哪些事件将兑现)\n   四、板块轮动图(今天热点→明天接力)\n   五、操作卡(触发窗+买入区间+止损+止盈)\n   六、预测跟踪表(本次预测记录,待未来兑现验证)\n7. WRITE '+RD+'/final.json + '+RD+'/_rec.json\n8. Bash: python scripts/portfolio_tracker.py record --run-id '+asOf+'_'+G+'_'+horizon+' --json-file '+RD+'/_rec.json 2>&1\n9. Bash: python scripts/forecast_tracker.py record --run-id '+asOf+'_'+G+'_'+horizon+' --json-file '+RD+'/_rec.json --horizon '+horizon+' 2>&1 (失败不影响)\n返回schema: {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}', ctx), {agentType:'governor',schema:GOV,label:'governor',phase:'潜力锁定'}))
ctx += ap(report,'潜力锁定')
log('✅ 潜力锁定完成')

// ════════════════════════════════════════
// 阶段5: 跟踪兑现 —— 已在阶段4 record,这里触发历史预测的回看
// ════════════════════════════════════════
phase('跟踪兑现')
log('🔄 跟踪兑现 — 回看历史预测命中率')
// forecast_tracker check: 看之前预测的票兑现了吗(失败不影响主流程)
await S('track', async () => {
  try {
    await agent('⚠️ 只运行不调试。\nBash: PYTHONIOENCODING=utf-8 python scripts/forecast_tracker.py check --as-of '+asOf+' 2>&1\nRead 输出获取历史预测命中率,写入报告补充"预测跟踪表"。', {label:'forecast_tracker', phase:'跟踪兑现'})
    return {path:'', summary:'跟踪兑现已检查'}
  } catch (e) { return {path:'', summary:'跟踪检查失败(不影响)'} }
})
log('✅ 跟踪兑现完成')
log('🎉 future-picks 全部完成!')
if (report?.path) log('📄 报告: '+report.path)
if (report?.topN?.length) log('📊 Top'+report.topN.length+': '+report.topN.map(t => t.code+' '+t.name).join(', '))

return report
