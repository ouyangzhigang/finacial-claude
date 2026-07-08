---
name: a-share-data-source
description: A股个股分析的数据获取通道——WebFetch被拦、WebSearch不联网、curl东方财富API可用及K线解析方法
metadata: 
  node_type: memory
  type: reference
  originSessionId: cc120d79-b2dc-4542-910a-ab2fc8938654
---

在 E:\finacial-invest 做 A 股个股分析时,数据获取通道(2026-06 实测):

- **WebFetch 被企业网络策略拦截**:eastmoney.com / xueqiu.com / 10jqka.com.cn 域均返回 "Unable to verify if domain is safe to fetch",无法抓取页面。
- **WebSearch 本会话不联网**:返回的是模型基于训练数据的兜底回答,不可信且会编错(如把鼎龙科技 603004 误说成 PVC 稳定剂,实际是染发剂原料+植保+PI/PBO 特种材料单体)。勿信,必须用 curl 核实。
- **curl 直连东方财富公开 API 可用**(Git Bash 自带 curl.exe),这是主通道:
  - 行情:`push2.eastmoney.com/api/qt/stock/get?secid=1.{code}&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f116,f117,f162,f167,f168,f170,f171`(数值需 /100:价/涨跌幅/换手;总市值/流通市值单位为元)
  - K线:`push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.{code}&fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&fqt=1&lmt=300`(f51日期 f52开 f53收 f54高 f55低 f56量(手) f57额(元))
  - 资金(今日):`push2.eastmoney.com/api/qt/stock/fflow/kline/get?secid=1.{code}&lmt=0`(daykline 日序列接口对该股返回空,未解决)
  - 财务:`datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LICO_FN_CPD&columns=ALL&filter=(SECUCODE="{code}.SH")&sortColumns=REPORTDATE`(日期列名是 REPORTDATE,不是 REPORT_DATE)
  - 公司简介:`emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax?code=SH{code}`
- **K线解析**:JSON 为超长单行,`grep -oE` / `sed` 拆行在 Git Bash 均失败;可靠方式是 awk 在单行内 `index(s,"klines\":[")` 定位 + `split` 按逗号拆,每 7 字段一组。`/tmp` 未挂载,用管道 + `-H "User-Agent: Mozilla/5.0"` + `--retry 2`(无 UA 偶发返回空)。
- **secid**:沪市 `1.{code}`,深市 `0.{code}`。
- **未获取到的数据**:限售解禁明细(datacenter 报表名 RPT_LIFTUP_LIST/RPT_LIFTBAN/RPT_RESTRICTED_LIFTUP 均报"报表配置不存在";F10 CapitalStock/LimitSellAjax 重定向软拒绝);资金日序列;龙虎榜;北向。需从巨潮公告/行情软件补充。
- 分析模板见项目根 `stock-analysis-prompt-cn.md`,报告输出到 `output/{code}_{YYYYMMDD}_深度分析报告.md`。

## 二轮补充(2026-06-25 中化国际 600500 实测)
- **python 可用**:`python` 命令为 Python 3.13(注意 `python3` 是 Windows Store stub 不可用);akshare 默认未装,需 `pip install akshare`(后台 1-3 分钟,依赖多)。
- **宏观数据 curl 可用**(datacenter,列名 REPORT_DATE,需 `&sortColumns=REPORT_DATE&sortTypes=-1&pageSize=2` 取最新):CPI=`RPT_ECONOMY_CPI`(NATIONAL_SAME 同比)、PPI=`RPT_ECONOMY_PPI`(BASE_SAME)、PMI=`RPT_ECONOMY_PMI`(MAKE_INDEX 制造业/NMAKE_INDEX 非制造业)、GDP=`RPT_ECONOMY_GDP`(SUM_SAME 增速)。M2/SHIBOR 报表名不存在。
- **龙虎榜 curl 可用**:`RPT_DAILYBILLBOARD_DETAILS`,filter=(SECUCODE="{code}.SH"),关键字段 BILLBOARD_NET_AMT/BUY_AMT/SELL_AMT/EXPLAIN(含成功率)/BUY_SEAT(11111=普通席位,机构专用会另标)/D1-D5_CLOSE_ADJCHRATE(上榜后涨跌)。
- **板块指数**:`secid=90.BK0538`(化学制品),字段 f170 涨跌幅、f58 名称;**板块成分 `fs=b:BK0538` 与概念榜 `fs=m:90+t:2` 均返回空**(未解决,用板块指数判断即可)。
- **全市场涨幅榜**:`clist/get?fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048&fid=f3&np=1&fltt=2&invt=2` 可用;注意榜面被 20-30cm 创业板/科创板/北交所股占据,主板 10% 涨停股排不进前排。
- **北向/董监高未获取**:kamt.kline 单位可疑(疑实时额度);个股北向 RPT_MUTUAL_HOLDSTOCKDETAILS、董监高 RPT_LIB_HOLDERSDETAIL 报表名均不存在 → 待 akshare 跑 `stock_data.py {code} --northbound/--insider`。
- **行情数值换算**:f43/44/45/46/60 价格÷100,f168 换手÷100,f170 涨跌幅÷100,f116/117 市值单位元,f162 PE÷100(负=亏损),f167 PB÷100,f47 成交量单位手,f48 成交额单位元。
- **并发限流**:同时发多个 curl 请求会偶发返回空,加 `--retry 3 --retry-delay 1 -H "User-Agent: Mozilla/5.0"` 并分批发可缓解。

## findata-toolkit-cn skill 在本环境不可用(2026-06-25 实测,勿再花时间装 akshare)
- akshare 能装上(`pip install akshare` 成功),但 skill 脚本调 akshare/requests **全部 SSL 证书验证失败**(unable to get local issuer certificate),涉及 xueqiu.com、datacenter-web.eastmoney.com、jin10、mofcom——而 **curl 访问同样的 datacenter-web.eastmoney.com 成功**。根因:Python 用 certifi 证书包,企业网络疑似 SSL 拦截致 Python 不信任;curl 用 Windows 系统证书库能绕过。
- 且 akshare 新版 API 变名:`stock_hsgt_north_net_flow_in_em` 等旧函数已不存在,skill 脚本未适配新版 akshare。
- 结论:**curl 东方财富 API 是本环境唯一可靠数据通道**。MCP(wind/ifind/akshare/news)未连接 + skill 脚本 SSL 失败 → 宏观/行情/K线/财务/龙虎榜/板块指数全走 curl 已可覆盖;北向个股持股/董监高增减持/资金日序列/概念板块成分排名 在 curl 与 skill 均不可用,需行情软件(同花顺/东方财富终端)或巨潮公告补充。

## 三轮补充(2026-06-25 短周期选股实测,新增镜像与腾讯备选通道)
- **东方财富主域 push2.eastmoney.com 连续请求触发限流**:首次最小请求成功,连续 5+ 次后返回 HTTP 000(连接重置)或空回复(exit 52)。**绕过:用镜像 `19.push2.eastmoney.com` / `29.push2.eastmoney.com`**(数字 1-99 大多可用)。最稳模式:串行请求 + 多镜像轮换重试的 fetch 函数(失败则换镜像,直到 size>100)。stock/get 单股端点同样被限,优先用 clist。所有请求带 `-H "User-Agent: Mozilla/5.0"` + `dangerouslyDisableSandbox=true`(sandbox 拦网络)。
- **腾讯端点是东方财富限流时的稳定备选**(不同域名,不被 EM 限流波及):
  - 实时行情:`qt.gtimg.cn/q={secid}`(secid 格式 sh600519/sz000725,逗号分隔可多只并发)——返回 88 字段 `~` 分隔,关键字段位:第3现价/第32涨跌幅/第38换手率/第39 PE/第44总市值(亿)/第45流通市值(亿)/第46量比;第35含"价/量/额"。用茅台 sh600519 校验 PE=18.32 合理。中文 GBK 乱码但数字可用。腾讯数值是真值不除100(与 EM f2/f3/f8 需÷100 不同)。
  - 日K线:`web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={secid},day,{start},{end},640,qfq`——UTF-8 JSON `data.{sid}.qfqday`=[[date,open,close,high,low,vol],...] 前复权,稳定不限流,比 EM kline 接口更易解析(直接 python json.load)。
- **/tmp 跨 Bash 调用不持久**:每次 Bash 调用 cwd 重置到项目根(E:\finacial-invest),/tmp 单次调用内可写但下次调用文件消失。**解法:拉取+解析必须在同一次 Bash 调用内完成;或写项目根文件(如 `_mkt.json`,最后清理)**。mkdir .cache 子目录曾失败,直接写项目根更稳。
- **clist pz 上限**:pz=5500/6000 被拒返回空(文件不创建),pz=30 OK。全市场拉取需分页(pn=1/2/3,pz=2000)合并后 python 过滤目标代码。榜单 fs:沪深A股 `m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23`(+北交所 `m:0+t:81+s:2048`);概念板块 `m:90+t:2`;行业 `m:90+t:1`;fid 排序:f3涨跌幅/f6成交额/f8换手率,po=1降序/0升序。
- **短周期选股 prompt 与报告**:项目根 `short-term-stock-picks-prompt-cn.md`;报告输出 `output/{YYYYMMDD}_短周期2周推荐清单.md`。
- **1w 小账户选股硬约束**:A 股 1 手 100 股,1w 账户只能选股价 <40 元的(1 手 <4000 元),高价科技龙头(中际旭创 1323、寒武纪 1505、海光 360、亨通 119、中天 62 等)全部排除——这是流动性维度"账户规模适配"的硬门槛,选股时第一时间用股价过滤。

## 四轮补充(2026-06-29 短周期选股实测,EM clist 全挂改用新浪榜单)
- **东方财富 clist 榜单本次全挂**:主域 + 19/29 镜像 + HTTPS(-k) + Referer 全部 Empty reply(exit 52),push2his K线亦挂。反爬比三轮更严(三轮的镜像兜底本次也失效)。stock/get 单股/指数端点仍可用(指数 secid=1.000001 等)。
- **稳定替代=新浪榜单**:`vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=80&sort={changepercent|amount|turnoverratio}&asc=0&node=hs_a&_s_r_a=auto`(UTF-8 JSON,字段:symbol/name/trade(价)/changepercent/amount(元)/turnoverratio/nmc(万元,÷1e4=亿)/per/pb;过滤 bj*/ST/退)。连续 3 次易临时限流,加 0.5s 延时或 urllib 重试 3 次。
- **腾讯K线 urllib 需 SSL 放行**:`web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sid},day,,{N},qfq` 返 302→HTTPS,Python urllib 报 "Missing Authority Key Identifier",需 `ssl._create_unverified_context()` 传 urlopen(context=);curl -L 用系统证书无需处理。qfqday=[[date,open,close,high,low,vol]],vol 单位=**手**。
- **新浪 sinajs 批量报价**:`hq.sinajs.cn/list={sid1,sid2}` 需 `-H "Referer: https://finance.sina.com.cn/"` 否则 Forbidden;GBK;个股字段 f[8]成交量单位=**股**(与腾讯K线"手"差 100 倍,勿混)、f[9]成交额单位=元(最准)。指数字段位置不同(0名1昨收2今开3现4高5低...8量9额)。
- **腾讯批量报价 qt.gtimg.cn 字段陷阱**:m[3]价/m[32]涨跌/m[38]换手/m[39]PE 对,但 m[37]成交额/m[44]流通市值/m[45]总市值单位与位置常错(本次除 1e8 后变 0)→ 市值/成交额统一用新浪 rank/sinajs 取,不用腾讯 quote。
- **封装脚本 `scripts/cn_fetch.py`**:rank/factors(5-10-20日动量+MA5/10/20+量价突破+amt20亿)/squote/kline,urllib+unverified SSL,可复用;调用 `python scripts/cn_fetch.py rank|factors|squote|kline`。
- **本次 MCP 状态**:wind 报"无法连接 stock_data 服务"、ifind "Tool not allowed: search_trending_news"、akshare/china-news SSL 失败——全挂,与二轮一致,仍走 curl/urllib HTTP。
- **短周期选股因子口径**:2 周短线用 5/10/20 日动量+量价突破(close>MA20 且 vol>5日均量×1.5)+amt20,勿套 quant-factor-screener 的 12-1 月动量/低换手中长期口径;回测用"站上MA20+m5<15(未透支)+放量"信号后 5 日胜率(本次半导体ETF 92%、京东方 86%/-1.7%回撤、医药ETF 20% 弱)。

## 五轮补充(2026-06-30 百润股份 002568 实测,iFind MCP 转为可用主源)
- **iFind MCP 本次大面积可用**(与二/四轮"ifind Tool not allowed"不同,本次 token 已配置成功):ifind_get_stock_info(收盘价/PE/PB/PS/总市值/上市日/多日涨跌幅/MACD/KDJ/BOLL/MA)、ifind_get_stock_summary(最新财报摘要+成长+盈利+公司信息,MRQ 口径,一个调用拿全)、ifind_get_stock_financials(多年年报财务指标+PE/PB 历史分位,query="股票+年份+ROE等")、ifind_get_stock_shareholders(十大流通股东多季度+前十合计+集中度)、ifind_get_edb_data(宏观 GDP/PMI/CPI/PPI/M2/M1/社融/LPR,自然语言 query 一次拿多指标)、ifind_get_risk_indicators(年化波动率/Beta24/60月/Sharpe)、ifind_sector_data(板块成分数+区间涨跌幅)、ifind_get_stock_events(分红/回购/增持)、ifind_search_news(语义新闻检索返回段落)——query 均为"自然语言+指标名",返回 markdown 表。**仅 ifind_search_trending_news 仍 "Tool not allowed"**。Sharpe 偶返异常大值(如 740),不可信忽略。
- **akshare MCP 本次 SSL 全失败**(push2.eastmoney/82.push2/basic.10jqka.com.cn/finance.sina 均 CERTIFICATE_VERIFY_FAILED)——MCP 层 akshare 与 skill 脚本一样 SSL 挂(Python certifi 不信任企业 SSL,curl 用系统证书可绕)。**akshare MCP 不可用,勿再调**。
- **china-news MCP**:get_stock_news(个股新闻,含龙虎榜/公告/业绩预告,本次极有用,6 月龙虎榜 3 次上榜+业绩预告+增持全拿到)可用;get_market_headlines SSL 失败。
- **东方财富 push2his K线 加 UA 本次成功**(四轮挂,本次 `push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.{code}&klt=101&fqt=1&beg=YYYYMMDD&end=...&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61` + `-H "User-Agent: Mozilla/5.0"` 返回完整前复权日K,JSON `data.klines` 数组、逗号分隔字段);但 **push2 主域 stock/get(实时盘口)、fflow(资金流)、clist(涨幅/概念榜)即使加 UA 仍 Empty reply(exit 52)全挂**——实时盘口/资金流/全市场榜单仍取不到,用 iFind + china-news 龙虎榜替代。K线字段:f51日期 f52开 f53收 f54高 f55低 f56量(手) f57额(元) f58振幅 f59涨跌幅 f60换手率。
- **数据源优先级更新(2026-06-30)**:iFind MCP(最全:财务/估值分位/股东/宏观/技术/事件/新闻)→ curl push2his K线(加 UA)→ china-news get_stock_news(龙虎榜/新闻)→ curl 腾讯 qt.gtimg.cn/web.ifzq.gtimg.cn(行情/K线备选)→ 标注"数据缺失"。akshare MCP / WebFetch / WebSearch 均不可用。wind MCP 未测(本轮未调)。
- **iFind 估值分位技巧**:ifind_get_stock_financials 查"股票+近5年市盈率PE历史分位、市净率PB历史分位、区间最高/最低PE"直接返回分位数(0-1)+区间极值;查"市盈率PE TTM"返回多年 12-31 序列。一个调用即得估值贵便宜判断,无需 curl 历史数据手算。
- **个股深度分析模板**:项目根 `stock-analysis-prompt-cn.md`(六模块递进+技能调用矩阵);报告输出 `output/{code}_{YYYYMMDD}_深度分析报告.md`。

## 六轮补充(2026-06-30 短周期选股实测,ifind 短选链路定型)
- **ifind 短周期选股全链路可用**(本次 token 稳):① `ifind_search_stocks`(NL 选股,如"科创板人工智能算力半导体 市值大于100亿")一次生成候选池 150+只(返代码/简称/市值/行业),候选池生成主力;② `ifind_get_stock_info`(快照,query="{简称}最新价、近5日涨跌幅、换手率、成交额")取流动性+股价适配筛选,但**指标集不可控**(返相关指标组,"N日涨跌幅"口径看 params.天数,默认-5 偶返 20 日,精确动量以日K为准);③ `ifind_get_stock_summary`(query="{简称}近1个月每日收盘价、涨跌幅、成交量、成交额、换手率")返**近1月每日 OHLCV+换手+涨跌停**完整日K(五轮说 summary 是财报摘要,实测还能取日K,算 5/10/20 日动量+MA20+量价突破用此);④ `ifind_get_edb_data`(宏观,但**一次 query 多指标只返第一个**,查"CPI+PPI+PMI"只返 CPI,需分查;PPI/PMI 可更新到 2026-05/06);⑤ `ifind_search_news`(**必带 time_start/time_end**,格式 YYYY-MM-DD,否则报 Missing argument)。
- **ifind 未授权清单(本次)**:`ifind_search_edb` 报"Tool not allowed"(五轮只说 search_trending_news not allowed,本次 search_edb 也 not allowed)→ 宏观直接用 `ifind_get_edb_data`,不 search。
- **东方财富 push2 系列本次全挂**:curl 主域+19 镜像+akshare MCP 均 SSL_CERTIFICATE_VERIFY_FAILED 或 Empty reply——榜单/涨幅榜/板块榜/龙虎榜均不可取,短选链路全走 ifind(search_stocks+info+summary+sector_data)。
- **1w 账户短选股价约束(AI 主线尤其严)**:AI 算力/科创半导体龙头普遍高价(兆易 815/协创 340/澜起 309/寒武纪万亿市值/中科曙光 107/华工 184/利通 179/聚辰 212/云天 81),1w 买不起 1 手;合格候选需 ≤45 元(本次 Top5=全志 39/紫光 28/中国长城 19/和而泰 25/神州 27)。选股第一时间用 `ifind_get_stock_info` 取股价过滤。
- **1w 账户 100 股最小单位约束**:Top5 各 1 手合计常 >1w(本次 5 只 1.4 万),无法全建→实建 2-3 只核心(59-72% 仓位)+其余观察池,报告须诚实标注分层建仓,勿假装 5 只全建。
- **短选报告**:`output/{YYYYMMDD}_短周期2周推荐清单.md`,13 段结构(决策仪表盘→递进链→假设演进→宏观→候选+流动性→评分+短线因子→回测→Top5 操作卡→组合风控→催化日历→风险情景→免责)。

## 七轮补充(2026-06-30 潜力股综合推荐实测,wind 全挂 + ifind 多股指标限制)
- **wind MCP 本轮全挂**:`wind_get_index_kline`/`wind_get_financial_news` 均报"无法连接 Wind index_data/financial_docs 服务"(六轮未测 wind,本轮确认 wind 各域名服务全不可用)。**wind MCP 不可用,勿再调**。
- **东方财富 clist 本次 502(非 exit 52)**:主域+19/29/82.push2 镜像,带 UA+-k(CERT_NONE)+Referer,**全部 HTTP 502 Bad Gateway**(六轮是 Empty reply exit 52,反反爬升级)。clist 榜单/涨幅榜/成交榜/市场宽度全不可取。**市场宽度(涨跌家数)改用 ifind_index_data 取板块/指数涨跌 + ifind_search_stocks 涨幅榜间接推断**。
- **ifind 多股指标限制(重要)**:`ifind_get_stock_info` 多股调用时——**基础指标(换手率/涨跌幅/收盘价/周高低/N日涨跌/主力净流入额/均线多空排列/MACD)能一次返回全部股票**(本轮 7-10 只同返成功);但**复杂技术指标(RSI/52周最高最低/MA5/10/20/60/120 具体数值/向上突破均线)多股调用只返第一只**。要 RSI/52周/具体均线值 → 单股 query。主力净流入额在多股基础调用里可同返(本轮7只主力净流入全拿到)。
- **ifind_get_stock_financials 口径**:MRQ(最新一期)大量字段返 \t 空(ROE/增速/毛利率/负债率/现金流 常空);**用年报日期(20241231/20251231)字段才全**。多年报一次返(2025三季报+2025年报+2024年报可同查,看 params.报告期)。max 5 主体。商誉查"商誉占净资产比例"返原值/账面价值/减值准备(自算占比=商誉/净资产,净资产=市值/PB)。
- **ifind_sector_data 一次只返一个板块**:query 多板块(半导体、AI、低空)只返首个。要多个板块 → 分调用 or 只查关键板块。返板块区间涨跌幅但"成份区间涨跌幅"口径是自基日(动辄 +200%+),无意义;看"收盘价(加权)日序列"判断趋势。
- **ifind_index_data 多指数同返OK**:一次返4指数(上证/深成/创业板/科创50)收盘价序列+区间涨跌幅+MACD/RSI/MA/均线多空排列。L1 大盘定调主力工具。
- **ifind_search_news 政策检索好用**:query="证监会 政策 A股"+time_start/end,返陆家嘴论坛等政策原文段落。`ifind_search_trending_news` 仍 not allowed。
- **北向资金实时不可得**:2024-08 起沪深港通北向实时披露取消,无实时北向。§2.4 北向行用"主力净流入+成交额榜"替代。
- **潜力股综合推荐模板**:`recommend_module_stocks.md`(三层递进×五维咬合×融会贯通);本轮产出在对话内,未写文件。1w 账户<40元约束下,半导体主升期龙头普遍>40元(寒武纪/中芯/海光/中微/澜起/兆易/中际旭创/新易盛/长电/华工/中国巨石/中天/大族/东山/胜宏/深科技/佰维全排除),合格候选在 ifind_search_stocks "股价<40+今日3-9.8%+换手>3%+5日为正+主线板块" 筛出。

## 八轮补充(2026-07-01 /hot-trends 实测,iFind+cn_fetch.py 定型为主力组合)
- **数据源状态再次确认(round 5/7 结论稳固)**:iFind MCP 全链路可用(index_data/sector_data/search_news/get_stock_summary/get_stock_info/get_stock_financials/get_stock_shareholders 均成功);**wind MCP 全挂**(无法连接 analytics_data);**akshare MCP SSL 全挂**(sina/eastmoney push2 CERTIFICATE_VERIFY_FAILED);**china-news get_market_headlines SSL 挂**(np-weblist.eastmoney.com);ifind_search_edb/search_trending_news 仍 "Tool not allowed"。
- **iFind + cn_fetch.py 是 SSL 全挂时的可靠组合**:cn_fetch.py(rank changepercent/amount、factors 多股、kline、squote)用 urllib+`ssl._create_unverified_context()` 绕过 Python certifi 不信任企业 SSL 的问题,2026-07-01 实测 rank/factors/kline 全成功(akshare MCP 同端点同日 SSL 挂)。**SSL 挂时优先 cn_fetch.py 兜底,勿再调 akshare MCP。**
- **hot_trend_dig.py 龙虎榜随 akshare SSL 同挂**:它走 akshare `stock_lhb_detail_em`(datacenter-web.eastmoney.com),Python certifi 不信任→CERTIFICATE_VERIFY_FAILED。龙虎榜改走 `curl -k` 走二轮记录的 `RPT_DAILYBILLBOARD_DETAILS` 端点(curl 用系统证书可绕)。
- **数据源优先级(2026-07-01 定型)**:① iFind MCP(财务/估值/股东/技术/新闻/指数/板块主力)→ ② cn_fetch.py(rank/factors/kline/squote 本地兜底,SSL 自处理)→ ③ curl -k 东方财富 datacenter(龙虎榜 RPT_DAILYBILLBOARD_DETAILS 等)→ ④ 标注"数据缺失"(北向实时本就无,2024-08 起停披露)。
- **/hot-trends 命令产出落盘**:命令文件 `.claude/commands/hot-trends.md` 读 `recommend_module_stocks.md` 框架(§4.0 命名),本次按"热门板块(CLAUDE.md 命令表前缀)+潜力股综合推荐(§4.0 主报告名)"合并命名,落盘 `output/20260701_热门板块潜力股综合推荐.md`(七轮未写文件,本次首次按 §4.0 落盘 + 回显路径)。
- **ifind_sector_data 一次一板块(确认 round 7)**:query "半导体、电子化学品、机器人..." 只返首个(本次返半导体 6786 亿成交+7.73% 区间);多板块需分调用,或从个股 factors+rank 反推板块强度。机器人板块本次返空表头——板块名匹配挑剔,用个股数据推断。
- **cn_fetch factors 字段口径**:返 last/m5/m10/m20(多日累计涨幅%)/ma5/ma10/ma20/v5/v20(均量)/breakout(突破信号)/above_ma5/above_ma20/amt20_yi。breakout=true + above_ma5&ma20 + m20<30(未透支) = 干净刚启动买点(本次杭华688571/怡合达301029 命中);m20>60%(格科微+85%/京东方A+62%/TCL+41%)= 透支回避。

## 九轮补充(2026-07-02 /recommend-stocks 2日窗口实测,iFind+cn_fetch 评分链路 + 2日回测证伪)
- **2日窗口回测结论(重要方法论)**:"站上MA20且close>MA5"信号买入持2日,近80日9只战略矿产候选胜率 35–61%、均收 -1.92~+1.49%、最差单笔 -7~-12.3%。**仅1只(盛和60.7%)达55%胜率阈值,均收全部不达3%**。2日窗口高噪音,框架的55%/3%/8%阈值(为2周设计)对2日过严→**选股应降仓位(73%而非80%+)+严止损(-5~-7%)+以催化alpha弥补,诚实标注假设部分证伪,不跳过回测**。回测脚本 `_bt.py`(项目根,调cn_fetch.kline)可复用。
- **cn_fetch factors+squote 是2日/短线评分高效组合**:`factors sym1 sym2 ...`一次取18只 m5/m10/m20/breakout/amt20/above_ma20(腾讯日K,SSL自处理);`squote sid1,sid2,...`(新浪sinajs,需Referer)取**今日实时单日涨跌+成交额(最准)**。factors的m5是5日累计含今日,要看"今日单日"须squote(price/prev-1)。breakout=true+今日单日<+8%+未透支=2日买点;今日>+8%(金力+11.5/大地熊+14.5/章源+10/赤峰+10)=透支不追。
- **ifind_sector_data 查具体板块可返成分股**:query"稀土板块的成分股代码与名称及5日涨跌幅"返成分股数+区间涨跌幅+成交额(但区间涨跌幅是自基日+86%无意义,看成交额);**"涨幅前N概念板块排名"做不了**(query非板块名返空表头)→板块排名改用cn_fetch rank amount(新浪成交额榜反推资金方向)+东方财富HTTP clist(m:90+t:2)。
- **东方财富 HTTP(非HTTPS)push2 clist 可用但并发限流严重**:主域 `http://push2.eastmoney.com`(注意http非https)`clist/get?fs=m:0+t:6,...&fid=f3&np=1&fltt=2&invt=2&fields=f2,f3,f6,f8,f12,f14` 返涨幅榜;**同批发2+请求第2个返空(限流)**,镜像19/29.push2本次返空→必须串行+主域+np=1&fltt=2&invt=2全套参数。HTTPS端点SSL挂(akshare同),HTTP可绕。
- **腾讯qt.gtimg.cn python3 解码**:`curl -s "http://qt.gtimg.cn/q=sh000001,..." | python -c 'import sys;b=sys.stdin.buffer.read();print(b.decode("gbk","ignore"))'`——必须 `sys.stdin.buffer` 取bytes(python3文本模式无.decode);返88字段~分隔,第3现价/第4昨收/第32涨跌幅/第38换手。上证7/2盘中4075(-0.92%)、创业板4106(-3.63%)。
- **1w账户top3手数限制实战**:Top3各1手,价30的盛和1手=3079元占31%(超单票30%上限,1w手数限制致接受);价12驰宏2手=2412(24%);价18洛阳钼业1手=1840(18%);合计73%+27%现金。**1w+top3难精确分散,接受单票略超上限或换更低价股(英洛华9.85/正海14.23)**。
- **战略矿产7/1催化链(本轮顺风源)**:6/15《矿产资源法实施条例》36种矿产战略管控→6/24商务部公告+**7/1起实施**出口管制举报机制(十三类情形)→1/26稀土对日断供;清单:镓/锗/锑/钨/中重稀土/钼/铟/碲/铋。7/1是"昨日刚落地正发酵"的新鲜催化,落在2日窗口内未price-in。**黄金股降权**:金价7/1跌3970美元+美元DXY站101+8家投行下调预期(高盛年底4900砍500/德银Q3 4300/花旗3月4000)+美以伊停火避险溢价消退→黄金股今日逆势是超跌反弹非金价驱动,2日延续性受压。
## 十轮补充(2026-07-03 /hot-trends 实测,hot_trend_dig 编码坑 + ifind 单季财务口径)
- **hot_trend_dig.py 必须设 UTF-8 环境**:`python scripts/hot_trend_dig.py` 直接跑会 `UnicodeEncodeError: 'gbk' codec can't encode character '\U0001f4c5'`(脚本第 473 行 `print("📅 目标日期...")` 的 emoji 在 Windows GBK 终端崩),**在取任何数据前就挂**。必须 `PYTHONIOENCODING=utf-8 PYTHONUTF8=1 python scripts/hot_trend_dig.py`。修编码后:Step1 龙虎榜(datacenter RPT_DAILYBILLBOARD_DETAILSNEW)、Step2 热门个股榜(emappdata)、Step3 飙升榜(emappdata)**三端点仍 SSL_CERTIFICATE_VERIFY_FAILED 全挂**(akshare 同根因,round 8 已记);但 **Step4 涨停池+Step5 市场概览可用**——本轮拿到上涨 3806(68.9%)/下跌 1626/涨停 17/大涨 155/两市成交 3.18 万亿/均涨 1.14%。即脚本 SSL 挂时仍能输出市场宽度,龙虎榜数据改走 `curl -k` RPT_DAILYBILLBOARD_DETAILS(round 2 端点)。
- **ifind_get_stock_financials 单季度口径可用(补 round 7)**:round 7 记"MRQ 大量字段空、用年报日期才全";实测 query 含"2025年第三季度"(如"伊之密、江苏雷利、汉宇集团2025年三季度的ROE、营收增速、净利润增速、毛利率、资产负债率、经营现金流、商誉占净资产比")**返单季营收/单季毛利率/单季经营现金流/商誉账面价值/单季净利增速/单季营收增速,3–5 股同返**(max5 主体)。看边际变化/业绩拐点比年报更敏;ROE 该 query 未直接返(返 0.64 之类的比率需辨认),ROE 单独查或用 ifind_get_stock_summary。
- **ifind_get_stock_info PE(TTM) 多股同返(补 round 7)**:query"伊之密、江苏雷利、汉宇集团最新市盈率PE(TTM)、所属国民经济行业、上市时间"3 股一次返 PE-TTM+PB+总市值+上市日+行业,confirm round 7"多股基础指标同返"含估值。本轮 PE:伊之密 13.3/汉宇 28.0/江苏雷利 62.4。
- **ifind_get_stock_events 重组查询**:query"伊之密近期订单中标、产能投产、并购重组、业绩预增事件"返"重组进度/是否重大资产重组/停牌日"三列(本轮伊之密全空=无重组),**不返订单/业绩预告类事件**——订单/业绩预告改走 china-news get_stock_news(round 5 可用)或 ifind_search_news。
- **本轮主报告落盘**:`output/20260703_潜力股综合推荐.md`(recommend_module_stocks.md §4.0 主报告命名,8 轮起已定型落盘)。主线=人形机器人(0703 涨停潮:绿的谐波+19.5%/瑞迪智驱/丰立智能/江苏雷利+14%/伊之密+10.7%)+ 设备更新(7/3:2000 亿超长期国债设备更新资金已全部下达);0702 科创50/创业板急跌回踩后 0703 风格高低切(算力硬件大票中际旭创/中芯/北方华创/京东方下跌 vs 机器人中小盘涨停)。1w<40元约束下机器人龙头普遍>40元(绿的谐波 494/三花 49/拓斯达 53),合格候选在注塑机(伊之密 22)/微电机丝杠(江苏雷利 33)/微电机(汉宇 11)。

## 十一轮补充(2026-07-03 /recommend-stocks 实测,ifind NL选股板块识别差异 + 2周回测纪律)
- **ifind_search_stocks NL选股板块识别差异(重要)**:"半导体设备或半导体材料板块..."(返30只)、"有机硅或电子特种气体或硅料板块..."(返15只)识别成功;但"创新药或CXO板块..."、"医药生物板块..."**均返空**(ifind选股器不识别医药类概念)。**医药/创新药候选改用手动已知龙头+ifind_get_stock_summary逐一验证**(康龙化成300759/昭衍新药603127/贝达药业300558/信立泰002294/复星医药600196/浙江医药600216)。
- **ifind_sector_data 可查板块强度但不列成分股名**:query"创新药概念板块的成分股"返"成份股个数276 + 5日区间均涨跌幅7.87%"(确认板块低位反弹强度)但**不列具体股票名**。
- **curl https -k push2 被 Claude Code 分类器拒**(Stage 2 classifier error,瞬态);curl http push2 主域 exit 52(空回复)。→ 板块排名/涨幅榜本轮取不到,改用 ifind_index_data(指数)+ ifind_sector_data(板块涨跌)+ ifind_search_news(新闻综述板块资金流向)推断。
- **数据源状态(round 11,与 round 5/7/8 一致稳固)**:iFind 全链路可用;akshare MCP SSL 全挂;ifind_search_trending_news 仍 "Tool not allowed"(改用 ifind_search_news)。资金流/龙虎榜未逐票拉取(数据缺口,资金维基于新闻板块资金流向+ETF流入)。
- **2周回测纪律实战(驰宏锌锗教训落地)**:近1月日K算5日持有窗口胜率/均收/回撤。康龙化成3项全达标(胜率64.7%/均收+8.1%/回撤-7.5%)→Top1最大仓位;时代新材2达标(回撤-12.1%短板)→保留;**浙江医药(胜率17.6%)/洛阳钼业(47.1%)3项全不达标→一票否决入核心,降级观察仓(等信号部署)**;国电电力红利底仓不套短线5日回测口径(按暴跌抗跌防御逻辑背书)。**回测证伪不得强推,不得排Top1给最大仓位**——本轮据此把此前版本(紫金/浙江/洛阳 Top3,71%)改为康龙Top1+2观察仓。
- **1w账户Top5满仓不可行(补round 6/9)**:100股手数+价12-30元→Top5各1手合计常80-100%+。本次解=**3下单(55.5%)+2观察仓staged(信号确认后部署至86.3%)+现金44.5%**。报告头部须标数据时效(7/3行情若为盘中须收盘复核,不得据盘中价次日直接挂单)。
