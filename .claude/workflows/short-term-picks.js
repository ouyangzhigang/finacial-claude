export const meta = {
  name: 'short-term-picks',
  description: 'A股短周期选股——宏观→候选→流动性→catalyst∥fundamentals→量化引擎(factor+timing+sentiment)→risk(回测+组合)→governor(审查+裁决+报告)',
  phases: [
    {title: '宏观定调', detail: 'regime+顺风方向(含 prefetch)'},
    {title: '候选池', detail: 'sector 30-50只'},
    {title: '流动性过滤', detail: 'technical 批量硬门槛'},
    {title: '并行评分', detail: 'catalyst∥fundamentals'},
    {title: '量化引擎', detail: 'factor_engine+timing_engine+regime'},
    {title: '回测组合', detail: 'risk(portfolio_optimizer)+评分+回测'},
    {title: '综合落盘', detail: 'governor 审查+裁决+报告+portfolio+notify'},
  ],
}

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const topN=args.topN||5, period=args.period||'2周', acc=args.account||'1w', rp=args.riskPref||'稳健偏积极', pos=args.position||'无持仓', asOf=args.asOf||'YYYYMMDD'
const G='short-term-picks', RD='data/runs/'+asOf+'_'+G
const goal='短周期选股: Top'+topN+' 周期'+period+' 风险'+rp+' 账户'+acc+' 持仓'+pos+' | 基准日'+asOf
const history = args.history || ''
const SHARED = 'data/runs/'+asOf+'_'+G+'/_shared.json'

// ── 预取指令(仅 macro agent 执行) ──
const PREFETCH = '⚠️ 前置步骤(必须在分析之前完成):\n1. 运行 Bash: python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' --extra hot 2>&1\n2. 运行 Bash: python scripts/portfolio_tracker.py update 2>&1\n3. 运行 Bash: PYTHONIOENCODING=utf-8 python scripts/regime_detector.py --output '+RD+'/regime.json 2>&1\n4. Read '+SHARED+' 获取共享市场数据(指数/榜单/核心信号)\n5. Read '+RD+'/regime.json 获取当前市场环境(regime/权重调整/风险预算)\n完成后再进入下方分析任务。\n\n'

const S = async (name, fn) => {
  try { const r = await fn(); if (r) return r } catch (e) {
    const msg = (e?.message||String(e)).slice(0,200)
    return {path:'',summary:name+' 失败(降级): '+msg,keyFields:{_error:true}}
  }
  return {path:'',summary:name+' 返回空',keyFields:{_error:'empty'}}
}
const P = (ag, task, extra, ctx) => task+'\n\n## 投资目标\n'+goal+'\n\n## 前序环节产出\n'+(ctx||'(本环节为起点,无前序)')+'\n\n## 你的任务\n'+extra+'\n\n## 数据落盘\n完整输出 WRITE 到 '+RD+'/'+ag+'.json,envelope:{"runId":"'+asOf+'_'+G+'","asOf":"'+asOf+'","goal":"'+G+'","agent":"'+ag+'","fetchedAt":"'+asOf+'","data":{完整输出},"summary":"一句话","keyFields":{小摘录}}\nschema 只返回 {path,summary,keyFields}。'
const ap = (r, l) => r ? '\n【'+l+'】'+r.summary+(r.path?' → '+r.path:'') : '\n【'+l+'】⚠️ 数据缺失'

// ── 周期下限硬约束 ──
if (/^([23]日|隔日)/.test(String(period))) {
  log('周期<5日,拒绝选股,降级日内跟踪简报')
  phase('综合落盘')
  const report = await S('governor', () => agent('周期<5日窗口无统计优势,拒绝输出TopN买入清单,只输出"事件驱动日内跟踪简报"。\n## 投资目标\n'+goal+'\n## 你的任务\n1. WRITE output/'+asOf+'_日内跟踪简报.md,提示用户"2日窗口无统计优势,建议改>=5日或用单股深评"。\n2. WRITE '+RD+'/final.json(envelope,data含verdict:"拒绝选股",reason)。\n3. 更新 data/index.json(Read→push→Write)。\nschema 返回 {path,dataPath,oneLineConclusion:"拒绝选股·降级日内跟踪",confidence:"低",keyRisks:["2日窗口高噪音"]}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
  return report
}

let ctx = ''

// ── Phase 1: 宏观定调(含 prefetch) ──
phase('宏观定调')
log('🔄 启动宏观定调 — agent: macro-strategist')
const macro = await S('macro', () => agent(PREFETCH+P('macro-strategist','未来2周"天时"五维定调,输出顺风方向2-3。','用工具链取宏观读数+政策节点+情绪,锁定顺风方向(政策周期+市场热度双确认)。顺风方向将决定后续候选池的行业选择。', ctx), {agentType:'macro-strategist',schema:RET,label:'macro',phase:'宏观定调'}))
ctx = ap(macro,'宏观')
log('✅ 宏观定调完成 — ' + (macro?.summary || '空'))

// ── Phase 2: 候选池(承接宏观顺风方向) ──
phase('候选池')
log('🔄 启动候选池生成 — agent: sector-analyst')
const sector = await S('sector', () => agent(P('sector-analyst','在顺风方向内撒网,生成候选池>=30只。','Read '+macro.path+' 的 data.tailwinds 确定顺风行业。用 ifind_search_stocks(NL选股)+ifind_sector_data+cn_fetch.py rank 多源汇总30-50只去重,标注来源。cn_fetch 不覆盖的用 web-scraping fetch.py。1w账户优先<40元。', ctx), {agentType:'sector-analyst',schema:RET,label:'sector',phase:'候选池'}))
ctx += ap(sector,'候选池')
log('✅ 候选池完成 — ' + (sector?.summary || '空'))

// ── Phase 3: 流动性过滤(读候选池) ──
phase('流动性过滤')
log('🔄 启动流动性过滤 — agent: technical-liquidity')
const tech = await S('technical', () => agent(P('technical-liquidity','对全部候选批量做流动性硬门槛过滤+短线因子。','用 Read 读 '+sector.path+' 的 data.candidates 获取候选清单;用 ifind_get_stock_summary 或 cn_fetch.py factors 批量算5/10/20日动量+MA20+量价突破+amt20;硬门槛(成交额>=1亿/换手1-7%/市值>=30亿/非ST/近5-10-20日>30%透支剔除)。返pass/reject/factors。', ctx), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'流动性过滤'}))
ctx += ap(tech,'流动性')
log('✅ 流动性过滤完成 — ' + (tech?.summary || '空'))

// ── Phase 4: 并行评分(catalyst ∥ fundamentals,都读 tech 的 pass 清单) ──
phase('并行评分')
log('🔄 启动并行评分 — catalyst-scanner ∥ fundamentals-analyst')
const [cat, fund] = await parallel([
  () => S('catalyst', () => agent(P('catalyst-scanner','对过关票批量做催化兑现度+情绪+资金。','用 Read 读 '+tech.path+' 的 data.pass 获取过关票清单;用 ifind_search_news(必带time_start/end)+china-news get_stock_news 取催化+情绪+资金,判断兑现度。非结构化页面用 web-scraping fetch.py。返每只催化+整体情绪。', ctx), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'并行评分'})),
  () => S('fundamentals', () => agent(P('fundamentals-analyst','对过关票批量做财务排雷+估值锚。','用 Read 读 '+tech.path+' 的 data.pass 获取过关票清单;用 ifind_get_stock_financials(年报日期优先,max5主体可分批)+ifind_get_stock_shareholders 批量排雷+估值分位。硬雷点一票否决。', ctx), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'并行评分'})),
])
ctx += ap(cat,'催化') + ap(fund,'财务')
log('✅ 并行评分完成')
log('  催化: ' + (cat?.summary || '空'))
log('  财务: ' + (fund?.summary || '空'))

// ── Phase 4.5: 量化引擎(factor_engine + timing_engine) ──
phase('量化引擎')
// 收集过关票代码(从 technical agent 的 pass 清单)
const passCodes = tech?.keyFields?.passCodes || ''
if (passCodes) {
  log('🔄 启动量化引擎 — 对 '+passCodes.split(',').length+' 只过关票运行 factor_engine + timing_engine')
  // factor_engine: 七维因子计算 + z-score + 综合评分
  await S('factor_engine', async () => {
    const cmd = 'PYTHONIOENCODING=utf-8 python scripts/factor_engine.py --codes '+passCodes+' --data-dir '+RD+' --json \'{"regime":"'+(tech?.keyFields?.regime||'ranging')+'"}\' --output '+RD+'/factor_scores.json 2>&1'
    await agent('运行 Bash: '+cmd, {label:'factor_engine', phase:'量化引擎'})
    return {path: RD+'/factor_scores.json', summary:'因子评分完成'}
  })
  // timing_engine: 入场信号 + 动量质量 + 透支概率
  await S('timing_engine', async () => {
    const cmd = 'PYTHONIOENCODING=utf-8 python scripts/timing_engine.py --codes '+passCodes+' --output '+RD+'/timing_scores.json 2>&1'
    await agent('运行 Bash: '+cmd, {label:'timing_engine', phase:'量化引擎'})
    return {path: RD+'/timing_scores.json', summary:'入场评估完成'}
  })
  // sentiment_engine: 社交舆情热度 + 炒作风险 + 情绪拐点
  await S('sentiment_engine', async () => {
    const cmd = 'PYTHONIOENCODING=utf-8 python scripts/sentiment_engine.py --codes '+passCodes+' --data-dir '+RD+' --output '+RD+'/sentiment_scores.json 2>&1'
    await agent('运行 Bash: '+cmd, {label:'sentiment_engine', phase:'量化引擎'})
    return {path: RD+'/sentiment_scores.json', summary:'舆情评分完成'}
  })
  log('✅ 量化引擎完成 — factor_scores.json + timing_scores.json + sentiment_scores.json')
  ctx += '\n【量化引擎】factor_engine + timing_engine + sentiment_engine 输出 → '+RD+'/factor_scores.json + '+RD+'/timing_scores.json + '+RD+'/sentiment_scores.json'
} else {
  log('⚠️ 量化引擎跳过 — 无过关票代码,降级到LLM评分')
  ctx += '\n【量化引擎】⚠️ 跳过(无过关票代码)'
}

// ── Phase 5: 回测组合(综合全链 + portfolio_optimizer) ──
phase('回测组合')
log('🔄 启动回测组合 — agent: risk-portfolio')
const risk = await S('risk', () => agent(P('risk-portfolio','综合评分排序+回测(环境分层)+组合配置。\n\n## 量化引擎产出(必读)\n1. Read '+RD+'/factor_scores.json → 八维因子(含social维)z-score+综合评分\n2. Read '+RD+'/timing_scores.json → 入场信号+动量质量+透支概率+timing_score\n3. Read '+RD+'/sentiment_scores.json → 社交热度(social_heat)+炒作风险(hype_risk)+情绪拐点(heat_momentum)\n4. Read '+RD+'/regime.json → 市场环境+权重调整+风险预算\n\n## 你的任务\n1. 融合量化引擎产出 + LLM质化评分(催化/基本面/情绪),做最终排序\n2. 社交排序规则:\n   - social_heat>80 且 hype_risk>70 → 标记"过热预警",降权\n   - heat_momentum正 且 bull_ratio>0.6 → 社交顺风加分\n   - 社交热度与基本面背离(heat高+fundamentals低) → 警惕空气票\n3. 运行 Bash: PYTHONIOENCODING=utf-8 python scripts/portfolio_optimizer.py --codes {Top'+topN+'代码} --account '+acc.replace('w','0000')+' --risk-budget {regime.risk_budget} --output '+RD+'/backtest.json 2>&1\n4. Read '+RD+'/backtest.json 获取回测结果(3月非重叠窗口+环境分层胜率)\n5. timing_score < -10 的票不得排Top1(追涨票); 回测 verdict=rejected 不入TopN\n6. 组合分散(行业<=40%/催化同源<=50%/单票<=25%)', ctx), {agentType:'risk-portfolio',schema:RET,label:'risk',phase:'回测组合'}))
ctx += ap(risk,'组合')
log('✅ 回测组合完成 — ' + (risk?.summary || '空'))

// ── Phase 6: 综合落盘(含对抗审查+裁决+portfolio+notify) ──
phase('综合落盘')
log('🔄 启动综合落盘 — agent: governor (对抗审查+裁决+报告)')
const report = await S('governor', () => agent('综合全链产出写短周期选股报告+Top'+topN+'操作卡。\n\n## 投资目标\n'+goal+'\n\n## 全链产出(用 Read 读各 json)\n'+ctx+'\n'+history+'\n\n## 你的任务\n### 0. 收尾脚本(先跑)\nBash: python scripts/portfolio_tracker.py update 2>&1\n\n### 1. 对抗审查\n逐对检测矛盾,用 MCP 只读工具抽查验证:\n- Top1入场优势是否够高?(九洲药业教训:入场优势<12/25=追涨票,查entryScore)\n- Top1回测综合胜率(环境加权)是否最优?(驰宏锌锗教训)\n- 催化评分高 vs 已price-in?(查近5日涨幅+催化时间)\n- 动量质量:均匀涨还是单日暴涨?(查每日涨跌分布)\n- 技术动量强 vs 基本面红旗?\n- 组合催化同源是否超50%?\n- 1w账户仓位是否诚实标注分层建仓?\n- 社交热度高 vs 基本面空气?(hype_risk>70 且 fundamentals_score<40 → 纯炒作风险)\n- 社交热度拐点 vs 技术动量?(heat_momentum转负但价格仍涨 = 量价背离先兆)\n- Top1的social_heat排名是否合理?(过热票排Top1须额外审查hype_risk)\n对每对矛盾用 ifind 抽查关键数据(ROE/日K/催化),标注 ✅核实/⚠️偏差/❌矛盾。\n\n### 2. 报告输出\nTop1须入场优势>=18/25(好价格)+回测综合胜率排名前列+非主升浪末期。\n1. WRITE output/'+asOf+'_短周期2周推荐清单.md(结论先行→总体策略→各专项+逻辑关系→对抗审查结论+总督验证→操作→风险→免责),头一句话附核心假设置信度+回测达标。\n2. WRITE '+RD+'/final.json(envelope,data 含 oneLineConclusion/topN/totalPosition/confidence/keyRisks/contradictions/backtest/modules)。\n3. 更新 data/index.json(Read→push→Write)。\n4. 如果有 topN 推荐:WRITE '+RD+'/_rec.json 含 {topN, confidence},然后 Bash: python scripts/portfolio_tracker.py record --run-id '+asOf+'_'+G+' --json-file '+RD+'/_rec.json 2>&1\n\n### 3. 组合记录\nBash: python scripts/portfolio_tracker.py record --run-id '+asOf+'_'+G+' --json-file '+RD+'/_rec.json 2>&1\n(失败不影响返回)\n\nschema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
log('✅ 综合落盘完成')
log('🎉 Workflow 全部完成!')
if (report?.path) {
  log('📄 报告: '+report.path)
}
if (report?.topN?.length) {
  log('📊 Top'+report.topN.length+': '+report.topN.map(t => t.code+' '+t.name).join(', '))
}

return report
