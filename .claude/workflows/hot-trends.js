export const meta = {
  name: 'hot-trends',
  description: 'A股热门板块/潜力股推荐——情绪+资金主导:catalyst先识别主线→sector板块→tech∥fund并行→risk→governor(审查+裁决+报告)。数据落盘不占上下文',
  phases: [
    {title: '热榜挖掘', detail: 'catalyst 识别主线(含 prefetch)'},
    {title: '板块成分', detail: 'sector 龙头+候选'},
    {title: '技术∥排雷', detail: 'technical + fundamentals 并行'},
    {title: '组合', detail: 'risk 配置'},
    {title: '硬门过滤', detail: '6道硬门,代码执行,governor不可override'},
    {title: '综合落盘', detail: 'governor 审查+裁决+报告+portfolio+notify'},
  ],
}

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const constraint=args.constraint||'热门板块潜力股综合推荐', topN=args.topN||8, acc=args.account||'1w', asOf=args.asOf||'YYYYMMDD'
const G='hot-trends', RD='data/runs/'+asOf+'_'+G
const goal='热门板块/潜力股: Top'+topN+' 约束['+constraint+'] 账户'+acc+' | 基准日'+asOf
const history = args.history || ''
const SHARED = 'data/runs/'+asOf+'_'+G+'/_shared.json'

// ── 预取指令(仅 catalyst agent 执行) ──
const PREFETCH = `⚠️ 前置步骤(必须在分析之前完成):
1. 运行 Bash: python scripts/prefetch_shared.py --run-id ${asOf}_${G} --extra hot 2>&1
2. 运行 Bash: python scripts/portfolio_tracker.py update 2>&1
3. Read ${SHARED} 获取共享数据(板块/涨停池/核心信号🔴🟡🟢)
完成后再进入下方分析任务。

`

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
// 压缩版P/O模板: 数据落盘格式提取为O(), 减少~60%模板字符
const O = (ag) => `\nWRITE ${RD}/${ag}.json; envelope:{"agent":"${ag}","asOf":"${asOf}","data":{...}}; schema→{path,summary,keyFields}`
const P = (ag, task, extra, ctx) => `${task}\n# 目标\n${goal}\n# 前序\n${ctx||'(起点)'}\n# 任务\n${extra}${O(ag)}`
const ap = (r, l) => {
  if (!r) return '\n【'+l+'】⚠️ 数据缺失'
  const pathInfo = r.path ? ' → '+r.path : ''
  return '\n【'+l+'】'+r.summary+pathInfo
}

let ctx = ''

// ── Phase 1: 热榜挖掘(含 prefetch) ──
phase('热榜挖掘')
log('🔄 启动热榜挖掘 — agent: catalyst-scanner')
const cat = await S('catalyst', () => agent(PREFETCH+P('catalyst-scanner','多源挖掘今日主线:热榜+龙虎榜+涨停池+连板梯队+市场概览。','⚠️ 不要用 MCP(全 SSL 挂)。用 PYTHONIOENCODING=utf-8 python scripts/hot_trend_dig.py + cn_fetch.py rank + astock_data.py tencent_quote 批量取行情。非结构化页面用 web-scraping fetch.py。输出主线主题+情绪(涨停/封板率/连板高度)+资金方向。', ctx), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'热榜挖掘'}))
ctx = ap(cat,'主线/情绪')
log('✅ 热榜挖掘完成 — ' + (cat?.summary || '空'))

// ── Phase 2: 板块成分(承接主线主题) ──
phase('板块成分')
log('🔄 启动板块成分 — agent: sector-analyst')
const sector = await S('sector', () => agent(P('sector-analyst','承接主线,挖板块成分+龙头+候选池。','⚠️ 不要用 MCP。用 Read 读 '+cat.path+' 的 data.mainThemes 确定主线方向;对主线用 cn_fetch.py rank + astock_data.py tencent_quote 批量取行情;候选优先<40元。', ctx), {agentType:'sector-analyst',schema:RET,label:'sector',phase:'板块成分'}))
ctx += ap(sector,'板块/候选')
log('✅ 板块成分完成 — ' + (sector?.summary || '空'))

// ── Phase 3: 技术∥排雷(并行,都读 sector 候选) ──
phase('技术∥排雷')
log('🔄 启动技术∥排雷 — technical-liquidity ∥ fundamentals-analyst')
const [tech, fund] = await parallel([
  () => S('tech', () => agent(P('technical-liquidity','对候选批量做流动性过滤+动量。','⚠️ 不要用 MCP。用 Read 读 '+sector.path+' 的 data.candidates 获取候选清单;用 cn_fetch.py factors kline 批量算动量+流动性;硬门槛过滤(成交额>=1亿/换手1-7%/非ST非次新/近5日>30%透支剔除)。返pass/reject/factors。', ctx), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'技术∥排雷'})),
  () => S('fund', () => agent(P('fundamentals-analyst','对候选批量排雷。','⚠️ 不要用 MCP。用 Read 读 '+sector.path+' 的 data.candidates 获取候选清单;用 astock_data.py tencent_quote 取PE/PB/市值;硬雷点(PE>200且无增速/亏损/商誉>30%)剔除。返每只 verdict。', ctx), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'技术∥排雷'})),
])
ctx += ap(tech,'技术') + ap(fund,'财务')
log('✅ 技术∥排雷完成')
log('  技术: ' + (tech?.summary || '空'))
log('  财务: ' + (fund?.summary || '空'))

// ── Phase 4: 组合(综合全链) ──
phase('组合')
log('🔄 启动组合配置 — agent: risk-portfolio')
const risk = await S('risk', () => agent(P('risk-portfolio','组合配置Top'+topN+'。','Read 全链 json(主线方向+候选+技术因子+排雷结论);按情绪/资金主导(权重高于基本面)排Top'+topN+';组合分散(行业<=40%/催化同源<=50%);1w手数致分层建仓须标注。回测未背书不入TopN。', ctx), {agentType:'risk-portfolio',schema:RET,label:'risk',phase:'组合'}))
ctx += ap(risk,'组合')
log('✅ 组合配置完成 — ' + (risk?.summary || '空'))

// ── Phase 5: 硬门过滤(代码执行,governor不可override) ──
phase('硬门过滤')
log('🔄 硬门过滤 — 6道硬门,代码执行,governor不可override')
await S('hard_gate', async () => {
  const cmd = 'PYTHONIOENCODING=utf-8 python scripts/hard_gate.py --run-id '+asOf+'_'+G+' 2>&1'
  await agent(`⚠️ 只运行命令不调试。\nBash: ${cmd}\nRead ${RD}/gate_report.json`, {label:'hard_gate', phase:'硬门过滤'})
  return {path: `${RD}/gate_report.json`, summary:'硬门过滤完成'}
})
ctx += `\n【硬门过滤】⚠️ governor不可override → ${RD}/gate_report.json`
log('✅ 硬门过滤完成')

// ── Phase 6: 综合落盘 ──
phase('综合落盘')
log('🔄 综合落盘 — governor')
const report = await S('governor', () => agent(`综合全链写热门板块潜力股报告。

## 投资目标
${goal}

## 全链产出(用 Read 读各 json)
${ctx}
${history}

## 🚫 硬门约束(代码执行,不可override)

**‼️ 第一步: Read ${RD}/gate_report.json 获取硬门过滤结果。**

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
- 前序环节(catalyst/sector/tech/fundamentals)筛选出的标的**不得因个人偏好丢弃**
- 若某个板块是前序确认的主线,即便该板块数据有瑕疵,也须保留至少1只入TopN
- 丢弃前序标的须在报告中说明具体原因

### 数据判断纪律
- Read 前序 json 文件前先检查文件是否存在
- 文件存在但数据全中性值→ 标注"数据源降级:全中性值,无区分度",不标注"未执行"

## 第一步：对抗审查(3项核心矛盾)
1. TopN中情绪高温但基本面排雷未通过的票是否仍在?
2. TopN催化同源是否超50%? 行业集中度是否合理?
3. 任一标的催化临近但已price-in?(查近5日涨幅)
每项标注 ✅/⚠️/❌, ❌则剔除或降权。

## 第二步：写报告文件
WRITE output/${asOf}_热门板块潜力股综合推荐.md, 结构: 结论先行→总体策略→TopN逐一说明→风险免责
头一句话: 情绪温度 + 置信度 + 回测达标情况。

## 第三步：落盘数据文件
1. WRITE ${RD}/final.json(envelope,data含oneLineConclusion/topN/totalPosition/confidence/keyRisks/contradictions/mainThemes/modules)
2. WRITE ${RD}/_rec.json 含 {topN, confidence}
3. Bash: python scripts/portfolio_tracker.py record --run-id ${asOf}_${G} --json-file ${RD}/_rec.json 2>&1 (失败不影响)
4. Bash: python scripts/notify_email.py --run-id ${asOf}_${G} 2>&1

schema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。
注意: 已移除 StructuredOutput 工具引用(W6修复), 直接按 schema 返回即可。`, {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
log('✅ 综合落盘完成')
log('🎉 Workflow 全部完成!')
if (report?.path) {
  log('📄 报告: '+report.path)
}
if (report?.topN?.length) {
  log('📊 Top'+report.topN.length+': '+report.topN.map(t => t.code+' '+t.name).join(', '))
}

return report
