# -*- coding: utf-8 -*-
import json

def rf(flag, sev, thr, act, actual):
    return {"flag": flag, "severity": sev, "threshold": thr, "actual": actual, "action": act}

passed = [
  {
    "code": "600595", "name": "中孚实业", "sector": "工业金属(铝冶炼)", "role": "估值修复+预增(资源主线)",
    "price": 6.62, "roe": 10.42, "peTtm": 9.51, "pb": 1.45, "fwdPe": 7.1, "totalMcapYi": 265.3, "circMcapYi": 265.3,
    "reportDate": "2026-06-30", "reportType": "半年报快报", "netProfitYi": 18.81,
    "revenueGrowthPct": 34.85, "netProfitGrowthPct": 165.84, "netMarginPct": 21.69,
    "cashflowPerShare": 0.253, "cashflowRatio": 0.54, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -3.0, "chg5": -1.2, "chg1d": -1.8,
    "redFlags": [
      rf("商誉/质押未直接核验", "soft", "商誉<40%净资产/质押<70%", "数据缺失(新浪财报SSL挂);工业金属低并购特征代理低风险", "数据缺失"),
      rf("超跌深度有限", "soft", "近20日跌>15%", "近20日跌3.0%,超跌不深", "近20日跌3.0%"),
      rf("经营现金流/净利0.54偏中性", "soft", "现金流/净利>0.5", "经营现金流10.1亿<净利18.8亿,比值0.54刚过0.5阈值(铝冶炼营运资本占用正常)", "现金流/净利0.54")
    ],
    "overrideContext": "资源主线(铝)+预增166%+营收+34.85%双增+forward PE7.1/PB1.45双低+现金流正,对齐宏观WTI原油催化扩散→工业金属资源股接力+中报兑现线;1w账户6.62元可够得",
    "verdict": "通过", "valuationVerdict": "低估(forward PE7.1/PB1.45,处历史低位区间)",
    "reasoningChain": [
      "因为半年报快报净利18.81亿同比+165.84%且营收+34.85%双增、EPS0.47正、ROE10.42%→预判基本面已扭转,铝价顺周期+业绩兑现双驱动",
      "因为forward PE仅7.1、PB1.45双低且经营现金流10.1亿为正(比值0.54刚过0.5阈值)→预判估值修复空间足,虽现金流略低于净利但铝冶炼营运资本占用属正常",
      "因为近20日仅跌3.0%、近5日跌1.2%未透支→预判未被资金抢跑,中报兑现窗口(近1-5日)有补涨修复空间",
      "因为宏观主线=上海原油主力+5%催化扩散至工业金属资源股+北向370亿回流→预判顺周期资源股有增量资金,铝冶炼顺周期受益"
    ]
  },
  {
    "code": "002064", "name": "华峰化学", "sector": "化学纤维(氨纶)", "role": "估值修复+预增(化工顺周期)",
    "price": 12.05, "roe": 7.03, "peTtm": 20.93, "pb": 2.08, "fwdPe": 15.1, "totalMcapYi": 598.0, "circMcapYi": 598.0,
    "reportDate": "2026-06-30", "reportType": "半年报快报", "netProfitYi": 19.83,
    "revenueGrowthPct": 16.73, "netProfitGrowthPct": 101.64, "netMarginPct": 21.82,
    "cashflowPerShare": 0.277, "cashflowRatio": 0.69, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": 0.0, "chg5": 6.0, "chg1d": 2.34,
    "redFlags": [
      rf("商誉/质押未直接核验", "soft", "商誉<40%/质押<70%", "数据缺失;化纤龙头低并购特征代理低风险", "数据缺失"),
      rf("超跌深度不足", "soft", "近20日跌>15%", "近20日0%已横盘企稳", "近20日0%横盘企稳"),
      rf("经营现金流/净利0.69中性", "soft", "现金流/净利>0.5", "比值0.69过阈值但非强势,氨纶景气初期正常", "现金流/净利0.69")
    ],
    "overrideContext": "氨纶化纤龙头+预增102%+营收+16.73%双增+forward PE15.1/PB2.08+现金流正,对齐化工顺周期+中报兑现;12.05元可够得1w账户",
    "verdict": "通过", "valuationVerdict": "低估(forward PE15.1/PB2.08,化纤龙头估值中低)",
    "reasoningChain": [
      "因为半年报快报净利19.83亿同比+101.64%、营收+16.73%双增且经营现金流13.7亿为正(比值0.69>0.5)→预判基本面反转属实,非一次性损益",
      "因为forward PE15.1、PB2.08处化纤龙头估值中低位→预判估值修复有空间,业绩兑现后PE有进一步压缩动力",
      "因为近20日0%横盘企稳、近5日+6%温和未透支(<30%)→预判资金刚启动,中报披露窗口1-5日有兑现接力空间",
      "因为氨纶化纤顺周期对齐宏观复苏中期+资源催化扩散链→预判顺周期中游受益于需求回暖+原料端油价传导"
    ]
  },
  {
    "code": "600711", "name": "盛屯矿业", "sector": "工业金属(有色采选)", "role": "估值修复+预增(资源主线,双增)",
    "price": 11.74, "roe": 10.47, "peTtm": 13.38, "pb": 2.03, "fwdPe": 10.1, "totalMcapYi": 362.8, "circMcapYi": 362.8,
    "reportDate": "2026-06-30", "reportType": "半年报快报", "netProfitYi": 18.04,
    "revenueGrowthPct": 39.56, "netProfitGrowthPct": 71.37, "netMarginPct": 22.87,
    "cashflowPerShare": 0.739, "cashflowRatio": 1.24, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -1.0, "chg5": 12.5, "chg1d": -1.04,
    "redFlags": [
      rf("商誉/质押未直接核验", "soft", "商誉<40%/质押<70%", "数据缺失;有色采选低商誉特征代理低风险", "数据缺失"),
      rf("历史财务争议需核验", "soft", "无立案/处罚", "盛屯矿业2024年曾因财务问题受监管关注,需核验历史是否已整改;快报现金流强佐证当期真实", "待核验历史监管记录")
    ],
    "overrideContext": "有色采选+预增71%+营收+39.56%双增(非增收不增收,已更正)+PE10.1/PB2.03双低+每股现金流0.739(Top5最强,现金流/净利1.24>1),对齐资源主线;历史监管争议需核验故降权观察而非重仓",
    "verdict": "通过", "valuationVerdict": "低估(forward PE10.1/PB2.03)",
    "reasoningChain": [
      "因为半年报净利18.04亿同比+71.37%且营收+39.56%双增(营收净利同向,非增收不增收)、每股经营现金流0.739(现金流/净利1.24>1最强)→预判盈利质量扎实,非账面利润",
      "因为forward PE10.1、PB2.03双低处有色采选估值低位→预判估值修复空间足,业绩兑现后安全边际厚",
      "因为有色对齐宏观资源股催化扩散+北向回流成长→预判顺周期资源股有增量资金推动,1-5日中报兑现窗口偏多",
      "因为历史监管争议待核验(2024年财务问题)→预判需控仓观察,待年报扣非核验后再决定是否加仓"
    ]
  },
  {
    "code": "002145", "name": "钛能化学", "sector": "化学原料(钛白粉)", "role": "估值修复+预增(低价化工)",
    "price": 4.49, "roe": 3.43, "peTtm": 33.04, "pb": 1.29, "fwdPe": 20.3, "totalMcapYi": 170.9, "circMcapYi": 170.9,
    "reportDate": "2026-06-30", "reportType": "半年报快报", "netProfitYi": 4.2,
    "revenueGrowthPct": 20.89, "netProfitGrowthPct": 61.93, "netMarginPct": 17.91,
    "cashflowPerShare": 0.093, "cashflowRatio": 0.79, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -3.8, "chg5": -1.5, "chg1d": -1.95,
    "redFlags": [
      rf("ROE仅3.43%偏低", "soft", "ROE>8%", "ROE3.43%,扭转初期盈利能力仍弱", "ROE3.43%"),
      rf("商誉/质押未直接核验", "soft", "商誉<40%/质押<70%", "数据缺失;钛白粉行业低商誉代理低风险", "数据缺失")
    ],
    "overrideContext": "钛白粉+预增62%+营收+20.89%双增+PB1.29超低+4.49元低价(1w账户友好)+现金流正,低价低估值修复候选",
    "verdict": "通过", "valuationVerdict": "低估(forward PE20.3/PB1.29超低)",
    "reasoningChain": [
      "因为半年报净利4.2亿同比+61.93%、营收+20.89%双增且经营现金流3.6亿为正(比值0.79>0.5)→预判基本面已从低谷扭转,现金流佐证真实",
      "因为PB仅1.29超低、forward PE20.3、4.49元低价→预判估值修复弹性大,1w账户单票预算可够得,低价修复股弹性优",
      "因为近20日跌3.8%、近5日跌1.5%未透支→预判资金未抢跑,中报兑现窗口有补涨修复空间",
      "因为钛白粉顺周期化工对齐宏观复苏+资源催化扩散→预判顺周期中游受益,但ROE3.43%偏低需控仓"
    ]
  },
  {
    "code": "002107", "name": "沃华医药", "sector": "中药Ⅱ", "role": "估值修复+预增(防守超跌修复,增收不增收)",
    "price": 6.19, "roe": 9.44, "peTtm": 30.12, "pb": 5.03, "fwdPe": 26.3, "totalMcapYi": 35.7, "circMcapYi": 35.7,
    "reportDate": "2026-06-30", "reportType": "半年报快报", "netProfitYi": 0.68,
    "revenueGrowthPct": -7.53, "netProfitGrowthPct": 51.23, "netMarginPct": 77.84,
    "cashflowPerShare": 0.141, "cashflowRatio": 1.17, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -12.5, "chg5": 2.2, "chg1d": -1.14,
    "redFlags": [
      rf("PB5.03偏高", "soft", "PB<3低估", "PB5.03,中药轻资产高ROE致PB偏高", "PB5.03"),
      rf("营收-7.53%而净利+51.23%(增收不增收)", "soft", "营收/净利同向", "营收降7.53%而净利+51.23%(降本/费用控制驱动),持续性存疑", "营收-7.53%/净利+51.23%"),
      rf("商誉/质押未直接核验", "soft", "商誉<40%/质押<70%", "数据缺失;中药老字号低商誉代理低风险", "数据缺失")
    ],
    "overrideContext": "中药+超跌-12.5%(Top5最深且现金流/净利1.17>1健康)+预增51%+ROE9.44%+6.19元低价,防守型估值修复候选;营收降净利增持续性存疑故防守仓位",
    "verdict": "通过", "valuationVerdict": "估值合理(forward PE26.3合理/PB5.03偏高,超跌修复弹性优)",
    "reasoningChain": [
      "因为半年报净利0.68亿同比+51.23%且每股经营现金流0.141(现金流/净利1.17>1)→预判盈利质量健康,扭转有现金流佐证",
      "因为近20日跌12.5%(Top5中超跌最深)、近5日+2.2%未透支→预判超跌修复弹性最大,资金刚企稳未抢跑",
      "因为营收-7.53%而净利+51.23%(增收不增收,降本驱动)→预判持续性存疑,作为防守修复仓而非进攻主仓",
      "因为中药非宏观进攻主线但属防御估值修复→预判在主线分化时有防御价值,1w账户6.19元低价可够得"
    ]
  }
]

downgraded = [
  {
    "code": "002611", "name": "东方精工", "sector": "专用设备", "role": "业绩暴增(疑似非经常性)",
    "price": 16.19, "roe": 50.88, "peTtm": 4.72, "pb": 2.08, "fwdPe": 2.5, "totalMcapYi": 162.5, "circMcapYi": 162.5,
    "reportDate": "2026-06-30", "reportType": "半年报快报", "netProfitYi": 38.46,
    "revenueGrowthPct": -21.68, "netProfitGrowthPct": 867.75, "netMarginPct": 23.46,
    "cashflowPerShare": 0.212, "cashflowRatio": 0.04, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -6.5, "chg5": 3.2, "chg1d": -1.94,
    "redFlags": [
      rf("营收同比-21.68%而净利+867.75%(增收不增收)", "hard", "营收/净利同向", "营收降21.68%而净利暴增867%,典型非经常性/一次性收益特征", "营收-21.68%/净利+867.75%"),
      rf("ROE50.88%异常高", "hard", "ROE<30%合理", "ROE50.88%非经常性损益特征", "ROE50.88%"),
      rf("现金流/净利仅0.04", "hard", "现金流/净利>0.5", "经营现金流/净利0.04严重不匹配,38亿净利无现金流支撑", "现金流/净利0.04")
    ],
    "overrideContext": "PE2.5看似极度低估,但营收-21.68%/净利+867.75%/ROE50.88%/现金流净利比0.04四重异常→典型非经常性损益/一次性收益驱动,纸面利润无现金流支撑,降权剔除",
    "verdict": "降权", "valuationVerdict": "表面低估但盈利质量存疑(非经常性损益疑似占比>20%)",
    "reasoningChain": [
      "因为营收-21.68%+ROE50.88%+净利暴增867%+现金流/净利0.04四重异常同时出现→预判为非经常性损益/一次性收益驱动,非可持续经营利润",
      "因为经营现金流/净利仅0.04(远<0.5阈值)→预判盈利质量红旗,38亿净利无现金流支撑,PE2.5为假低估",
      "因为降权剔除而非硬否决(商誉/质押未命中硬雷)→预判作为观察仓,待年报扣非核验后再定夺"
    ]
  },
  {
    "code": "600110", "name": "诺德股份", "sector": "电池(铜箔)", "role": "超跌但现金流负",
    "price": 10.46, "roe": 1.77, "peTtm": -147.36, "pb": 3.02, "fwdPe": 79.5, "totalMcapYi": 181.5, "circMcapYi": 181.5,
    "reportDate": "2026-06-30", "reportType": "半年报快报", "netProfitYi": 1.03,
    "revenueGrowthPct": 113.33, "netProfitGrowthPct": 242.07, "netMarginPct": 9.16,
    "cashflowPerShare": -0.631, "cashflowRatio": -5.81, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -18.28, "chg5": 18.6, "chg1d": 1.6,
    "redFlags": [
      rf("经营现金流持续为负(每股-0.631)", "hard", "经营现金流>0", "每股经营现金流-0.631,现金流/净利-5.81", "每股经营现金流-0.631/现金流净利比-5.81"),
      rf("forward PE79.5偏贵", "soft", "PE<30低估", "forward PE79.5", "forward PE79.5")
    ],
    "overrideContext": "超跌-18.28%最深+预增242%但每股经营现金流-0.631(净利正现金流负)+forward PE79.5贵+电池非宏观主线,降权剔除",
    "verdict": "降权", "valuationVerdict": "估值偏贵(forward PE79.5)+盈利质量红旗(现金流负)",
    "reasoningChain": [
      "因为净利正1.03亿但经营现金流每股-0.631(持续为负)→预判盈利质量红旗,纸面利润无现金流支撑",
      "因为forward PE79.5偏贵且超跌-18.28%多反映基本面恶化而非错杀→预判超跌修复逻辑弱,反弹持续性存疑",
      "因为电池铜箔非宏观主线(资源/油服/中报)→预判题材错配,1w账户优先主线,降权剔除"
    ]
  },
  {
    "code": "002787", "name": "华源控股", "sector": "包装印刷", "role": "超跌但现金流负",
    "price": 21.24, "roe": 4.03, "peTtm": 50.41, "pb": 3.87, "fwdPe": 46.2, "totalMcapYi": 52.7, "circMcapYi": 52.7,
    "reportDate": "2026-06-30", "reportType": "半年报快报", "netProfitYi": 0.75,
    "revenueGrowthPct": 2.4, "netProfitGrowthPct": 54.81, "netMarginPct": 18.48,
    "cashflowPerShare": -0.319, "cashflowRatio": -2.13, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -21.8, "chg5": 18.4, "chg1d": 1.97,
    "redFlags": [
      rf("经营现金流每股-0.319(净利正现金流负)", "hard", "经营现金流>0", "现金流/净利-2.13", "每股经营现金流-0.319/现金流净利比-2.13"),
      rf("forward PE46.2+PB3.87偏贵", "soft", "PE<30/PB<3", "PE46.2/PB3.87", "PE46.2/PB3.87")
    ],
    "overrideContext": "超跌-21.8%但现金流负+PE46/PB3.87贵+包装印刷非主线,降权剔除",
    "verdict": "降权", "valuationVerdict": "估值偏贵(forward PE46.2/PB3.87)+盈利质量红旗",
    "reasoningChain": [
      "因为净利正但经营现金流每股-0.319→预判盈利质量红旗,超跌或反映基本面恶化",
      "因为forward PE46.2/PB3.87偏贵+包装印刷非宏观主线→预判估值修复+主线错配双失,降权剔除"
    ]
  },
  {
    "code": "300139", "name": "晓程科技", "sector": "贵金属(黄金)", "role": "短线题材(机构建仓),估值偏贵非价值",
    "price": 45.72, "roe": 14.02, "peTtm": 67.6, "pb": 10.69, "fwdPe": None, "totalMcapYi": 125.3, "circMcapYi": 125.3,
    "reportDate": "2025-12-31", "reportType": "2025年报", "netProfitYi": 1.51,
    "revenueGrowthPct": 80.08, "netProfitGrowthPct": 225.26, "netMarginPct": 62.48,
    "cashflowPerShare": 1.051, "cashflowRatio": 1.91, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -2.0, "chg5": None, "chg1d": -0.7,
    "redFlags": [
      rf("PE67.6偏贵(成长股可接受但非低估)", "soft", "PE<30低估", "PE67.6,PB10.69高", "PE67.6/PB10.69"),
      rf("1w账户单票45.72元超40元预算上限", "soft", "单票≤40元", "45.72元,1手=4572元占仓位46%", "单票45.72元>40元预算"),
      rf("无2026H1中报快报,仅2025年报", "soft", "最新一期", "仅2025年报预增+225%,2026H1待确认", "仅2025年报数据")
    ],
    "overrideContext": "2025年报预增+225%(净利1.51亿)+贵金属+现金流强(每股1.051,比值1.91)+ROE14%健康,基本面无硬雷;但PE67.6/PB10.69贵+45.72元超1w账户预算→估值维不加分为中性偏降权,属短线题材/机构建仓票非价值修复票",
    "verdict": "降权", "valuationVerdict": "估值偏贵(PE67.6/PB10.69,成长股可接受但非低估,不符价值修复)",
    "reasoningChain": [
      "因为2025年报净利同比+225%+营收+80%双增+每股经营现金流1.051(比值1.91>1强)+ROE14%→预判基本面健康无硬雷,非一票否决",
      "因为PE67.6/PB10.69偏高(成长/贵金属股估值合理但非低估)→预判不符价值修复低估标准,估值维中性偏降权",
      "因为45.72元超1w账户单票≤40元预算(1手=4572元占仓位46%偏高)+无2026H1快报→预判作为短线题材/机构建仓票而非价值底仓,本路不加分为中性"
    ]
  },
  {
    "code": "002579", "name": "中京电子", "sector": "元件(PCB)", "role": "短线题材(PCB低价补涨),盈利能力极弱",
    "price": 14.38, "roe": 1.13, "peTtm": 335.88, "pb": 3.66, "fwdPe": None, "totalMcapYi": 88.1, "circMcapYi": 88.1,
    "reportDate": "2025-12-31", "reportType": "2025年报", "netProfitYi": 0.27,
    "revenueGrowthPct": 7.11, "netProfitGrowthPct": 131.3, "netMarginPct": 16.94,
    "cashflowPerShare": 0.407, "cashflowRatio": 10.18, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": 3.0, "chg5": None, "chg1d": 3.2,
    "redFlags": [
      rf("ROE仅1.13%极低", "soft", "ROE>8%", "ROE1.13%,盈利能力极弱", "ROE1.13%"),
      rf("PE335.88失效(微利)", "soft", "PE<30低估", "净利仅0.27亿EPS0.04,PE335失效", "PE335.88微利失效"),
      rf("无2026H1中报快报", "soft", "最新一期", "仅2025年报,2026H1待确认", "仅2025年报数据")
    ],
    "overrideContext": "PCB主线低价14.38元补涨票,但2025年报净利仅0.27亿(微利)+ROE1.13%极弱+PE335失效+PB3.66中位→盈利能力弱,估值维不支持,属题材动量非价值修复,降权",
    "verdict": "降权", "valuationVerdict": "估值失效(PE335微利)+盈利能力极弱(ROE1.13%)",
    "reasoningChain": [
      "因为2025年报净利仅0.27亿、EPS0.04、ROE1.13%极低→预判盈利能力极弱,PE335失效无法估值",
      "因为PB3.66中位(非低估)+近20日+3%未超跌→预判不符价值修复(低估+超跌+预增)三标准,纯PCB题材低价补涨",
      "因为基本面弱+无2026H1快报→预判作为短线题材动量票,估值维降权不加分为本路线"
    ]
  },
  {
    "code": "600871", "name": "石化油服", "sector": "油服工程", "role": "短线题材(油服跟风),估值偏贵+增速弱",
    "price": 2.22, "roe": 7.35, "peTtm": 65.22, "pb": 4.53, "fwdPe": None, "totalMcapYi": 420.9, "circMcapYi": 420.9,
    "reportDate": "2025-12-31", "reportType": "2025年报", "netProfitYi": 6.59,
    "revenueGrowthPct": -0.47, "netProfitGrowthPct": 4.3, "netMarginPct": 8.12,
    "cashflowPerShare": 0.351, "cashflowRatio": 10.03, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -2.0, "chg5": None, "chg1d": 0.0,
    "redFlags": [
      rf("净利同比仅+4.3%增速弱", "soft", "净利同比>50%预增", "净利+4.3%,非预增", "净利+4.3%非预增"),
      rf("PE65.22+PB4.53偏贵", "soft", "PE<30/PB<3低估", "PE65/PB4.53", "PE65.22/PB4.53"),
      rf("无2026H1中报快报", "soft", "最新一期", "仅2025年报,2026H1待确认", "仅2025年报数据")
    ],
    "overrideContext": "油服跟风+2.22元超低价弹性+对齐油价催化(上海原油+5%),但2025年报净利+4.3%增速弱+PE65/PB4.53贵→估值维不支持,属低价题材跟风非价值修复,降权",
    "verdict": "降权", "valuationVerdict": "估值偏贵(PE65.22/PB4.53)+增速弱(净利+4.3%非预增)",
    "reasoningChain": [
      "因为2025年报净利6.59亿同比仅+4.3%(非预增>50%)+营收-0.47%停滞→预判业绩无显著增长,不符预增标准",
      "因为PE65.22/PB4.53偏贵→预判不符价值修复低估标准,2.22元低价为弹性非估值优势",
      "因为油服对齐油价催化(上海原油主力+5%)属短线题材跟风→预判作为低价弹性票,估值维降权不加分为本路线"
    ]
  },
  {
    "code": "000723", "name": "美锦能源", "sector": "焦炭Ⅱ", "role": "短线题材(焦化+氢能),业绩亏损",
    "price": 3.5, "roe": -8.13, "peTtm": -14.0, "pb": 1.22, "fwdPe": None, "totalMcapYi": 154.1, "circMcapYi": 154.1,
    "reportDate": "2025-12-31", "reportType": "2025年报", "netProfitYi": -11.23,
    "revenueGrowthPct": -5.58, "netProfitGrowthPct": 1.7, "netMarginPct": 5.46,
    "cashflowPerShare": 0.35, "cashflowRatio": -0.49, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -3.0, "chg5": None, "chg1d": -2.8,
    "redFlags": [
      rf("2025年报亏损11.23亿", "hard", "净利>0", "净利-11.23亿,EPS-0.25,ROE-8.13%", "净利-11.23亿/ROE-8.13%"),
      rf("经营现金流/净利-0.49(净利负致比值失真)", "soft", "现金流/净利>0.5", "净利为负,现金流比失真", "现金流比-0.49失真"),
      rf("无2026H1中报快报", "soft", "最新一期", "仅2025年报亏损,2026H1待确认", "仅2025年报数据")
    ],
    "overrideContext": "焦化+氢能题材+3.5元低价,但2025年报亏损11.23亿+ROE-8.13%→盈利质量红旗,估值维失效(PE负),属题材跟风非价值修复,降权(非一票否决,因非ST)",
    "verdict": "降权", "valuationVerdict": "估值失效(PE负)+盈利质量红旗(亏损11.23亿)",
    "reasoningChain": [
      "因为2025年报净利-11.23亿(亏损)、ROE-8.13%、EPS-0.25→预判盈利质量红旗,估值(PE)失效",
      "因为虽同比+1.7%仅减亏未扭转→预判不符预增/扭转标准,3.5元低价为弹性非估值优势",
      "因为焦化+氢能属短线题材跟风→预判作为低价弹性票,估值维降权不加分为本路线(非一票否决因非ST)"
    ]
  },
  {
    "code": "000963", "name": "华东医药", "sector": "化学制药(创新药+医美)", "role": "低估+超跌但非预增,待中报确认(观察)",
    "price": 28.52, "roe": 14.28, "peTtm": 14.28, "pb": 2.02, "fwdPe": None, "totalMcapYi": 500.2, "circMcapYi": 500.2,
    "reportDate": "2025-12-31", "reportType": "2025年报", "netProfitYi": 34.14,
    "revenueGrowthPct": 4.07, "netProfitGrowthPct": -2.78, "netMarginPct": 32.36,
    "cashflowPerShare": 2.421, "cashflowRatio": 1.24, "goodwillYi": None, "goodwillRatioPct": None,
    "pullback20": -12.25, "chg5": None, "chg1d": -2.0,
    "redFlags": [
      rf("2025年报净利-2.78%微降(非预增)", "soft", "净利同比>50%预增", "净利-2.78%微降,不符预增标准", "净利-2.78%非预增"),
      rf("超跌-12.25%未达>15%深度", "soft", "近20日跌>15%", "近20日跌12.25%", "近20日跌12.25%"),
      rf("无2026H1中报快报", "soft", "最新一期", "仅2025年报,2026H1待8/15前披露确认", "仅2025年报数据")
    ],
    "overrideContext": "PE14.28低估+PB2.02+ROE14.28%强+每股现金流2.421极强(比值1.24>1)+超跌-12.25%+创新药/医美主线,价值修复潜力大;但2025年报净利-2.78%微降非预增,待2026H1中报确认是否扭转,降权观察",
    "verdict": "降权", "valuationVerdict": "低估(PE14.28/PB2.02)但业绩微降非预增,待中报确认",
    "reasoningChain": [
      "因为PE14.28低估+PB2.02+ROE14.28%强+每股经营现金流2.421(比值1.24>1极强)→预判估值与盈利质量均优,价值修复潜力大",
      "因为2025年报净利-2.78%微降(非预增>50%)+无2026H1快报→预判不符预增标准,需待8/15前中报披露确认是否扭转",
      "因为超跌-12.25%未达>15%深度阈值→预判超跌深度中等,作为待确认的价值修复观察仓而非主推"
    ]
  }
]

all_list = []
for s in passed + downgraded:
    all_list.append({
      "code": s["code"], "name": s["name"], "sector": s.get("sector", ""),
      "role": s["role"], "price": s["price"],
      "roe": s["roe"], "peTtm": s["peTtm"], "pb": s["pb"], "fwdPe": s.get("fwdPe"),
      "totalMcapYi": s["totalMcapYi"], "circMcapYi": s["circMcapYi"],
      "reportDate": s["reportDate"], "reportType": s["reportType"], "netProfitYi": s["netProfitYi"],
      "revenueGrowthPct": s["revenueGrowthPct"], "netProfitGrowthPct": s["netProfitGrowthPct"],
      "netMarginPct": s["netMarginPct"],
      "cashflowPerShare": s["cashflowPerShare"], "cashflowRatio": s["cashflowRatio"],
      "goodwillYi": s["goodwillYi"], "goodwillRatioPct": s["goodwillRatioPct"],
      "pullback20": s["pullback20"], "sjltz": s["netProfitGrowthPct"],
      "verdict": s["verdict"], "valuationVerdict": s["valuationVerdict"]
    })

keyFields = {
  "valueCandidates": [
    {"code": "600595", "name": "中孚实业", "pe": 7.1, "peTtm": 9.51, "pb": 1.45, "pullback": -3.0, "pullbackDepth": "浅(-3%,资源底仓型)", "earningsSignal": "半年报快报净利18.81亿同比+165.84%+营收+34.85%双增,EPS0.47,ROE10.42%,每股经营现金流0.253(现金流/净利0.54)", "reasoningChain": ["因为半年报净利同比+165.84%+营收+34.85%双增+EPS正+ROE10.42%→预判基本面已扭转", "因为forward PE7.1/PB1.45双低+经营现金流10.1亿为正(比值0.54刚过阈值)→预判低估+盈利质量可接受,估值修复空间足", "因为近20日仅跌3.0%/近5日跌1.2%未透支→预判资金未抢跑,中报兑现窗口1-5日有补涨修复", "因为铝冶炼对齐宏观上海原油+5%催化扩散→工业金属资源股接力+北向370亿回流→预判顺周期资源股有增量资金"]},
    {"code": "002064", "name": "华峰化学", "pe": 15.1, "peTtm": 20.93, "pb": 2.08, "pullback": 0.0, "pullbackDepth": "无(横盘企稳型)", "earningsSignal": "半年报快报净利19.83亿同比+101.64%+营收+16.73%双增,每股经营现金流0.277(现金流/净利0.69)", "reasoningChain": ["因为净利+101.64%/营收+16.73%双增+经营现金流13.7亿为正(比值0.69>0.5)→预判基本面反转属实非一次性", "因为forward PE15.1/PB2.08处化纤龙头估值中低→预判估值修复有空间,业绩兑现后PE有压缩动力", "因为近20日0%横盘企稳/近5日+6%温和未透支(<30%)→预判资金刚启动,中报披露窗口1-5日有兑现接力", "因为氨纶化纤顺周期对齐宏观复苏中期+资源催化扩散→预判顺周期中游受益需求回暖+油价传导"]},
    {"code": "600711", "name": "盛屯矿业", "pe": 10.1, "peTtm": 13.38, "pb": 2.03, "pullback": -1.0, "pullbackDepth": "浅(-1%,横盘型,双增最强)", "earningsSignal": "半年报快报净利18.04亿同比+71.37%+营收+39.56%双增(已更正非增收不增收),ROE10.47%,每股经营现金流0.739(Top5最强,现金流/净利1.24>1)", "reasoningChain": ["因为净利+71.37%+营收+39.56%双增(营收净利同向)+每股经营现金流0.739(比值1.24>1最强)→预判盈利质量扎实非账面利润", "因为forward PE10.1/PB2.03双低处有色采选估值低位→预判估值修复空间足,安全边际厚", "因为有色对齐宏观资源股催化扩散+北向回流成长→预判顺周期资源股有增量资金,中报兑现窗口偏多", "因为历史监管争议(2024年财务问题)待核验→预判需控仓观察,待年报扣非核验后再决定加仓"]},
    {"code": "002145", "name": "钛能化学", "pe": 20.3, "peTtm": 33.04, "pb": 1.29, "pullback": -3.8, "pullbackDepth": "浅(-3.8%,低价修复型)", "earningsSignal": "半年报快报净利4.2亿同比+61.93%+营收+20.89%双增,ROE3.43%偏低,每股经营现金流0.093(现金流/净利0.79)", "reasoningChain": ["因为净利+61.93%/营收+20.89%双增+经营现金流3.6亿为正(比值0.79>0.5)→预判基本面已从低谷扭转,现金流佐证真实", "因为PB1.29超低+forward PE20.3+4.49元低价→预判估值修复弹性大,1w账户可够得,低价修复股弹性优", "因为近20日跌3.8%/近5日跌1.5%未透支→预判资金未抢跑,中报兑现窗口有补涨修复空间", "因为钛白粉顺周期化工对齐宏观复苏+资源催化扩散→预判顺周期中游受益,但ROE3.43%偏低需控仓"]},
    {"code": "002107", "name": "沃华医药", "pe": 26.3, "peTtm": 30.12, "pb": 5.03, "pullback": -12.5, "pullbackDepth": "中(-12.5%,Top5最深且现金流/净利1.17>1)", "earningsSignal": "半年报快报净利0.68亿同比+51.23%(但营收-7.53%增收不增收),ROE9.44%,每股经营现金流0.141(现金流/净利1.17>1)", "reasoningChain": ["因为净利+51.23%+每股经营现金流0.141(比值1.17>1)→预判盈利质量健康,扭转有现金流佐证", "因为近20日跌12.5%(Top5最深)/近5日+2.2%未透支→预判超跌修复弹性最大,资金刚企稳未抢跑", "因为营收-7.53%而净利+51.23%(增收不增收,降本驱动)→预判持续性存疑,作为防守修复仓而非进攻主仓", "因为中药非宏观进攻主线但防御估值修复→预判主线分化时有防御价值,6.19元低价1w账户可够得"]}
  ],
  "scanUniverse": "中报业绩快报(RPT_LICO_FN_CPD)500只→预增(净利同比>50%)+正盈利+正EPS+正ROE+非ST+半年报=97只→主板/创业板/科创板=44只→低价(≤40)+低估值(fwd PE<50或PB<3)=23只→K线超跌核验=23只(20260807经东方财富datacenter+tencent_quote复核)",
  "softFailNote": "商誉/质押因新浪财报SSL挂+东财数据中心无对应reportName未直接核验;以快报字段(每股经营现金流、ROE合理区间、PB中低)为代理排雷,工业金属/化工/中药传统低并购低商誉行业特征,红旗风险低;深度排雷待iFind/Wind MCP SSL恢复后补。600711盛屯矿业历史财务争议(2024年监管关注)需核验已标注。",
  "dataCorrections": "经20260807 11:30东方财富快报复核,修正3处旧数据:①600711盛屯矿业营收实际+39.56%(非-23.2%),系营收净利双增非增收不增收,redflag移除并升级;②002064华峰化学营收+16.73%(非+96.5%);③002145钛能化学营收+20.89%(非+204%非扭转型);现金流/净利比值按每股现金流/EPS重算(600595=0.54/002064=0.69/600711=1.24/002145=0.79/002107=1.17)。",
  "thesisFit": "中线估值修复逻辑>短线1-5日驱动;Top5对齐宏观资源/化工顺周期+中报兑现线,但严格三标准(超跌>15%+PE分位<30%+预增)无完全命中——深度超跌(>-15%)的预增票多伴随现金流为负(诺德-18%/华源-22%)或PE失效(博敏-17%微利)或PE贵(信立泰-16% PE58),故超跌深度有限(-3%~-12.5%)。建议作为防御底仓而非进攻主仓,进攻主仓仍看题材动量(AI/油服接力)。短线_rec组合(晓程/中京/石化油服/美锦)均PE贵或亏损/微利,估值维不加分为中性偏降权,系题材动量票非价值修复票。"
}

out = {
  "agent": "fundamentals-analyst",
  "asOf": "20260807",
  "horizon": "短线",
  "fetchedAt": "2026-08-07 11:35",
  "data": {
    "summary": "估值修复+业绩预增扫描(20260807 11:30经东方财富RPT_LICO_FN_CPD快报+tencent_quote复核):半年报快报筛预增(净利同比>50%)+正盈利+正EPS+正ROE+非ST+半年报=97只→低价(≤40,1w账户)+低估值(fwd PE<50或PB<3)过滤=23只→逐一取20日K线算超跌深度。结论:预增+低估值+现金流正的票以工业金属/化工/中药顺周期为主,对齐宏观资源股原油催化扩散+中报兑现线;但严格三标准(超跌>15%+PE分位<30%+预增)无完全命中——深度超跌(>-15%)的预增票多伴随现金流为负(诺德-18%/华源-22%)或PE失效(博敏-17%微利)或PE贵(信立泰-16% PE58),故超跌深度有限(-3%~-12.5%)。Top5=中孚实业(铝,PE7.1/PB1.45,预增166%+营收双增,现金流正)、华峰化学(氨纶化纤,PE15.1/PB2.08,预增102%+营收双增,现金流正)、盛屯矿业(有色,PE10.1/PB2.03,预增71%+营收+39.56%双增,现金流/净利1.24最强,历史监管争议待核验)、钛能化学(钛白粉,PE20.3/PB1.29超低,预增62%+营收双增,4.49元低价,现金流正)、沃华医药(中药,PE26.3/PB5.03,预增51%但营收-7.53%增收不增收,超跌-12.5%最深且现金流/净利1.17>1,防守修复)。短线_rec组合(晓程PE68/中京PE335微利/石化油服PE65增速4%/美锦亏损)均不符价值修复,估值维中性偏降权。排雷:商誉/质押因新浪财报SSL挂+东财数据中心无对应reportName,soft-fail;以快报字段(每股经营现金流全正、ROE合理区间、PB中低)为代理排雷,工业金属/化工/中药低并购低商誉行业特征红旗风险低。东方精工(002611)PE2.5看似低估但营收-21.68%/净利+867%/ROE50.88%/现金流净利比0.04四重异常→非经常性损益疑似,降权剔除;诺德股份/华源控股超跌但现金流为负→盈利质量红旗降权。注:此路为中线估值修复逻辑,短线1-5日驱动弱于题材动量,建议作为防御底仓而非进攻主仓。",
    "passed": passed,
    "downgraded": downgraded,
    "vetoed": [],
    "all": all_list,
    "keyFields": keyFields
  }
}

with open("data/runs/20260807_future-picks_短线/fundamentals-analyst.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("written OK, all=", len(all_list), "passed=", len(passed), "downgraded=", len(downgraded))
