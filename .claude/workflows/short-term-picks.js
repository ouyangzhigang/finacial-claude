export const meta = {
  name: 'short-term-picks',
  description: 'A股短周期选股——宏观→候选→流动性→catalyst∥fundamentals→量化引擎→硬门∥走势→回测→governor',
  phases: [
    {title: '宏观定调', detail: 'regime+顺风方向'},
    {title: '候选池', detail: 'sector 30-50只'},
    {title: '流动性过滤', detail: 'technical 批量硬门槛'},
    {title: '并行评分', detail: 'catalyst∥fundamentals'},
    {title: '量化引擎', detail: '5引擎并行→factor汇总'},
    {title: '硬门∥走势', detail: 'hard_gate ∥ forecast 概率路径'},
    {title: '回测组合', detail: 'risk+回测(引用forecast)'},
    {title: '综合落盘', detail: 'governor报告'},
  ],
}

// 兼容层:Workflow 的 args 可能被序列化成字符串(Object.keys 返回 0..N)而非对象,
// 此时 args.asOf/topN 等全 undefined,asOf 退回默认 YYYYMMDD 或被残留目录推断成昨日日期
// (07-30 事故:asOf 丢成 20260729 拼留目录)。检测并解析回对象。
if (typeof args === 'string') {
  try { args = JSON.parse(args); } catch (e) { args = {}; }
}
log('🔍 DEBUG args注入: typeof='+typeof args+' keys='+Object.keys(args||{}).join(',').slice(0,60)+' | asOf='+(args&&args.asOf)+' topN='+(args&&args.topN))

const RET = {type:'object',properties:{path:{type:'string'},summary:{type:'string'},keyFields:{type:'object'}},required:['path','summary']}
const GOV = {type:'object',properties:{path:{type:'string'},dataPath:{type:'string'},oneLineConclusion:{type:'string'},topN:{type:'array',items:{type:'object'}},totalPosition:{type:'string'},confidence:{type:'string'},keyRisks:{type:'array',items:{type:'string'}}},required:['path','oneLineConclusion','confidence']}

const topN=args.topN||5, period=args.period||'2周', acc=args.account||'1w', rp=args.riskPref||'稳健偏积极', pos=args.position||'无持仓', asOf=args.asOf||'YYYYMMDD'
// 进攻模式:用户要"涨幅最高/最具潜力"时 riskPref=积极/进攻 → hard_gate 用 aggressive 模式
// (根因:回测硬门把高弹性票全杀,致TopN只剩防御票。进攻模式让回测证伪的弹性票降级观察仓保留)
const AGGRO = (rp === '积极' || rp === '进攻' || /涨幅|潜力|弹性|进攻/.test(rp)) ? 'aggressive' : 'normal'
const G='short-term-picks', RD='data/runs/'+asOf+'_'+G
const goal='短周期选股: Top'+topN+' 周期'+period+' 风险'+rp+' 账户'+acc+' 持仓'+pos+' | 基准日'+asOf+' | 模式'+AGGRO
const history = args.history || ''
const SHARED = 'data/runs/'+asOf+'_'+G+'/_shared.json'

const PREFETCH = '⚠️ 前置步骤(并行执行,一条 Bash 命令):\n1. Bash: python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' --extra hot & PYTHONIOENCODING=utf-8 python scripts/regime_detector.py --output '+RD+'/regime.json & python scripts/portfolio_tracker.py update & wait 2>&1\n2. Read '+SHARED+'\n3. Read '+RD+'/regime.json\n完成后再分析。\n\n'

// 公共 helper 标准实现见 .claude/workflows/_lib.js(改造5) — 改 helper 时先改 _lib.js 再同步本文件
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

if (/^([1234]日|隔日|当日|次日)/.test(String(period))) {
  const dayCount = String(period).match(/(\d+)日/)?.[1] || '?'
  log('周期<5日,拒绝选股')
  phase('综合落盘')
  const report = await S('governor', () => agent('周期<5日窗口('+dayCount+'日)无统计优势,拒绝输出TopN买入清单。\n## 投资目标\n'+goal+'\n## 任务\n1. WRITE output/'+asOf+'_日内跟踪简报.md\n2. WRITE '+RD+'/final.json\n3. 更新 data/index.json\nschema 返回 {path,dataPath,oneLineConclusion:"拒绝选股",confidence:"低",keyRisks:["'+dayCount+'日高噪音"]}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
  return report
}

let ctx = ''

phase('宏观定调')
log('🔄 宏观定调 — macro-strategist')
const macro = await S('macro', () => agent(PREFETCH+P('macro-strategist','未来2周天时五维定调,输出顺风方向2-3。','用工具链取宏观读数+政策节点+情绪,锁定顺风方向。改造9账户适配: 判断顺风方向龙头股价中位数 vs 账户'+acc+'单票预算(1w≤4000元→股价≤40元), 若>70%龙头>40元则accountMismatch=true+说明(建议切低价主线或提账户), 写入keyFields.leadingStockMedianPrice/accountMismatch/accountMismatchNote。', ctx), {agentType:'macro-strategist',schema:RET,label:'macro',phase:'宏观定调'}))
ctx = ap(macro,'宏观')
log('✅ 宏观定调完成')

phase('候选池')
log('🔄 候选池 — sector-analyst')
const sectorDir = AGGRO==='aggressive' ? '\n🔥 进攻模式定向:候选池须含≥30%进攻方向票——成长/题材/小盘弹性/次新/政策催化/动量突破,不能只撒防御板块(银行/石油/红利)。用 cn_fetch.py ths_hot(同花顺热点)+ hot_trend_dig.py(龙虎榜/资金)挖掘进攻主线。' : ''
const sector = await S('sector', () => agent(P('sector-analyst','在顺风方向内撒网,生成候选池>=30只。','⚠️ Read '+macro.path+' 的 data.tailwinds 确定顺风行业。用 cn_fetch.py rank + astock_data.py tencent_quote + cn_fetch.py kline 多源汇总30-50只。1w账户优先<40元。'+sectorDir, ctx), {agentType:'sector-analyst',schema:RET,label:'sector',phase:'候选池'}))
ctx += ap(sector,'候选池')
log('✅ 候选池完成')

phase('流动性过滤')
log('🔄 流动性过滤 — technical-liquidity')
const tech = await S('technical', () => agent(P('technical-liquidity','对全部候选批量做流动性硬门槛过滤+短线因子。','⚠️。Read '+sector.path+' 的 data.candidates 获取候选清单;用 cn_fetch.py factors 批量算动量+MA20+量价突破;硬门槛(成交额>=1亿/换手1-7%/市值>=30亿/非ST/近5日>30%透支剔除)。', ctx), {agentType:'technical-liquidity',schema:RET,label:'technical',phase:'流动性过滤'}))
ctx += ap(tech,'流动性')
log('✅ 流动性过滤完成')

phase('并行评分')
log('🔄 并行评分 — catalyst ∥ fundamentals')
const [cat, fund] = await parallel([
  () => S('catalyst', () => agent(P('catalyst-scanner','对过关票批量做催化兑现度+情绪+资金。','⚠️ 1) python scripts/cn_fetch.py --keyword 取资讯; 2) python scripts/hot_trend_dig.py 取龙虎榜; 3) astock_data.py 取资金流。', ctx), {agentType:'catalyst-scanner',schema:RET,label:'catalyst',phase:'并行评分'})),
  () => S('fundamentals', () => agent(P('fundamentals-analyst','对过关票批量做财务排雷+估值锚。','⚠️ Read '+tech.path+' 的 data.pass 获取过关票清单;用 astock_data.py tencent_quote 取PE/PB/市值 + cn_fetch.py kline 算技术位。硬雷点(PE>200且无增速/亏损/商誉>30%)一票否决。', ctx), {agentType:'fundamentals-analyst',schema:RET,label:'fundamentals',phase:'并行评分'})),
])
ctx += ap(cat,'催化') + ap(fund,'财务')
log('✅ 并行评分完成')

phase('量化引擎')
const passCodes = tech?.keyFields?.passCodes || ''
const regime = macro?.keyFields?.regime || 'trending'
if (passCodes) {
      log('🔄 量化引擎 — 对 '+passCodes.split(',').length+' 只过关票运行5引擎 (分批: 4并行→1汇总)')
      const RUN = '⚠️ 只运行命令+读结果+直接返回。不要调试。'
      // Phase 1: 4个独立引擎并行 (timing/sentiment/supply/capital — 互不依赖)
      const [te, se, sr, cs] = await parallel([
        () => S('timing_engine', async () => {
          const cmd = 'PYTHONIOENCODING=utf-8 python scripts/timing_engine.py --codes '+passCodes+' --output '+RD+'/timing_scores.json 2>&1'
          await agent(RUN+'\nBash: '+cmd+'\nRead '+RD+'/timing_scores.json', {label:'timing_engine', phase:'量化引擎'})
          return {path: RD+'/timing_scores.json', summary:'入场评估完成'}
        }),
        () => S('sentiment_engine', async () => {
          const cmd = 'PYTHONIOENCODING=utf-8 python scripts/sentiment_engine.py --codes '+passCodes+' --data-dir '+RD+' --output '+RD+'/sentiment_scores.json 2>&1'
          await agent(RUN+'\nBash: '+cmd+'\nRead '+RD+'/sentiment_scores.json', {label:'sentiment_engine', phase:'量化引擎'})
          return {path: RD+'/sentiment_scores.json', summary:'舆情评分完成'}
        }),
        () => S('supply_risk', async () => {
          const cmd = 'PYTHONIOENCODING=utf-8 python scripts/astock_cli.py supply_risk --codes '+passCodes+' > '+RD+'/supply_risk.json 2>&1'
          await agent(RUN+'\nBash: '+cmd+'\nRead '+RD+'/supply_risk.json', {label:'supply_risk', phase:'量化引擎'})
          return {path: RD+'/supply_risk.json', summary:'供给端风险评分完成'}
        }),
        () => S('capital_score', async () => {
          const cmd = 'PYTHONIOENCODING=utf-8 python scripts/astock_cli.py capital_score --codes '+passCodes+' > '+RD+'/capital_scores.json 2>&1'
          await agent(RUN+'\nBash: '+cmd+'\nRead '+RD+'/capital_scores.json', {label:'capital_score', phase:'量化引擎'})
          return {path: RD+'/capital_scores.json', summary:'资金流评分完成'}
        }),
      ])
      // Phase 2: factor_engine 汇总 (依赖 Phase 1 的 sentiment/capital/supply JSON + 前序 fundamentals-analyst JSON)
      const fe = await S('factor_engine', async () => {
        const cmd = 'PYTHONIOENCODING=utf-8 python -m core factor --codes '+passCodes+' --as-of '+asOf+' --regime '+regime+' --output '+RD+'/factor_scores.json 2>&1'
        await agent(RUN+'\nBash: '+cmd+'\nRead '+RD+'/factor_scores.json', {label:'factor_engine', phase:'量化引擎'})
        return {path: RD+'/factor_scores.json', summary:'core 因子评分完成(6族量化+IC加权)'}
      })
      log('✅ 量化引擎完成')
      ctx += '\n【量化引擎】4引擎并行(timing/sentiment/supply/capital) → factor_engine汇总 → '+RD+'/'
  } else {
    // passCodes为空时从sector候选池降级取代码, 避免量化引擎完全跳过
    const fallbackCodes = sector?.keyFields?.candidateCodes || ''
    if (fallbackCodes) {
      log('⚠️ passCodes为空, 从sector候选池降级取 '+fallbackCodes.split(',').length+' 只代码')
      const RUN = '⚠️ 只运行命令+读结果+直接返回。不要调试。'
      await parallel([
        () => S('factor_engine', async () => {
          const cmd = 'PYTHONIOENCODING=utf-8 python -m core factor --codes '+fallbackCodes+' --as-of '+asOf+' --regime '+regime+' --output '+RD+'/factor_scores.json 2>&1'
          await agent(RUN+'\nBash: '+cmd+'\nRead '+RD+'/factor_scores.json', {label:'factor_engine', phase:'量化引擎'})
          return {path: RD+'/factor_scores.json', summary:'core 因子评分完成(降级代码)'}
        }),
        () => S('timing_engine', async () => {
          const cmd = 'PYTHONIOENCODING=utf-8 python scripts/timing_engine.py --codes '+fallbackCodes+' --output '+RD+'/timing_scores.json 2>&1'
          await agent(RUN+'\nBash: '+cmd+'\nRead '+RD+'/timing_scores.json', {label:'timing_engine', phase:'量化引擎'})
          return {path: RD+'/timing_scores.json', summary:'入场评估完成(降级代码)'}
        }),
      ])
      ctx += '\n【量化引擎】⚠️ 降级代码(sector候选池) → '+RD+'/'
    } else {
      log('⚠️ 量化引擎跳过 — 无过关票代码且无sector候选,降级到LLM评分')
      ctx += '\n【量化引擎】⚠️ 跳过(无代码可用)'
    }
  }

phase('硬门∥走势')
log('🔄 硬门∥走势 — validate+hard_gate ∥ forecast(并行,互不依赖)')
// 硬门过滤依赖 validate_run(契约校验), 走势判断依赖 factor_scores(量化引擎产出)
// 两者互不依赖 → 并行执行, 节省串行等待时间
const [gateResult, forecastResult] = await parallel([
  // Branch A: validate_run → hard_gate (串行, hard_gate 依赖 validate_run)
  async () => {
    await S('validate_run', async () => {
      const cmd = 'PYTHONIOENCODING=utf-8 python scripts/validate_run.py --run-id '+asOf+'_'+G+' 2>&1'
      await agent('⚠️ 只运行不调试。\nBash: '+cmd+'\nRead '+RD+'/_validation.json', {label:'validate_run', phase:'硬门∥走势'})
      return {path: RD+'/_validation.json', summary:'契约校验完成'}
    })
    return await S('hard_gate', async () => {
      const cmd = 'PYTHONIOENCODING=utf-8 python scripts/hard_gate.py --run-id '+asOf+'_'+G+' --mode '+AGGRO+' 2>&1'
      await agent('⚠️ 只运行不调试。\nBash: '+cmd+'\nRead '+RD+'/gate_report.json', {label:'hard_gate', phase:'硬门∥走势'})
      return {path: RD+'/gate_report.json', summary:'硬门过滤完成(模式'+AGGRO+')'}
    })
  },
  // Branch B: forecast (独立, 只读 factor_scores.json)
  () => S('forecast', async () => {
    const cmd = 'PYTHONIOENCODING=utf-8 python -m core forecast --run-id '+asOf+'_'+G+' --output '+RD+'/forecast_scores.json 2>&1'
    await agent('⚠️ 只运行不调试。\nBash: '+cmd+'\nRead '+RD+'/forecast_scores.json', {label:'forecast', phase:'硬门∥走势'})
    return {path: RD+'/forecast_scores.json', summary:'走势判断完成(概率路径+质化偏移)'}
  }),
])
ctx += '\n【契约校验】'+RD+'/_validation.json (红=数据不可信,governor须降置信度)'
ctx += '\n【硬门过滤】⚠️ governor不可override → '+RD+'/gate_report.json'
ctx += '\n【走势判断】core cli forecast → '+RD+'/forecast_scores.json (up/neutral/down概率+置信度+qual_bias)'
log('✅ 硬门∥走势完成')

phase('回测组合')
log('🔄 回测组合 — risk-portfolio(引用 forecast 概率路径)')
const risk = await S('risk', () => agent(P('risk-portfolio','综合评分排序+回测(环境分层)+组合配置。\n\n## 量化引擎+走势产出(必读)\n1. Read '+RD+'/factor_scores.json\n2. Read '+RD+'/timing_scores.json\n3. Read '+RD+'/sentiment_scores.json\n4. Read '+RD+'/supply_risk.json\n5. Read '+RD+'/capital_scores.json\n6. Read '+RD+'/regime.json\n7. Read '+RD+'/forecast_scores.json\n\n## 走势判断引用规则\n- forecast up概率>60%→可加仓; down概率>50%→降仓或剔除\n- qual_bias与量化分背离(如同涨跌方向但幅度差>20%)→警惕,降低置信度\n\n## 前瞻减分项(防\"已涨到位\"票排高位, 必须执行)\n- 近5日涨>15%且催化在7日内兑现→-15(透支, 兑现即利好出尽)\n- 近20日涨>30%→-20(已涨到位, 追高接盘)\n- 高位回调伪装(近20日涨>20%且近5日转负)→-12\n- Read '+RD+'/gate_report.json: G10降级(PE分位>80%)的票→再-10; G11(归母同比<-30%)→不得排Top1/3\n减分后总分<40不得入TopN(进攻模式弹性票降级保留除外)\n## 任务\n1. 融合量化引擎+走势判断产出+LLM质化评分,做最终排序\n2. 社交排序: social_heat>80且hype_risk>70→过热降权; heat_momentum正且bull_ratio>0.6→加分; 社交vs基本面背离→警惕\n3. 供给端: supply_risk>50→降仓; 大额解禁→否决; 股东户数增加→降权\n4. 资金流: capital<30→降权; capital>70→加分\n5. Bash: PYTHONIOENCODING=utf-8 python scripts/portfolio_optimizer.py --codes {Top'+topN+'代码} --account '+acc.replace("w","0000")+' --risk-budget '+({trending:'0.8',ranging:'0.6',high_volatility:'0.4'}[regime]||'0.5')+' --output '+RD+'/backtest.json 2>&1\n6. Read '+RD+'/backtest.json\n7. timing<-10不得排Top1; 回测rejected不入TopN'+(AGGRO==='aggressive'?'(进攻模式例外:rejected的弹性票降级高风险观察仓,不直接踢出,须严止损-5%)':'')+'; forecast down>50%→仓位再砍一档\n8. 组合分散(行业<=40%/催化同源<=50%/单票<=25%)', ctx), {agentType:'risk-portfolio',schema:RET,label:'risk',phase:'回测组合'}))
ctx += ap(risk,'组合')
log('✅ 回测组合完成')

phase('综合落盘')
log('🔄 综合落盘 — governor')
const report = await S('governor', () => agent('综合全链产出写短周期选股报告+Top'+topN+'操作卡。\n\n投资目标:'+goal+'\n\n全链产出:'+ctx+'\n'+history+'\n\n🚫 硬门约束(代码执行,不可override):\n‼️ Read '+RD+'/gate_report.json 获取硬门过滤结果。\n1.否决的标的→不得入TopN\n2.降级的标的→遵守max_rank限制\n3.position_cap→仓位上限不可超过\n4.confidence_floor→置信度下限不可上调\n5.若momentum_priority→因子排名第一,不可用回测推翻\n违反→报告无效。\n\n📊 走势判断引用:\n‼️ Read '+RD+'/forecast_scores.json 获取概率路径。\n- Top1 forecast up概率应>50%, 若down概率>40%→须在报告显眼处标注"走势判断有分歧"\n- qual_bias与quant_score方向背离→置信度降一档\n\n硬约束:\n回测3项全不达标→剔出TopN\n2项不达标→仓位砍半\nTop1须回测胜率排名前列+非高位回调者\nforecast down>50%的标的→不入Top3\n\n🔥 进攻模式约束(本轮 mode='+AGGRO+', 当 AGGRO=aggressive 时生效):\n- 回测rejected的弹性票(动量强/RPS高/催化真)→不剔出,以"高风险观察仓"保留进TopN(标注·须严止损-5%)\n- TopN至少保留2只进攻弹性票(非纯防御银行/石油/红利),若候选池无进攻票须显式说明\n- 追涨型标的可进TopN但标注"追涨·须T+1收盘复核不追封板价"\n- 进攻票仓位可至单票上限,但须附明确止损位\n\n对抗审查(5项):\n1.Top1回测胜率最优?\n2.Top1入场优势?\n3.催化同源超50%?\n4.社交vs基本面?\n5.走势判断一致性:Top1 forecast up概率是否>50%? 若否,须说明理由\n\n写报告: WRITE output/'+asOf+'_短周期2周推荐清单.md\n落盘: 1.WRITE '+RD+'/final.json 2.WRITE '+RD+'/_rec.json 3.Bash: python scripts/portfolio_tracker.py record --run-id '+asOf+'_'+G+' --json-file '+RD+'/_rec.json 2>&1\n4.Bash: python scripts/forecast_tracker.py record --run-id '+asOf+'_'+G+' --json-file '+RD+'/_rec.json --horizon 2周 2>&1 (失败不影响, 记录预测供2周后回看兑现率反调因子)\n返回schema: {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))
log('✅ 综合落盘完成')
log('🎉 Workflow 全部完成!')
if (report?.path) log('📄 报告: '+report.path)
if (report?.topN?.length) log('📊 Top'+report.topN.length+': '+report.topN.map(t => t.code+' '+t.name).join(', '))

return report