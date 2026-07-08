export const meta = {
  name: 'sentiment-trend-picks',
  description: 'A股舆情与趋势预判选股——catalyst先挖掘舆情/趋势识别主线+候选→macro验证趋势是否顺风→sector板块+候选→technical→fundamentals→risk组合+回测→governor报告。lead with 舆情,再用各维度验证,防纯炒作空气票。数据落盘data/不占上下文',
  phases: [
    {title: '舆情挖掘', detail: 'catalyst 识别趋势+候选'},
    {title: '趋势验证', detail: 'macro 趋势是否顺风'},
    {title: '板块候选', detail: 'sector 趋势板块+候选'},
    {title: '技术流动性', detail: 'technical 候选动量+流动性'},
    {title: '排雷', detail: 'fundamentals 排雷'},
    {title: '组合回测', detail: 'risk 组合+回测'},
    {title: '综合落盘', detail: 'governor 报告+final.json'},
  ],
}

const RET = {type: 'object', properties: {path: {type: 'string'}, summary: {type: 'string'}, keyFields: {type: 'object'}}, required: ['path', 'summary']}
const GOV_RET = {type: 'object', properties: {path: {type: 'string'}, dataPath: {type: 'string'}, oneLineConclusion: {type: 'string'}, topN: {type: 'array', items: {type: 'object'}}, totalPosition: {type: 'string'}, confidence: {type: 'string'}, keyRisks: {type: 'array', items: {type: 'string'}}}, required: ['path', 'oneLineConclusion', 'confidence']}

const keyword = args.keyword || '', trend = args.trend || '', topN = args.topN || 5, acc = args.account || '1w', asOf = args.asOf || 'YYYYMMDD'
const G = 'sentiment-trend-picks', RD = 'data/runs/' + asOf + '_' + G
const focus = keyword || trend || '近期舆情热点'
const goal = '舆情趋势预判选股: 关键词[' + focus + '] Top' + topN + ' 账户' + acc + ' | 基准日' + asOf

const P = (agent, task, extra, ctx) => task + '\n\n## 投资目标\n' + goal + '\n\n## 前序环节产出(承接,勿无视;如需细节用 Read 读对应 json 的 data 字段)\n' + (ctx || '(本环节为起点,无前序)') + '\n\n## 你的任务\n' + extra + '\n\n## 数据落盘(节约上下文,必须)\n把完整结构化输出 WRITE 到 ' + RD + '/' + agent + '.json(目录不存在先创建),envelope:{"runId":"' + asOf + '_' + G + '","asOf":"' + asOf + '","goal":"' + G + '","agent":"' + agent + '","fetchedAt":"' + asOf + '","data":{完整输出},"summary":"一句话","keyFields":{小摘录如 trends/codes}}\nschema 只返回 {path, summary, keyFields},勿把完整 data 塞进返回值。'

let ctx = ''

phase('舆情挖掘')
const cat = await agent(P('catalyst-scanner', '舆情挖掘:从新闻语义+热榜+社交情绪识别趋势+候选股。', '用 ifind_search_news(必带time_start/end,query含"' + focus + '")+china-news+hot_trend_dig.py(涨停池/热榜)识别2-3个趋势主题,每个趋势给信号强度(强/中/弱)+信息源+候选股代码。警惕纯炒作(无基本面/无政策=空气票),给情绪温度+市场怀疑度(skepticism,高怀疑=趋势未price-in)。', ctx), {agentType: 'catalyst-scanner', schema: RET, label: 'catalyst', phase: '舆情挖掘'})
ctx = '【舆情趋势】' + cat.summary + ' → ' + cat.path

phase('趋势验证')
const macro = await agent(P('macro-strategist', '验证舆情趋势是否与宏观顺风方向一致(防逆风炒作)。', '用 Read 读 ' + cat.path + ' 的 data.trends 取趋势;用 ifind_index_data+ifind_search_news+ifind_get_edb_data 判断上述趋势是否落在宏观顺风方向(政策周期+市场热度双确认)。trendAligned=true 才继续推标的,false 则降权或转观察。', ctx), {agentType: 'macro-strategist', schema: RET, label: 'macro', phase: '趋势验证'})
ctx += '\n【趋势验证】' + macro.summary + ' → ' + macro.path

phase('板块候选')
const sector = await agent(P('sector-analyst', '承接趋势,挖对应板块+候选池。', '用 Read 读 ' + cat.path + ' 的 data.trends.candidateCodes + ' + macro.path + ' 的 data.trendAligned;对验证通过的趋势,用 ifind_sector_data+ifind_search_stocks(细分板块)+手动龙头 取板块成分+候选,优先<40元(1w)。合并舆情候选+板块候选去重。', ctx), {agentType: 'sector-analyst', schema: RET, label: 'sector', phase: '板块候选'})
ctx += '\n【候选】' + sector.summary + ' → ' + sector.path

phase('技术流动性')
const tech = await agent(P('technical-liquidity', '对候选批量做流动性过滤+动量(趋势启动信号)。', '用 Read 读 ' + sector.path + ' 的 data.candidates 取候选;用 ifind_get_stock_summary或 cn_fetch.py factors 批量算动量+流动性;硬门槛过滤;重点识别趋势启动特征(站上MA20+放量突破+m5正但未透支)。返pass/reject/factors。', ctx), {agentType: 'technical-liquidity', schema: RET, label: 'technical', phase: '技术流动性'})
ctx += '\n【技术】' + tech.summary + ' → ' + tech.path

phase('排雷')
const fund = await agent(P('fundamentals-analyst', '对过关票批量排雷(防空气票)。', '用 Read 读 ' + tech.path + ' 的 data.pass 取过关清单;用 ifind_get_stock_financials+ifind_get_stock_shareholders 批量排雷;重点:纯炒作票(无业绩+高估值+无机构持仓)直接剔除。返每只verdict。', ctx), {agentType: 'fundamentals-analyst', schema: RET, label: 'fundamentals', phase: '排雷'})
ctx += '\n【排雷】' + fund.summary + ' → ' + fund.path

phase('组合回测')
const risk = await agent(P('risk-portfolio', '组合配置+回测验证预判。', '用 Read 读前序各 json 的 data 取细节;排Top' + topN + '(趋势强度+技术启动+排雷通过);用 ifind_get_stock_summary近1月日K回测5日窗口(胜率>=55%/均收>=3%/回撤<=8%);回测3项全不达标一票否决(驰宏锌锗纪律);组合分散(行业<=40%/催化同源<=50%)。', ctx), {agentType: 'risk-portfolio', schema: RET, label: 'risk', phase: '组合回测'})
ctx += '\n【组合/回测】' + risk.summary + ' → ' + risk.path

phase('综合落盘')
const report = await agent('综合全链写舆情趋势预判选股报告。\n\n## 投资目标\n' + goal + '\n\n## 全链产出(承接,勿无视;用 Read 读各 json 的 data 取细节)\n' + ctx + '\n\n## 你的任务\n1. WRITE 报告到 output/' + asOf + '_舆情趋势预判选股.md(目录不存在先创建),按 governor 报告结构与命名规范(结论先行→总体策略→各专项核心细节+逻辑关系→专业知识点→操作→风险情景→免责)写,预判置信度基于趋势强度+宏观对齐+回测达标,风险含趋势证伪触发条件。报告头一句话结论附趋势+置信度+回测达标情况。\n2. WRITE 结构化最终到 ' + RD + '/final.json(envelope,data含oneLineConclusion/topN/totalPosition/confidence/keyRisks/trends/modules各环节path)。\n3. 更新 data/index.json(数组push {runId,asOf,goal,path:dataPath,headline,confidence,fetchedAt})。\nschema 返回 {path, dataPath, oneLineConclusion, topN, totalPosition, confidence, keyRisks}。', {agentType: 'governor', schema: GOV_RET, label: 'governor', phase: '综合落盘'})
return report
