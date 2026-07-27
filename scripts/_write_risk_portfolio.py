import json
import os

output = {
    'runId': '20260727_single-stock-deep',
    'asOf': '20260727',
    'goal': 'single-stock-deep',
    'agent': 'risk-portfolio',
    'fetchedAt': '20260727',
    'data': {
        'target': {
            'code': '002185',
            'name': '华天科技',
            'price': 18.59,
            'marketCapYi': 617.82,
            'sector': '半导体-集成电路封装测试',
            'sectorRole': '跟风',
            'sectorRank': '国产封测三雄之第三',
            'lotCost': 1859,
            'accountBudget': 10000,
            'maxLotsPossible': 5,
            'maxLotsBudget': 2
        },
        'multiAgentSynthesis': {
            'macroAlignment': {
                'score': 14, 'maxScore': 20, 'weight': 0.15,
                'assessment': '行业方向落在最强顺风区（半导体/先进封装双确认），大基金三期3440亿+AI算力+国产替代三重驱动。但个股层面存在独立且显著的逆风（中报扣非低于预期引发34%暴跌），属于"方向对但节奏错"的标的。',
                'keyPoints': [
                    '大基金三期25-30%明确投向先进封装，华天科技直接受益方向',
                    '台积电CoWoS扩产至600-640亿美元，封装产能外溢利好国产封测',
                    '但个股经历34%暴跌后技术面严重破坏，情绪修复需要时间',
                    '美联储7/28-29议息为本周最关键外部变量（大概率按兵不动74.9%）'
                ]
            },
            'fundamentalQuality': {
                'score': 6, 'maxScore': 20, 'weight': 0.25,
                'assessment': '盈利质量存在严重缺陷：非经常性损益占比71.7%，扣非PE>300倍；PE处于近5年100%分位，PB处于82.3%分位；2026Q1单季转亏，毛利率骤降至9%。但经营现金流健康（34.72亿，现金流/净利润=4.3倍），供给端无风险，大基金二期持股2.89%提供政策背书。',
                'keyPoints': [
                    '扣非净利润仅2.00亿（2025年），非经常性损益5.10亿占比71.7%',
                    'PE(TTM)=86.96处于近5年100%分位，估值极度高估',
                    '2026Q1单季亏损-0.19亿，毛利率从13.26%骤降至9.00%',
                    '经营现金流34.72亿远超净利润，盈利含金量高（但掩盖不了主业疲软）',
                    '商誉7.20亿仅占净资产4.02%，控股股东质押仅7.42%，无硬红旗',
                    '6个软红旗（3红3黄）触发降权'
                ]
            },
            'technicalHealth': {
                'score': 7, 'maxScore': 20, 'weight': 0.20,
                'assessment': '技术面处于暴跌后弱势修复阶段：入场得分10/20（OVERSOLD_BOUNCE_WEAK），换手率16.27%严重超标（CRITICAL），5日累计换手82.97%显示筹码高度不稳定。布林下轨反弹信号+8分，但量能确认不足（5日均量=20日均量），反弹力度弱。前期107%暴涨后42%暴跌的完整周期表明主力出货痕迹明显。',
                'keyPoints': [
                    '入场信号：OVERSOLD_BOUNCE_WEAK（10/20），风险较高',
                    '布林下轨反弹信号成立（7/21锤子线+7/22确认），+8分',
                    '换手率16.27%远超7%上限，5日累计换手82.97%——筹码极度不稳定',
                    'RSI 41.9中性偏弱，未进入超卖区',
                    '价格远低于MA20（20.87），中期下跌趋势未扭转',
                    '前期完整周期：温和上涨34%→连续涨停27%→高位放量（日均换手23%）→暴跌42%',
                    '透支概率：MINIMAL（前期暴涨已通过暴跌出清）'
                ]
            },
            'catalystStrength': {
                'score': 10, 'maxScore': 20, 'weight': 0.20,
                'assessment': '未来2周有ICEPT 2026（8/5-7，西安）关键行业催化+半年报正式披露验证窗口，催化时间线清晰。但资金面持续偏空（主力近6日5日净流出、融资余额8连降-13%、龙虎榜上榜后5日平均跌8.58%），Capital Score 40/100偏低。业绩预告催化已半兑现，当前18.59距预告前24.13仍有-23%差距。',
                'keyPoints': [
                    'ICEPT 2026（8/5-7，西安）：亚洲顶级封装技术会议，华天科技主场优势，未price-in',
                    '半年报正式披露（预计8月中下旬）：验证扣非+毛利率改善程度，二向催化',
                    '南京先进封装产线Q3逐步放量+30亿二期项目：中长期核心逻辑，但产能2028年才完全释放',
                    '资金面偏空：主力近6日5日净流出，融资余额8连降-13%',
                    '龙虎榜统计：上榜后5日平均跌8.58%，接力极差',
                    'Capital Score 40/100，120日资金趋势偏弱',
                    '社交舆情预估：热度60-80偏高但下降中，多空分歧大（bull ratio 0.4-0.5）'
                ]
            },
            'sectorPosition': {
                'score': 8, 'maxScore': 20, 'weight': 0.20,
                'assessment': '在集成电路封测板块中定位为"跟风"角色——市值618亿仅为龙头长电科技（1474亿）的42%，扣非净利率1.16%行业垫底，20日-15.19%是四家同业中唯一负值。板块轮动当下不利封测。但公司深度绑定长鑫存储/长江存储，国内存储封测市占率~30%，DDR5服务器内存封装份额居前，南京产线稼动率>90%订单排至年底——这些产业细节构成差异化竞争力。',
                'keyPoints': [
                    '市值618亿=长电科技（1474亿）的42%，营收172亿=长电（389亿）的44%',
                    '扣非净利率1.16%行业垫底（长电3.52%/通富3.01%/晶方22.26%）',
                    '20日-15.19%是四家同业中唯一负值，短期大幅跑输',
                    '板块轮动不利：封测+0.86% vs 半导体+2.2% vs 先进封装+3.0%',
                    '差异化优势：深度绑定长鑫存储/长江存储，国内存储封测市占率~30%',
                    '南京存储封测产线稼动率>90%，订单排至2026年底',
                    '30亿二期项目达产后预计年封装存储IC约4.3亿只',
                    '行业顺风方向明确但个股传导存在时滞（产能2028年才完全释放）'
                ]
            },
            'compositeScore': 45, 'maxCompositeScore': 100,
            'verdict': '不推荐（45/100）',
            'verdictRationale': '综合评分45/100，远低于60分及格线。核心矛盾：行业顺风（半导体/先进封装双确认）vs 个股基本面（扣非PE>300/Q1转亏/估值100%分位）+ 技术面（暴跌后弱势反弹/换手率CRITICAL）+ 资金面（持续偏空）。对于1w账户风险稳健目标，当前价位（18.59）风险收益比不匹配。若价格回落至15-16.5区间（PB 2.7-3.0x，接近暴跌低点），风险收益比将显著改善，届时可重新评估。'
        },
        'valuationFramework': {
            'methodology': '多维度交叉验证：PB Band（基于BPS 5.485+5年分位）、PS Band（基于2025营收172.14亿）、PE（基于2026E归母9.0亿+扣非2.0亿）、技术面（支撑/阻力位）。当前价格18.59处于估值中区上沿，向上空间有限而向下风险显著。',
            'pbBased': {
                'bps': 5.485, 'currentPb': 3.45, 'pbPercentile5y': 82.32,
                'conservative': {'pb': 2.5, 'price': 13.71, 'percentile': '~40%', 'scenario': '深度回调/系统性风险'},
                'base': {'pb': 3.0, 'price': 16.46, 'percentile': '~60%', 'scenario': '震荡筑底/情绪修复'},
                'optimistic': {'pb': 3.5, 'price': 19.20, 'percentile': '~82%', 'scenario': '催化兑现/情绪回暖'},
                'stretch': {'pb': 4.0, 'price': 21.94, 'percentile': '~95%', 'scenario': '强催化+资金共振'}
            },
            'psBased': {
                'revenuePerShare': 5.18, 'currentPs': 3.35,
                'conservative': {'ps': 2.5, 'price': 12.94, 'scenario': '封测行业估值收缩'},
                'base': {'ps': 3.0, 'price': 15.53, 'scenario': '行业均值回归'},
                'optimistic': {'ps': 3.5, 'price': 18.12, 'scenario': '行业景气+成长溢价'},
                'note': 'PS方法对华天科技适用性较好（营收真实，不受非经常性损益扭曲）'
            },
            'peBased': {
                'eps2026eAttributable': 0.27, 'eps2025Core': 0.06,
                'currentPeAttributable': 68.6, 'currentPeCore': 309,
                'conservative': {'peAttributable': 40, 'price': 10.80, 'scenario': '封测行业PE均值回归'},
                'base': {'peAttributable': 50, 'price': 13.50, 'scenario': '成长性部分定价'},
                'optimistic': {'peAttributable': 60, 'price': 16.20, 'scenario': '高成长溢价'},
                'note': 'PE方法受非经常性损益严重扭曲，仅供参考。基于扣非EPS(0.06)定价，当前价格完全脱离基本面。'
            },
            'technicalBased': {
                'supports': [
                    {'level': 17.08, 'type': '近期低点支撑（7/24）'},
                    {'level': 15.81, 'type': '布林下轨'},
                    {'level': 15.17, 'type': '本轮暴跌最低点（7/21盘中）'}
                ],
                'resistances': [
                    {'level': 18.82, 'type': '7/27高点'},
                    {'level': 19.68, 'type': 'MA10均线'},
                    {'level': 20.87, 'type': 'MA20/布林中轨'},
                    {'level': 22.00, 'type': '前期平台下沿'}
                ],
                'currentPosition': '价格18.59处于支撑/阻力密集区，紧贴第一阻力位（18.82），向上突破需放量配合'
            },
            'synthesized': {
                'low': {
                    'range': '14.5 - 16.5', 'centralValue': 15.5,
                    'methodology': 'PB 2.6-3.0x + PS 2.8-3.2x + 技术面（暴跌低点附近）',
                    'probability': '30-35%',
                    'trigger': '美联储意外鹰派 + 半年报扣非不及预期 + 资金持续流出',
                    'upsideFromCurrent': '-12% ~ -17%',
                    'riskReward': '该区间风险收益比显著改善，适合作为观察/试探性建仓区域'
                },
                'mid': {
                    'range': '16.5 - 19.5', 'centralValue': 18.0,
                    'methodology': 'PB 3.0-3.6x + PS 3.2-3.8x + 技术面（震荡区间）',
                    'probability': '50-55%',
                    'trigger': '美联储按兵不动 + 市场情绪中性 + 无超预期催化',
                    'upsideFromCurrent': '-11% ~ +5%',
                    'riskReward': '当前价格18.59处于中区上沿，向上空间仅+5%至19.5，向下空间-11%至16.5，风险收益比约1:2.2（不利）'
                },
                'high': {
                    'range': '19.5 - 22.0', 'centralValue': 20.5,
                    'methodology': 'PB 3.6-4.0x + PS 3.8-4.2x + 技术面（MA20-前期平台）',
                    'probability': '15-20%',
                    'trigger': 'ICEPT超预期催化 + 半年报扣非大超预期 + 美联储鸽派 + 主力资金持续回流',
                    'upsideFromCurrent': '+5% ~ +18%',
                    'riskReward': '需强催化+资金共振才能触及，且上方套牢盘沉重（19-26区间），到达后抛压显著'
                }
            }
        },
        'scenarioAnalysis': {
            'breakout': {
                'label': '向上突破（强反弹）',
                'probability': '15-20%',
                'triggers': [
                    '美联储7/28-29鸽派按兵不动 → 美元走弱 → 北向加速流入 → 半导体板块情绪提振',
                    'ICEPT 2026（8/5-7）释放超预期利好（华天科技发布先进封装重大进展/订单公告）',
                    '半年报正式披露扣非净利润超预期 + 毛利率Q2环比大幅改善',
                    '主力资金连续3日净流入 + 融资余额企稳回升 + 北向转为净买入',
                    '封测板块轮动切换（资金从上游设备/材料回流封测后端）'
                ],
                'priceTarget': '20.0 - 22.0（MA20~前期平台下沿）',
                'timeframe': '8/5-7 ICEPT会议前后（1-2周）',
                'keyResistance': '19.68（MA10）→ 20.87（MA20/布林中轨）→ 22.0（前期平台）',
                'volumeRequirement': '突破19.0需放量至1.2倍20日均量以上（约140亿），缩量突破视为假突破',
                'response': {
                    'for10kAccount': '1-2手试探（1859-3718元，占账户18-37%），突破19.0放量确认后加至2手，不追涨',
                    'entry': '突破19.0 + 日成交额>120亿 + 主力净流入>2亿确认后，以19.0-19.3区间介入',
                    'stop': '17.5（-8%），跌破即离场',
                    'target': '第一目标20.0（+5%），第二目标20.87（+10%），到达第一目标后上移止损至成本价',
                    'maxPosition': '2手（3718元，37%仓位），剩余63%现金应对风险',
                    'riskNote': '即使突破，上方19-26区间套牢盘沉重，反弹空间受限，不建议重仓'
                }
            },
            'consolidation': {
                'label': '区间震荡（筑底）',
                'probability': '50-55%',
                'triggers': [
                    '美联储按兵不动（中性表态），市场无方向性突破',
                    'ICEPT 2026催化力度一般（行业会议无个股级利好）',
                    '半年报数据符合预告区间（7.5-8.5亿），无超预期成分',
                    '资金面维持偏弱格局（主力小幅流出/流入交替，融资余额继续缓慢下降）',
                    '封测板块继续跟随半导体波动，无独立行情'
                ],
                'priceRange': '17.0 - 19.0（窄幅震荡）',
                'timeframe': '2-4周（至半年报披露前后）',
                'keyLevels': '支撑17.08（近期低点）/ 阻力18.82（近期高点）',
                'volumeRequirement': '震荡期量能萎缩至日均60-80亿为健康筑底，放量至100亿以上需警惕方向选择',
                'response': {
                    'for10kAccount': '观望为主，不参与震荡。1w账户不应在无方向性行情中消耗资金和机会成本。',
                    'observation': '等待以下信号之一出现再行动：①放量突破19.0（做多信号）②缩量回踩16.5以下（低吸机会）',
                    'alternative': '若看好封测方向，可考虑长电科技（600584）或通富微电（002156）作为替代标的，基本面更优'
                }
            },
            'breakdown': {
                'label': '向下破位（二次探底）',
                'probability': '25-30%',
                'triggers': [
                    '美联储意外鹰派加息 → 美元反弹 → 北向大幅流出 → 成长股杀估值',
                    '半年报扣非净利润低于预告下限（<2亿）或毛利率继续恶化',
                    '主力资金加速流出 + 融资余额继续大幅下降 + 龙虎榜再现机构大额卖出',
                    '半导体板块整体回调（如大基金三期细节不及预期/中美科技摩擦升级）',
                    '华天科技出现新的利空（解禁/减持/项目延期/客户流失）'
                ],
                'priceTarget': '15.0 - 16.5（二次探底，可能测试15.17前低）',
                'timeframe': '1-2周内（取决于利空触发速度）',
                'keySupport': '17.08（近期低点）→ 15.81（布林下轨）→ 15.17（前低）',
                'volumeRequirement': '破位放量（>100亿）为有效破位，缩量阴跌为阴跌磨底',
                'response': {
                    'for10kAccount': '坚决不参与，空仓等待。15.0-15.8区间重新评估（PB 2.7-2.9x，PS 2.9-3.0x，风险收益比改善）。',
                    'bottomFishing': '若跌至15.0-15.8区间且出现以下信号可考虑1手试探：①缩量止跌（日成交<50亿）②出现锤子线/启明星等底部K线形态③主力资金转为净流入④融资余额企稳',
                    'stop': '若已持有仓位，跌破17.0无条件止损（-8.5%），不扛单',
                    'riskNote': '二次探底可能跌破前低15.17，极限支撑在13.5-14.0（PB 2.5x，2025年起涨点附近）'
                }
            }
        },
        'fomcOverlay': {
            'event': '美联储7/28-29 FOMC利率决议（7/29凌晨公布）',
            'importance': '极高——本周最重要外部变量，直接影响北向资金流向和成长股估值',
            'scenarios': [
                {
                    'scenario': '鸽派按兵不动（基准）',
                    'probability': '50-55%',
                    'marketImpact': '美元走弱→人民币升值→北向继续流入→半导体/成长股受益',
                    'huatianImpact': '温和正面，但不改变个股基本面弱势格局。若北向流入带动半导体板块上涨2-3%，华天科技可能跟涨1-2%至18.8-19.0区域。',
                    'response': '若价格随板块反弹至19.0附近但无放量配合，考虑减仓而非加仓'
                },
                {
                    'scenario': '鹰派按兵不动',
                    'probability': '25-30%',
                    'marketImpact': '美元反弹→北向流入放缓或小幅流出→成长股承压',
                    'huatianImpact': '负面，弱势股在板块承压时跌幅更大（封测三雄中20日唯一负值）。可能回落至17.0-17.5区间。',
                    'response': '观望，不抄底。若已持有，17.0为最后止损线'
                },
                {
                    'scenario': '意外加息',
                    'probability': '15-20%',
                    'marketImpact': '美元大幅走强→北向大幅流出→A股普跌，成长股首当其冲',
                    'huatianImpact': '严重负面，大概率跌破17.08近期低点，测试15.81布林下轨。弱势股+系统性风险=跌幅放大。',
                    'response': '坚决空仓。若已持有，集合竞价即挂单离场，不抱幻想'
                }
            ]
        },
        'riskAssessment': {
            'overallRiskScore': 72, 'maxRiskScore': 100,
            'riskLevel': '高',
            'riskLevelRationale': '72/100为高风险评级。基本面（扣非PE>300/Q1亏损）、技术面（暴跌后弱势反弹）、资金面（持续偏空）、估值面（5年100%分位）四维共振指向高风险。主要矛盾在于行业顺风与个股质地的严重背离。',
            'riskFactors': [
                {
                    'factor': '盈利质量风险', 'severity': '极高',
                    'detail': '非经常性损益占比71.7%，扣非PE>300倍。若市场系统性修正对扣非的定价，股价可能跌至10-13元区间（基于扣非EPS 0.06xPE 40-50倍+PB 2.0-2.5x）。',
                    'mitigation': '不重仓，等待扣非盈利实质性改善（毛利率恢复至12%+、Q2扣非转正）后再考虑'
                },
                {
                    'factor': '估值泡沫风险', 'severity': '高',
                    'detail': 'PE(TTM)处于近5年100%分位，PB处于82.3%分位。当前估值已price-in了最乐观预期（先进封装+存储封测+AI算力），任何不及预期都将触发估值收缩。',
                    'mitigation': '仅在PB<3.0x（价格<16.5）时考虑介入，留有安全边际'
                },
                {
                    'factor': '筹码结构风险', 'severity': '高',
                    'detail': '5日累计换手82.97%，7/10-7/14高位区间（21-26元）日均换手15-25%，大量套牢盘堆积。反弹至19-22区间将触发解套抛压。',
                    'mitigation': '反弹目标不宜设太高，20元以上分批止盈'
                },
                {
                    'factor': '资金面持续偏空', 'severity': '高',
                    'detail': '主力近6日5日净流出，融资余额8连降-13%，Capital Score 40/100。龙虎榜上榜后5日平均跌8.58%。资金面不支持追涨。',
                    'mitigation': '等待主力资金连续3日净流入+融资余额企稳后再考虑介入'
                },
                {
                    'factor': '板块轮动不利', 'severity': '中高',
                    'detail': '封测板块+0.86%持续跑输半导体+2.2%和先进封装+3.0%，资金偏好上游设备/材料端。华天科技作为封测三雄之末受影响最大。',
                    'mitigation': '关注封测板块是否出现资金回流信号（连续2日跑赢半导体板块）'
                },
                {
                    'factor': 'FOMC事件风险', 'severity': '中高',
                    'detail': '7/28-29美联储议息为本周最重要外部变量。意外鹰派/加息将引发系统性回调，弱势股跌幅放大。',
                    'mitigation': 'FOMC结果公布前（7/29凌晨）不持仓或仅持极轻仓位'
                },
                {
                    'factor': '同业竞争风险', 'severity': '中',
                    'detail': '长电科技和通富微电在规模/盈利/技术/客户关系上全面领先。华天科技ROE 4.12%为四家最低，扣非净利率1.16%行业垫底。',
                    'mitigation': '如看好封测方向，优先考虑长电科技（600584）或通富微电（002156）'
                }
            ],
            'riskMitigationSummary': '核心策略：不追涨（当前18.59无安全边际），等回调（15.0-16.5区间观察），轻仓试探（最多1-2手），严格止损（-8%），关注基本面验证信号（Q2扣非转正+毛利率恢复）。'
        },
        'positionRecommendation': {
            'accountSize': 10000, 'riskProfile': '稳健',
            'primaryRecommendation': '观望/不参与',
            'rationale': '综合评分45/100，风险评分72/100。当前价格18.59处于估值中区上沿，向上空间有限（+5%至19.5），向下风险显著（-11%至16.5，极端-18%至15.0）。风险收益比约1:2.2（不利）。对于1w账户风险稳健目标，当前价位不应参与。',
            'conditionalEntry': {
                'condition': '若价格回落至15.0-16.5区间（PB 2.7-3.0x，PS 2.9-3.2x）',
                'maxPosition': '1-2手（1859-3718元，占账户18-37%）',
                'stopLoss': '14.5（-10%至-15%）',
                'target': '17.5-18.5（+8%至+15%）',
                'holdingPeriod': '1-2周',
                'entrySignal': '缩量止跌（日成交<50亿）+ 底部K线形态 + 主力资金转净流入 + 融资余额企稳'
            },
            'alternativeRecommendation': '若看好封测/AI算力方向，建议关注：①长电科技（600584，龙头，扣非净利13.69亿，20日仍正收益）②通富微电（002156，次龙头，ROE 8.08%四家最高，5日+21.70%弹性最强）'
        },
        'tradingZones': {
            'accumulationZone': {
                'range': '15.0 - 16.5',
                'description': '低吸区域：PB 2.7-3.0x，PS 2.9-3.2x，接近暴跌低点。风险收益比改善（向下空间-10%至14.5，向上空间+15%至19.0）。适合1w账户试探性建仓。',
                'action': '1-2手试探，严格止损14.5',
                'confidence': '中等（需基本面/资金面配合确认）'
            },
            'consolidationZone': {
                'range': '16.5 - 19.0',
                'description': '震荡区域：当前价格18.59处于此区间上沿。方向不明，多看少动。',
                'action': '观望，不参与',
                'confidence': '高（确定性等待优于不确定性参与）'
            },
            'distributionZone': {
                'range': '19.0 - 22.0',
                'description': '套牢密集区：上方堆积大量7/10-7/14高位筹码（日均换手15-25%）。反弹至此区域将触发解套抛压。',
                'action': '若持有仓位，分批止盈（19.0减半仓，20.0清仓）',
                'confidence': '高（套牢盘压力客观存在）'
            },
            'sellZone': {
                'range': '22.0+',
                'description': '前期平台/主升浪区域：接近7/10峰值25.31-25.68。除非出现超预期强催化（如先进封装重大订单），否则极难触及。',
                'action': '触及即为减仓/清仓信号',
                'confidence': '极高（估值+筹码双重压力）'
            }
        },
        'keyMonitoringPoints': [
            {
                'category': '短期（本周1-2日）',
                'items': [
                    '美联储7/28-29 FOMC决议及鲍威尔/沃什新闻发布会措辞——本周最重要变量',
                    '7/28政治局会议公告——关注是否有超预期半导体产业扶持政策',
                    '华天科技7/28开盘价及量能——FOMC前最后一个交易日资金态度'
                ]
            },
            {
                'category': '中期（1-2周）',
                'items': [
                    'ICEPT 2026（8/5-7，西安）——华天科技是否发布先进封装进展/订单公告',
                    '半年报正式披露日期及具体数据——扣非净利润、毛利率、研发投入、现金流',
                    '主力资金流向——是否出现连续3日净流入（扭转当前6日5日净流出趋势）',
                    '融资余额——是否企稳（当前8连降，关注拐点）',
                    '北向资金——是否转为净买入华天科技（7/15单日净卖出10.61亿后持续偏空）',
                    '封测板块轮动——是否出现资金回流封测的信号（连续2日跑赢半导体板块）'
                ]
            },
            {
                'category': '长期（1-3个月）',
                'items': [
                    '南京先进封装产线Q3放量进度——是否如期爬坡',
                    '30亿二期项目环评/建设进展——是否按期推进',
                    '存储封测订单变化——稼动率是否维持>90%',
                    'Q3财报——毛利率是否恢复至12%+，扣非净利润是否转正',
                    '大基金三期先进封装方向的具体投资落地——华天科技是否获得直接注资'
                ]
            }
        ],
        'dataSources': {
            'macro': 'macro-strategist.json',
            'fundamentals': 'fundamentals-analyst.json',
            'technical': 'technical-liquidity.json',
            'catalyst': 'catalyst-scanner.json',
            'sector': 'sector-analyst.json',
            'latestNews': 'iFind MCP search_news (2026-07-20至2026-07-27)',
            'latestQuote': 'iFind MCP get_stock_info (2026-07-27)',
            'note': '所有前序环节数据已交叉验证。iFind MCP数据可用，AkShare/Wind MCP SSL挂。新闻面补充了7/24主力净买入8749万、南京产线稼动率>90%等关键细节。'
        }
    },
    'summary': '华天科技(002185)综合评分45/100，风险评分72/100——不推荐当前价位参与。核心矛盾：行业顺风（半导体/先进封装双确认）vs 个股质地（扣非PE>300/Q1转亏/估值100%分位/暴跌后弱势反弹/资金持续偏空）。估值区间：低14.5-16.5（PB 2.7-3.0x）、中16.5-19.5、高19.5-22.0。当前18.59处于中区上沿，风险收益比约1:2.2（不利）。三情景：突破（15-20%概率，目标20-22）→1-2手试探不追涨；震荡（50-55%概率，区间17-19）→观望；破位（25-30%概率，目标15-16.5）→空仓等低吸。FOMC 7/28-29为本周最关键变量。建议等待价格回落至15.0-16.5区间再评估，或关注基本面更优的长电科技/通富微电。',
    'keyFields': {
        'compositeScore': '45/100',
        'riskScore': '72/100',
        'verdict': '不推荐（当前价位风险收益比不匹配）',
        'valuationLow': '14.5-16.5',
        'valuationMid': '16.5-19.5',
        'valuationHigh': '19.5-22.0',
        'currentPrice': 18.59,
        'currentZone': '中区上沿（接近高区）',
        'upsideToMidTop': '+5%',
        'downsideToMidBottom': '-11%',
        'riskRewardRatio': '1:2.2（不利）',
        'breakoutProb': '15-20%',
        'consolidationProb': '50-55%',
        'breakdownProb': '25-30%',
        'criticalEvent': '美联储7/28-29 FOMC',
        'nextCatalyst': 'ICEPT 2026（8/5-7，西安）',
        'primaryRecommendation': '观望/不参与',
        'alternativeWatch': '长电科技(600584) / 通富微电(002156)',
        'conditionalEntryZone': '15.0-16.5',
        'conditionalStopLoss': 14.5,
        'maxPosition10k': '2手（3718元，37%）',
        'sectorRole': '跟风（国产封测三雄之第三）',
        'corePE': '>300倍',
        'pePercentile5y': '100%',
        'turnoverWarning': 'CRITICAL（16.27%，5日累计82.97%）',
        'capitalScore': '40/100',
        'dragonTiger5d': '平均-8.58%',
        'marginTrend': '8连降-13%',
        'fomcProbability': '鸽派50% / 鹰派25% / 加息15%'
    }
}

os.makedirs('E:/finacial-invest/data/runs/20260727_single-stock-deep', exist_ok=True)
with open('E:/finacial-invest/data/runs/20260727_single-stock-deep/risk-portfolio.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('risk-portfolio.json written successfully')
print(f'Composite score: {output["data"]["multiAgentSynthesis"]["compositeScore"]}/100')
print(f'Risk score: {output["data"]["riskAssessment"]["overallRiskScore"]}/100')
print(f'Verdict: {output["data"]["multiAgentSynthesis"]["verdict"]}')