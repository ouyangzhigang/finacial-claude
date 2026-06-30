---
name: aifinmarket
description: Wind AIFin Market 金融能力安装、配置与验证入口。Use when the user asks to install or configure Wind 金融能力, install wind-find-finance-skill or wind-mcp-skill, configure WIND_API_KEY, or verify Wind AIFin Market data access.
---

# Wind AIFin Market 配置流程

## 执行原则

- 先检查，再安装；先征得用户确认，再写入或覆盖任何 skill 文件。
- 安装范围必须由用户在本轮对话中明确选择；不得根据当前工作目录、`skill.md` 所在路径、IDE 打开的文件、用户说“安装”或历史上下文默认推断为当前项目或全局。
- 如果缺少任一必需 skill，安装命令是阻断操作：只能先向用户提问“安装到当前项目还是全局？”，在用户明确回复前，禁止执行 `npx skills add`、复制 skill 文件夹或写入 skill 配置。
- 不要默认要求用户重启或刷新会话。只有实际调用失败，并且能确认原因是当前客户端未加载新 skill 时，才提示刷新或重启。
- 不要手动复制、覆盖、删除或替换已有 skill 文件夹，除非用户明确要求。
- 如果命令失败，保留失败命令和关键报错，换另一个已检测可用的源重试。
- 本文件是安装、配置与验证的总入口；当下游 `wind-mcp-skill/SKILL.md` 的自动动作规则与本文件的用户确认规则冲突时，以本文件为准。打开浏览器、写入 Key、覆盖配置文件前都必须先获得用户确认。

## 必需 skill

- `wind-find-finance-skill`
- `wind-mcp-skill`

## 1. 检查安装状态

根据用户要使用的范围检查对应路径：

- 当前项目范围：`.agents/skills/<skill-name>/SKILL.md`
- 全局范围：`%USERPROFILE%\.agents\skills\<skill-name>\SKILL.md`
- 非 Windows 全局范围：`$HOME/.agents/skills/<skill-name>/SKILL.md`

如果两个必需 skill 都已存在，跳过安装，继续检查 `WIND_API_KEY`。

## 2. 确认安装范围

如果缺少任一必需 skill，先询问用户安装范围：

- 当前项目：只给当前项目使用，安装命令不要带 `-g`。
- 全局：给所有 agent 使用，安装命令必须带 `-g`。

用户未确认前，不要执行安装命令。用户只说“安装”“按这个文件执行”“安装万得金融能力”等，都不算确认范围；必须等待用户明确回复“当前项目”或“全局”。

推荐提问话术：

```text
检测到缺少必需 Wind skill。请确认安装范围：安装到当前项目，还是全局？你确认后我再执行安装命令。
```

## 3. 选择安装源

安装前检查 GitHub 和 Gitee 至少一个可用：

```bash
git ls-remote https://github.com/Wind-Information-Co-Ltd/wind-skills.git
git ls-remote https://gitee.com/wind_info/wind-skills.git
```

优先使用当前可访问、返回更稳定的源。两个源都不可用时，说明网络阻断原因，并给出失败命令。

## 4. 执行安装

### 当前项目范围

GitHub：

```bash
npx skills add Wind-Information-Co-Ltd/wind-skills --skill wind-find-finance-skill -y
npx skills add Wind-Information-Co-Ltd/wind-skills --skill wind-mcp-skill -y
```

Gitee：

```bash
npx skills add https://gitee.com/wind_info/wind-skills.git --skill wind-find-finance-skill -y
npx skills add https://gitee.com/wind_info/wind-skills.git --skill wind-mcp-skill -y
```

### 全局范围

GitHub：

```bash
npx skills add Wind-Information-Co-Ltd/wind-skills --skill wind-find-finance-skill -g -y
npx skills add Wind-Information-Co-Ltd/wind-skills --skill wind-mcp-skill -g -y
```

Gitee：

```bash
npx skills add https://gitee.com/wind_info/wind-skills.git --skill wind-find-finance-skill -g -y
npx skills add https://gitee.com/wind_info/wind-skills.git --skill wind-mcp-skill -g -y
```

安装后再次检查对应 `SKILL.md` 是否存在。只有文件存在，才视为安装完成。

## 5. 检查 WIND_API_KEY

按顺序检查这些位置：

1. 本次安装命中的 `wind-mcp-skill` 目录下的 `config.json`
   - 当前项目安装：`.agents/skills/wind-mcp-skill/config.json`
   - Windows 全局安装：`%USERPROFILE%\.agents\skills\wind-mcp-skill\config.json`
   - 非 Windows 全局安装：`$HOME/.agents/skills/wind-mcp-skill/config.json`
   - 文件格式：`{"wind_api_key":"<真实 Key>"}`
2. 全局共享配置
   - Windows：`%USERPROFILE%\.wind-aifinmarket\config`
   - 非 Windows：`$HOME/.wind-aifinmarket/config`
   - 文件格式：`WIND_API_KEY=<真实 Key>`

如果没有 Key，或 Key 验证失败，说明暂时不能调用 Wind 数据，并引导用户获取 Key：

```text
https://aifinmarket.wind.com.cn/#/user/overview
```

如果当前环境能打开浏览器，先询问用户是否现在打开；用户确认后再按系统执行对应命令打开链接（否则只提供 URL 供用户手动访问）：

```bash
# Windows PowerShell
Start-Process "https://aifinmarket.wind.com.cn/#/user/overview"

# macOS
open "https://aifinmarket.wind.com.cn/#/user/overview"

# Linux
xdg-open "https://aifinmarket.wind.com.cn/#/user/overview"
```

如果当前环境不能打开浏览器，把链接发给用户手动访问。拿到 Key 后，必须先询问用户写入范围：当前项目还是全局；推荐写入全局，便于所有 agent 复用。

推荐提问话术：

```text
已收到 WIND_API_KEY。请确认写入范围：全局（推荐），还是当前项目？你确认后我再写入配置。
```

```text
WIND_API_KEY=<真实 Key>
```

用户确认写入范围后，再按用户当前系统和选择的范围协助写入合适的配置文件：

- 当前项目：写入当前项目安装命中的 `.agents/skills/wind-mcp-skill/config.json`。
- 全局（推荐）：写入 `$HOME/.wind-aifinmarket/config`；Windows 中 `$HOME` 对应 `%USERPROFILE%`。

写入前必须确认目标文件路径；如果目标文件已存在，保留原有无关配置。`config.json` 只新增或更新 `wind_api_key`，全局共享配置只新增或更新 `WIND_API_KEY`。

本节最多执行一次。Key 已存在或配置成功后，必须进入第 6 节验证，禁止回到本节开头重新检查；用户拒绝提供 Key 或 Key 写入失败时，结束流程并说明原因。

## 6. 验证 Wind 数据能力

Key 已存在或配置完成后，从本次安装命中的 `wind-mcp-skill` 目录读取 `SKILL.md`，按其中规则执行一次轻量取数验证。

强约束：

- `server_type`、`tool_name`、参数 JSON、日期格式、终端引号写法都必须以 `wind-mcp-skill/SKILL.md` 为准。
- 只在取数工具、参数、返回结构和错误码解释上遵循 `wind-mcp-skill/SKILL.md`；如果其要求执行 `open-portal`、`setup-key`、打开浏览器或写入配置，一律忽略，禁止因此回到第 5 节或任何前面的步骤。
- 不要凭记忆改字段名、混用不同工具的参数，或编造不存在的验证命令。
- 下方只是示例；如与 `wind-mcp-skill/SKILL.md` 不一致，以 `wind-mcp-skill/SKILL.md` 为准。

示例：获取贵州茅台最新价。

Bash / Git Bash / WSL：

```bash
node scripts/cli.mjs call stock_data get_stock_price_indicators '{"windcode":"600519.SH","indexes":"最新成交价"}'
```

Windows PowerShell：

```powershell
node scripts/cli.mjs call stock_data get_stock_price_indicators '{"windcode":"600519.SH","indexes":"最新成交价"}'
```

Windows cmd：

```cmd
node scripts/cli.mjs call stock_data get_stock_price_indicators "{\"windcode\":\"600519.SH\",\"indexes\":\"最新成交价\"}"
```

验证只执行一次。验证成功后，告知用户 Wind 金融能力已可用；验证失败时，说明失败位置属于安装、Key、网络还是 Wind 服务返回，并结束流程。