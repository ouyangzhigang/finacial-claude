# -*- coding: utf-8 -*-
"""Phase2: 对survivors拉CPD财报(ROE/增速/现金流/PB/毛利率)+业绩预告, 排雷."""
import sys, json, time
sys.path.insert(0, r'E:\finacial-invest\scripts')
import astock_data as A

SURV = [
 ('688512','慧智微','射频芯片',12.9,-20.4,-17.36,10.63,61.0),
 ('300943','春晖智控','智控/汽配',26.6,95.22,-37.32,17.34,54.22),
 ('300433','蓝思科技','消费电子',34.54,53.01,-24.99,3.44,1823.28),
 ('000725','京东方A','面板',5.92,36.86,-22.41,3.68,2193.02),
 ('002129','TCL中环','光伏硅',9.12,-4.1,-14.69,5.8,368.73),
 ('600522','中天科技','光通信',31.74,33.92,-28.83,8.18,1083.27),
]

def secucode(c):
    return c+'.SH' if c[0] in '69' else c+'.SZ'

s=A.EM_SESSION
u='https://datacenter-web.eastmoney.com/api/data/v1/get'

def cpd(c):
    p={'reportName':'RPT_LICO_FN_CPD','columns':'ALL','filter':f'(SECUCODE="{secucode(c)}")',
       'pageNumber':1,'pageSize':8,'sortColumns':'REPORTDATE','sortTypes':'-1'}
    r=s.get(u,params=p,timeout=20).json()
    return (r.get('result') or {}).get('data') or []

def forecast(c):
    # 业绩预告 endpoint
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
    except Exception as e:
        return {}

out={}
for c,name,sec,price,pe,m20,m5,mk in SURV:
    rec={'code':c,'name':name,'sector':sec,'price':price,'peTtm':pe,
         'pullback20':m20,'m5':m5,'mktcapYi':mk}
    # CPD: latest annual + Q1
    cp=cpd(c)
    if cp:
        # find annual (DATATYPE contains 年报) and Q1
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
        # Q1 growth (marginal inflection)
        if q1:
            rec['q1_npGrowthPct']=q1.get('SJLTZ')
            rec['q1_revGrowthPct']=q1.get('YSTZ')
            rec['q1_roePct']=q1.get('WEIGHTAVG_ROE')
            rec['q1_npYi']=round((q1.get('PARENT_NETPROFIT') or 0)/1e8,3)
    # forecast (业绩预告)
    fc=forecast(c)
    if fc:
        latest=fc[0]
        rec['forecastType']=latest.get('FORECAST_TYPE') or latest.get('PREDICT_TYPE')
        rec['forecastProfitLow']=latest.get('PROFIT_MIN') or latest.get('PREDICT_FUND_MIN')
        rec['forecastProfitHigh']=latest.get('PROFIT_MAX') or latest.get('PREDICT_FUND_MAX')
        rec['forecastChangePct']=latest.get('YYSJRTZ') or latest.get('ADD_YSRTZ') or latest.get('CHANGE_RATE')
        rec['forecastReport']=latest.get('REPORTDATE','')[:10]
        rec['forecastNotice']=latest.get('NOTICE_DATE','')[:10]
    # balance sheet (goodwill/equity check)
    bal=balance(c)
    if bal:
        eq=bal.get('TOTAL_EQUITY')
        rec['equityYi']=round(eq/1e8,3) if eq else None
        rec['monetaryFunds']=round((bal.get('MONETARYFUNDS') or 0)/1e8,3)
        rec['accountsRece']=round((bal.get('ACCOUNTS_RECE') or 0)/1e8,3)
        rec['shortLoan']=round((bal.get('SHORT_LOAN') or 0)/1e8,3)
        rec['acctRecRatioPct']=bal.get('ACCOUNTS_RECE_RATIO')
    out[c]=rec
    time.sleep(0.2)

print(json.dumps(out, ensure_ascii=False, indent=1))
