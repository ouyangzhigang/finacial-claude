# -*- coding: utf-8 -*-
"""深核 v4: 东财 datacenter-web (trust_env=False+verify=False 绕代理)
   主财务指标(多期:营收/净利同比/ROE/净利率/毛利率) + 资产负债表(商誉/净资产/应收/资产负债率)"""
import sys, os, json, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
import requests, urllib3
urllib3.disable_warnings()
S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0'}); S.trust_env=False
DC='https://datacenter-web.eastmoney.com/api/data/v1/get'

def dc(report, filt, cols='ALL', sort='REPORT_DATE', stype='-1', ps=8):
    p={'reportName':report,'columns':cols,'filter':filt,'pageNumber':'1','pageSize':str(ps),
       'sortColumns':sort,'sortTypes':stype,'source':'WEB','client':'WEB'}
    try:
        r=S.get(DC,params=p,timeout=15,verify=False)
        d=r.json()
        return (d.get('result') or {}).get('data') or []
    except Exception as e:
        return [{'err':str(e)[:80]}]

def main_fin(code):  # 主要财务指标 多期
    return dc('RPT_F10_FINANCE_MAINFINADATA', f'(SECURITY_CODE="{code}")')

def balance(code):   # 资产负债表 多期
    return dc('RPT_F10_FINANCE_GBALANCENEW', f'(SECURITY_CODE="{code}")')

PICKS=["002407","300319","002805","603386","603078","002579","002134","300285","300037","002446","300322","002549","688549"]

def run():
    out={}
    for c in PICKS:
        mf=main_fin(c)
        bal=balance(c)
        # 提取关键: 营收同比/净利同比/ROE/净利率/毛利率 (近4期)
        fin_rows=[]
        for it in (mf[:4] if isinstance(mf,list) else []):
            fin_rows.append({
                'date':(it.get('REPORT_DATE') or '')[:10],
                'rev_yoy':it.get('YSTZ'),     # 营收同比
                'np_yoy':it.get('SJLTZ'),     # 净利润同比
                'roe':it.get('ROEJQ'),
                'npm':it.get('XSJLL'),
                'gpm':it.get('XSMLL'),
                'eps':it.get('EPSJB'),
                'np':it.get('NETPROFIT'),     # 净利润
            })
        bal_rows=[]
        for it in (bal[:3] if isinstance(bal,list) else []):
            bal_rows.append({
                'date':(it.get('REPORT_DATE') or '')[:10],
                'goodwill':it.get('GOODWILL'),
                'equity':it.get('TOTAL_EQUITY') or it.get('EQUITY_PARENT_COMPANY'),
                'recv':it.get('ACCOUNTS_RECE'),
                'total_asset':it.get('TOTAL_ASSETS'),
                'total_liab':it.get('TOTAL_LIABILITIES'),
            })
        out[c]={'fin':fin_rows,'bal':bal_rows}
        print(f"\n=== {c} ===")
        print("FIN:", json.dumps(fin_rows, ensure_ascii=False))
        print("BAL:", json.dumps(bal_rows, ensure_ascii=False))
    print("\n===JSON===")
    print(json.dumps(out, ensure_ascii=False))
    return out

if __name__=="__main__":
    run()
