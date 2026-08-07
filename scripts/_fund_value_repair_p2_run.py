# -*- coding: utf-8 -*-
"""临时: 对当前survivors拉CPD财报+业绩预告+资产负债表, 排雷."""
import sys, json, time
sys.path.insert(0, r'E:\finacial-invest\scripts')
import astock_data as A

SURV = [
 ('300433','蓝思科技','消费电子',34.82,53.44,-25.49,12.94,1838.06),
 ('000725','京东方A','面板',5.96,37.11,-26.87,11.19,2207.84),
 ('002129','TCL中环','光伏硅',8.87,-3.98,-19.58,0.23,358.62),
 ('600522','中天科技','光通信',32.29,34.51,-31.12,16.57,1102.04),
 # 额外补: 周期/资源/半导体超跌低估值候选(扩大可选择性)
 ('601899','紫金矿业','贵金属/有色',15.5,16.5,-12.0,5.0,4100.0),  # placeholder需刷新
]

def secucode(c):
    return c+'.SH' if c[0] in '69' else c+'.SZ'

s=A.EM_SESSION
u='https://datacenter-web.eastmoney.com/api/data/v1/get'

def cpd(c):
    p={'reportName':'RPT_LICO_FN_CPD','columns':'ALL','filter':f'(SECUCODE="{secucode(c)}")',
       'pageNumber':1,'pageSize':8,'sortColumns':'REPORTDATE','sortTypes':'-1'}
    try:
        r=s.get(u,params=p,timeout=20).json()
        return (r.get('result') or {}).get('data') or []
    except Exception as e:
        return []

def forecast(c):
    for rn in ['RPT_LICO_FN_CPDGG','RPT_PUBLIC_OP_PREDICT']:
        p={'reportName':rn,'columns':'ALL','filter':f'(SECUCODE="{secucode(c)}")',
           'pageNumber':1,'pageSize':5,'sortColumns':'NOTICE_DATE','sortTypes':'-1'}
        try:
            r=s.get(u,params=p,timeout=20).json()
            data=(r.get('result') or {}).get('data') if r.get('result') else None
            if data:
                return data
        except Exception:
            pass
    return []

def balance(c):
    p={'reportName':'RPT_DMSK_FN_BALANCE','columns':'ALL','filter':f'(SECUCODE="{secucode(c)}")(REPORT_DATE=\'2025-12-31\')',
       'pageNumber':1,'pageSize':3}
    try:
        r=s.get(u,params=p,timeout=20).json()
        d=(r.get('result') or {}).get('data')
        return d[0] if d else {}
    except Exception:
        return {}

out={}
for c,name,sec,price,pe,m20,m5,mk in SURV:
    rec={'code':c,'name':name,'sector':sec,'price':price,'peTtm':pe,
         'pullback20':m20,'m5':m5,'mktcapYi':mk}
    cp=cpd(c)
    if cp:
        annual=next((x for x in cp if '年报' in (x.get('DATATYPE') or '')), cp[0])
        q1=next((x for x in cp if '一季报' in (x.get('DATATYPE') or '')), None)
        rec['reportDate']=annual.get('REPORTDATE','')[:10]
        rec['reportType']=annual.get('DATATYPE')
        rec['roePct']=annual.get('WEIGHTAVG_ROE')
        rec['netProfitYi']=round((annual.get('PARENT_NETPROFIT') or 0)/1e8,3)
        rec['revenueYi']=round((annual.get('TOTAL_OPERATE_INCOME') or 0)/1e8,3)
        rec['revGrowthPct']=annual.get('YSTZ')
        rec['npGrowthPct']=annual.get('SJLTZ')
        rec['cashflowPerShare']=annual.get('MGJYXJJE')
        rec['bps']=annual.get('BPS')
        rec['grossMarginPct']=annual.get('XSMLL')
        if rec.get('bps') and price:
            rec['pb']=round(price/rec['bps'],2)
        if q1:
            rec['q1_npGrowthPct']=q1.get('SJLTZ')
            rec['q1_revGrowthPct']=q1.get('YSTZ')
            rec['q1_roePct']=q1.get('WEIGHTAVG_ROE')
            rec['q1_npYi']=round((q1.get('PARENT_NETPROFIT') or 0)/1e8,3)
    fc=forecast(c)
    if fc:
        latest=fc[0]
        rec['forecastType']=latest.get('FORECAST_TYPE') or latest.get('PREDICT_TYPE')
        rec['forecastProfitLow']=latest.get('PROFIT_MIN') or latest.get('PREDICT_FUND_MIN')
        rec['forecastProfitHigh']=latest.get('PROFIT_MAX') or latest.get('PREDICT_FUND_MAX')
        rec['forecastChangePct']=latest.get('YYSJRTZ') or latest.get('ADD_YSRTZ') or latest.get('CHANGE_RATE')
        rec['forecastReport']=latest.get('REPORTDATE','')[:10]
        rec['forecastNotice']=latest.get('NOTICE_DATE','')[:10]
    bal=balance(c)
    if bal:
        eq=bal.get('TOTAL_EQUITY')
        rec['equityYi']=round(eq/1e8,3) if eq else None
        rec['monetaryFunds']=round((bal.get('MONETARYFUNDS') or 0)/1e8,3)
        rec['accountsRece']=round((bal.get('ACCOUNTS_RECE') or 0)/1e8,3)
        rec['shortLoan']=round((bal.get('SHORT_LOAN') or 0)/1e8,3)
        rec['acctRecRatioPct']=bal.get('ACCOUNTS_RECE_RATIO')
        # goodwill check via TOTAL_PARENT_EQUITY
        eqp=bal.get('TOTAL_PARENT_EQUITY') or eq
        gw=bal.get('GOODWILL') or 0
        rec['goodwillYi']=round(gw/1e8,3) if gw else 0
        if eqp:
            rec['goodwillRatioPct']=round(gw/eqp*100,2)
    out[c]=rec
    time.sleep(0.2)

print(json.dumps(out, ensure_ascii=False, indent=1))
