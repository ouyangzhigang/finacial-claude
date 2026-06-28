# /stock-pick — 多股票筛选推荐

## 用法
输入: `/stock-pick [时间周期] [推荐数量] [附加条件]`
- 时间周期: 不写默认 2 周(10 个交易日),可写"2 周"/"2 个月"/"到 X 月 X 日"
- 推荐数量: 不写默认 Top 5,范围 3-8
- 附加条件: 如"科技股""红利""小盘""事件驱动"等风格限定

## 示例
```
/stock-pick 2 周 Top 5
/stock-pick 2 个月 Top 8
/stock-pick 到 7 月 15 日 Top 3 科技股
/stock-pick 红利方向
```

## 执行流程

1. **解析输入参数**
   - 从用户输入中提取: 时间周期(默认 2 周)、推荐数量(默认 5)、风格限定(默认不限)
   - 确认投资周期: 2 周=短线(10 个交易日)、2 个月=中线(约 40 个交易日)、自定义=按实际天数
   - 确认日期基准: 执行当日

2. **读取选股框架**
   - 加载 [short-term-stock-picks-prompt-cn.md](short-term-stock-picks-prompt-cn.md) 中的完整选股流程
   - 严格遵循五级数据源架构和选股漏斗纪律

3. **执行选股漏斗**
   - 模块一: 宏观国际定调 → 锁定顺风方向
   - 模块二: 候选池生成 30-50 只(多源汇总,去重)
   - 模块三: 流动性硬门槛过滤(成交额≥1亿、换手率 1-7%、非 ST/次新/透支)
   - 模块四: 六维评分排序(基本面 20% + 技术 20% + 催化 20% + 资金 15% + 估值 15% + 流动性 10%)
   - 模块五: 组合风控(行业≤40%、风格平衡、相关性核验)
   - 模块六: Top N 操作卡输出

4. **调用技能**
   - 必调: `china-idea-generation` → `undervalued-stock-screener` → `quant-factor-screener` → `event-driven-detector` → `china-catalyst-calendar` → `financial-statement-analyzer` → `china-comps` → `findata-toolkit-cn`(行情/资金) → `risk-adjusted-return-optimizer` → `portfolio-health-check`
   - 按风格裁剪: 科技股加跑 `tech-hype-vs-fundamentals`,红利股加跑 `high-dividend-strategy`,小盘股加跑 `small-cap-growth-identifier`
   - 跨市场对标: `fmp-global-data` 查全球对标公司估值
   - 兜底抓取: MCP 不可用时用 `Scrapling-Skill` 抓东方财富/巨潮公告

5. **输出报告**
   - 写入 `output/{YYYYMMDD}_短周期{周期}推荐清单.md`
   - 报告中必须包含:
     - 决策仪表盘(宏观/国际/政策/情绪/流动性/全球对标/组合建议)
     - 候选池与剔除明细
     - 评分总表(所有候选打分排序)
     - Top N 操作卡(每只: 代码/名称/板块/推荐逻辑/买卖区间/止损/目标/仓位/催化剂/流动性/风险/全球对标)
     - 组合风控表(行业分布/风格搭配/相关性/仓位)
     - 未来催化日历
   - 对话中给出文件路径 + 一句话结论 + Top N 代码清单 + 总仓位

6. **数据纪律**
   - 每只推荐必须有: 日均成交额、换手率、量比数据,空白视为不合格
   - 实时行情注明截至时间
   - 数据缺失处明确标注,不编造
   - 禁止"可能""也许""大概",每个判断附关键数据
