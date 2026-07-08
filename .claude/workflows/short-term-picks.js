export const meta = {
  name: 'short-term-picks',
  description: 'A股短周期(2周)潜力价值股推荐——漏斗式选股:宏观→候选池→流动性过滤→并行评分(catalyst+fundamentals)→回测+组合→governor操作卡。数据落盘data/不占上下文',
  phases: [
    {title: '宏观定调', detail: '顺风方向'},
    {title: '候选池', detail: 'sector 30-50只'},
    {title: '流动性过滤', detail: 'technical 批量硬门槛'},
    {title: '并行评分', detail: 'catalyst+fundamentals 并行'},
    {title: '回测组合', detail: 'risk 评分排序+回测+组合'},
    {title: '综合落盘', detail: 'governor 操作卡+报告+final.json'},
  ],
}

const RET = {type: 'object', properties: {path: {type: 'string'}, summary: {type: 'string'}, keyFields: {type: 'object'}}, required: ['path', 'summary']}
const GOV_RET = {type: 'object', properties: {path: {type: 'string'}, dataPath: {type: 'string'}, oneLineConclusion: {type: 'string'}, topN: {type: 'array', items: {type: 'object'}}, totalPosition: {type: 'string'}, confidence: {type: 'string'}, keyRisks: {type: 'array', items: {type: 'string'}}}, required: ['path', 'oneLineConclusion', 'confidence']}

const topN = args.topN || 5, period = args.period || '2周', acc = args.account || '1w', rp = args.riskPref || '稳健偏积极', pos = args.position || '无持仓', asOf = args.asOf || 'YYYYMMDD'
const G = 'short-term-picks', RD = 'data/runs/' + asOf + '_' + G
const goal = '短周期选股: Top' + topN + ' 周期' + period + ' 风险' + rp + ' 账户' + acc + ' 持仓' + pos + ' | 基准日' + asOf

// 本机数据源状态(2026-07-08 实测):iFind/akshare/wind MCP SSL 全挂,必须走 curl -k/新浪/china-news 降级链。
// 每个 agent prompt 前置此块,避免子 agent 在 iFind SSL 上重试卡死。
const DATA_STATUS = '\n## ⚠️ 本机数据源状态(实测·按此降级,勿在 iFind 上重试)\n' +
  '- **iFind MCP**: SSL 证书验证失败(CERTIFICATE_VERIFY_FAILED) → **跳过,不要调用 mcp__ifind__***\n' +
  '- **akshare MCP**: 走东方财富 push2,同 SSL 挂 → **跳过**\n' +
  '- **wind MCP**: 常全挂 → **跳过**(除非已设 WIND_SSL_NO_VERIFY)\n' +
  '- **可用通道(按优先)**:\n' +
  '  1. `curl -k -s -H "User-Agent: Mozilla/5.0" "https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date=YYYYMMDD"` → 涨停池(-k 跳证书;字段 c代码 n名称 zdp涨跌幅 amount成交额 lbc连板 ltsz流通市值)\n' +
  '  2. `curl -k -s "http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=30&po=1&fid=f3&fs=m:90+t:2&fields=f2,f3,f12,f14"` → 概念板块涨幅(-k;f12代码 f14名称 f3涨跌幅)\n' +
  '  3. `curl -s "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol=sh600519&scale=240&ma=no&datalen=30"` → **新浪日K首选**(http 不走 SSL;返回[{day,open,high,low,close,volume}];算 m5/m10/m20/MA20 用 close 序列)\n' +
  '  4. `curl -s "http://qt.gtimg.cn/q=sh603118"` → 腾讯实时快照(GBK,http;字段索引:1名称 2代码 3现价 4昨收 5今开 31涨跌额 32涨跌幅 36成交量 37成交额 38换手 39PE 44流通市值 45总市值;用 python .decode(\'gbk\') 后 split(\'~\'))\n' +
  '  5. `python scripts/cn_fetch.py squote sh603118` → 腾讯单股报价(SSL 自处理,可用;**注意 factors/kline 子命令有 bug,勿用**)\n' +
  '  6. china-news MCP `get_stock_news`(ticker="603118") → 个股新闻+催化(**可用,不需分类器**)\n' +
  '- **日K首选新浪 API**(cn_fetch factors bug + 东方财富 push2his 502 + 腾讯 web.ifzq.gtimg.cn 302,都不要用)\n' +
  '- secid 规则:沪市 `1.代码`,深市 `0.代码`;新浪/腾讯前缀:沪 sh 深 sz\n' +
  '- **Bash/Write 若被 glm 分类器拦(间歇性 "temporarily unavailable")**:等 5-10 秒重试同一命令,勿卡住勿换路\n' +
  '- 连续 2 层挂 → 输出中显式标注"数据缺失"并继续,勿崩溃\n\n'

const P = (agent, task, extra, ctx) => task + DATA_STATUS + '\n\n## 投资目标\n' + goal + '\n\n## 前序环节产出(承接,勿无视;如需细节用 Read 读对应 json 的 data 字段)\n' + (ctx || '(本环节为起点,无前序)') + '\n\n## 你的任务\n' + extra + '\n\n## 数据落盘(节约上下文,必须)\n把完整结构化输出 WRITE 到 ' + RD + '/' + agent + '.json(目录不存在先创建),envelope:{"runId":"' + asOf + '_' + G + '","asOf":"' + asOf + '","goal":"' + G + '","agent":"' + agent + '","fetchedAt":"' + asOf + '","data":{完整输出},"summary":"一句话","keyFields":{小摘录如 codes/verdicts/tailwinds}}\nschema 只返回 {path, summary, keyFields},勿把完整 data 塞进返回值。'

if (String(period).match(/^[23]日|隔日/)) {
  log('周期<5日,拒绝选股,降级日内跟踪简报')
  phase('综合落盘')
  const report = await agent('周期<5日窗口无统计优势,拒绝输出TopN买入清单,只输出"事件驱动日内跟踪简报"(观察位/触发位,无买入区间/仓位)。\n## 投资目标\n' + goal + '\n## 你的任务\n1. WRITE output/' + asOf + '_日内跟踪简报.md,提示用户"2日窗口无统计优势,建议改>=5日或用单股深评"。\n2. WRITE ' + RD + '/final.json(envelope,data含verdict:"拒绝选股",reason)。\n3. 更新 data/index.json(数组push {runId,asOf,goal,path:dataPath,headline,confidence:"低",fetchedAt})。\nschema 返回 {path, dataPath, oneLineConclusion:"拒绝选股·降级日内跟踪", confidence:"低", keyRisks:["2日窗口高噪音"]}。', {agentType: 'governor', schema: GOV_RET, label: 'governor', phase: '综合落盘'})
  return report
}

let ctx = ''

phase('宏观定调')
const macro = await agent(P('macro-strategist', '未来2周"天时"五维定调,输出顺风方向2-3。', '用工具链取宏观读数+政策节点+情绪,锁定顺风方向(政策周期+市场热度双确认)。', ctx), {agentType: 'macro-strategist', schema: RET, label: 'macro', phase: '宏观定调'})
ctx = '【宏观】' + macro.summary + ' → ' + macro.path

phase('候选池')
const sector = await agent(P('sector-analyst', '在顺风方向内撒网,生成候选池>=30只。', '用 ifind_search_stocks(NL选股,医药类返空则手动龙头)+ifind_sector_data+cn_fetch.py rank 多源汇总候选30-50只去重,每只标注来源。1w账户优先含<40元标的。', ctx), {agentType: 'sector-analyst', schema: RET, label: 'sector', phase: '候选池'})
ctx += '\n【候选池】' + sector.summary + ' → ' + sector.path

phase('流动性过滤')
const tech = await agent(P('technical-liquidity', '对全部候选批量做流动性硬门槛过滤+短线因子。', '用 ifind_get_stock_summary(近1月日K)或 cn_fetch.py factors 批量算5/10/20日动量+MA20+量价突破+amt20;流动性硬门槛(成交额>=1亿/换手1-7%/市值>=30亿/非ST非次新/近5-10-20日任一>30%透支剔除)逐只过滤。返pass/reject/factors。', ctx), {agentType: 'technical-liquidity', schema: RET, label: 'technical', phase: '流动性过滤'})
ctx += '\n【流动性过滤】' + tech.summary + ' → ' + tech.path

phase('并行评分')
const [cat, fund] = await parallel([
  () => agent(P('catalyst-scanner', '对过关票批量做催化兑现度+情绪+资金。', '用 ifind_search_news(必带time_start/end)+china-news get_stock_news+curl龙虎榜 取催化+情绪+资金,判断每只兑现度(近5日涨>15%半兑现/>30%透支)。返每只催化+整体情绪。先用 Read 读 ' + tech.path + ' 的 data.pass 取过关清单。', ctx), {agentType: 'catalyst-scanner', schema: RET, label: 'catalyst', phase: '并行评分'}),
  () => agent(P('fundamentals-analyst', '对过关票批量做财务排雷+估值锚。', '用 ifind_get_stock_financials(年报日期优先,max5主体可分批)+ifind_get_stock_shareholders 批量排雷(商誉/质押/造假)+估值分位。硬雷点一票否决。先用 Read 读 ' + tech.path + ' 的 data.pass 取过关清单。', ctx), {agentType: 'fundamentals-analyst', schema: RET, label: 'fundamentals', phase: '并行评分'}),
])
ctx += '\n【催化】' + cat.summary + ' → ' + cat.path
ctx += '\n【财务】' + fund.summary + ' → ' + fund.path

phase('回测组合')
const risk = await agent(P('risk-portfolio', '七维评分排序+回测+组合配置。', '按七维权重(技术25/资金20/催化20/情绪15/基本面10/估值5/流动性5)评分排序Top' + topN + ';对Top' + topN + '用 ifind_get_stock_summary近1月日K做5日持有窗口回测(胜率>=55%/均收>=3%/回撤<=8%);回测3项全不达标一票否决不入TopN(驰宏锌锗纪律);组合分散(行业<=40%/催化同源<=50%/单票<=25%,1w手数豁免须标注)。用 Read 读前序各 json 的 data 取细节。', ctx), {agentType: 'risk-portfolio', schema: RET, label: 'risk', phase: '回测组合'})
ctx += '\n【风险/组合】' + risk.summary + ' → ' + risk.path

phase('综合落盘')
const report = await agent('综合全链产出写短周期选股报告+Top' + topN + '操作卡。\n\n## 投资目标\n' + goal + '\n\n## 全链产出(承接,勿无视;用 Read 读各 json 的 data 取细节)\n' + ctx + '\n\n## 你的任务\n按矛盾调和矩阵综合,Top1须回测相对最优且非高位回调者(回测未背书不得排Top1给最大仓位)。\n1. WRITE 报告到 output/' + asOf + '_短周期2周推荐清单.md(目录不存在先创建),按 governor 报告结构与命名规范(结论先行→总体策略→各专项核心细节+逻辑关系→专业知识点→操作→风险情景→免责)写,报告头一句话结论附核心假设置信度+回测达标情况。\n2. WRITE 结构化最终到 ' + RD + '/final.json(envelope,data含oneLineConclusion/topN/totalPosition/confidence/keyRisks/backtest/modules各环节path)。\n3. 更新 data/index.json(数组push {runId,asOf,goal,path:dataPath,headline,confidence,fetchedAt})。\nschema 返回 {path, dataPath, oneLineConclusion, topN, totalPosition, confidence, keyRisks}。', {agentType: 'governor', schema: GOV_RET, label: 'governor', phase: '综合落盘'})
return report
