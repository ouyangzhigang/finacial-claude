#!/usr/bin/env python3
"""Batch technical liquidity analysis for 48 candidates."""
import json, subprocess, sys, os, time

CANDIDATES = [
    ("sh688728","格科微","半导体/CMOS传感器",16.90,11.64,3.05,422.3,True,"live_rank"),
    ("sh688729","屹唐股份","半导体/设备(去胶)",29.72,21.51,4.54,519.6,True,"live_rank"),
    ("sh688371","菲沃泰","半导体/纳米镀膜",27.43,3.90,4.83,92.0,True,"live_rank"),
    ("sz301282","金禄电子","半导体/PCB",20.83,2.77,8.26,36.8,True,"live_rank"),
    ("sh688328","深科达","半导体/设备",78.94,8.44,12.99,74.6,False,"live_rank"),
    ("sh688596","正帆科技","半导体/设备",50.21,20.01,15.10,146.0,False,"live_rank"),
    ("sh688110","东芯股份","存储芯片",120.46,43.89,8.93,532.9,False,"live_rank"),
    ("sh688261","东微半导","半导体/功率器件",71.81,7.99,9.95,87.7,False,"live_rank"),
    ("sh688347","华虹宏力","半导体/晶圆代工",397.78,128.77,8.68,1621.9,False,"live_rank"),
    ("sh688361","中科飞测","半导体/检测设备",366.46,55.70,4.72,1290.1,False,"live_rank"),
    ("sh688001","华兴源创","半导体/检测设备",57.36,9.83,4.05,270.5,False,"live_rank"),
    ("sh688037","芯源微","半导体/设备(涂胶显影)",358.50,32.53,4.98,723.3,False,"live_rank"),
    ("sh688072","拓荆科技","半导体/设备(薄膜沉积)",764.46,80.78,4.15,2161.1,False,"live_rank"),
    ("sh688627","精智达","半导体/设备(测试)",549.01,39.01,8.44,516.8,False,"live_rank"),
    ("sh688797","臻宝科技","半导体/材料",352.38,17.18,18.49,102.9,False,"live_rank"),
    ("sz300604","长川科技","半导体/设备(测试)",318.00,120.48,8.47,1556.5,False,"live_rank"),
    ("sz301369","联动科技","半导体/设备",155.76,7.15,9.32,85.4,False,"live_rank"),
    ("sh688809","强一股份","半导体/设计",429.61,13.42,13.30,111.3,False,"live_rank"),
    ("sh688002","睿创微纳","半导体/红外芯片",150.67,43.33,6.37,708.1,False,"live_rank"),
    ("sh688120","华海清科","半导体/设备(CMP)",273.56,54.24,4.52,1353.4,False,"live_rank"),
    ("sh688003","天准科技","半导体/机器视觉",79.75,6.81,4.91,155.3,False,"live_rank"),
    ("sh688141","杰华特","半导体/模拟芯片",137.36,25.20,4.45,618.6,False,"live_rank"),
    ("sz300814","中富电路","半导体/PCB载板",137.30,13.99,6.02,262.8,False,"live_rank"),
    ("sh688147","微导纳米","半导体/设备(ALD)",125.84,12.84,2.44,584.5,False,"live_rank"),
    ("sz301583","托伦斯","半导体/设备",132.26,14.16,39.64,40.8,False,"live_rank"),
    ("sh688012","中微公司","半导体/设备(刻蚀)",407.89,166.46,4.78,3843.1,False,"live_rank"),
    ("sz300666","江丰电子","半导体/靶材",236.76,62.49,13.23,526.9,False,"live_rank"),
    ("sh688409","富创精密","半导体/零部件",204.10,28.71,5.24,625.0,False,"live_rank"),
    ("sh688662","富信科技","半导体/热电",84.60,11.65,13.88,97.0,False,"live_rank"),
    ("sh688610","埃科光电","半导体/光电检测",165.77,5.04,8.23,67.9,False,"live_rank"),
    ("sh688392","骄成超声","半导体/超声波设备",166.24,10.90,6.26,192.4,False,"live_rank"),
    ("sh688308","欧科亿","半导体/刀具",101.68,16.44,11.75,161.4,False,"live_rank"),
    ("sh688059","华锐精密","半导体/刀具",81.18,10.38,11.16,106.4,False,"live_rank"),
    ("sz002156","通富微电","先进封装",28.5,None,None,380,True,"estimated"),
    ("sh600584","长电科技","先进封装",35.2,None,None,620,True,"estimated"),
    ("sz002185","华天科技","先进封装",12.8,None,None,410,True,"estimated"),
    ("sh603005","晶方科技","先进封装/TSV",32.5,None,None,210,True,"estimated"),
    ("sh600460","士兰微","功率半导体/IGBT",28.8,None,None,450,True,"estimated"),
    ("sh600171","上海贝岭","模拟芯片/电源管理",22.5,None,None,160,True,"estimated"),
    ("sz002079","苏州固锝","半导体分立器件",16.8,None,None,135,True,"estimated"),
    ("sz300236","上海新阳","半导体材料/电镀液",38.5,None,None,120,True,"estimated"),
    ("sz002747","埃斯顿","人形机器人/工业机器人",18.5,None,None,160,True,"estimated"),
    ("sz300024","机器人","人形机器人/工业机器人",22.0,None,None,340,True,"estimated"),
    ("sz300607","拓斯达","人形机器人/注塑机+机器人",16.5,None,None,70,True,"estimated"),
    ("sz300068","南都电源","储能/储能电池",14.5,None,None,125,True,"estimated"),
    ("sz002518","科士达","储能/PCS",32.0,None,None,185,True,"estimated"),
    ("sz002236","大华股份","中报预增/AI安防",22.5,None,None,750,True,"estimated"),
    ("sz002415","海康威视","中报预增/AI安防",35.0,None,None,3200,True,"estimated"),
]

def fetch(code):
    for attempt in range(3):
        try:
            r = subprocess.run(['python','scripts/cn_fetch.py','kline',code,'30'],
                capture_output=True,text=True,timeout=25,cwd=r'E:\finacial-invest')
            if r.returncode==0 and r.stdout.strip():
                return json.loads(r.stdout)
        except:
            time.sleep(1)
    return None

def compute(code,name,sector,price_est,amount_est,turnover_est,fmcap_est,oneW,dq,kline):
    if not kline or len(kline)<21:
        return None
    closes=[float(r[1]) for r in kline][::-1]
    opens=[float(r[2]) for r in kline][::-1]
    highs=[float(r[3]) for r in kline][::-1]
    lows=[float(r[4]) for r in kline][::-1]
    vols=[float(r[5]) for r in kline][::-1]
    n=len(closes)
    tc=closes[-1]; to=opens[-1]; th=highs[-1]; tl=lows[-1]; tv=vols[-1]
    ma5=sum(closes[-5:])/5; ma10=sum(closes[-10:])/10; ma20=sum(closes[-20:])/20
    m5=(tc/closes[-6]-1)*100 if n>=6 else None
    m10=(tc/closes[-11]-1)*100 if n>=11 else None
    m20=(tc/closes[-21]-1)*100 if n>=21 else None
    avg_vol_5=sum(vols[-6:-1])/5 if n>=6 else sum(vols[-5:])/5
    vr=tv/avg_vol_5 if avg_vol_5>0 else None
    avg_amt=sum(vols[i]*closes[i] for i in range(n-20,n))/20/1e8
    # turnover est
    if fmcap_est and tc>0:
        fs=fmcap_est*1e8/tc
        avg_v20=sum(vols[-20:])/20
        to20=(avg_v20/fs)*100 if fs>0 else None
    else:
        to20=None
    # yizi check
    yizi=(to==tc==th==tl and tc>closes[-2]*1.095)
    lu=(tc>=closes[-2]*1.095)
    ld=(tc<=closes[-2]*0.905)
    fsd=(to==tc==th==tl and tc<closes[-2]*0.95)
    # momentum uniformity
    dc5=[(closes[i]-closes[i-1])/closes[i-1]*100 for i in range(n-5,n)]
    up5=sum(1 for c in dc5 if c>0)
    sp=sum(c for c in dc5 if c>0)
    mx=max(dc5) if dc5 else 0
    mcr=mx/sp if sp>0 else 1
    mu="优质(均匀)" if up5>=4 and mcr<0.6 else ("一般" if up5>=3 and mcr<0.8 else "差(集中暴涨)")
    # vol health
    uv=sum(vols[i] for i in range(n-5,n) if closes[i]>closes[i-1])
    dv=sum(vols[i] for i in range(n-5,n) if closes[i]<closes[i-1])
    vhr=uv/dv if dv>0 else 999
    vhl="健康" if vhr>1.2 else ("中性" if vhr>0.8 else "不健康")
    # accel
    m5a=(tc/closes[-6]-1)*100 if n>=6 else 0
    m5b=(closes[-6]/closes[-11]-1)*100 if n>=11 else 0
    ma_val=m5a-m5b
    mal="加速" if ma_val>2 else ("减速" if ma_val<-2 else "平稳")
    # entry type
    a20=tc>ma20; a5=tc>ma5
    h20=max(highs[-20:])
    pd=(tc-h20)/h20*100
    pv="缩量" if tv<avg_vol_5*0.8 else ("放量" if tv>avg_vol_5*1.2 else "正常")
    et=None; es=0
    if a20 and m5 and -8<m5<-3 and pv=="缩量":
        et="健康回调买点"; es=20
    elif a5 and a20 and m5 and 0<m5<5 and vr and vr<1.5:
        et="突破回踩确认"; es=15
    elif m20 and m20<-15 and m5 and m5>0 and vr and vr>1.2:
        et="超跌反弹启动"; es=10
    elif m5 and m5>10 and vr and vr>1.5 and tc<to:
        et="追涨入场(警惕)"; es=-15
    elif m20 and m20>20 and m5 and m5<0 and not a5:
        et="高位派发"; es=-20
    elif a20 and m5 and 0<m5<10 and vr and 0.8<vr<2:
        et="趋势延续"; es=5
    elif not a20 and m5 and m5>0 and m20 and m20<-5:
        et="超跌反弹启动"; es=10
    else:
        et="无明确信号"; es=0
    # exhaustion
    ep="低(<30%)"
    if m5 and m5>15: ep="高(>70%)"
    elif m20 and m20>25 and m5 and m5<0: ep="极高(>80%)"
    elif m5 and m5>10: ep="中(40%)"
    elif m20 and m20>20 and m5 and m5<0: ep="极高(>80%)"
    # RSI14
    gains=[max(0,closes[i]-closes[i-1]) for i in range(n-14,n)]
    losses=[max(0,closes[i-1]-closes[i]) for i in range(n-14,n)]
    ag=sum(gains)/14; al=sum(losses)/14
    rsi=100-(100/(1+ag/al)) if al>0 else 100
    return {
        "code":code,"name":name,"price":round(tc,2),"todayOpen":round(to,2),
        "todayHigh":round(th,2),"todayLow":round(tl,2),
        "isYizi":yizi,"isLimitUp":lu,"isLimitDown":ld,"isFengsiDieting":fsd,
        "m5":round(m5,2) if m5 else None,"m10":round(m10,2) if m10 else None,
        "m20":round(m20,2) if m20 else None,
        "ma5":round(ma5,2),"ma10":round(ma10,2),"ma20":round(ma20,2),
        "avgAmount20d":round(avg_amt,2),
        "estTurnover20d":round(to20,2) if to20 else None,
        "volumeRatio":round(vr,2) if vr else None,
        "upDays5":up5,"momentumUniformity":mu,"maxChangeRatio":round(mcr,2),
        "volumeHealth":vhl,"volumeHealthRatio":round(vhr,2),
        "momentumAccel":round(ma_val,2),"momentumAccelLabel":mal,
        "aboveMA20":a20,"aboveMA5":a5,
        "pullbackDepth":round(pd,2),"pullbackVolume":pv,
        "entryType":et,"entryScore":es,"exhaustionProb":ep,
        "rsi":round(rsi,1),"high20d":round(h20,2),
        "floatMarketCapYi":fmcap_est,"sector":sector,"dataQuality":dq,
        "oneWEligible":oneW,"todayTurnover":turnover_est,"todayAmountYi":amount_est
    }

def threshold(f):
    rs=[]
    if f["avgAmount20d"]<1.0: rs.append(f"日均成交额{f['avgAmount20d']:.2f}亿<1亿")
    if f["estTurnover20d"] is not None:
        if f["estTurnover20d"]<1.0: rs.append(f"换手率20日均{f['estTurnover20d']:.2f}%<1%")
        elif f["estTurnover20d"]>7.0: rs.append(f"换手率20日均{f['estTurnover20d']:.2f}%>7%")
    if f["floatMarketCapYi"] and f["floatMarketCapYi"]<30: rs.append(f"自由流通市值{f['floatMarketCapYi']:.1f}亿<30亿")
    if f["isYizi"]: rs.append("一字涨停(买不进)")
    if f["isFengsiDieting"]: rs.append("封死跌停(出不来)")
    if f["exhaustionProb"] in ["高(>70%)","极高(>80%)"]: rs.append(f"透支概率{f['exhaustionProb']}")
    if f["oneWEligible"] and f["price"]>=40: rs.append(f"股价{f['price']:.2f}>=40元(1w账户)")
    if f["volumeRatio"] is not None:
        if f["volumeRatio"]<0.5: rs.append(f"量比{f['volumeRatio']:.2f}<0.5")
        elif f["volumeRatio"]>5: rs.append(f"量比{f['volumeRatio']:.2f}>5")
    if rs: return (False,"; ".join(rs))
    return (True,"")

results={"pass":[],"reject":[],"factors":[]}
total=len(CANDIDATES)
for i,(code,name,sector,pe,ae,te,fmce,ow,dq) in enumerate(CANDIDATES):
    print(f"[{i+1}/{total}] {code} {name}", file=sys.stderr)
    kl=fetch(code)
    if not kl:
        reasons=[f"K线数据缺失"]
        if fmce and fmce<30: reasons.append(f"自由流通市值{fmce:.1f}亿<30亿")
        if ow and pe and pe>=40: reasons.append(f"股价{pe:.2f}>=40元(1w账户)")
        results["reject"].append({"code":code,"name":name,"reason":"; ".join(reasons),"sector":sector})
        continue
    f=compute(code,name,sector,pe,ae,te,fmce,ow,dq,kl)
    if not f:
        results["reject"].append({"code":code,"name":name,"reason":"K线数据不足(<21日)","sector":sector})
        continue
    passed,reason=threshold(f)
    if passed:
        results["pass"].append(f)
    else:
        results["reject"].append({"code":code,"name":name,"reason":reason,"sector":sector,"price":f["price"]})
    results["factors"].append(f)
    time.sleep(0.2)

np=len(results["pass"]); nr=len(results["reject"])
ets={}
for f in results["pass"]:
    ets[f["entryType"]]=ets.get(f["entryType"],0)+1
rrs={}
for r in results["reject"]:
    mr=r["reason"].split(";")[0]
    rrs[mr]=rrs.get(mr,0)+1
summary=f"过关{np}只/剔除{nr}只; "
if ets: summary+="入场: "+", ".join(f"{k}{v}只" for k,v in sorted(ets.items(),key=lambda x:-x[1])[:3])
if rrs: summary+="; 主要剔除: "+", ".join(f"{k}({v}只)" for k,v in sorted(rrs.items(),key=lambda x:-x[1])[:3])

out={
    "runId":"20260721_short-term-picks","asOf":"20260721","goal":"short-term-picks",
    "agent":"technical-liquidity","fetchedAt":"20260721",
    "data":{"pass":results["pass"],"reject":results["reject"],"factors":results["factors"]},
    "summary":summary,
    "keyFields":{
        "passCodes":",".join(f["code"] for f in results["pass"]),
        "passCount":np,"rejectCount":nr,"totalCandidates":total,
        "hardThresholds":"日均成交额>=1亿,换手率20日均1-7%,自由流通市值>=30亿,非一字涨停/封死跌停,非透支(>70%),1w<40元,量比0.5-5"
    }
}
op=r"E:\finacial-invest\data\runs\20260721_short-term-picks\technical-liquidity.json"
os.makedirs(os.path.dirname(op),exist_ok=True)
with open(op,'w',encoding='utf-8') as fh:
    json.dump(out,fh,ensure_ascii=False,indent=2)
print(f"\nPASS:{np} REJECT:{nr} OUTPUT:{op}",file=sys.stderr)
print(json.dumps(out,ensure_ascii=False,indent=2))