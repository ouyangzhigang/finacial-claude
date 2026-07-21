#!/usr/bin/env python
"""Build catalyst-scanner.json for short-term-picks workflow."""
import json

output = {
    'agent': 'catalyst-scanner',
    'asOf': '20260721',
    'data': {
        'catalystCalendar': [
            {
                'date': '2026-07-21至2026-08-04',
                'event': '中报密集披露窗口',
                'relatedCodes': ['600460','002396','600988','000426','600884','000603','002245','002459','300433','600667','600206','688728','688403','688729','002273'],
                'direction': '利好',
                'fulfillment': '未price-in',
                'notes': '中报季核心催化窗口,预增标的业绩兑现是短期股价催化剂;大部分标的近5日深度回调,消息未price-in'
            },
            {
                'date': '2026-07-29至2026-07-30',
                'event': '美联储FOMC议息会议',
                'relatedCodes': ['all'],
                'direction': '双向(偏鸽利好成长/偏鹰利空)',
                'fulfillment': '未price-in',
                'notes': '若偏鸽→北向继续流入,成长股(半导体/机器人)估值扩张;若偏鹰→北向流出压力,短期利空高估值标的'
            },
            {
                'date': '2026-07月底(约7/28-7/31)',
                'event': '政治局会议(定调下半年经济)',
                'relatedCodes': ['all'],
                'direction': '双向(关注财政/产业/地产表述)',
                'fulfillment': '未price-in',
                'notes': '关注新质生产力(半导体/机器人/储能)政策加码表述;若超预期利好→相关板块催化'
            },
            {
                'date': '2026-07-21',
                'event': '国家超算互联网上线Kimi K3 API服务',
                'relatedCodes': ['002396','600330','002273'],
                'direction': '利好',
                'fulfillment': '未price-in(当日新闻)',
                'notes': 'AI算力需求催化,利好数据中心交换机(星网锐捷)、光模块上游(天通股份)、AI光学(水晶光电)'
            },
            {
                'date': '2026-07-21',
                'event': '头部基金二季报披露:张坤等加仓AI方向',
                'relatedCodes': ['002396','600330','600667','600460','600206'],
                'direction': '利好',
                'fulfillment': '未price-in(当日新闻)',
                'notes': '机构资金确认AI/半导体方向,利好情绪面;但需注意基金季报有滞后性(持仓截至6/30)'
            },
            {
                'date': '2026-07-21',
                'event': '阳光电源董事长提议回购5-10亿元',
                'relatedCodes': ['300450','002459','688772'],
                'direction': '利好',
                'fulfillment': '未price-in(当日新闻)',
                'notes': '储能龙头回购信号提振板块情绪;先导智能/晶澳科技/珠海冠宇为储能链受益标的'
            },
            {
                'date': '2026-07-21至2026-08-04',
                'event': '大基金三期/国产替代政策预期',
                'relatedCodes': ['688729','000021','600460','600206','600641','688403','600330','600667','688728','001399'],
                'direction': '利好',
                'fulfillment': '未price-in',
                'notes': '半导体设备/材料/封测国产替代逻辑持续,大基金三期预期+先进制程突破是中长期催化;当前板块深度回调,政策催化未兑现'
            },
            {
                'date': '2026-07-21至2026-08-04',
                'event': '存储芯片涨价周期延续',
                'relatedCodes': ['000021','600667','600206','688403'],
                'direction': '利好',
                'fulfillment': '未price-in',
                'notes': '存储芯片涨价周期下,封测(深科技/太极实业/汇成股份)和靶材(有研新材)受益;近5日大幅回调,涨价逻辑未price-in'
            },
            {
                'date': '2026-07-21至2026-08-04',
                'event': '人形机器人政策+特斯拉Optimus进展',
                'relatedCodes': ['002747','002245','300735','000048','603890'],
                'direction': '利好',
                'fulfillment': '未price-in',
                'notes': '新质生产力方向,政策持续加码;但机器人板块为单确认方向(政策强/热度弱),催化力度弱于半导体'
            }
        ],
        'stockCatalysts': [],
        'sentiment': {
            'limitUpCount': 121,
            'limitDownCount': 21,
            'sealRate': 0.938,
            'failRate': 0.062,
            'boardHeight': 4,
            'boardLadder': {'首板': 116, '2连板': 3, '3连板': 1, '4连板': 1},
            'sealRateEval': '极强',
            'makingMoneyRatio': 0.562,
            'emotionPhase': '发酵',
            'emotionNote': '涨停121/跌停21=5.8倍,封板率93.8%极强,上涨家数56.2%,情绪从退潮转向发酵,但连板高度仅4板说明追高意愿有限'
        },
        'capitalFlow': [],
        'social': [],
        'fulfillmentSummary': {
            'total': 27,
            'unpriced': 26,
            'inMotion': 1,
            'halfPriced': 0,
            'exhausted': 0,
            'note': '26只标的近5日回调(多数跌10-26%),催化剂未price-in;仅星网锐捷(002396)近5日+10.45%处于启动区,RSI=77.5需警惕追涨风险'
        }
    },
    'path': 'e:/finacial-invest/data/runs/20260721_short-term-picks/catalyst-scanner.json',
    'summary': '',
    'keyFields': {}
}

stocks = [
    {'code': '001399', 'name': '惠科股份', 'sector': '半导体', 'catalyst_str': '先进封装+半导体显示面板', 'm5': None, 'm5_note': 'K线缺失', 'price': 27.87, 'social_heat': 96.0, 'heat_momentum': 0.1, 'bull_ratio': 0.5, 'hype_risk': 30, 'ths_rank': 22},
    {'code': '300433', 'name': '蓝思科技', 'sector': '半导体', 'catalyst_str': '消费电子+玻璃', 'm5': -5.03, 'm5_note': '回调', 'price': 38.29, 'social_heat': 77.2, 'heat_momentum': 0.12, 'bull_ratio': 0.5, 'hype_risk': 15, 'ths_rank': 47},
    {'code': '688729', 'name': '屹唐股份', 'sector': '半导体', 'catalyst_str': '半导体设备+干法去胶', 'm5': -15.54, 'm5_note': '深度回调', 'price': 29.72, 'social_heat': 8.6, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
    {'code': '000021', 'name': '深科技', 'sector': '半导体', 'catalyst_str': '高端存储封测+扩产', 'm5': -26.39, 'm5_note': '深度回调', 'price': 38.65, 'social_heat': 99.0, 'heat_momentum': 0.02, 'bull_ratio': 0.5, 'hype_risk': 45, 'ths_rank': 18},
    {'code': '600460', 'name': '士兰微', 'sector': '半导体', 'catalyst_str': 'SiC+中报预增+IDM', 'm5': -21.21, 'm5_note': '深度回调', 'price': 32.87, 'social_heat': 91.5, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 45, 'ths_rank': 28},
    {'code': '688728', 'name': '格科微', 'sector': '半导体', 'catalyst_str': 'CMOS图像传感器+12英寸产线', 'm5': -11.75, 'm5_note': '回调', 'price': 16.90, 'social_heat': 15, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
    {'code': '002203', 'name': '海亮股份', 'sector': '半导体', 'catalyst_str': 'PCB铜箔+固态电池', 'm5': -6.14, 'm5_note': '回调', 'price': 18.33, 'social_heat': 9.3, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
    {'code': '002273', 'name': '水晶光电', 'sector': '半导体', 'catalyst_str': 'AI光学+CPO', 'm5': -11.84, 'm5_note': '回调', 'price': 27.56, 'social_heat': 15, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 15, 'ths_rank': None},
    {'code': '600667', 'name': '太极实业', 'sector': '半导体', 'catalyst_str': '存储芯片+先进封装', 'm5': -26.25, 'm5_note': '深度回调', 'price': 16.69, 'social_heat': 100, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 45, 'ths_rank': 10},
    {'code': '600206', 'name': '有研新材', 'sector': '半导体', 'catalyst_str': '半导体靶材+存储芯片', 'm5': -25.02, 'm5_note': '深度回调', 'price': 39.46, 'social_heat': 96.8, 'heat_momentum': -0.02, 'bull_ratio': 0.5, 'hype_risk': 45, 'ths_rank': 21},
    {'code': '688538', 'name': '和辉光电-U', 'sector': '半导体', 'catalyst_str': 'AMOLED显示面板', 'm5': 0.42, 'm5_note': '横盘', 'price': 2.40, 'social_heat': 9.6, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
    {'code': '600641', 'name': '先导基电', 'sector': '半导体', 'catalyst_str': '拟收购先导微电子+半导体设备', 'm5': -20.70, 'm5_note': '深度回调', 'price': 31.83, 'social_heat': 15, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 15, 'ths_rank': None},
    {'code': '688403', 'name': '汇成股份', 'sector': '半导体', 'catalyst_str': '显示驱动芯片封测', 'm5': -15.38, 'm5_note': '回调', 'price': 27.57, 'social_heat': 15, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
    {'code': '002396', 'name': '星网锐捷', 'sector': '半导体', 'catalyst_str': '数据中心交换机+CPO+中报预增', 'm5': 10.45, 'm5_note': '启动(5-15%)', 'price': 31.61, 'social_heat': 100, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 45, 'ths_rank': 13},
    {'code': '600330', 'name': '天通股份', 'sector': '半导体', 'catalyst_str': '光模块上游+铌酸锂+先进封装', 'm5': -16.72, 'm5_note': '深度回调', 'price': 19.13, 'social_heat': 15, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 15, 'ths_rank': None},
    {'code': '600988', 'name': '赤峰黄金', 'sector': '中报预增', 'catalyst_str': '黄金+紫金矿业入主+中报预增', 'm5': 1.52, 'm5_note': '横盘', 'price': 35.48, 'social_heat': 9.5, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
    {'code': '000426', 'name': '兴业银锡', 'sector': '中报预增', 'catalyst_str': '白银+锡+中报预增', 'm5': -7.35, 'm5_note': '回调', 'price': 29.62, 'social_heat': 6.3, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
    {'code': '600884', 'name': '杉杉股份', 'sector': '中报预增', 'catalyst_str': '安徽国资入主+负极材料+中报预增', 'm5': 2.22, 'm5_note': '横盘', 'price': 12.45, 'social_heat': 15, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 15, 'ths_rank': None},
    {'code': '000603', 'name': '盛达资源', 'sector': '中报预增', 'catalyst_str': '白银+铅锌+中报预增', 'm5': -5.57, 'm5_note': '回调', 'price': 20.52, 'social_heat': 3.0, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
    {'code': '002747', 'name': '埃斯顿', 'sector': '机器人', 'catalyst_str': '工业机器人龙头', 'm5': -12.94, 'm5_note': '回调', 'price': 33.43, 'social_heat': 85.5, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 45, 'ths_rank': 36},
    {'code': '002245', 'name': '蔚蓝锂芯', 'sector': '机器人', 'catalyst_str': 'BBU电源+人形机器人+中报预增', 'm5': -17.52, 'm5_note': '深度回调', 'price': 17.23, 'social_heat': 15, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 15, 'ths_rank': None},
    {'code': '300735', 'name': '光弘科技', 'sector': '机器人', 'catalyst_str': 'EMS+机器人', 'm5': -13.15, 'm5_note': '回调', 'price': 19.15, 'social_heat': 15, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 15, 'ths_rank': None},
    {'code': '000048', 'name': '京基智农', 'sector': '机器人', 'catalyst_str': '生猪养殖+机器人+股权转让', 'm5': -8.51, 'm5_note': '回调', 'price': 20.22, 'social_heat': 6.4, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
    {'code': '603890', 'name': '春秋电子', 'sector': '机器人', 'catalyst_str': '液冷服务器+人形机器人', 'm5': -11.35, 'm5_note': '回调', 'price': 19.99, 'social_heat': 15, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 15, 'ths_rank': None},
    {'code': '300450', 'name': '先导智能', 'sector': '储能', 'catalyst_str': '锂电设备+储能', 'm5': -4.96, 'm5_note': '回调', 'price': 32.76, 'social_heat': 15, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 15, 'ths_rank': None},
    {'code': '002459', 'name': '晶澳科技', 'sector': '储能', 'catalyst_str': '光伏组件+储能', 'm5': 0.42, 'm5_note': '横盘', 'price': 7.11, 'social_heat': 9.9, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
    {'code': '688772', 'name': '珠海冠宇', 'sector': '储能', 'catalyst_str': '消费电池+储能', 'm5': -9.84, 'm5_note': '回调', 'price': 14.20, 'social_heat': 13.6, 'heat_momentum': 0.0, 'bull_ratio': 0.5, 'hype_risk': 0, 'ths_rank': None},
]

for s in stocks:
    m5 = s['m5']
    if m5 is None:
        fulfillment = 'K线缺失-按启动处理'
        fulfillment_score = 0
    elif m5 < -15:
        fulfillment = '深度回调-未price-in(正常加分)'
        fulfillment_score = 0
    elif m5 < -5:
        fulfillment = '回调-未price-in(正常加分)'
        fulfillment_score = 0
    elif m5 < 5:
        fulfillment = '横盘-未price-in(正常加分)'
        fulfillment_score = 0
    elif m5 < 15:
        fulfillment = '启动(5-15%)-正常'
        fulfillment_score = 0
    elif m5 < 30:
        fulfillment = '半兑现(15-30%)-催化维-10'
        fulfillment_score = -10
    else:
        fulfillment = '已透支(>30%)-剔除'
        fulfillment_score = -999

    if s['social_heat'] >= 90:
        capital_signal = '高热度(社交热榜前10)-资金关注度高但无龙虎榜明细'
    elif s['social_heat'] >= 70:
        capital_signal = '中高热度-资金关注度中等'
    else:
        capital_signal = '低热度-资金关注度低,龙虎榜无记录'

    sector = s['sector']
    if sector == '半导体':
        catalyst_notes = f"{s['catalyst_str']}:中报窗口+国产替代双催化;近5日{s['m5_note']},催化未price-in,回调可布局"
    elif sector == '中报预增':
        catalyst_notes = f"{s['catalyst_str']}:中报密集披露窗口核心催化;近5日{s['m5_note']},催化未price-in"
    elif sector == '机器人':
        catalyst_notes = f"{s['catalyst_str']}:人形机器人政策+新质生产力;近5日{s['m5_note']},催化未price-in,但单确认方向催化力度弱于半导体"
    else:
        catalyst_notes = f"{s['catalyst_str']}:储能政策+阳光电源回购提振情绪;近5日{s['m5_note']},催化未price-in"

    output['data']['stockCatalysts'].append({
        'code': s['code'],
        'name': s['name'],
        'sector': s['sector'],
        'catalyst': s['catalyst_str'],
        'm5Pct': m5,
        'm5Note': s['m5_note'],
        'fulfillment': fulfillment,
        'fulfillmentScore': fulfillment_score,
        'catalystNotes': catalyst_notes
    })

    output['data']['capitalFlow'].append({
        'code': s['code'],
        'name': s['name'],
        'mainForceNetInflow': 'N/A',
        'dragonTigerSeats': [],
        'signal': capital_signal,
        'dataSource': 'MCP全SSL挂+龙虎榜无记录;替代:社交热度+概念热度'
    })

    output['data']['social'].append({
        'code': s['code'],
        'name': s['name'],
        'heat': s['social_heat'],
        'heat_momentum': s['heat_momentum'],
        'bull_ratio': s['bull_ratio'],
        'hype_risk': s['hype_risk'],
        'ths_rank': s['ths_rank']
    })

top_heat = [s for s in stocks if s['social_heat'] >= 70]
top_heat_names = ', '.join([f"{s['name']}(heat={s['social_heat']})" for s in sorted(top_heat, key=lambda x: x['social_heat'], reverse=True)])

output['summary'] = (
    f"催化主线:中报密集披露+半导体国产替代(双确认顺风)+政治局会议(7月底)+美联储FOMC(7/29-30);"
    f"兑现度:27只中26只近5日回调(多数跌10-26%),催化未price-in,仅星网锐捷(+10.45%)处于启动区;"
    f"情绪温度:涨停121/跌停21,封板率93.8%极强,连板高度4板,上涨家数56.2%,情绪发酵中;"
    f"社交热度Top5:{top_heat_names};"
    f"资金:龙虎榜无记录+主力净流入数据缺失(MCP全SSL挂),替代为社交热度+概念热度评估;"
    f"核心风险:7/29-30美联储偏鹰+政治局会议政策不及预期+中东地缘升级;"
    f"最佳催化窗口:半导体超跌反弹(中报+国产替代)+中报预增业绩兑现,机器人/储能为观察方向"
)

output['keyFields'] = {
    'passCodes': '001399,300433,688729,000021,600460,688728,002203,002273,600667,600206,688538,600641,688403,002396,600330,600988,000426,600884,000603,002747,002245,300735,000048,603890,300450,002459,688772',
    'totalStocks': 27,
    'unpricedCount': 26,
    'inMotionCount': 1,
    'halfPricedCount': 0,
    'exhaustedCount': 0,
    'marketEmotion': '发酵',
    'sealRate': 0.938,
    'boardHeight': 4,
    'mainCatalyst': '中报密集披露+半导体国产替代',
    'dataSource': 'sentiment_engine.py(社交热度)+technical-liquidity(近5日涨幅)+sector-analyst(题材归因)+market_radar(快讯);MCP全SSL挂,龙虎榜/主力资金缺失',
    'note': 'iFind/China-news/Wind MCP全SSL挂,龙虎榜curl端点无记录,资金维仅基于社交热度+概念热度推断'
}

with open('E:/finacial-invest/data/runs/20260721_short-term-picks/catalyst-scanner.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('OK - catalyst-scanner.json written')
print(f"Total stocks: {len(output['data']['stockCatalysts'])}")
print(f"Unpriced: {output['data']['fulfillmentSummary']['unpriced']}")
print(f"In motion: {output['data']['fulfillmentSummary']['inMotion']}")
print(f"Sentiment: limitUp={output['data']['sentiment']['limitUpCount']}, limitDown={output['data']['sentiment']['limitDownCount']}, sealRate={output['data']['sentiment']['sealRate']}")