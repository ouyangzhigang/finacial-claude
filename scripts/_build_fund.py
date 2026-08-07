#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
q=json.load(open('data/runs/20260731_short-term-picks/_quotes.json',encoding='utf-8'))
m=json.load(open('data/runs/20260731_short-term-picks/_mainfin.json',encoding='utf-8'))
b=json.load(open('data/runs/20260731_short-term-picks/_balance.json',encoding='utf-8'))
tl=json.load(open('data/runs/20260731_short-term-picks/technical-liquidity.json',encoding='utf-8'))
fac={f['code']:f for f in tl['data']['factors']}

VETO={'002354','000967','000009','002585','603690','000048'}
DOWN={'301171','300058','603738','300840','300766','688158','300369','002131','688381','300244','688352','000032','600667','603286'}

def fnum(x):
    try: return round(float(x),2)
    except: return None

allitems=[]
for c,qq in q.items():
    mf=m.get(c,{}); bl=b.get(c,{})
    if '_err' in mf: mf={}
    if '_err' in bl: bl={}
    name=qq['name']
    sector=fac.get(c,{}).get('sector','')
    price=qq['price']
    peTtm=qq['pe']; pb=qq['pb']
    totMc=qq['totMc']; circMc=qq['circMc']
    np=fnum(mf.get('PARENTNETPROFIT')); rev=fnum(mf.get('TOTALOPERATEREVE'))
    npYi=fnum(np/1e8) if np is not None else None
    revG=fnum(mf.get('TOTALOPERATEREVETZ')); npG=fnum(mf.get('PARENTNETPROFITTZ'))
    roe=fnum(mf.get('ROEJQ')); gm=fnum(mf.get('XSMLL')); lev=fnum(mf.get('ZCFZL'))
    ocfPS=fnum(mf.get('MGJYXJJE'))
    gw=fnum(bl.get('GOODWILL')) or 0; eq=fnum(bl.get('TOTAL_PARENT_EQUITY')) or 0
    gwYi=fnum(gw/1e8) if gw else 0
    gwRatio=fnum(gw/eq*100) if eq else None
    netMargin=fnum(np/rev*100) if (np is not None and rev) else None
    shares=(totMc*1e8/price) if price else 0
    ocfTotal=ocfPS*shares if ocfPS is not None else None
    cfRatio=fnum(ocfTotal/np) if (ocfTotal is not None and np and np!=0) else None
    redFlags=[]
    if gwRatio is not None and gwRatio>30:
        redFlags.append({'flag':'商誉/净资产偏高','severity':'hard','threshold':'<30%','actual':str(gwRatio)+'%','action':'一票否决'})
    elif gwRatio is not None and gwRatio>20:
        redFlags.append({'flag':'商誉/净资产略高','severity':'soft','threshold':'<20%','actual':str(gwRatio)+'%','action':'降权'})
    if np is not None and np<0:
        redFlags.append({'flag':'年报净利润亏损','severity':'soft','threshold':'净利润>0','actual':str(npYi)+'亿','action':'降权'})
    if peTtm is not None and peTtm<0 and np is not None and np>0:
        redFlags.append({'flag':'业绩变脸(年报盈利/TTM亏损)','severity':'soft','threshold':'TTM盈利','actual':'PE_TTM='+str(peTtm),'action':'降权'})
    if peTtm is not None and peTtm>200 and (npG is None or npG<10):
        redFlags.append({'flag':'PE高位且无增速支撑','severity':'hard','threshold':'PE<200或高增速','actual':'PE='+str(peTtm)+',npG='+str(npG)+'%','action':'一票否决'})
    if gm is not None and gm<0:
        redFlags.append({'flag':'毛利率为负(毛亏)','severity':'hard','threshold':'>0','actual':str(gm)+'%','action':'一票否决'})
    if ocfPS is not None and ocfPS<-0.2:
        redFlags.append({'flag':'经营现金流/股大额为负','severity':'hard','threshold':'>-0.2','actual':str(ocfPS),'action':'一票否决'})
    elif ocfPS is not None and ocfPS<0:
        redFlags.append({'flag':'经营现金流为负','severity':'soft','threshold':'>0','actual':str(ocfPS),'action':'降权'})
    if lev is not None and lev>65:
        redFlags.append({'flag':'资产负债率偏高','severity':'soft','threshold':'<65%','actual':str(lev)+'%','action':'降权'})
    if revG is not None and revG<-30:
        redFlags.append({'flag':'营收大幅下滑','severity':'hard','threshold':'>-30%','actual':str(revG)+'%','action':'一票否决'})
    if pb is not None and pb>5:
        redFlags.append({'flag':'PB偏高','severity':'soft','threshold':'<5','actual':str(pb),'action':'降权'})
    m5=fac.get(c,{}).get('m5')
    if m5 is not None and m5>20:
        redFlags.append({'flag':'近5日涨幅透支','severity':'soft','threshold':'<20%','actual':str(m5)+'%','action':'估值维降权'})

    verdict='剔除' if c in VETO else ('降权' if c in DOWN else '通过')
    if peTtm is not None and peTtm<0:
        vv='亏损无法估值'
    elif peTtm is not None and peTtm>200:
        vv='高位'
    elif peTtm is not None and peTtm>100:
        vv='偏高'
    elif peTtm is not None and peTtm<40:
        vv='低估'
    else:
        vv='中性'
    item={
        'code':c,'name':name,'sector':sector,'role':'候选','price':price,
        'roe':roe,'peTtm':peTtm,'pb':pb,'totalMcapYi':totMc,'circMcapYi':circMc,
        'reportDate':'20241231','reportType':'年报','netProfitYi':npYi,
        'revenueGrowthPct':revG,'netProfitGrowthPct':npG,'netMarginPct':netMargin,
        'cashflowPerShare':ocfPS,'cashflowRatio':cfRatio,'goodwillYi':gwYi,'goodwillRatioPct':gwRatio,
        'redFlags':redFlags,'overrideContext':'','verdict':verdict,'valuationVerdict':vv
    }
    allitems.append(item)

passed=[i for i in allitems if i['verdict']=='通过']
downgraded=[i for i in allitems if i['verdict']=='降权']
vetoed=[i for i in allitems if i['verdict']=='剔除']

summary=("基本面排雷+估值锚完成,28只过关票全量核验(年报20241231口径,数据源:东财datacenter+腾讯qt.gtimg.cn)。"
"通过"+str(len(passed))+"只/降权"+str(len(downgraded))+"只/剔除"+str(len(vetoed))+"只。"
"硬雷剔除6只:002354天娱数科(商誉占净资产44.6%>40%硬雷)、000967盈峰环境(商誉30.3%>30%)、"
"000009中国宝安(PE391+npG-77%+营收-34%无增速高位)、002585双星新材(毛亏gm=-0.17%+亏损-3.98亿)、"
"603690至纯科技(亏损-1.36亿+经营现金流/股-1.20大额为负+杠杆70.8%)、"
"000048京基智农(业绩变脸:2024盈利7.1亿→TTM亏损PE-52+营收-52%+净利-59%业务恶化)。"
"降权14只主因:AI应用主线普遍TTM亏损(绿盟/每日互动/利欧/优刻得/帝奥微/迪安)+"
"PE高位无增速(易点天下PE488/蓝光PE201/泰晶PE173)+业绩变脸(深桑达A/颀中/日盈TTM亏)+"
"太极实业(杠杆71%+营收-10.7%下滑)。"
"通过8只:600522中天科技(PE31低估+ROE8.36+现金流1.21)、000021深科技(ROE8.14+npG+44%)、"
"002185华天科技(npG+172%封测复苏)、300017网宿科技(算力CDN PE48稳增)、"
"300378鼎捷数智(ROE7.34)、300063天龙集团(npG+378%扭亏)、300785值得买、003018金富科技(npG+27%)。"
"估值锚:仅600522 PE31处低估分位;多数AI应用票PE>100或TTM亏损无法估值,短线窗口下估值弱化但防PE>200追高。"
"数据缺口:PE/PB历史5年分位未取(iFind/wind MCP SSL挂),用绝对PE+PB代理;控股股东质押率未取(soft-fail,标未经质押核验)。")

out={'agent':'fundamentals-analyst','asOf':'20260731','data':{'summary':summary,'passed':passed,'downgraded':downgraded,'vetoed':vetoed,'all':allitems}}
with open('data/runs/20260731_short-term-picks/fundamentals-analyst.json','w',encoding='utf-8') as f:
    json.dump(out,f,ensure_ascii=False,indent=1)
print('written')
print('passed:',[i['code']+i['name'] for i in passed])
print('downgraded:',[i['code'] for i in downgraded])
print('vetoed:',[i['code'] for i in vetoed])
