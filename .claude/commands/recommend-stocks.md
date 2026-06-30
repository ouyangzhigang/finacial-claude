# /recommend-stocks — 短周期股票推荐

## 用法
输入: `/recommend-stocks [描述任务]`
- 描述任务: 必填,描述你的选股需求和偏好
- 支持的要素: 时间周期(2 周/2 个月/到 X 月 X 日)、推荐数量(Top 3/Top 5)、风格限定(科技股/红利/小盘/事件驱动)、行业方向(半导体/新能源/AI/白酒等)、风险偏好(稳健/积极/激进)

## 示例
```
/recommend-stocks 未来2周推荐Top5科技股
/recommend-stocks 2周Top3红利方向稳健型
/recommend-stocks 到7月15日Top5小盘成长股
/recommend-stocks 推荐Top5半导体方向积极型
/recommend-stocks 本周推荐Top8事件驱动股
/recommend-stocks 2周Top5新能源+AI方向
```

## 执行流程

1. **解析用户任务描述**
   - 提取时间周期: 默认 2 周(10 个交易日),可自定义
   - 提取推荐数量: 默认 Top 5,范围 3-8
   - 提取风格限定: 科技股/红利/小盘/事件驱动等
   - 提取行业方向: 半导体/新能源/AI/白酒等具体行业
   - 提取风险偏好: 稳健/积极/激进
   - 确认日期基准: 执行当日

2. **读取选股框架**
   - 加载 [short-term-stock-picks-prompt-cn.md](short-term-stock-picks-prompt-cn.md) 中的完整选股流程
   - 严格遵循六级数据源架构和选股漏斗纪律

3. **执行选股漏斗**

   **模块一 · 宏观国际定调**
   - Tushare MCP `cn_gdp/cn_pmi/cn_cpi/cn_ppi` → 国内宏观
   - `fmp-global-data`(treasury-rates) → 美债收益率曲线
   - `sector-rotation-detector` → 行业轮动信号
   - Tushare MCP `limit_list_ths` → 涨停榜测情绪
   - 锁定 2-3 个顺风方向

   **模块二 · 候选池生成(30-50 只)**
   - `china-idea-generation` → 系统性选股
   - Tushare MCP `daily_basic` → 批量财务筛选
   - 顺风板块成分股龙头+次龙头
   - 热门榜单上榜股(涨停池/概念板块排行)
   - 事件驱动命中标的
   - 错杀反弹候选
   - 全球对标映射(FMP company-screener)
   - 用户指定的行业方向优先纳入

   **模块三 · 流动性硬门槛过滤**
   - 日均成交额 ≥ 1 亿
   - 换手率 1%-7%
   - 自由流通市值 ≥ 30 亿
   - 剔除 ST/次新/透支/一字板
   - 记录每只剔除原因

   **模块四 · 六维评分排序**
   - 基本面质量 20% + 技术位置 20% + 催化确定性 20% + 资金推动 15% + 估值安全边际 15% + 流动性适配 10%
   - 按用户风格裁剪权重(科技股重技术和催化,红利股重基本面和估值)
   - 输出评分总表,取 Top N

   **模块五 · 组合风控**
   - 行业分散: 单一行业 ≤ 40%
   - 风格平衡: 价值底仓 + 弹性进攻 + 事件催化
   - 相关性核验: `portfolio-health-check` 检查 Top N 相关性
   - 仓位分配: `risk-adjusted-return-optimizer` 定仓位

   **模块六 · 推荐清单输出**
   - 每只操作卡: 代码/名称/板块/推荐逻辑/买卖区间/止损/目标/仓位/催化剂/流动性/风险/全球对标

4. **调用技能矩阵**
   - 必调: `china-idea-generation` → `undervalued-stock-screener` → `quant-factor-screener` → `event-driven-detector` → `china-catalyst-calendar` → `financial-statement-analyzer` → `china-comps` → `findata-toolkit-cn`(行情/资金) → `risk-adjusted-return-optimizer` → `portfolio-health-check`
   - 按风格裁剪: 科技股加跑 `tech-hype-vs-fundamentals`, 红利股加跑 `high-dividend-strategy`, 小盘股加跑 `small-cap-growth-identifier`, 事件驱动加跑 `sentiment-reality-gap`
   - 跨市场对标: `fmp-global-data` 查全球对标公司估值
   - 兜底抓取: MCP 不可用时用 `Scrapling-Skill` 抓东方财富/巨潮公告

5. **输出报告**
   - 写入 `output/{YYYYMMDD}_短周期2周推荐清单.md`
   - 报告中必须包含:
     - 决策仪表盘(宏观/国际/政策/情绪/流动性/全球对标/组合建议)
     - 候选池与剔除明细
     - 评分总表(所有候选打分排序)
     - Top N 操作卡(每只: 代码/名称/板块/推荐逻辑/买卖区间/止损/目标/仓位/催化剂/流动性/风险/全球对标)
     - 组合风控表(行业分布/风格搭配/相关性/仓位)
     - 未来 2 周催化日历
   - 对话中给出文件路径 + 一句话结论 + Top N 代码清单 + 总仓位

6. **数据纪律**
   - 每只推荐必须有: 日均成交额、换手率、量比数据,空白视为不合格
   - 实时行情注明截至时间
   - 数据缺失处明确标注,不编造
   - 禁止"可能""也许""大概",每个判断附关键数据
   - 按用户指定风格定向筛选,不泛泛而谈
