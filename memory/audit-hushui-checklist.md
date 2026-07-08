---
name: audit-hushui-checklist
description: "糊弄自查清单——已改13处+待改60+处(附行号改法),2026-07-03因驰宏锌锗荐股失误触发的全工作区审计"
metadata: 
  node_type: memory
  type: project
  originSessionId: 250d53b2-cd13-4f47-853f-b7aac01a3b58
---

2026-07-03 用户因驰宏锌锗(600497)荐股失误震怒,触发全工作区"糊弄"自查。糊弄=规则写了但留逃生通道让该剔除的留下(7形态:逃生通道/标注代替修正/数据缺失充数/结论先行证据不足/验证可跳过/措辞后门/兜底假通)。4个subagent扫了12 A股技能+12 US技能副本+脚本层。**已改13处,待改60+处清单如下,下次精准继续。**

## ✅ 已改(13+26=39处)
### 一轮(框架/命令/技能,13处)
- `short-term-stock-picks-prompt-cn.md`:周期下限≥5日/回测三项全不达标一票否决/盘中价不作买入区间/透支看5/10/20日任一/催化同源≤50%/禁承诺措辞(9处)
- `stock-analysis-prompt-cn.md`:双红不给买点(2处)/结论无歧义不双动作/数据缺失≥2项降级条件单/措辞纪律(5处)
- `recommend_module_stocks.md`:加Step7回测/信心填高须回测背书/止损标注可执行性/主跌期不推/降级失败标注不可得(5处)
- `.claude/commands/recommend-stocks.md`:周期<5日拒绝选股拦截
- `.claude/commands/analysis-stock.md`:资金流不得估算/回报附置信度+多红不给建仓价(2处)
- `.claude/commands/hot-trends.md`:回测必做跳过则作废/soft-fail不静默(2处)
- `high-dividend-strategy/SKILL.md`:第三点五步硬剔除闸门(FCF<1.2/负债>70%/可持续<50等6条)
- `quant-factor-screener/SKILL.md`:第五点五步回测验证门
- `scripts/generate_a_share_ppt.py:579`:硬编码"增持"→数据驱动(PE vs 可比中位),数据不足NR
- `scripts/hot_trend_dig.py`:success_rate默认None/解析失败不伪造"低胜率机构"(3处)
- `mcp-servers/akshare-mcp/server.py:_df_to_json`:空DataFrame返回error而非[]
- `mcp-servers/china-news-mcp/server.py:_df_to_json`:空DataFrame返回error而非[]
### 二轮(脚本/MCP数据层,26处,2026-07-03)
- `mcp-servers/ifind-mcp/server.py`:SSL硬编码verify=False→IFIND_SSL_NO_VERIFY环境变量/adapter check_hostname受控/_post verify受控/_call_ifind空响应返error而非"null"+非JSON返error+_init_session移进try(4处)
- `mcp-servers/wind-mcp/server.py`:result缺失返error非整个body/JSON解析失败返error非{text:}/SSLError独立捕获提示WIND_SSL_NO_VERIFY/异常不剥离e带类型(2处编辑覆盖4点)
- `mcp-servers/fmp-mcp/server.py`:配置except pass→打印WARNING
- `scripts/cn_fetch.py`:SSL无注释硬编码→CN_FETCH_SSL_NO_VERIFY环境变量/quote pe_ttm+mktcap空填None非0/quote+sina_quote except continue打印stderr/rank PE+PB空打印NA非0(4处)
- `scripts/hot_trend_dig.py`:3个subprocess returncode!=0打印stderr返_error非静默None/cross_reference源缺失失败stderr标注/parse_interpretation空文本success_rate 0.0→None(上次漏改,驰宏案根因)(5处)
- `scripts/fetch_market.py`:SSL monkeypatch→FETCH_SSL_NO_VERIFY环境变量/zt_pool全失败for-else写_error/dt_pool同款(3处)
- `scripts/fetch_stock.py`:SSL monkeypatch环境变量/concept except pass→打印[SKIP](2处)
- `scripts/fetch_stock2.py`:SSL monkeypatch→环境变量
- `scripts/generate_a_share_ppt.py`:Thesis通用占位→数据不足标注⚠/行业默认电池股→未指定则空+提示/估值机械系数图标题标注"经验系数非DCF+可比N家"/数据支撑bullet数据量偏少标注⚠(4处)
- py_compile 全部9文件通过(2026-07-03)

## ⏳ 待改清单(按层,附行号+改法)

### ✅ 脚本/MCP层(二轮已清零,见上"已改"段)
ifind/wind/fmp/akshare/china-news MCP + cn_fetch/hot_trend_dig/fetch_market/fetch_stock/fetch_stock2/generate_a_share_ppt 已改，py_compile 通过。
注:fetch_market 的 dt_pool for-else、analyze.py:203 zt_pool 检查已在二轮补齐；kline 空[]链路(factors返None→main打印缺失)保持,非糊弄。

### A股技能层(.claude/skills/,已改3,剩9个)
- `small-cap-growth-identifier/references/small-cap-screening-criteria.md:173`:止损"重新评估"→"必须卖出"(⚠改了4次被classifier挡,待重试);`:162/174`:流动性门槛3000万vs1000万矛盾→统一3000万;`:41`:利润率"拐点预期"→实际2季环比;`:82`:<15%赋2分→0分剔除;`:172-176`:纪律无"跳过则作废"→加
- `portfolio-health-check/SKILL.md:129`"不要大幅推翻"→删/改;`references/diagnostic-framework.md:19-25`集中度只"建议"→硬减持目标;`:32/110/111`"有意为之可接受"→须可证伪逻辑;`SKILL.md:86`压力测试跳过无惩罚→跳过则评分不完整
- `risk-adjusted-return-optimizer`:SKILL:51 vs framework:139行业25%vs30%矛盾→统一25%;`framework:21-37/147-149`回撤红线突破不降仓→配置不成立;`SKILL:73`"极端时适当降仓"→量化触发器;`SKILL:55-65`风险仪表盘缺项无惩罚→缺则不输出
- `tech-hype-vs-fundamentals`:SKILL:75/framework:49政策溢价20-40%+不应视为泡沫→+20%上限;`framework:68`PEG>2"需强逻辑"→列高估候选;`framework:180-190`🔴严重无动作列→加剔除;`framework:99/107-108`SBC/资本化只标→重算;`:175`解禁>50%"严格关注"→回避;全篇无回测→加估值回测
- `insider-trading-analyzer`:SKILL:35 vs screening:147质押硬排除vs"动机存疑"→统一≥30%剔除;`output:33`个股回测缺失用全市场研究→留空;`screening:149-150`ST/解禁不硬排除→一律剔除;`:109-115`信号分无门槛→加;`:39`回购激励"较弱"→不纳入强信号;`SKILL:80`减持"不应解读为看空"→集群窗口有减持则剔除
- `undervalued-stock-screener`:methodology:50"跑赢行业即可"→删;SKILL:37净利润→扣非;`:27`扣非PE差异>30%"特别关注"→重判;`:36-38`PB<1验证无后果→三项验证;`:143-165`红旗无剔除→命中N个剔除;`:79-92`ROIC/WACC缺失无处理→缺即剔除;`:84`高杠杆ROE"扣分"→量化;output:57-62估值无离散度→>50%标注不可靠
- `sentiment-reality-gap`:SKILL:77"低估合理坦诚指出"→不进推荐;`:80`催化剂"还需要"无剔除→无催化不推荐;methodology:142-148偏差分档无门槛→<65不进;`:154-158`回归概率无来源→标注;SKILL:30/73北向2024-08停披露→标注滞后
- `event-driven-detector`:output:84"参与/关注/回避"→改二元;framework:192-208低概率"投机性"无剔除→失败≥40%剔除;SKILL:81"始终量化下行"无跳过惩罚→缺则不输出;framework:20-29典型价差无来源→标注;`:157-158`指数剔除"可能反弹"→默认回避;SKILL:85仓位"通常不超过"→硬上限3%
- `sector-rotation-detector`:framework:32-33过渡期"标注两者"→强制标配;output:16置信度中低仍发信号→低则标配;framework:131-143跨资产验证无硬前置→≥2项同向;`:173-187`历史超额无来源→标注;SKILL:31/84北向停披露→标注
- `esg-screener`:SKILL:70严重"排除或大幅减分"→强制排除;SKILL:37/70/framework:105三处矛盾→统一;SKILL:111数据缺失只"披露"→缺则不排名;SKILL:86财务整合"评估"→财务弱移出;framework:22/48/69定性子因素→客观代理;SKILL:103 ESG数据源付费受限但暗示工具包可用→标注不通
- `financial-statement-analyzer`:SKILL:41-52/128红灯只标注→治理红灯触发则不合格;methodology:159 M>-1.78"需关注"→剔除;全篇无数据缺失处理→缺核心科目则停止;SKILL:96-114同行比较无"必做"→跳过则作废;output:142-153强制看多看空各2-3点→红灯满屏不列看多;methodology:137-159 Z/F/M矛盾→M优先否决
- `findata-toolkit-cn/SKILL.md`:39/51-52/73/77涨停板数据源降级到新浪(新浪无此数据)→加source_status;72-76源可用性静态→以--health为准;75/81北向API废弃+错误进stderr→核心数据失败返回error JSON

### US技能副本(finskills/US-market/ + finskills/China-market/)
同名技能同款糊弄(改法同上)+额外:`dividend-aristocrat-calculator`(无剔除底线/FCF<1.0 Danger不剔除→加硬闸门)、`suitability-report-generator`(SKILL:69-72"附条件适当"软出口→任一不通过则不适当;report-framework适格门槛不满足只"说明"→合规否决)、`findata-toolkit-us`(yfinance/EDGAR/FRED海外端点本机未验证+未安装于.claude/skills/→加可达性自检+不可达则中止)。⚠**finskills是独立git repo,改源码不会同步到.claude/skills/实际生效副本——须在.claude/skills/改或跑sync脚本。**

相关:[[short-term-stock-discipline]] [[a-share-data-source]]
