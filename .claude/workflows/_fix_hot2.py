"""Fix hot-trends.js: governor prompt syntax error + style consistency."""
import sys

with open('.claude/workflows/hot-trends.js', 'r', encoding='utf-8') as f:
    content = f.read()

fixes = []

# Fix 1: Convert governor prompt from single-quoted concatenation to template literal
# This fixes the SYNTAX ERROR (unescaped newlines in single-quoted string)
# and makes the code cleaner

old = """const report = await S('governor', () => agent('综合全链写热门板块潜力股报告。

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
WRITE output/'+asOf+'_热门板块潜力股综合推荐.md, 结构: 结论先行→总体策略→TopN逐一说明→风险免责
头一句话: 情绪温度 + 置信度 + 回测达标情况。

## 第三步：落盘数据文件
1. WRITE '+RD+'/final.json(envelope,data含oneLineConclusion/topN/totalPosition/confidence/keyRisks/contradictions/mainThemes/modules)
2. WRITE '+RD+'/_rec.json 含 {topN, confidence}
3. Bash: python scripts/portfolio_tracker.py record --run-id '+asOf+'_'+G+' --json-file '+RD+'/_rec.json 2>&1 (失败不影响)
4. Bash: python scripts/notify_email.py --run-id '+asOf+'_'+G+' 2>&1

schema 返回 {path,dataPath,oneLineConclusion,topN,totalPosition,confidence,keyRisks}。
注意: 已移除 StructuredOutput 工具引用(W6修复), 直接按 schema 返回即可。', {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))"""

new = """const report = await S('governor', () => agent(`综合全链写热门板块潜力股报告。

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
注意: 已移除 StructuredOutput 工具引用(W6修复), 直接按 schema 返回即可。`, {agentType:'governor',schema:GOV,label:'governor',phase:'综合落盘'}))"""

if old in content:
    content = content.replace(old, new)
    fixes.append('1. Governor prompt: 单引号拼接→模板字符串 (修复语法错误)')
else:
    fixes.append('1. SKIP: governor prompt pattern not matched')
    # Debug
    idx = content.find("综合全链写热门板块潜力股报告")
    if idx >= 0:
        print(f"  Found at offset {idx}")
        print(f"  Context: {repr(content[idx:idx+150])}")

# Fix 2: Convert PREFETCH from concatenation to template literal for consistency
old = """const PREFETCH = '⚠️ 前置步骤(必须在分析之前完成):\\n1. 运行 Bash: python scripts/prefetch_shared.py --run-id '+asOf+'_'+G+' --extra hot 2>&1\\n2. 运行 Bash: python scripts/portfolio_tracker.py update 2>&1\\n3. Read '+SHARED+' 获取共享数据(板块/涨停池/核心信号🔴🟡🟢)\\n完成后再进入下方分析任务。\\n\\n'"""
new = """const PREFETCH = `⚠️ 前置步骤(必须在分析之前完成):
1. 运行 Bash: python scripts/prefetch_shared.py --run-id ${asOf}_${G} --extra hot 2>&1
2. 运行 Bash: python scripts/portfolio_tracker.py update 2>&1
3. Read ${SHARED} 获取共享数据(板块/涨停池/核心信号🔴🟡🟢)
完成后再进入下方分析任务。

`"""
if old in content:
    content = content.replace(old, new)
    fixes.append('2. PREFETCH: 拼接→模板字符串')
else:
    fixes.append('2. SKIP: PREFETCH pattern not matched')

# Fix 3: Convert ctx strings from concatenation to template literals
old = """ctx += '\\n【硬门过滤】⚠️ governor不可override → '+RD+'/gate_report.json'"""
new = """ctx += `\\n【硬门过滤】⚠️ governor不可override → ${RD}/gate_report.json`"""
if old in content:
    content = content.replace(old, new)
    fixes.append('3. ctx硬门: 拼接→模板字符串')

# Fix 4: Convert hard_gate agent prompt from concatenation to template literal
old = """await agent('⚠️ 只运行命令不调试。\\nBash: '+cmd+'\\nRead '+RD+'/gate_report.json', {label:'hard_gate', phase:'硬门过滤'})"""
new = """await agent(`⚠️ 只运行命令不调试。\\nBash: ${cmd}\\nRead ${RD}/gate_report.json`, {label:'hard_gate', phase:'硬门过滤'})"""
if old in content:
    content = content.replace(old, new)
    fixes.append('4. hard_gate prompt: 拼接→模板字符串')

# Fix 5: Convert hard_gate return path from concatenation to template literal
old = """return {path: RD+'/gate_report.json', summary:'硬门过滤完成'}"""
new = """return {path: `${RD}/gate_report.json`, summary:'硬门过滤完成'}"""
if old in content:
    content = content.replace(old, new)
    fixes.append('5. hard_gate return: 拼接→模板字符串')

with open('.claude/workflows/hot-trends.js', 'w', encoding='utf-8') as f:
    f.write(content)

print('\n'.join(fixes))
print('Done.')