# /hot-trends — 热门板块与资金流向分析

## 用法
输入: `/hot-trends [时间范围] [附加条件]`
- 时间范围: 不写默认"今日",可写"本周"/"近5日"/"近20日"
- 附加条件: 如"只看概念板块""只看北向资金""只看游资"等

## 示例
```
/hot-trends
/hot-trends 本周
/hot-trends 近5日 只看概念板块
/hot-trends 北向资金流向
```

## 执行流程

1. **解析输入参数**
   - 时间范围: 今日(默认)/本周/近5日/近20日
   - 筛选条件: 不限(默认)/概念板块/行业板块/北向资金/游资/机构

2. **数据获取(四级并行,确保覆盖)**

   **第一优先级 — Scrapling 抓取同花顺交易数据中心**
   ```
   URL: https://data.10jqka.com.cn/mobile/transaction/index.html
   工具: StealthyFetcher (同花顺有反爬保护)
   目标数据:
     - 热门概念板块排行(涨幅/成交额/资金净流入)
     - 行业板块排行
     - 个股资金流向(主力/超大单/大单/中单/小单)
     - 北向资金实时流向
     - 游资席位动向
   ```

   **第二优先级 — curl 东方财富 API(免费稳定)**
   ```bash
   # A 股涨幅榜 Top20
   curl -s "http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048&fields=f2,f3,f5,f6,f8,f12,f14"
   # 热门概念板块 Top10
   curl -s "http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&po=1&fid=f3&fs=m:90+t:2&fields=f2,f3,f8,f12,f14,f104,f105"
   # 行业板块 Top10
   curl -s "http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&po=1&fid=f3&fs=m:90+t:1&fields=f2,f3,f8,f12,f14,f104,f105"
   # 北向资金净流入 Top20
   curl -s "http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f62&fs=m:9+t:80,m:1+t:80&fields=f12,f14,f2,f3,f62"
   # 主力资金净流入排行
   curl -s "http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f62&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14,f2,f3,f62,f184,f185"
   ```

   **第三优先级 — AkShare MCP**
   - `get_market_overview` → 涨跌/成交额/换手率榜
   - `get_industry_stocks` → 行业成分股

   **第四优先级 — iFind MCP**
   - `ifind_search_trending_news` → 热点事件资讯
   - `ifind_sector_data` → 板块行情/成分股分析

3. **数据处理与分析**

   **板块分析**
   - 热门概念板块 Top10: 涨幅/成交额/资金净流入/上涨家数/下跌家数
   - 行业板块 Top10: 同上
   - 板块轮动信号: 结合 `sector-rotation-detector` 判断经济周期下的超配行业
   - 主线方向锁定: "政策周期 + 市场热度"双确认的主线 2-3 个

   **资金流向分析**
   - 北向资金: 当日/近5日/近20日净流入 Top20,判断外资偏好
   - 主力资金: 超大单/大单净流入排行,判断机构动向
   - 游资动向: 龙虎榜机构专用席位/知名游资席位进出
   - 行业资金: 各行业板块资金净流入/净流出排名

   **个股热度分析**
   - 人气榜 Top20: 散户关注度最高的股票
   - 涨幅榜 Top20: 当日最强个股
   - 成交额榜 Top20: 资金最集中的个股
   - 换手率榜 Top20: 最活跃的个股
   - 每只热门股标注: 所属板块/角色(龙头/跟风/边缘)/上榜次数

4. **调用分析技能**
   - `sector-rotation-detector` → 行业轮动信号确认
   - `china-sector-overview` → 热门板块行业格局分析
   - `event-driven-detector` → 热门股中事件驱动机会
   - `insider-trading-analyzer` → 热门股董监高增减持信号
   - `china-catalyst-calendar` → 热门股未来催化

5. **输出报告**
   - 写入 `output/{YYYYMMDD}_热门板块资金流向分析报告.md`
   - 报告中必须包含:
     - 决策仪表盘(市场热度/资金方向/主线方向/风格偏好)
     - 热门概念板块 Top10 排行表(涨幅/成交额/资金净流入)
     - 行业板块 Top10 排行表
     - 北向资金净流入 Top20
     - 主力资金净流入 Top20
     - 人气/涨幅/成交额/换手率四大榜单 Top20
     - 游资/机构资金动向分析
     - 主线方向锁定(2-3 个)
     - 热门个股推荐(附操作建议)
     - 风险提示
   - 对话中给出文件路径 + 一句话结论

6. **数据纪律**
   - 所有排行数据必须标注截至时间
   - 资金流向数据注明是当日/近5日/近20日
   - 数据缺失处明确标注,不编造
   - 禁止模棱两可,每个判断附具体数据
