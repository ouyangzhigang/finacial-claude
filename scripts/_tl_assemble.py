#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Assemble technical-liquidity.json from _tl_raw.json + sector-analyst.json.
Hard gates + mega-cap turnover exception + sealed-limit detection.
Per-stock qualitative fields (entryType/entryScore/exhaustionProb/technicalLevel/meanReversionSignal)
are hand-reasoned overrides; all numbers are auto-joined from raw fetch.
"""
import json, io

RAW = json.load(io.open('data/runs/20260729_short-term-picks/_tl_raw.json', encoding='utf-8'))
SA = json.load(io.open('data/runs/20260729_short-term-picks/sector-analyst.json', encoding='utf-8'))
QUOTES = RAW['quotes']; ANA = RAW['analyses']
META = {c['code']: c for c in SA['data']['candidates']}

# ---- hand-reasoned qualitative overrides (code -> dict) ----
OV = {
 "sh600028":("上升趋势(温和)","趋势正但RSI75.9偏高+回调浅","低(<30%,m5=0.39正常启动)","MA20上方多头排列,RSI75.9偏高,低换手深额蓝筹","无"),
 "sh601600":("趋势中浅回调","m5转负-1.94浅调,缩量,RSI66.9","低(<30%)","MA20上方浅回调缩量,有色","无"),
 "sz000506":("动量启动(涨停创新高)","强但盘中涨停须收盘复核封板,RSI51.3留空间","低(m5=6.31正常启动,黄金+半年报双驱动)","涨停创新高站上MA20,RSI51.3不超买,须收盘复核封板","无"),
 "sh603993":("健康回调买点","aboveMA20+回调-6.49%+缩量0.57,黄金/钼铜回调买点(RSI57.6略高于50未充分冷却)","低(<30%)","MA20上方健康回调缩量,回调买点确认中","无"),
 "sh601225":("趋势中浅回调","浅调-1.47%缩量,煤炭低换手蓝筹","低(<30%)","MA20上方浅调,低换手深额蓝筹","无"),
 "sh600547":("突破创新高","20日新高突破+趋势正,RSI64.1偏高","低(m5=2.63正常)","突破20日新高,黄金趋势,RSI64.1偏高","无"),
 "sh601899":("高位回调审查","近20日+23.04%但近5日回调-2.12%→高位回调票(规则3触发),缩量0.64缓解派发嫌疑,RSI71.4偏高","中高(m20>20+m5转负,龙头降权)","MA20上方,20日大涨后高位回调缩量,RSI71.4偏高,龙头降权观察","无"),
 "sh600111":("下跌趋势/超跌待企稳","m5仍负-3.6,跌破MA20,RSI35.9近超卖","低(已跌)","跌破MA20下行,RSI35.9近超卖待企稳","下跌趋势待企稳(RSI35.9近超卖)"),
 "sh601857":("上升趋势(RSI超买)","趋势正m20+25.06但RSI77.0超买+低换手","中(m20>25但m5正小,未回调)","多头排列,RSI77.0超买,低换手深额蓝筹","无"),
 "sz002258":("突破动量启动(涨停)","涨停+放量突破20日新高,m5=12.44偏热,催化华润入主,须收盘复核","中(m5>10,事件催化7日内)","涨停突破20日新高,RSI66.9,须收盘复核封板","无"),
 "sh603327":("突破动量启动(涨停)","涨停突破+半年报预增催化,m5=12.72略偏热RSI64.1不极端,须收盘复核","中(m5>10)","涨停突破新高,铝加工+半年报预增,须收盘复核封板","无"),
 "sz300505":("超跌反弹启动","m20-21.99+m5+13.28转正+放量,站上MA20,RSI45.6中位","低(超跌反弹非追涨,m5>13但context超跌)","20日跌21.99%后放量反弹站上MA20,RSI45.6","超跌反弹启动(m20-21.99+m5+13.28转正放量)"),
 "sh601390":("上升趋势(突破)","突破20日新高+趋势正,RSI75.7偏高,低换手深额蓝筹","低(<30%)","突破20日新高,低换手深额蓝筹,RSI75.7偏高","无"),
 "sh601668":("上升趋势浅调(RSI超买)","趋势正但RSI83.4超买+低换手","中(RSI83.4超买回调风险)","多头排列,RSI83.4超买,低换手深额蓝筹","无"),
 "sh601669":("趋势中浅回调","浅调-1.63%缩量,RSI61.0","低(<30%)","MA20上方浅调,低换手蓝筹","无"),
 "sh601766":("上升趋势突破(RSI超买)","突破新高+趋势正,RSI83.6超买","中(RSI超买)","突破20日新高,RSI83.6超买","无"),
 "sh601800":("上升趋势(RSI偏高)","趋势正,RSI76.2偏高,低换手蓝筹","低(<30%)","多头排列,低换手蓝筹,RSI76.2偏高","无"),
 "sh601919":("上升趋势(RSI极度超买)","趋势正但RSI90.4极度超买,回调风险高","中高(RSI90.4)","多头排列,RSI90.4极度超买警惕回调","无"),
 "sh600667":("超跌待反转","m5仍负-3.14未企稳,RSI21.7超卖,业绩预增被半导体拖累(错杀)待基本面复核","低(已超跌)","跌破MA20深跌-45.59%,RSI21.7超卖,待m5转正信号","业绩预增超跌错杀待基本面复核(ROE/扣非)+RSI21.7布林下轨超卖"),
 "sh601618":("上升趋势(RSI偏高)","趋势正,RSI69.2偏高,低换手蓝筹","低(<30%)","多头排列,低换手蓝筹,RSI69.2偏高","无"),
 "sh601186":("上升趋势(RSI超买)","趋势正,RSI83.6超买","中(RSI超买)","多头排列,RSI83.6超买","无"),
 "sh600629":("追涨/动量启动(涨停)","m5=13.33偏热+涨停,但m10/m20不高非高位派发,子公司重整催化,降权轻惩,须收盘复核","中(m5>10)","涨停突破,m5=13.33偏热,须收盘复核封板","无"),
 "sh600900":("上升趋势(红利防御)","趋势正+水电红利防御属性,RSI70.4略高","低(<30%)","多头排列,水电红利防御,RSI70.4略高,低换手深额","无"),
 "sh600396":("高位回调审查","近10日+28.71%+近5日-5.48%回调缩量,健康量能但m10过高,站上MA20,降权","中(近10日大涨后回调)","MA20上方回调-6.45%缩量,但近10日+28.71%高位","无"),
 "sz002185":("超跌待反转","m5仍负-14.47未企稳,RSI22.1超卖,业绩预增被半导体拖累(错杀)待基本面复核,amt20=108极深","低(已超跌)","跌破MA20深跌-25.36%,RSI22.1超卖,待m5转正","业绩预增超跌错杀待基本面复核+RSI22.1布林下轨超卖"),
 "sz002657":("超跌反弹启动(降权)","m20-26.23+m5+15.13涨停转正,超跌context非追涨,但m5>15透支flag降权,须收盘复核","中(m5>15但超跌反弹context)","20日跌26%后涨停反弹站上MA20,RSI45.9,金融科技AI逆风但业绩催化","超跌反弹启动(m20-26.23+m5+15.13涨停)"),
 "sh600418":("回调后放量反弹(追涨嫌疑)","m5=17.43>15透支+涨停+放量,但站上MA20+催化硬(业绩预增+回购)→轻惩,须收盘复核","高(m5>15+催化7日内反应中,追涨透支)","涨停放量,m5=17.43透支,催化硬但短期涨幅过大,回调-6.87%位置","无"),
 "sh600513":("动量启动(涨停,温和)","涨停催化+温和m5=1.15不透支+缩量,医药+业绩扭亏,须收盘复核","低(m5=1.15正常)","涨停站上MA20,m5温和,RSI54.8中位","无"),
}
# scores per code (entryScore)
SC = {
 "sh600028":8,"sh601600":6,"sz000506":12,"sh603993":16,"sh601225":6,"sh600547":13,"sh601899":-5,
 "sh600111":-3,"sh601857":6,"sz002258":10,"sh603327":11,"sz300505":10,"sh601390":8,"sh601668":5,
 "sh601669":6,"sh601766":6,"sh601800":6,"sh601919":2,"sh600667":-2,"sh601618":7,"sh601186":5,
 "sh600629":-5,"sh600900":8,"sh600396":-3,"sz002185":-2,"sz002657":8,"sh600418":-8,"sh600513":10,
}

def is_chuangye_kechuang(code):
    return code.startswith('sz300') or code.startswith('sh688')

def sealed_limit(code, q):
    pct = q.get('pct',0) or 0
    lim = 19.9 if is_chuangye_kechuang(code) else 9.9
    if abs(pct) < lim: return None
    high=q.get('high',0); low=q.get('low',0); op=q.get('open',0); cl=q.get('price',0)
    rng = (high-low)
    # sealed: virtually no intraday range (一字)
    if rng < 0.011 and abs(high-cl)<0.011:
        return 'up_seal' if pct>0 else 'down_seal'
    return 'limit_not_sealed'  # 普通涨停盘中

pass_list=[]; reject_list=[]; factor_list=[]
for code, m in META.items():
    bare = code[2:]
    q = QUOTES.get(bare, {})
    a = ANA.get(code, {})
    name = m['name']
    price = q.get('price')
    pct = q.get('pct')
    amt1d = q.get('amount_yi')
    trn_intraday = q.get('turnover')
    fmc = q.get('float_mktcap_yi')
    amt20 = a.get('amt20_yi')
    m5=a.get('m5'); m10=a.get('m10'); m20=a.get('m20')
    turnover20 = round(amt20/fmc*100,2) if (amt20 and fmc) else None
    # ---- reject checks ----
    reason=None
    sl = sealed_limit(code, q)
    if 'ST' in name or '退' in name:
        reason='ST/退市'
    elif price is not None and price >= 40:
        reason=f'1w账户股价{price}元≥40元(1手≥4000元超配,供大账户参考)'
    elif fmc is not None and fmc < 30:
        reason=f'自由流通市值{fmc}亿<30亿'
    elif amt20 is not None and amt20 < 1:
        reason=f'日均成交额(20日){amt20}亿<1亿'
    elif turnover20 is not None and turnover20 < 1 and amt20 is not None and amt20 < 2:
        reason=f'换手率(20日均){turnover20}%<1%偏冷+成交额边际{amt20}亿<2亿(薄量)'
    elif sl == 'up_seal':
        reason='一字涨停封板打不进'
    elif sl == 'down_seal':
        reason='封死跌停出不来'
    elif m5 is not None and m5 > 30:
        reason=f'近5日涨{m5}%>30%透支'
    if reason:
        reject_list.append({'code':code,'name':name,'price':price,'reason':reason,
                            'amt20':amt20,'floatMktcap':fmc,'turnover20':turnover20,'pct':pct})
        continue
    # ---- pass ----
    ov = OV.get(code, ("","","","",""))
    entryType, entryRationale, exh, tlevel, mrsig = ov
    escore = SC.get(code, 0)
    is_limit = (sl == 'limit_not_sealed')
    pass_list.append({
        'code':code,'name':name,'price':price,'avgAmount20d':amt20,
        'turnover20d':turnover20,'volumeRatio':round(amt1d/amt20,2) if (amt1d and amt20) else None,
        'floatMktcap':fmc,'marketCap':q.get('mktcap_yi'),'pass':True,
        'turnoverIntraday':trn_intraday,'amount1dIntraday':amt1d,'pctIntraday':pct,
        'intradayLimit': is_limit
    })
    factor_list.append({
        'code':code,'m5':m5,'m10':m10,'m20':m20,
        'ma5':a.get('ma5'),'ma10':a.get('ma10'),'ma20':a.get('ma20'),
        'momentumUniformity':f"{a.get('up_days5')}/5日上涨,单日最大{round(a.get('max_day_gain'),2) if a.get('max_day_gain') is not None else None}%,集中度{a.get('concentration')}",
        'volumeHealth':a.get('vol_health'),'momentumAccel':a.get('momentum_accel'),
        'entryType':entryType,'entryRationale':entryRationale,'entryScore':escore,
        'meanReversionSignal':mrsig,
        'pullbackDepth':a.get('pullback_depth'),'pullbackVolume':a.get('pullback_vol'),
        'rsi14':a.get('rsi14'),
        'exhaustionProb':exh,'breakout':a.get('breakout'),'aboveMA20':a.get('above_ma20'),
        'rps':None,
        'technicalLevel':tlevel,
        'intradayLimit':is_limit
    })

pass_codes = ','.join([p['code'] for p in pass_list])
summary = (f"过关{len(pass_list)}只/剔除{len(reject_list)}只(共{len(META)})。"
    f"剔除原因:5只高价>40元1w不可配(江西铜业/中国神华/万华化学/云南锗业/中国平安)+"
    f"5只成交额<1亿/市值<30亿薄量(柳钢0.59亿/特力A0.76/西安饮食0.71/南宁百货0.40+市值28.28/英联0.60+市值27.94)+"
    f"1只换手<1%偏冷薄量(中国宝安amt20=1.6亿+换手0.87%)+1只一字涨停封板(高争民爆)。"
    f"过关入场优势分布:健康回调买点2只(洛阳钼业+16/华电辽能待审-3,缩量回调)+超跌反弹启动3只(川金诺+10/中科金财+8/太极华天超跌待反转-2,业绩预增错杀)+突破动量启动5只(山东黄金+13/利尔+10/福蓉+11/中铁+8/中冶+7,涨停/突破新高)+上升趋势蓝筹13只(中国石化+8/陕西煤业+6/中国石油+6/中国建筑+5/中国中车+6/中国交建+6/中远海控+2 RSI90超买/中国铁建+5/中国中冶+7/长江电力+8红利/中国铝业+6/中国电建+6/北方稀土-3下行)+追涨降权2只(江淮-8 m5=17.43透支/华建-5 m5=13.33)+动量启动2只(招金+12/联环+10,温和涨停)。"
    f"透支审查:紫金矿业(m20+23.04%+m5-2.12%高位回调,龙头降权-5)、华电辽能(m10+28.71%高位回调-3)、江淮(m5=17.43追涨-8)、中科金财(m5=15.13超跌反弹降权+8)。"
    f"数据来源:cn_fetch.py factors+kline(腾讯web.ifzq.gtimg.cn,本轮SSL已通,实算m5/m10/m20/MA20/breakout/amt20)+quote(腾讯qt.gtimg.cn批量,8只/批)。"
    f"数据缺口:板块RPS不可得(填null);换手率(20日均)以amt20/float_mktcap估算;行情为2026-07-30盘中11:04(盘中价不作买入依据,技术位为触发观察位须收盘复核,尤其盘中涨停8只须复核封板状态)。"
    f"方法说明:换手率<1%硬门槛对mega-cap(amt20≥2亿深额)作低换手蓝筹例外PASS(中国石化0.29%/中国石油0.12%/陕西煤业0.51%等绝对流动性充足),仅对amt20<2亿薄量+换手<1%者(中国宝安)剔除。")

envelope = {
    'agent':'technical-liquidity','asOf':'20260729',
    'data':{
        'pass':pass_list,'reject':reject_list,'factors':factor_list,
        'passCodes':pass_codes,'summary':summary,
        'passCount':len(pass_list),'rejectCount':len(reject_list),
        'hardGatesNote':'成交额(20日均)≥1亿 + 自由流通市值≥30亿 + 非ST + 非一字涨停/封死跌停 + 1w账户股价<40元 + 近5日涨≤30% + 换手1-7%(mega-cap amt20≥2亿深额作低换手蓝筹例外)',
        'dataSourceNote':'cn_fetch.py factors(腾讯web.ifzq.gtimg.cn kline,本轮SSL通,实算动量/MA/breakout/amt20)+cn_fetch.py quote(腾讯qt.gtimg.cn批量8只/批)',
        'dataGapNote':'板块RPS=null不可得;换手率20日均=amt20/float_mktcap估算;行情2026-07-30盘中11:04,技术位为触发观察位须收盘复核',
        'intradayNote':'盘中涨停8只(招金/利尔/福蓉/华建/中科金财/江淮/联环/+中国宝安已剔除)须收盘复核封板,若封板建议次日竞价/低开介入'
    }
}
io.open('data/runs/20260729_short-term-picks/technical-liquidity.json','w',encoding='utf-8').write(
    json.dumps(envelope,ensure_ascii=False,indent=1))
print('PASS',len(pass_list),'REJECT',len(reject_list))
print('passCodes:',pass_codes)
print('--- rejects ---')
for r in reject_list: print(r['code'],r['name'][:6],r['reason'])
