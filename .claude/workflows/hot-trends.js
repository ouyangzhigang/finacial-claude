export const meta = {
  name: 'hot-trends',
  description: 'A股热门板块/潜力股推荐——情绪+资金主导:catalyst先识别主线(热榜/龙虎榜/涨停池)→sector板块成分→technical候选→fundamentals排雷→risk组合→governor报告。数据落盘data/不占上下文',
  phases: [
    {title: '热榜挖掘', detail: 'catalyst 识别主线'},
    {title: '板块成分', detail: 'sector 龙头+候选'},
    {title: '技术流动性', detail: 'technical 候选动量+流动性'},
    {title: '排雷', detail: 'fundamentals 财务排雷'},
    {title: '组合', detail: 'risk 组合配置'},
    {title: '综合落盘', detail: 'governor 报告+final.json'},
  ],
}

const RET = {type: 'object', properties: {path: {type: 'string'}, summary: {type: 'string'}, keyFields: {type: 'object'}}, required: ['path', 'summary']}
const GOV_RET = {type: 'object', properties: {path: {type: 'string'}, dataPath: {type: 'string'}, oneLineConclusion: {type: 'string'}, topN: {type: 'array', items: {type: 'object'}}, totalPosition: {type: 'string'}, confidence: {type: 'string'}, keyRisks: {type: 'array', items: {type: 'string'}}}, required: ['path', 'oneLineConclusion', 'confidence']}

const constraint = args.constraint || '热门板块潜力股综合推荐', topN = args.topN || 8, acc = args.account || '1w', asOf = args.asOf || 'YYYYMMDD'
const G = 'hot-trends', RD = 'data/runs/' + asOf + '_' + G
const goal = '热门板块/潜力股: Top' + topN + ' 约束[' + constraint + '] 账户' + acc + ' | 基准日' + asOf

const P = (agent, task, extra, ctx) => task + '\n\n## 投资目标\n' + goal + '\n\n## 前序环节产出(承接,勿无视;如需细节用 Read 读对应 json 的 data 字段)\n' + (ctx || '(本环节为起点,无前序)') + '\n\n## 你的任务\n' + extra + '\n\n## 数据落盘(节约上下文,必须)\n把完整结构化输出 WRITE 到 ' + RD + '/' + agent + '.json(目录不存在先创建),envelope:{"runId":"' + asOf + '_' + G + '","asOf":"' + asOf + '","goal":"' + G + '","agent":"' + agent + '","fetchedAt":"' + asOf + '","data":{完整输出},"summary":"一句话","keyFields":{小摘录如 themes/codes}}\nschema 只返回 {path, summary, keyFields},勿把完整 data 塞进返回值。'

let ctx = ''

phase('热榜挖掘')
const cat = await agent(P('catalyst-scanner', '多源挖掘今日主线:热榜+龙虎榜+涨停池+连板梯队+市场概览,识别热门板块与情绪温度。', "用 ifind_search_news(必带time_start/end)+china-news+ 'PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python scripts/hot_trend_dig.py' (Step4-5涨停池+市场概览可用,Step1-3 SSL挂则curl龙虎榜 RPT_DAILYBILLBOARD_DETAILS)+cn_fetch.py rank。输出主线主题(热榜)+情绪(涨停/封板率/炸板率/连板高度)+资金方向。", ctx), {agentType: 'catalyst-scanner', schema: RET, label: 'catalyst', phase: '热榜挖掘'})
ctx = '【主线/情绪】' + cat.summary + ' → ' + cat.path

phase('板块成分')
const sector = await agent(P('sector-analyst', '承接主线,挖板块成分+龙头+候选池。', '用 Read 读 ' + cat.path + ' 的 data.mainThemes 取主线;对主线主题用 ifind_sector_data(一次一板块)+cn_fetch.py rank 取板块成分+龙头+5日涨幅排名;候选优先<40元(1w账户)。', ctx), {agentType: 'sector-analyst', schema: RET, label: 'sector', phase: '板块成分'})
ctx += '\n【板块/候选】' + sector.summary + ' → ' + sector.path

phase('技术流动性')
const tech = await agent(P('technical-liquidity', '对候选批量做流动性过滤+动量。', '用 Read 读 ' + sector.path + ' 的 data.candidates 取候选;用 ifind_get_stock_summary或 cn_fetch.py factors 批量算动量+流动性;硬门槛过滤(成交额>=1亿/换手1-7%/非ST非次新/近5-20日任一>30%透支剔除)。返pass/reject/factors。', ctx), {agentType: 'technical-liquidity', schema: RET, label: 'technical', phase: '技术流动性'})
ctx += '\n【技术】' + tech.summary + ' → ' + tech.path

phase('排雷')
const fund = await agent(P('fundamentals-analyst', '对过关票批量排雷。', '用 Read 读 ' + tech.path + ' 的 data.pass 取过关清单;用 ifind_get_stock_financials+ifind_get_stock_shareholders 批量排雷(商誉/质押/造假),硬雷点剔除。返每只verdict。', ctx), {agentType: 'fundamentals-analyst', schema: RET, label: 'fundamentals', phase: '排雷'})
ctx += '\n【财务】' + fund.summary + ' → ' + fund.path

phase('组合')
const risk = await agent(P('risk-portfolio', '组合配置Top' + topN + '。', '用 Read 读前序各 json 的 data 取细节;按情绪/资金主导(权重高于基本面)排Top' + topN + ';组合分散(行业<=40%/催化同源<=50%);1w手数致分层建仓须标注。', ctx), {agentType: 'risk-portfolio', schema: RET, label: 'risk', phase: '组合'})
ctx += '\n【组合】' + risk.summary + ' → ' + risk.path

phase('综合落盘')
const report = await agent('综合全链写热门板块潜力股报告。\n\n## 投资目标\n' + goal + '\n\n## 全链产出(承接,勿无视;用 Read 读各 json 的 data 取细节)\n' + ctx + '\n\n## 你的任务\n1. WRITE 报告到 output/' + asOf + '_热门板块潜力股综合推荐.md(目录不存在先创建),按 governor 报告结构与命名规范(结论先行→总体策略→各专项核心细节+逻辑关系→专业知识点→操作→风险情景→免责)写,报告头一句话结论附情绪温度+置信度。\n2. WRITE 结构化最终到 ' + RD + '/final.json(envelope,data含oneLineConclusion/topN/totalPosition/confidence/keyRisks/mainThemes/modules各环节path)。\n3. 更新 data/index.json(数组push {runId,asOf,goal,path:dataPath,headline,confidence,fetchedAt})。\nschema 返回 {path, dataPath, oneLineConclusion, topN, totalPosition, confidence, keyRisks}。', {agentType: 'governor', schema: GOV_RET, label: 'governor', phase: '综合落盘'})
return report
