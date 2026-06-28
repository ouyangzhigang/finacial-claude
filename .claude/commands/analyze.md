# /analyze — 个股深度分析与投资策略

## 用法
输入: `/analyze [股票名称或股票代码] [附加条件]`
- 股票: 必填,支持中文名/代码(如"贵州茅台"/"600519"/"002594.SZ")
- 附加条件: 可选,如"持仓分析""估值分析""技术面分析""财务排雷""对比对标"等

## 示例
```
/analyze 贵州茅台
/analyze 600519
/analyze 002594.SZ 持仓分析
/analyze 比亚迪 对比对标
/analyze 宁德时代 财务排雷+技术面
```

## 执行流程

1. **解析输入参数**
   - 股票名称/代码: 从用户输入提取
   - 自动搜索: 用 `search_stock`(AkShare) 或 `ifind_search_stocks` 确认准确代码
   - 附加条件: 识别用户指定侧重方向,调整分析重点
   - 默认假设: 若无持仓信息,按空仓分析;若无账户信息,按通用分析

2. **读取分析框架**
   - 加载 [stock-analysis-prompt-cn.md](stock-analysis-prompt-cn.md) 中的完整分析流程
   - 严格遵循五级数据源架构

3. **数据获取(六模块并行)**

   **模块一 · 宏观与政策**
   - `findata-toolkit-cn`(macro_data) → GDP/PMI/CPI/PPI/社融/M2/LPR
   - `sector-rotation-detector` → 行业轮动信号
   - `fmp-global-data`(treasury-rates) → 美债收益率曲线

   **模块二 · 基本面**
   - `china-market-data`/`findata-toolkit-cn` → 财报数据(利润表/资产负债表/现金流量表)
   - `financial-statement-analyzer` → 杜邦拆解/盈利质量/Z值&M值造假筛查
   - `china-break-trace` → 财务红旗排查
   - `china-comps` + `china-dcf` → 双估值锚定
   - `fmp-global-data`(profile + quote) → 全球对标公司估值
   - 按股性加跑: `tech-hype-vs-fundamentals`/`high-dividend-strategy`/`small-cap-growth-identifier`/`undervalued-stock-screener`/`esg-screener`

   **模块三 · 技术面**
   - `findata-toolkit-cn`(stock_data --history) → 多周期 K 线 OHLCV
   - `china-market-data` → 技术指标(MACD/KDJ/RSI/布林带)
   - `quant-factor-screener` → 价值/动量/质量因子暴露打分

   **模块四 · 资金面**
   - `findata-toolkit-cn`(--insider / --northbound) → 董监高增减持/北向资金
   - `insider-trading-analyzer` → 内部人交易信号
   - `china-market-data` → 股本结构/十大流通股东

   **模块五 · 情绪与事件**
   - `event-driven-detector` → 并购/回购/指数调整
   - `sentiment-reality-gap` → 情绪 vs 基本面背离
   - `china-catalyst-calendar` → 未来催化日历
   - `fmp-global-data`(earnings-calendar) → 全球财报日历
   - `Scrapling-Skill` → 雪球/东财股吧散户情绪
   - 同花顺热门榜单 → 该股角色定位(龙头/跟风/边缘)

   **模块六 · 操作策略**
   - `risk-adjusted-return-optimizer` → 仓位与配置建议
   - `portfolio-health-check` → 组合影响分析(若有持仓)
   - `suitability-report-generator` → 合规留痕(可选)

4. **附加条件处理**
   - "持仓分析": 重点分析持仓成本、盈亏状况、加仓/减仓/清仓建议
   - "估值分析": 深度展开 DCF + 可比公司估值,给出合理价格区间
   - "技术面分析": 重点展开多周期 K 线、均线系统、量价关系、筹码分布
   - "财务排雷": 深度展开 Z 值/M 值、商誉/质押/解禁/应收坏账/关联交易
   - "对比对标": 用 FMP 查找全球对标公司,多维度对比估值与基本面

5. **输出报告**
   - 写入 `output/{股票代码}_{YYYYMMDD}_深度分析报告.md`
   - 报告中必须包含:
     - 报告头(H1 标题 + 一句话结论)
     - 决策仪表盘(宏观/基本面/技术/资金/情绪/榜单/全球对标/综合建议)
     - 六大模块逐项展开,每模块结尾引用块小结
     - 操作策略(方向/建仓区间/分批节奏/止损/目标/仓位/持有时间/最大回撤)
     - 情景预演(突破/跌破/横盘三种情景)
     - 风险提示与认知偏差校准
   - 对话中给出文件路径 + 一句话结论 + 关键价位

6. **数据纪律**
   - 实时行情注明截至时间
   - 数据缺失处明确标注"数据缺失",不编造
   - 禁止"可能""也许""大概",每个判断附关键数据
   - 跨市场对标必跑: 查找 1-3 家全球对标公司
   - 兜底抓取: MCP 数据源缺失时,用 Scrapling 抓公告原文/研报/社区舆情
