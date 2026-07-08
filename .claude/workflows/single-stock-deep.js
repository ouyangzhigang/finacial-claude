export const meta = {
  name: 'single-stock-deep',
  description: 'A股单股深度分析——6专精agent+governor漏斗式递进,数据落盘data/不占上下文,输出深度分析报告',
  phases: [
    {title: '宏观定调', detail: 'macro-strategist 天时'},
    {title: '行业地位', detail: 'sector-analyst 行业+同业'},
    {title: '财务排雷', detail: 'fundamentals-analyst 财务+估值+排雷'},
    {title: '技术流动性', detail: 'technical-liquidity 技术位+流动性'},
    {title: '催化情绪', detail: 'catalyst-scanner 催化+资金+情绪'},
    {title: '风险估值', detail: 'risk-portfolio 估值区间+情景'},
    {title: '综合落盘', detail: 'governor 综合写报告+final.json'},
  ],
}

const RET = {type: 'object', properties: {path: {type: 'string'}, summary: {type: 'string'}, keyFields: {type: 'object'}}, required: ['path', 'summary']}
const GOV_RET = {type: 'object', properties: {path: {type: 'string'}, dataPath: {type: 'string'}, oneLineConclusion: {type: 'string'}, topN: {type: 'array', items: {type: 'object'}}, totalPosition: {type: 'string'}, confidence: {type: 'string'}, keyRisks: {type: 'array', items: {type: 'string'}}}, required: ['path', 'oneLineConclusion', 'confidence']}

const t = args.ticker || '', n = args.name || '', acc = args.account || '1w', hor = args.horizon || '波段', rp = args.riskPref || '稳健', pos = args.position || '无持仓', asOf = args.asOf || 'YYYYMMDD'
const G = 'single-stock-deep', RD = 'data/runs/' + asOf + '_' + G
const goal = '单股深评: ' + t + ' ' + n + ' | 账户' + acc + ' 周期' + hor + ' 风险' + rp + ' 持仓' + pos + ' | 基准日' + asOf

const P = (agent, task, extra, ctx) => task + '\n\n## 投资目标\n' + goal + '\n\n## 前序环节产出(承接,勿无视;如需细节用 Read 读对应 json 的 data 字段)\n' + (ctx || '(本环节为起点,无前序)') + '\n\n## 你的任务\n' + extra + '\n\n## 数据落盘(节约上下文,必须)\n把完整结构化输出 WRITE 到 ' + RD + '/' + agent + '.json(目录不存在先创建),envelope:{"runId":"' + asOf + '_' + G + '","asOf":"' + asOf + '","goal":"' + G + '","agent":"' + agent + '","fetchedAt":"' + asOf + '","data":{完整输出},"summary":"一句话","keyFields":{小摘录如 codes/verdicts/tailwinds}}\nschema 只返回 {path, summary, keyFields},勿把完整 data 塞进返回值。'

let ctx = ''

phase('宏观定调')
const macro = await agent(P('macro-strategist', '对该股所属行业做"天时"五维定调(周期/货币流动性/国际地缘/政策/情绪),输出顺风方向与占优风格。', '用工具链(iFind主→wind→akshare→curl)取该股所属行业宏观读数+政策节点+情绪,输出顺风方向2-3。', ctx), {agentType: 'macro-strategist', schema: RET, label: 'macro', phase: '宏观定调'})
ctx = '【宏观】' + macro.summary + ' → ' + macro.path

phase('行业地位')
const sector = await agent(P('sector-analyst', '分析该股的行业地位、同业竞争、板块强度。', '承接宏观顺风,定位该股在所属板块的龙头/跟风/边缘角色,列同业可比。', ctx), {agentType: 'sector-analyst', schema: RET, label: 'sector', phase: '行业地位'})
ctx += '\n【行业】' + sector.summary + ' → ' + sector.path

phase('财务排雷')
const fund = await agent(P('fundamentals-analyst', '该股财务画像+估值锚+排雷。', '用 ifind_get_stock_financials(年报日期优先)+ifind_get_stock_summary+ifind_get_stock_shareholders 取财务+估值分位+排雷,硬雷点(商誉/质押/造假)一票否决。', ctx), {agentType: 'fundamentals-analyst', schema: RET, label: 'fundamentals', phase: '财务排雷'})
ctx += '\n【财务】' + fund.summary + ' → ' + fund.path

phase('技术流动性')
const tech = await agent(P('technical-liquidity', '该股流动性硬门槛+短线因子+技术位。', '用 ifind_get_stock_summary 取近1月日K算5/10/20日动量+MA20+量价突破;流动性硬门槛(成交额>=1亿/换手1-7%/市值>=30亿)不过关直接剔除。盘中价须收盘复核。', ctx), {agentType: 'technical-liquidity', schema: RET, label: 'technical', phase: '技术流动性'})
ctx += '\n【技术】' + tech.summary + ' → ' + tech.path

phase('催化情绪')
const cat = await agent(P('catalyst-scanner', '该股催化日历+兑现度+情绪+资金。', '用 ifind_search_news(必带time_start/time_end)+china-news get_stock_news+curl龙虎榜 取催化+情绪+资金,判断兑现度(近5日涨>15%半兑现/>30%透支)。', ctx), {agentType: 'catalyst-scanner', schema: RET, label: 'catalyst', phase: '催化情绪'})
ctx += '\n【催化】' + cat.summary + ' → ' + cat.path

phase('风险估值')
const risk = await agent(P('risk-portfolio', '该股估值区间+情景预演。', '综合前五模块(用Read读各json取细节),给估值区间(低/中/高)+突破/震荡/破位三情景应对。单股深评不需TopN排序,但需操作区间。', ctx), {agentType: 'risk-portfolio', schema: RET, label: 'risk', phase: '风险估值'})
ctx += '\n【风险估值】' + risk.summary + ' → ' + risk.path

phase('综合落盘')
const report = await agent('综合全链产出写单股深评报告。\n\n## 投资目标\n' + goal + '\n\n## 全链产出(承接,勿无视;用 Read 读各 json 的 data 字段取细节)\n' + ctx + '\n\n## 你的任务\n按矛盾调和矩阵综合六模块,若多环红(技术+资金双红)不得给建仓价位只给观望+触发条件。\n1. WRITE 人类报告到 output/' + t + '_' + asOf + '_深度分析报告.md(目录不存在先创建),按 governor 报告结构与命名规范(结论先行→总体策略→各专项核心细节+逻辑关系→专业知识点→操作→风险情景→免责)写,报告头一句话结论附核心假设置信度。\n2. WRITE 结构化最终到 ' + RD + '/final.json(同 envelope,data 含 oneLineConclusion/topN/totalPosition/confidence/keyRisks/modules各环节path)。\n3. 更新 data/index.json(数组,元素 {runId,asOf,goal,path:dataPath,headline,confidence,fetchedAt};Read 现有→push→Write,不存在则建空数组)。\nschema 返回 {path, dataPath, oneLineConclusion, topN, totalPosition, confidence, keyRisks}。', {agentType: 'governor', schema: GOV_RET, label: 'governor', phase: '综合落盘'})
return report
