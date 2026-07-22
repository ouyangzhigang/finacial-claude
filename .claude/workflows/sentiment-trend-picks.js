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
let SHARED = 'data/runs/'+asOf+'_'+G+'/_shared.json'

// ── 预取指令(仅 catalyst agent 执行) ──
let PREFETCH = '⚠️ 前置步骤(必须在分析之前完成):\n1. 运行 Bash: python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' 2>&1\n2. 运行 Bash: python scripts/portfolio_tracker.py update 2>&1\n3. Read '+SHARED+' 获取共享数据(核心信号🔴🟡🟢)\n完成后再进入下方分析任务。\n\n'

const S = async (name, fn) => {
  try { const r = await fn(); if (r) return r } catch (e) {
    const msg = (e?.message||String(e)).slice(0,200)
    return {path:'',summary:name+' 失败(降级): '+msg,keyFields:{_error:true}}
  }
  return {path:'',summary:name+' 返回空',keyFields:{_error:'empty'}}
}
// 压缩版P/O模板: 数据落盘格式提取为O(), 减少~60%模板字符
const O = (ag) => `\nWRITE ${RD}/${ag}.json; envelope:{"agent":"${ag}","asOf":"${asOf}","data":{...}}; schema→{path,summary,keyFields}`
const P = (ag, task, extra, ctx) => `${task}\n# 目标\n${goal}\n# 前序\n${ctx||'(起点)'}\n# 任务\n${extra}${O(ag)}`
const ap = (r, l) => {
  if (!r) return '\n【'+l+'】⚠️ 数据缺失'
  const pathInfo = r.path ? ' → '+r.path : ''
  return '\n【'+l+'】'+r.summary+pathInfo
}

let ctx = ''

// ── Phase 1: 舆情挖掘(含 prefetch) ──
phase('舆情挖掘')
const cat = await S('catalyst', () => agent(PREFETCH+P('catalyst-scanner','舆情挖掘:从新闻语义+热榜+社交情绪识别趋势+候选股。','⚠️ 不要用 MCP(全 SSL 挂)。用 python scripts/hot_trend_dig.py + cn_fetch.py rank + astock_data.py 取新闻/资金流。识别2-3个趋势主题,给信号强度+信息源+候选代码。警惕纯炒作,给情绪温度+市场怀疑度。', ctx), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'舆情挖掘'}))
ctx = ap(cat,'舆情趋势')

// ── Phase 2: 趋势验证(读 catalyst 的趋势主题) ──
phase('趋势验证')
const macro = await S('macro', () => agent(P('macro-strategist','验证舆情趋势是否与宏观顺风方向一致。','⚠️ 不要用 MCP。用 Read 读 '+cat.path+' 的 data.trends 获取舆情趋势;用 cn_fetch.py kline sh000001 30 取上证K线 + astock_data.py tencent_quote 取指数估值。判断趋势是否落在宏观顺风方向。trendAligned=true 才继续,false 则降权。', ctx), {agentType:'macro-strategist',schema:RET,label:'macro',phase:'趋势验证'}))
ctx += ap(macro,'趋势验证')

// ── Phase 3: 板块候选(读 catalyst + macro) ──
phase('板块候选')
const sector = await S('sector', () => agent(P('sector-analyst','承接趋势,挖对应板块+候选池。','⚠️ 不要用 MCP。用 Read 读 '+cat.path+' 和 '+macro.path+';对验证通过的趋势(trendAligned=true),用 cn_fetch.py rank + astock_data.py tencent_quote 取板块成分+候选,优先<40元。合并去重。', ctx), {agentType:'sector-analyst',schema:RET,label:'sector',phase:'板块候选'}))
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
// ── Phase 5.5: 硬门过滤(代码执行,governor不可override) ──
	phase('硬门过滤')
	log('🔄 启动硬门过滤 — 6道硬门,代码执行,governor不可override')
	await S('hard_gate', async () => {
	  const cmd = 'PYTHONIOENCODING=utf-8 python scripts/hard_gate.py --run-id '+asOf+'_'+G+' 2>&1'
	  await agent('⚠️ 只运行命令不调试。
运行 Bash: '+cmd+'
然后 Read '+RD+'/gate_report.json。', {label:'hard_gate', phase:'硬门过滤'})
	  return {path: RD+'/gate_report.json', summary:'硬门过滤完成'}
	})
	ctx += '
【硬门过滤】⚠️ governor不可override → '+RD+'/gate_report.json'
	log('✅ 硬门过滤完成')

	// ── Phase 6: 综合落盘 ──
	phase('综合落盘')
	const report = await S('governor', () => agent('综合全链写舆情趋势预判选股报告。

## 投资目标
'+goal+'

## 全链产出(用 Read 读各 json)
'+ctx+'
'+history+'

## 🚫 硬门约束(代码执行,不可override)

**‼️ 第一步: Read '+RD+'/gate_report.json 获取硬门过滤结果。**

硬门由 scripts/hard_gate.py 代码执行, governor **不可推翻**:

1. **status="❌否决"** 的标的 → 不得入TopN, 不得出现在报告中
2. **status="⚠️降级"** 的标的 → 遵守 max_rank 限制
3. **system_flags.position_cap** → 总仓位上限, 不可超过
4. **system_flags.confidence_floor** → 置信度下限, 不可上调

**违反以上任何一条 → 报告无效, 退回重写。**

## ⚠️ 硬约束(违反任何一条视为未完成)

### 回测纪律
- 回测3项全不达标(胜率<55%+均收<3%+回撤>8%)→ 该标的**剔出TopN**,不得靠"降仓位+严止损"硬留
- 2项不达标→ 仓位砍半+信心列标"低·回测未背书"
- 1项不达标→ 正常保留但标注短板

### 板块纪律
- 前序环节(catalyst/macro/sector/tech/fundamentals)筛选出的标的**不得因个人偏好丢弃**
- 若某个趋势是前序确认的主线,即便该趋势数据有瑕疵,也须保留至少1只入TopN
- 丢弃前序标的须在报告中说明具体原因

### 数据判断纪律
- Read 前序 json 文件前先检查文件是否存在
- 文件存在但数据全中性值→ 标注"数据源降级:全中性值,无区分度",不标注"未执行"

## 第一步：对抗审查(3项核心矛盾)
1. Top1舆情热度高但回测全面跑输?
2. 趋势信号强但催化已price-in?(查近5日涨幅)
3. 宏观逆风但标的仍在TopN?
每项标注 ✅/⚠️/❌, ❌则剔除或降权。

## 第二步：写报告文件
WRITE output/'+asOf+'_舆情趋势预判选股.md, 结构: 结论先行→总体策略→TopN逐一说明→风险免责
头一句话: 趋势强度 + 置信度 + 回测达标情况。

## 第三步：落盘数据文件
1. WRITE '+RD+'/final.json(envelope,data含oneLineConclusion/topN/totalPosition/confidence/keyRisks/contradictions/trends/modules)
2. WRITE '+RD+'/_rec.json 含 {topN, confidence}
3. Bash: python scripts/portfolio_tracker.py record --run-id '+asOf+'_'+G+' --json-file '+RD+'/_rec.json 2>&1 (失败不影响)
4. Bash: python scripts/notify_email.py --run-id '+asOf+'_'+G+' 2>&1

schema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。
注意: 已移除 StructuredOutput 工具引用(W6修复), 直接按 schema 返回即可。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))

return report
