import json, sys
sys.path.insert(0, '.')

candidates = [
    # === AI算力/半导体 (27 stocks) ===
    {'code':'603690','name':'至纯科技','sector':'半导体设备','source':'顺风板块+涨幅榜','price':24.88,'mktcap_yi':95.28,'dayChangePct':9.99,'amount_yi':8.51,'note':''},
    {'code':'603931','name':'格林达','sector':'光刻胶/半导体材料','source':'顺风板块+涨幅榜','price':36.22,'mktcap_yi':72.28,'dayChangePct':9.99,'amount_yi':1.76,'note':''},
    {'code':'688709','name':'成都华微','sector':'AI芯片+军工','source':'顺风板块+涨幅榜','price':26.91,'mktcap_yi':59.7,'dayChangePct':15.49,'amount_yi':3.73,'note':'双属性:AI芯片+军工+央企'},
    {'code':'600667','name':'太极实业','sector':'半导体+数据中心','source':'顺风板块+涨幅榜+成交额榜','price':17.92,'mktcap_yi':374.8,'dayChangePct':10.01,'amount_yi':29.54,'note':'双属性:半导体+央企改革'},
    {'code':'002185','name':'华天科技','sector':'半导体封测','source':'顺风板块+成交额榜','price':18.39,'mktcap_yi':611.0,'dayChangePct':-1.08,'amount_yi':53.65,'note':''},
    {'code':'000938','name':'紫光股份','sector':'算力基础设施','source':'顺风板块+成交额榜','price':40.20,'mktcap_yi':1149.7,'dayChangePct':-3.02,'amount_yi':90.35,'note':''},
    {'code':'000063','name':'中兴通讯','sector':'通信设备','source':'顺风板块+成交额榜','price':34.89,'mktcap_yi':1405.2,'dayChangePct':-0.31,'amount_yi':28.06,'note':''},
    {'code':'002436','name':'兴森科技','sector':'PCB+半导体','source':'顺风板块+成交额榜','price':34.62,'mktcap_yi':525.5,'dayChangePct':2.43,'amount_yi':31.12,'note':'双属性:半导体+军工'},
    {'code':'300458','name':'全志科技','sector':'芯片设计','source':'顺风板块+成交额榜','price':40.85,'mktcap_yi':332.6,'dayChangePct':-0.34,'amount_yi':33.29,'note':''},
    {'code':'600522','name':'中天科技','sector':'通信+AI','source':'顺风板块+成交额榜','price':31.97,'mktcap_yi':1091.0,'dayChangePct':1.85,'amount_yi':31.36,'note':''},
    {'code':'603660','name':'苏州科达','sector':'AI应用','source':'顺风板块+涨幅榜','price':8.48,'mktcap_yi':48.5,'dayChangePct':9.99,'amount_yi':1.61,'note':''},
    {'code':'301085','name':'亚康股份','sector':'算力+数据中心','source':'顺风板块+涨幅榜','price':58.16,'mktcap_yi':34.8,'dayChangePct':13.46,'amount_yi':2.83,'note':''},
    {'code':'300684','name':'中石科技','sector':'散热材料','source':'顺风板块+涨幅榜','price':51.40,'mktcap_yi':105.2,'dayChangePct':10.78,'amount_yi':7.85,'note':''},
    {'code':'000636','name':'风华高科','sector':'被动元件','source':'顺风板块+涨幅榜+成交额榜','price':44.24,'mktcap_yi':511.9,'dayChangePct':9.99,'amount_yi':42.63,'note':'双属性:半导体+央企'},
    {'code':'603459','name':'红板科技','sector':'PCB+光模块','source':'顺风板块+涨幅榜','price':92.50,'mktcap_yi':73.1,'dayChangePct':10.00,'amount_yi':13.52,'note':''},
    {'code':'002156','name':'通富微电','sector':'半导体封测','source':'顺风板块+成交额榜','price':74.39,'mktcap_yi':1128.8,'dayChangePct':-2.94,'amount_yi':109.68,'note':'龙头'},
    {'code':'600584','name':'长电科技','sector':'半导体封测','source':'顺风板块+成交额榜','price':81.00,'mktcap_yi':1449.4,'dayChangePct':-2.29,'amount_yi':76.36,'note':'龙头+央企'},
    {'code':'002409','name':'雅克科技','sector':'半导体材料','source':'顺风板块+成交额榜','price':166.31,'mktcap_yi':529.7,'dayChangePct':8.03,'amount_yi':71.04,'note':'龙头'},
    {'code':'600206','name':'有研新材','sector':'半导体材料','source':'顺风板块+成交额榜','price':46.11,'mktcap_yi':390.3,'dayChangePct':4.79,'amount_yi':49.22,'note':'双属性:半导体+央企'},
    {'code':'002281','name':'光迅科技','sector':'光模块','source':'顺风板块+成交额榜','price':188.94,'mktcap_yi':1473.7,'dayChangePct':1.15,'amount_yi':39.26,'note':'龙头+央企'},
    {'code':'000988','name':'华工科技','sector':'光模块','source':'顺风板块+成交额榜','price':109.62,'mktcap_yi':1101.7,'dayChangePct':1.32,'amount_yi':27.13,'note':'双属性:光模块+央企'},
    {'code':'603019','name':'中科曙光','sector':'算力','source':'顺风板块+成交额榜','price':95.33,'mktcap_yi':1394.7,'dayChangePct':-2.23,'amount_yi':35.43,'note':'龙头'},
    {'code':'601138','name':'工业富联','sector':'AI服务器','source':'顺风板块+成交额榜','price':60.97,'mktcap_yi':12098.9,'dayChangePct':1.20,'amount_yi':27.92,'note':'龙头'},
    {'code':'000977','name':'浪潮信息','sector':'服务器','source':'顺风板块+成交额榜','price':83.55,'mktcap_yi':1225.5,'dayChangePct':-2.06,'amount_yi':44.01,'note':'龙头+央企'},
    {'code':'000021','name':'深科技','sector':'封测+存储','source':'顺风板块+成交额榜','price':42.28,'mktcap_yi':665.6,'dayChangePct':0.69,'amount_yi':65.47,'note':'双属性:半导体+央企'},
    {'code':'603228','name':'景旺电子','sector':'PCB','source':'顺风板块+成交额榜','price':79.09,'mktcap_yi':776.6,'dayChangePct':6.02,'amount_yi':25.51,'note':'双属性:PCB+军工'},
    {'code':'002141','name':'贤丰控股','sector':'覆铜板/PCB','source':'热门题材+换手榜','price':5.73,'mktcap_yi':59.2,'dayChangePct':9.98,'amount_yi':9.94,'note':'PCB上游材料'},

    # === 自主可控/军工 (11 stocks) ===
    {'code':'601606','name':'长城军工','sector':'军工','source':'顺风板块+涨幅榜+成交额榜','price':35.26,'mktcap_yi':255.4,'dayChangePct':10.02,'amount_yi':24.17,'note':'龙头+央企;兵装重组'},
    {'code':'002415','name':'海康威视','sector':'安防','source':'顺风板块+成交额榜','price':37.24,'mktcap_yi':3368.8,'dayChangePct':4.93,'amount_yi':74.78,'note':'龙头+央企'},
    {'code':'300045','name':'华力创通','sector':'军工电子','source':'顺风板块+涨幅榜','price':12.21,'mktcap_yi':63.9,'dayChangePct':6.54,'amount_yi':6.75,'note':'双属性:军工+芯片'},
    {'code':'300589','name':'江龙船艇','sector':'船舶制造','source':'顺风板块+换手榜','price':12.45,'mktcap_yi':30.8,'dayChangePct':1.63,'amount_yi':3.58,'note':''},
    {'code':'600775','name':'南京熊猫','sector':'军工+央企','source':'顺风板块+涨幅榜','price':9.41,'mktcap_yi':63.2,'dayChangePct':10.06,'amount_yi':3.26,'note':'双属性:军工+央企;脑机接口概念'},
    {'code':'002309','name':'中利集团','sector':'军工+央企','source':'顺风板块+涨幅榜','price':3.06,'mktcap_yi':73.6,'dayChangePct':10.07,'amount_yi':8.07,'note':'双属性:军工+央企'},
    {'code':'300427','name':'红相股份','sector':'军工电子','source':'顺风板块+换手榜','price':6.42,'mktcap_yi':32.3,'dayChangePct':0.94,'amount_yi':4.20,'note':'双属性:军工+芯片'},
    {'code':'002300','name':'太阳电缆','sector':'军工','source':'顺风板块+换手榜','price':7.36,'mktcap_yi':53.2,'dayChangePct':3.66,'amount_yi':6.22,'note':''},
    {'code':'002298','name':'中电鑫龙','sector':'军工+数据中心','source':'顺风板块+换手榜','price':8.45,'mktcap_yi':55.8,'dayChangePct':4.32,'amount_yi':8.88,'note':'双属性:军工+数据中心'},
    {'code':'603082','name':'北自科技','sector':'军工+机器人','source':'顺风板块+涨幅榜','price':37.29,'mktcap_yi':15.1,'dayChangePct':10.00,'amount_yi':1.51,'note':'双属性:军工+央企;机器人概念'},
    {'code':'688171','name':'纬德信息','sector':'军工信息化','source':'顺风板块+涨幅榜','price':28.20,'mktcap_yi':33.0,'dayChangePct':20.00,'amount_yi':0.91,'note':'量子科技+重大资产重组'},

    # === 央企/国企改革 (8 stocks) ===
    {'code':'600962','name':'国投中鲁','sector':'央企改革','source':'顺风板块+涨幅榜','price':23.57,'mktcap_yi':61.8,'dayChangePct':9.99,'amount_yi':1.83,'note':''},
    {'code':'000011','name':'深物业A','sector':'央企改革','source':'顺风板块+涨幅榜','price':9.09,'mktcap_yi':47.9,'dayChangePct':10.05,'amount_yi':2.42,'note':''},
    {'code':'600617','name':'国新能源','sector':'央企改革','source':'顺风板块+涨幅榜','price':3.73,'mktcap_yi':66.2,'dayChangePct':10.03,'amount_yi':1.94,'note':''},
    {'code':'601218','name':'吉鑫科技','sector':'央企改革','source':'顺风板块+涨幅榜','price':4.47,'mktcap_yi':43.3,'dayChangePct':10.10,'amount_yi':0.85,'note':''},
    {'code':'002310','name':'东方新能','sector':'央企改革','source':'顺风板块+涨幅榜','price':2.41,'mktcap_yi':106.0,'dayChangePct':10.05,'amount_yi':3.61,'note':''},
    {'code':'000815','name':'美利云','sector':'央企+数据中心','source':'顺风板块+换手榜','price':15.73,'mktcap_yi':109.4,'dayChangePct':-2.84,'amount_yi':16.52,'note':'双属性:央企+数据中心'},
    {'code':'301526','name':'国际复材','sector':'央企+通信','source':'顺风板块+成交额榜','price':28.90,'mktcap_yi':405.9,'dayChangePct':12.45,'amount_yi':44.92,'note':'双属性:央企+通信材料'},
    {'code':'688146','name':'中船特气','sector':'军工+央企','source':'顺风板块+涨幅榜+成交额榜','price':276.90,'mktcap_yi':401.4,'dayChangePct':12.71,'amount_yi':48.82,'note':'三属性:半导体材料+军工+央企'},
]

# Add 1w account constraint note
for c in candidates:
    if c['price'] > 40:
        suffix = ';1w不可配' if c['note'] else '1w不可配'
        c['note'] = c['note'] + suffix if c['note'] else suffix

# Sector strengths
sectorStrengths = [
    {'sector':'AI算力/半导体','dayChangePct':1.4,'amount5dEstimate_yi':'高(万亿能级)','leaderCode':'688256','leaderName':'寒武纪','hotTags':['中报预增(9)','半导体板块大面积预增','长鑫科技上市催化','海外AI Capex持续加码'],'subSectors':['半导体设备','芯片设计','封测','光模块','算力/服务器','PCB','材料']},
    {'sector':'自主可控/军工','dayChangePct':2.0,'amount5dEstimate_yi':'中高','leaderCode':'601606','leaderName':'长城军工','hotTags':['央企标签第二(6)','美伊冲突催化','兵装重组','军工现代化'],'subSectors':['军工电子','船舶制造','安防','弹药装备']},
    {'sector':'央企/国企改革','dayChangePct':1.8,'amount5dEstimate_yi':'中','leaderCode':'600667','leaderName':'太极实业','hotTags':['央企标签第二(6)','涨停板多只央企','政治局会议预期','市值管理'],'subSectors':['央企+科技','央企+能源','央企+军工','央企+通信']}
]

# Leaders
leaders = [
    {'code':'688256','name':'寒武纪','sector':'AI算力/半导体','role':'AI芯片龙头;市值7639亿;今日成交63.58亿;20日超跌反弹'},
    {'code':'002371','name':'北方华创','sector':'AI算力/半导体','role':'半导体设备龙头;市值5483亿;今日成交71.63亿;PE=98.9'},
    {'code':'688012','name':'中微公司','sector':'AI算力/半导体','role':'半导体刻蚀设备龙头;市值3684亿;今日成交66.82亿'},
    {'code':'300308','name':'中际旭创','sector':'AI算力/半导体','role':'光模块全球龙头;市值11615亿;今日成交170.16亿;海外AI Capex映射'},
    {'code':'000977','name':'浪潮信息','sector':'AI算力/半导体','role':'AI服务器龙头+央企;市值1226亿;今日成交44.01亿'},
    {'code':'601606','name':'长城军工','sector':'自主可控/军工','role':'军工弹药龙头+央企;兵装重组;今日涨停+10.02%;成交24.17亿'},
    {'code':'002415','name':'海康威视','sector':'自主可控/军工','role':'安防龙头+央企;市值3369亿;今日+4.93%;成交74.78亿;自主可控核心'},
    {'code':'600667','name':'太极实业','sector':'央企/国企改革','role':'半导体+数据中心+央企三属性;今日涨停+10.01%;成交29.54亿;央企改革标杆'},
    {'code':'600775','name':'南京熊猫','sector':'央企/国企改革','role':'军工+央企+脑机接口;今日涨停+10.06%;市值63.2亿;弹性标的'},
]

output = {
    'agent': 'sector-analyst',
    'asOf': '20260727',
    'data': {
        'candidates': candidates,
        'sectorStrengths': sectorStrengths,
        'leaders': leaders,
        'poolSize': len(candidates),
        'summary': '候选池46只,覆盖AI算力/半导体(27只)+自主可控军工(11只)+央企改革(8只)三大顺风方向;1w账户可配(<40元)27只,高价龙头19只标注1w不可配供大账户参考;数据源:cn_fetch.py rank(涨幅/成交额/换手三榜)+astock_data.py概念板块归因+ths_hot_reason热门题材;20日超跌反弹窗口,政治局会议+中报业绩双催化,集中度偏向AI算力/半导体(占59%)',
        'dataSources': ['cn_fetch.py rank changepercent 80', 'cn_fetch.py rank amount 80', 'cn_fetch.py rank turnoverratio 80', 'astock_data.py eastmoney_concept_blocks', 'astock_data.py ths_hot_reason'],
        'dataGaps': ['cn_fetch.py quote/squote/kline均返空(Whistle代理拦截HTTPS),因子数据(m5/m10/m20/amt20)缺失需后续环节补;东财接口SSL全挂,行业板块成分股列表缺失'],
        'tailwinds': ['AI算力/半导体','自主可控/军工','央企/国企改革'],
        'affordableCount': sum(1 for c in candidates if c['price'] <= 40),
        'highPriceCount': sum(1 for c in candidates if c['price'] > 40)
    }
}

with open('data/runs/20260727_short-term-picks/sector-analyst.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'Written {len(candidates)} candidates to sector-analyst.json')
print(f'Affordable (<40): {sum(1 for c in candidates if c["price"] <= 40)}')
print(f'High price (>40): {sum(1 for c in candidates if c["price"] > 40)}')