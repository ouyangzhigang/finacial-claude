# CLAUDE.md — A 股金融投资分析平台

## 项目定位
这是一个面向 A 股市场的专业金融投资分析平台。以 Claude Code 为核心,整合 46+ 个专业金融技能、多级数据源(MCP/REST API/网页抓取)和机构级分析框架,覆盖从宏观研判→行业轮动→选股筛选→财务分析→估值定价→技术择时→资金追踪→事件催化→组合风控→合规输出的完整投研链条。

## 核心工作流

### 工作流 A: 单股深度分析
**触发**: 用户提供具体股票代码,要求进行全方位分析
**入口**: [stock-analysis-prompt-cn.md](stock-analysis-prompt-cn.md)
**流程**: 宏观定调 → 基本面诊断 → 技术面研判 → 资金面追踪 → 情绪事件面 → 操作策略
**输出**: `output/{股票代码}_{YYYYMMDD}_深度分析报告.md`

### 工作流 B: 短周期选股推荐
**触发**: 用户要求筛选短期(2 周)潜力股、推荐股票组合
**入口**: [short-term-stock-picks-prompt-cn.md](short-term-stock-picks-prompt-cn.md)
**流程**: 宏观国际定调 → 候选池生成(30-50 只) → 流动性过滤 → 六维评分排序 → 组合风控 → Top N 推荐
**输出**: `output/{YYYYMMDD}_短周期2周推荐清单.md`

### 工作流 C: 行业/板块研究
**触发**: 用户询问某个行业/板块的分析、龙头公司、政策环境
**技能**: `china-sector-overview` + `sector-rotation-detector` + `china-comps-analysis`

### 工作流 D: 晨会纪要/日报
**触发**: 用户要求早报、晨会纪要、每日市场回顾
**技能**: `china-morning-note`

### 工作流 E: 财报分析
**触发**: 用户要求分析某公司季报/年报、业绩点评
**技能**: `china-earnings-analysis` / `china-earnings-preview` / `financial-statement-analyzer`

### 工作 F: 首次覆盖
**触发**: 用户要求对新覆盖的股票出具完整研报
**技能**: `china-initiating-coverage`

## 数据源五级架构(所有工作流共用)

| 层级 | 来源 | 类型 | 适用 |
|---|---|---|---|
| Tier-0 | 万得 Wind(`wind-mcp`) | MCP 结构化 | 全市场+研报+量化+港美股,机构首选 |
| Tier-1 | 同花顺 iFind(`ifind-mcp`) | MCP 结构化 | 财务/一致预期/ESG/债券/港美股/宏观 |
| Tier-2 | AkShare(`akshare-mcp`) | MCP 结构化 | 免费,行情/财报/行业/指数,高频批量 |
| Tier-3 | FMP(`fmp-global-data`) | REST API | 全球股票/ETF/加密货币/外汇/商品/分析师评级/宏观 |
| Tier-4 | Scrapling | 自适应爬虫 | 公告原文/研报/社区舆情/反爬站点兜底 |
| Tier-5 | 脚本/MCP 兜底 | 混合 | MCP 全部失效时的最后手段 |

**升级原则**: 结构化优先 → 跨市场用 FMP → 兜底用 Scrapling → 最后用脚本。

## 技能分类总览(46+ 技能)

### 📊 数据获取层(6 个)
| 技能 | 用途 |
|---|---|
| `china-market-data` | 多源数据入口,统一调度 Wind/iFind/AkShare/Scrapling |
| `findata-toolkit-cn` | 免密钥脚本:行情/财报/董监高/北向/宏观仪表盘 |
| `fmp-global-data` | 全球金融数据:股票/ETF/加密/外汇/商品/分析师评级/宏观 |
| `Scrapling-Skill` | 自适应网页抓取:公告/研报/舆情/反爬站点 |
| `china-news-mcp` | 个股新闻/市场头条 |
| `china-sector-overview` | 行业格局/竞争/政策/估值/龙头全景 |

### 🔍 选股与筛选层(6 个)
| 技能 | 用途 |
|---|---|
| `china-idea-generation` | 系统性选股:量化筛选+主题+模式识别 |
| `undervalued-stock-screener` | 基本面强+估值低估筛选 |
| `quant-factor-screener` | 多因子模型打分(价值/动量/质量) |
| `small-cap-growth-identifier` | 小盘高成长/专精特新识别 |
| `event-driven-detector` | 并购/回购/指数调整/资产注入事件驱动 |
| `sentiment-reality-gap` | 情绪超跌但基本面稳的逆向机会 |

### 💰 财务分析层(5 个)
| 技能 | 用途 |
|---|---|
| `financial-statement-analyzer` | 杜邦拆解/盈利质量/Z值&M值造假筛查 |
| `china-break-trace` | 财务异常 forensic、earnings quality、红旗排查 |
| `china-earnings-analysis` | 季报/年报点评、业绩驱动、variance |
| `china-earnings-preview` | 财报前瞻、scenario framework |
| `china-variance-commentary` | 业绩差异分析评论 |

### 📈 估值层(4 个)
| 技能 | 用途 |
|---|---|
| `china-comps` / `china-comps-analysis` | 可比公司 PE/PB/PS 相对估值 |
| `china-dcf` / `china-dcf-model` | DCF 绝对估值 |
| `tech-hype-vs-fundamentals` | 科技股估值泡沫 vs 基本面 |
| `high-dividend-strategy` | 高股息策略/分红可持续性 |

### 📉 技术与资金层(3 个)
| 技能 | 用途 |
|---|---|
| `insider-trading-analyzer` | 董监高增减持/内部人交易/管理层信心 |
| `portfolio-health-check` | 持仓集中度/因子暴露/相关性/隐性偏移 |
| `risk-adjusted-return-optimizer` | 风险调整后收益最优的仓位与配置 |

### 🗓 催化与轮动层(3 个)
| 技能 | 用途 |
|---|---|
| `china-catalyst-calendar` | 财报/政策/展会/解禁催化剂日历 |
| `sector-rotation-detector` | 宏观经济周期→行业轮动信号 |
| `china-thesis-tracker` | 持仓投资逻辑跟踪与复盘 |

### 📋 合规与输出层(6 个)
| 技能 | 用途 |
|---|---|
| `suitability-report-generator` | 机构级适当性报告/风险披露 |
| `china-xlsx-author` | 专业 Excel 财务模型 |
| `china-pptx-author` | 路演 PPT 制作 |
| `china-ppt-template-creator` | PPT 模板创建 |
| `china-audit-xls` | Excel 模型审计/QC |
| `china-deck-refresh` | 更新现有路演 deck |

### 🏗 建模层(8 个)
| 技能 | 用途 |
|---|---|
| `china-3-statement-model` | 三表财务模型(利润表/资产负债表/现金流) |
| `china-lbo-model` | 杠杆收购模型 |
| `china-roll-forward` | 模型滚动更新 |
| `china-model-update` | 季度数据更新 |
| `china-deal-screening` | 交易机会筛选评估 |
| `china-initiating-coverage` | 首次覆盖完整研报 |
| `china-clean-data-xls` | 财务数据清洗标准化 |
| `china-gl-recon` | 总账核对 |
| `china-accrual-schedule` | 应计项目排程 |

### 🌿 其他(4 个)
| 技能 | 用途 |
|---|---|
| `esg-screener` | ESG 筛选/治理评估/争议事件 |
| `china-tax-loss-harvesting` | 税务亏损抵扣策略 |
| `china-skill-creator` | 创建新金融技能 |
| `china-ib-check-deck` | 投行 deck 质量检查 |

## 关键操作规范

### 数据获取纪律
1. **结构化优先**: 永远先从 MCP 结构化数据源(Tier-0→2)取数,不使用 Scrapling 除非必要
2. **跨市场必跑**: 分析 A 股公司时,优先用 FMP 查找全球对标公司进行估值交叉验证
3. **多源交叉**: 关键财务/估值数据至少两源核对,差异大时标注
4. **兜底链**: MCP → 脚本(findata-toolkit-cn) → curl 东方财富 → Scrapling → 标注"数据缺失"
5. **Scrapling 克制**: 网页抓取仅在其他源不可用时启用,抓取后及时清理临时文件

### 分析输出纪律
1. **结论先行**: 每个判断先给结论,再展开论证
2. **数据说话**: 每个判断附关键数据/价位,禁用"可能""也许""大概"
3. **逻辑链完整**: 因为 A → 所以 B → 因此 C,而非断言
4. **可执行**: 价格、仓位、动作具体到可下单
5. **诚实标注**: 数据缺失处明确标注"数据缺失",不编造
6. **表格化**: 所有结构化数据用表格呈现,不用大段文字
7. **短话长说**: 每个判断不超过 3 行,禁用整段流水账

### 文件输出规范
- 深度分析报告: `output/{股票代码}_{YYYYMMDD}_深度分析报告.md`
- 选股推荐清单: `output/{YYYYMMDD}_短周期2周推荐清单.md`
- Excel 模型: `output/{股票代码}_模型.xlsx`
- PPT 路演: `output/{股票代码}_路演.pptx`
- 若 `output/` 不存在,先创建再写入

### 环境变量
- `IFIND_DATA_SOURCE_MODE`: 数据源切换(`wind-fallback`/`ifind-fallback`/`akshare-only`/`scrapling-only`)
- 默认值: `ifind-fallback`(iFind 优先,AkShare 兜底)

## 用户偏好
- 语言: 中文(简体)
- 风格: 机构级专业分析,拒绝"正确但无用"的废话,拒绝模棱两可
- 输出: Markdown 表格化、视觉标识(🟢🟡🔴)、关键数据加粗
- 市场: 聚焦 A 股(沪深/科创板/创业板/北交所),兼顾港股通和中概股
- 方法论: 自上而下(宏观→行业→个股),价值为盾+催化为矛+流动性为基
