// ════════════════════════════════════════════════════════════
// _lib.js — 6 个 workflow 公共 helper 的单一真相源(改造5)
// ════════════════════════════════════════════════════════════
//
// ⚠️ Workflow 脚本被复制到 session 目录执行, 跨文件 import 不可靠,
//    故各 workflow 仍内联 helper 副本以保持自包含运行。
//    本文件是**标准实现参考**——改 helper 时先改本文件, 再同步到各 workflow。
//    各 workflow 顶部注释 "// 公共 helper 见 _lib.js" 标记。
//
// 真正动态 import 去重待 Workflow 工具支持跨文件依赖(计划标注: 待工具支持)。

// ── schema 定义 ──
export const RET = {
  type: 'object',
  properties: { path: { type: 'string' }, summary: { type: 'string' }, keyFields: { type: 'object' } },
  required: ['path', 'summary'],
}

export const GOV = {
  type: 'object',
  properties: {
    path: { type: 'string' }, dataPath: { type: 'string' },
    oneLineConclusion: { type: 'string' },
    topN: { type: 'array', items: { type: 'object' } },
    totalPosition: { type: 'string' },
    confidence: { type: 'string' },
    keyRisks: { type: 'array', items: { type: 'string' } },
  },
  required: ['path', 'oneLineConclusion', 'confidence'],
}

// ── S(): agent 错误降级包装(单点失败不连坏整条链) ──
// 各 workflow 内联副本须与此一致
export const S = async (name, fn) => {
  try {
    const r = await fn()
    if (r) return r
  } catch (e) {
    const msg = (e?.message || String(e)).slice(0, 200)
    return { path: '', summary: name + ' 失败: ' + msg, keyFields: { _error: true } }
  }
  return { path: '', summary: name + ' 返回空', keyFields: { _error: 'empty' } }
}

// ── O(): 输出落盘指令(各 agent 写 data/runs/{asOf}_{G}/{agent}.json) ──
// 依赖外层 RD/asOf 变量
export const O = (ag) =>
  '\nWRITE ' + RD + '/' + ag + '.json; envelope:{"agent":"' + ag + '","asOf":"' + asOf + '","data":{...}}; schema→{path,summary,keyFields}'

// ── P(): 构建 agent prompt(短周期选股口径, 4参数版) ──
// 单股深评用 5 参数版(多 target), 见 single-stock-deep.js
export const P = (ag, task, extra, ctx) =>
  task + '\n# 目标\n' + goal + '\n# 前序\n' + (ctx || '(起点)') + '\n# 任务\n' + extra + O(ag)

// ── ap(): 前序产出摘要拼接(失败标⚠️数据缺失) ──
export const ap = (r, l) =>
  r ? '\n【' + l + '】' + r.summary + (r.path ? ' → ' + r.path : '') : '\n【' + l + '】⚠️ 数据缺失'

// ── buildPrefetch(): Phase0 预取指令(prefetch_shared + portfolio_tracker update) ──
// 依赖外层 asOf/G 变量
export const buildPrefetch = (asOf, G, extra = '') =>
  '⚠️ 前置步骤:\n' +
  '1. Bash: python scripts/prefetch_shared.py --run-id ' + asOf + '_' + G + (extra ? ' --extra ' + extra : '') + ' 2>&1\n' +
  '2. Bash: python scripts/portfolio_tracker.py update 2>&1\n' +
  '3. Read data/runs/' + asOf + '_' + G + '/_shared.json\n' +
  '完成后再分析。\n\n'

// ════════════════════════════════════════════════════════════
// 变体说明(各 workflow 与标准版的差异)
// ════════════════════════════════════════════════════════════
// - single-stock-deep.js: P() 多第5参数 target(目标标的段), ap() 失败分支更详细
// - ultra-short-picks.js: 无 prefetch(改 market_radar 市场温度), S() 同标准
// - portfolio-review.js: P() 多 holdings 段
// - 其余(short-term/hot-trends/sentiment-trend): 与标准版一致
//
// 同步规则: 改本文件后, 用 diff 对照各 workflow 内联副本, 保持逻辑一致
