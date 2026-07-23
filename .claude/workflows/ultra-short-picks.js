export const meta = {
  name: 'ultra-short-picks',
  description: 'A股超短1日选股——市场温度→事件催化→涨停池→龙虎榜→舆情资金→超短因子→胜率校准→governor裁决',
  phases: [
    {title: '市场温度', detail: '判断是否适合超短交易'},
    {title: '事件催化', detail: '当日最强题材/政策/业绩方向'},
    {title: '涨停池+龙虎榜', detail: '封板质量+机构/游资信号'},
    {title: '舆情+资金', detail: 'social_heat+主力资金+北向'},
    {title: '超短因子', detail: 'ultra_factor.py 6维评分'},
    {title: '胜率校准', detail: '同类封板模式历史溢价概率'},
    {title: '综合落盘', detail: 'governor裁决+报告+操作卡'},
  ],
}

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const topN=args.topN||3, acc=args.account||'1w', rp=args.riskPref||'积极', asOf=args.asOf||'YYYYMMDD'
const G='ultra-short-picks', RD='data/runs/'+asOf+'_'+G
const goal='超短1日选股: Top'+topN+' 风险'+rp+' 账户'+acc+' | 基准日'+asOf+' | 尾盘入场→次日冲高出'

const S = async (name, fn) => {
  try { const r = await fn(); if (r) return r } catch (e) {
    const msg = (e?.message||String(e)).slice(0,200)
    return {path:'',summary:name+' 失败: '+msg,keyFields:{_error:true}}
  }
  return {path:'',summary:name+' 返回空',keyFields:{_error:'empty'}}
}
const O = (ag) => '\nWRITE '+RD+'/'+ag+'.json; envelope:{"agent":"'+ag+'","asOf":"'+asOf+'","data":{...}}; schema→{path,summary,keyFields}'
const P = (ag, task, extra, ctx) => task+'\n# 目标\n'+goal+'\n# 前序\n'+(ctx||'(起点)')+'\n# 任务\n'+extra+O(ag)
const ap = (r, l) => r ? '\n【'+l+'】'+r.summary+(r.path?' → '+r.path:'') : '\n【'+l+'】⚠️ 数据缺失'

let ctx = ''

// ════════════════════════════════════════════
// Phase 0: 市场温度计
// ════════════════════════════════════════════
phase('市场温度')
log('🌡️ 市场温度计 — 判断是否适合超短交易')
await S('market_radar', async () => {
  const cmd = 'PYTHONIOENCODING=utf-8 python scripts/market_radar.py --section zt,capital,index 2>&1'
  await agent('⚠️ 只运行不调试。\nBash: '+cmd+'\nRead 输出获取涨停家数/封板率/炸板率/连板高度/赚钱效应/成交额。\n计算市场温度(0-100): 涨停家数+封板率+炸板率+连板高度+赚钱效应 各20分。\n温度<30→拒绝选股, 直接返回。温度30-60→谨慎1-2只。温度60-80→正常2-3只。温度>80→警惕过热1-2只。', {label:'market_radar', phase:'市场温度'})
  return {path: RD+'/market_radar.json', summary:'市场温度已采集'}
})
ctx += '\n【市场温度】market_radar.py → '+RD+'/market_radar.json'

// ════════════════════════════════════════════
// Phase 1: 事件催化扫描
// ════════════════════════════════════════════
phase('事件催化')
log('📰 事件催化扫描 — 新浪7x24+东财新闻')
await S('catalyst_scan', async () => {
  const cmd1 = 'PYTHONIOENCODING=utf-8 python scripts/market_radar.py --section news 2>&1'
  const cmd2 = 'PYTHONIOENCODING=utf-8 python scripts/cn_fetch.py --keyword 涨停 2>&1'
  await agent('⚠️ 只运行不调试。\n1. Bash: '+cmd1+'\n2. Bash: '+cmd2+'\n从新闻中提取当日最强催化方向(政策/业绩/订单/重组), 标注政策级别(国务院>部委>地方)和新闻新鲜度(小时)。输出Top3催化方向。', {label:'catalyst_scan', phase:'事件催化'})
  return {path: RD+'/catalyst_scan.json', summary:'事件催化扫描完成'}
})
ctx += ap({path:RD+'/catalyst_scan.json',summary:'事件催化'}, '催化')

// ════════════════════════════════════════════
// Phase 2&3: 涨停池+龙虎榜 (并行)
// ════════════════════════════════════════════
phase('涨停池+龙虎榜')
log('📊 涨停池+龙虎榜 并行分析')
const [zt, lhb] = await parallel([
  () => S('zt_pool', async () => {
    const cmd = 'PYTHONIOENCODING=utf-8 python scripts/market_radar.py --section zt 2>&1'
    await agent('⚠️ 只运行不调试。\nBash: '+cmd+'\n从涨停池提取每只票: 封板时间(早=好)/封单量(大=好)/开板次数(0=满分)/连板高度(2-4板最优)/板块涨停家数。标注一字板(不追)和尾盘封板(弱)。', {label:'zt_pool', phase:'涨停池+龙虎榜'})
    return {path: RD+'/zt_pool.json', summary:'涨停池分析完成'}
  }),
  () => S('lhb_deep', async () => {
    const cmd = 'PYTHONIOENCODING=utf-8 python scripts/hot_trend_dig.py 2>&1'
    await agent('⚠️ 只运行不调试。\nBash: '+cmd+'\n从龙虎榜提取每只票: 机构净买入额/知名游资(华鑫上海分/中信上海分等)/拉萨席位(扣分)/净买额占成交额比。拉萨主导的票标记为不买。', {label:'lhb_deep', phase:'涨停池+龙虎榜'})
    return {path: RD+'/lhb_deep.json', summary:'龙虎榜分析完成'}
  }),
])
ctx += ap(zt,'涨停池') + ap(lhb,'龙虎榜')

// ════════════════════════════════════════════
// Phase 4: 舆情+资金融合
// ════════════════════════════════════════════
phase('舆情+资金')
log('🔥 舆情+资金融合 — sentiment_engine + capital_flow')
const codes = zt?.keyFields?.codes || lhb?.keyFields?.codes || ''
await S('sentiment', async () => {
  if (!codes) return {path:'', summary:'无代码,跳过'}
  const cmd = 'PYTHONIOENCODING=utf-8 python scripts/sentiment_engine.py --codes '+codes+' --data-dir '+RD+' --output '+RD+'/sentiment_scores.json 2>&1'
  await agent('⚠️ 只运行不调试。\nBash: '+cmd+'\nRead '+RD+'/sentiment_scores.json 确认。', {label:'sentiment', phase:'舆情+资金'})
  return {path: RD+'/sentiment_scores.json', summary:'舆情评分完成'}
})
await S('capital', async () => {
  const cmd = 'PYTHONIOENCODING=utf-8 python scripts/market_radar.py --section capital 2>&1'
  await agent('⚠️ 只运行不调试。\nBash: '+cmd+'\n提取主力净流入/大单占比/北向资金。', {label:'capital', phase:'舆情+资金'})
  return {path: RD+'/capital_flow.json', summary:'资金流分析完成'}
})
ctx += '\n【舆情+资金】sentiment_engine + capital_flow → '+RD+'/'

// ════════════════════════════════════════════
// Phase 5: 超短因子引擎
// ════════════════════════════════════════════
phase('超短因子')
log('🧮 超短因子引擎 — ultra_factor.py 6维评分')
await S('ultra_factor', async () => {
  const cmd = 'PYTHONIOENCODING=utf-8 python scripts/ultra_factor.py --date '+asOf+' --data-dir '+RD+' --output '+RD+'/ultra_scores.json --top-n '+topN+' 2>&1'
  await agent('⚠️ 只运行不调试。\nBash: '+cmd+'\nRead '+RD+'/ultra_scores.json 获取评分结果。\n检查 market.temperature: 若<30°则报告拒绝选股。\n检查 gates_summary: 确认硬门过滤结果。\n检查 top_n: 获取综合评分TopN。', {label:'ultra_factor', phase:'超短因子'})
  return {path: RD+'/ultra_scores.json', summary:'超短因子评分完成'}
})
ctx += '\n【超短因子】ultra_factor.py 6维评分 → '+RD+'/ultra_scores.json'

// ════════════════════════════════════════════
// Phase 6: 胜率校准
// ════════════════════════════════════════════
phase('胜率校准')
log('🎲 胜率校准 — 同类封板模式历史溢价概率')
await S('win_rate', async () => {
  await agent('Read '+RD+'/ultra_scores.json 获取 top_n 候选。\n对每只候选: 根据封板时间段(早盘/午盘/尾盘)+连板高度(首板/2板/3板)+板块+市场温度, 估计同类模式的次日溢价概率。\n参考值: 早盘封板首板→次日溢价概率65-75%; 午盘封板2连板→55-65%; 尾盘封板→40-50%。\n输出每只票的: 预期次日涨幅范围+胜率+置信度。', {label:'win_rate', phase:'胜率校准'})
  return {path: RD+'/win_rate.json', summary:'胜率校准完成'}
})
ctx += '\n【胜率校准】→ '+RD+'/win_rate.json'

// ════════════════════════════════════════════
// Phase 7: Governor 裁决
// ════════════════════════════════════════════
phase('综合落盘')
log('🎯 综合落盘 — governor 裁决+报告')
const report = await S('governor', () => agent(
  '超短1日选股最终裁决+操作卡。\n\n投资目标:'+goal+'\n\n全链产出:'+ctx+'\n\n' +
  '## 🚫 超短硬门(不可override)\n' +
  '1.一字板→不推(买不到,买到就是坑)\n2.6连板以上→不推(接力风险极大)\n3.尾盘炸板→不推(封板失败)\n4.拉萨主导→不推(散户接盘)\n5.成交额<1亿→不推(流动性不足)\n6.ST股票→不推\n' +
  'Read '+RD+'/ultra_scores.json 获取超短因子评分。\n' +
  'Read '+RD+'/win_rate.json 获取胜率校准。\n' +
  '## 任务\n' +
  '1. 对抗审查: Top1封板质量是否最优? 机构/游资是否净买入? 舆情是否过热(hype>70)? 板块效应是否支撑?\n' +
  '2. 写报告: WRITE output/'+asOf+'_超短1日操作卡.md\n' +
  '   结构: 结论先行→市场温度→TopN逐一(代码/封板时间/封单量/连板/机构净买/舆情/预期涨幅/胜率)→操作卡(入场区间/止损/目标)→风控规则→免责声明\n' +
  '3. 操作卡: 尾盘14:30-15:00入场, 次日开盘冲高出。入场价以封板价为准(若开板则等重新封板)。止损: 次日开盘价-3%。\n' +
  '4. 落盘: WRITE '+RD+'/final.json\n' +
  '5. 返回schema: {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。',
  {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}
))
log('✅ 综合落盘完成')
if (report?.path) log('📄 报告: '+report.path)
if (report?.topN?.length) log('📊 Top'+report.topN.length+': '+report.topN.map(t => t.code+' '+t.name).join(', '))

return report