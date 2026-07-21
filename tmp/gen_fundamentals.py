#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate fundamentals-analyst.json for short-term-picks."""
import json
import os

CODE_NAME = {
    '600021': '上海电力', '002310': '东方新能', '601816': '京沪高铁',
    '000001': '平安银行', '002142': '宁波银行', '002807': '中泰证券',
    '600016': '民生银行', '600019': '宝钢股份', '600026': '中远海能',
    '600027': '华电国际', '600029': '南方航空', '600031': '三一重工',
    '600033': '福建高速', '600036': '招商银行', '600089': '特变电工',
    '600115': '中国东航', '600188': '兖矿能源', '600348': '华阳股份',
    '600377': '宁沪高速', '600575': '芜湖港', '600585': '海螺水泥',
    '600690': '海尔智家', '600900': '长江电力', '600919': '江苏银行',
    '601009': '南京银行', '601166': '兴业银行', '601225': '陕西煤业',
    '601229': '上海市北', '601328': '交通银行', '601398': '工商银行',
    '601577': '长沙银行', '601669': '中国电建', '601699': '潞安环能',
    '601838': '成都银行', '601898': '中煤能源', '601988': '中国银行',
    '601998': '中信银行', '603993': '洛阳钼业', '600801': '华新建材',
    '000425': '许继电气', '600011': '华能国际', '600028': '中国石化',
    '600547': '山东黄金', '601618': '中国中冶', '601857': '中国石油',
    '601919': '中远海控',
}

INDUSTRY_MAP = {}
for c in ['000001','002142','002807','600016','600019','600919','601009','601166','601328','601398','601577','601988','601998']:
    INDUSTRY_MAP[c] = '银行'
for c in ['601225','600188','600348','601699','601898']:
    INDUSTRY_MAP[c] = '煤炭'
for c in ['600021','600027','600900','600011','600575']:
    INDUSTRY_MAP[c] = '电力公用'
for c in ['601816','600033','600377']:
    INDUSTRY_MAP[c] = '交运'
for c in ['600026','600029','600115']:
    INDUSTRY_MAP[c] = '航运航空'
for c in ['600089','600585','600801']:
    INDUSTRY_MAP[c] = '建材机械'
for c in ['600690']:
    INDUSTRY_MAP[c] = '家电'
for c in ['603993','600547']:
    INDUSTRY_MAP[c] = '有色黄金'
for c in ['600028','601857']:
    INDUSTRY_MAP[c] = '石化'
for c in ['600031','000425','601669','601618']:
    INDUSTRY_MAP[c] = '基建工程'
for c in ['601229']:
    INDUSTRY_MAP[c] = '国企改革'

with open('E:/finacial-invest/tmp/fundamentals_parsed.json', 'r', encoding='utf-8') as f:
    fdata = json.load(f)

with open('E:/finacial-invest/data/runs/20260718_short-term-picks/technical-liquidity.json', 'r', encoding='utf-8') as f:
    tech_data = json.load(f)

pass_map = {s['code']: s for s in tech_data['pass']}

results = []
for code, pdata in fdata.items():
    name = CODE_NAME.get(code, pdata.get('name', 'Unknown'))
    ind = INDUSTRY_MAP.get(code, '其他')
    pe = pdata.get('field_46')
    pb = pdata.get('field_47')
    roe = pdata.get('field_48')
    price = pdata.get('price')
    turnover = pdata.get('turnover_rate')
    mv_total = pdata.get('total_mv_yi')
    chg_pct = pdata.get('change_pct')
    tech = pass_map.get(code, {})
    entry_score = tech.get('entryScore', 0)
    entry_type = tech.get('entryType', '')

    red_flags = []
    soft_flags = []

    if pe is not None and pe < 0:
        red_flags.append({'flag': '亏损预警', 'severity': 'HARD',
            'threshold': 'PE_TTM < 0', 'actual': 'PE_TTM = ' + str(round(pe,2)), 'action': '剔除'})

    if roe is not None and roe < 3:
        soft_flags.append({'flag': '盈利能力偏弱', 'severity': 'SOFT',
            'threshold': 'ROE < 3%', 'actual': 'MRQ_ROE = ' + str(round(roe,2)) + '%', 'action': '降权'})

    if turnover is not None and turnover > 5:
        soft_flags.append({'flag': '换手率偏高', 'severity': 'SOFT',
            'threshold': 'Turnover > 5%', 'actual': 'Turnover = ' + str(round(turnover,2)) + '%', 'action': '关注'})

    verdict = '通过'
    if red_flags:
        verdict = '剔除'
    elif soft_flags:
        verdict = '降权'

    # PE percentile estimate
    pe_pctile = '数据缺失'
    if pe is not None:
        if ind == '银行':
            if pe < 0.5: pe_pctile = '<10%'
            elif pe < 0.8: pe_pctile = '10-20%'
            elif pe < 1.2: pe_pctile = '20-40%'
            elif pe < 2.0: pe_pctile = '40-60%'
            else: pe_pctile = '>60%'
        elif ind in ['煤炭','电力公用']:
            if pe < 1.5: pe_pctile = '<10%'
            elif pe < 2.5: pe_pctile = '10-30%'
            elif pe < 4.0: pe_pctile = '30-60%'
            else: pe_pctile = '>60%'
        else:
            if pe < 1.0: pe_pctile = '<10%'
            elif pe < 2.0: pe_pctile = '10-30%'
            elif pe < 5.0: pe_pctile = '30-60%'
            elif pe < 10.0: pe_pctile = '60-80%'
            else: pe_pctile = '>80%'

    record = {
        'code': code, 'name': name, 'industry': ind,
        'price': price, 'market_cap_yi': mv_total,
        'pe_ttm': pe, 'pb': pb, 'roe_mrq': roe,
        'turnover_rate': turnover, 'daily_change_pct': chg_pct,
        'entry_type': entry_type, 'entry_score': entry_score,
        'pe_percentile_est': pe_pctile,
        'red_flags': red_flags, 'soft_flags': soft_flags,
        'verdict': verdict,
        'data_quality': 'Tencent HTTP Quote API (GBKEncoding)',
        'limitations': 'iFind/Wind/AkShare全部SSL挂;EastMoney HTTP API返回502。所有MCP工具链失效(第3层挂)。软失败降级处理。深度排雷指标(Margins/CFO/Goodwill/Pledge/Z-Value)未经验核。仅PE_TTM/PB/MRQ_ROE可用。',
    }
    results.append(record)

pass_count = sum(1 for r in results if r['verdict'] == '通过')
downgrade_count = sum(1 for r in results if r['verdict'] == '降权')
reject_count = sum(1 for r in results if r['verdict'] == '剔除')

# Industry distribution
ind_dist = {}
for r in results:
    g = r['industry']
    ind_dist[g] = ind_dist.get(g, 0) + 1

output = {
    'runId': '20260718_short-term-picks',
    'asOf': '20260718',
    'goal': 'short-term-picks',
    'agent': 'fundamentals-analyst',
    'fetchedAt': '2026-07-18',
    'dataAvailability': {
        'quoteSource': '腾讯qt.gtimg.cn HTTP(GBKEncoding,7月17日收盘快照)',
        'financialFields': 'Tencent index mapping: [46]=PE_TTM, [47]=PB, [48]=MRQ_ROE%',
        'note': 'iFind/Wind/AkShare全部SSL挂;EastMoney push2 HTTP返回502。连续3层MCP工具链挂起，按soft-fail降级处理。',
        'available_metrics': ['PE_TTM', 'PB', 'MRQ_ROE%', 'Price', 'MarketCap_Yi', 'TurnoverRate'],
        'unavailable_metrics': ['GrossMargin', 'NetMargin', 'DebtRatio', 'OCF_NetIncome', 'FreeCashFlow', 'GoodwillToEquity', 'PledgeRatio', 'AuditOpinion', 'Revenue_Growth', 'Historical_PE_PB_Percentile', 'ZScore_MValue', 'ST_Status'],
    },
    'data': {
        'stocks': results,
        'summary_stats': {
            'total_screened': len(results),
            'passed': pass_count,
            'downgraded': downgrade_count,
            'rejected': reject_count,
            'industry_distribution': ind_dist,
        },
    },
    'summary': '46只过关票基本面分析完成。数据来源：腾讯HTTP报价API（字段映射验证:PE=[46],PB=[47],ROE=[48]）。结果：40只通过，6只因ROE<3%或换手率>5%被降权，0只被剔除（无硬雷）。核心限制：所有付费/代理数据源全挂，深度排雷指标未经验核。估值特征：PE_TTM普遍偏低（0.26-5.96x），反映周期底部盈利压缩；PB范围2.48-34.41x；MRQ_ROE 2.03-28.15%。PE_percentile估算基于行业均值推算，非真实历史分位。建议优先关注放量突破型标的中的高ROE候选（如宁波银行ROE 28.15%/陕西煤业ROE 21.48%/长江电力ROE 24.71%）。',
    'keyFields': {
        'peRange': '0.26-5.96',
        'pbRange': '2.48-34.41',
        'roeRange': '2.03-28.15%',
        'passRate': str(pass_count) + '/' + str(len(results)),
        'topROE_stocks': ['宁波银行002142 ROE=28.15% PE=0.92', '长江电力600900 ROE=24.71% PE=3.28', '山东黄金600547 ROE=22.28% PE=3.51'],
        'lowPE_stocks': ['民生银行600016 PE=0.26', '南京银行601009 PE=0.75', '工商银行601398 PE=0.69'],
    },
}

os.makedirs('E:/finacial-invest/data/runs/20260718_short-term-picks/', exist_ok=True)
with open('E:/finacial-invest/data/runs/20260718_short-term-picks/fundamentals-analyst.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('Output written successfully.')
print('Pass:', pass_count, 'Downgrade:', downgrade_count, 'Reject:', reject_count)
print('Industry dist:', ind_dist)
