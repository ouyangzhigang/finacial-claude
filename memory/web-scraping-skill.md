---
name: web-scraping-skill
description: web-scraping 技能(Scrapling)已集成到数据获取链路——cn_fetch.py 与 curl 之间的兜底层,3 fetcher 全通,fetch.py 自动降级链
metadata:
  type: project
  date: 2026-07-09
---

## web-scraping 技能集成状态(2026-07-09)

**技能路径**:`.claude/skills/web-scraping/`(SKILL.md + scripts/fetch.py + references/)

**在数据链中的位置**:cn_fetch.py(②)→ **web-scraping fetch.py(③)** → curl -k(④)

**三条通道**:
- `Fetcher`(HTTP+TLS 指纹伪装,curl_cffi)——静态页/JSON API
- `DynamicFetcher`(Playwright JS 渲染)——SPA/动态加载
- `StealthyFetcher`(反爬/Cloudflare Turnstile)——受保护站点

**调用方式**:
```bash
python .claude/skills/web-scraping/scripts/fetch.py "URL" --no-verify          # auto 降级
python .claude/skills/web-scraping/scripts/fetch.py "URL" --no-verify --json   # 容错提取 API
python .claude/skills/web-scraping/scripts/fetch.py "URL" --channel stealthy --solve-cloudflare  # 反爬
```

**已写入的文件**:
- `.claude/agents/references/cheatsheet.md` — 新增 web-scraping 节 + soft-fail 链更新
- 6 个 agent body(catalyst-scanner/technical-liquidity/sector-analyst/risk-portfolio/fundamentals-analyst/macro-strategist)
- `.claude/commands/invest.md` — soft-fail 链
- `.claude/commands/hot-trends.md` — 数据工具表 + 取数原则
- `CLAUDE.md` — Key scripts + Environment gotchas
- `memory/a-share-data-source.md` — 数据源优先级

**何时用(与现有工具分工)**:
| 场景 | 用什么 |
|---|---|
| 结构化金融数据(行情/财务/龙虎榜) | MCP 数据层(wind/ifind/akshare)优先 |
| 新浪榜单/腾讯 K线等无密钥 HTTP | `scripts/cn_fetch.py` |
| **网页内容/JS 渲染/反爬/批量采集** | **web-scraping fetch.py** |
| 简单 API 端点(不需要 JS/反爬) | `curl -k` |
| 交互式浏览器操作 | `browser-act` 技能 |

**Why:** web-scraping 技能 2026-07-08 创建后未集成到任何 agent/workflow 链路,2026-07-09 补齐。
**How to apply:** 数据获取时按 ① MCP → ② cn_fetch.py → ③ fetch.py → ④ curl 顺序降级;agent 在 Tool Chain 部分已内化此顺序。

[[a-share-data-source]]
