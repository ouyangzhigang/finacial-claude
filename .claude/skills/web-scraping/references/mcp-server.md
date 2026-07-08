# Scrapling 内置 MCP 服务器

Scrapling 自带 MCP server，供 AI（Claude/Cursor 等）辅助抓取与提取，**先把目标内容用 Scrapling 提取成精简片段再交给 AI，省 token、降成本**。

## 安装

```bash
pip install "scrapling[ai]"
```

> 本机当前未装此 extra；需要时再装。本项目的 `.mcp.json` 暂未接入此 server——按需手动接入。

## 能力概览

- 抓取指定 URL，先用 Scrapling 提取目标内容（CSS/文本/自适应），再把精简结果交给 AI
- 持久 session 管理（跨请求复用 cookie/状态）
- 减少 token 消耗：避免把整页 HTML 丢给模型

## 何时用

- 反复让 AI 解析同一类页面时，用 MCP server 把"抓+提取"固化，AI 只看精简结果
- 长会话抓取需保持 cookie/session 时

## 与本技能其它入口的关系

- 不装 MCP 也能用本技能：`scripts/fetch.py` + `scrapling extract` CLI 已覆盖日常抓取
- MCP server 适合"AI 频繁交互式抓取"场景，属进阶能力
- 官方文档：https://scrapling.readthedocs.io/en/latest/ai/mcp-server.html
