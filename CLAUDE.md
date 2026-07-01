# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository shape

A workspace assembling a China/US financial-investment analysis stack for Claude Code. No top-level build system, package manifest, or test suite — it composes data servers, installed Claude Skills, and two source trees.

- `mcp-servers/` — **data layer**: 5 stdio MCP servers (FastMCP + Python)
- `.claude/skills/` — **capability layer**: 47 installed Claude Skills
- `.mcp.json` — project MCP config (holds plaintext tokens — keep git-ignored)
- `claude-for-financial-services-cn/` — sell-side agents/cookbooks/skills source tree; has its own CLAUDE.md
- `finskills/` — separate git repo; buy-side skills source (US-market + China-market)

## MCP data layer (`mcp-servers/`)

FastMCP + Python, default `stdio` (SSE via `--transport sse --port`). Run from repo root. **Windows: use `python`, not `python3`** (`python3` is not on PATH here).

| Server | Tools | Auth env var | Tier |
|---|---|---|---|
| wind-mcp | 44 / 8 domains | `WIND_API_KEY` (starts `ak_`) | Tier-0 paid |
| ifind-mcp | 31 | `IFIND_AUTH_TOKEN` | Tier-1 paid |
| fmp-mcp | 9 | `FMP_API_KEY` | overseas paid |
| akshare-mcp | 9 | — | Tier-2 free |
| china-news-mcp | 2 | — | Tier-3 free |

**Soft-fail design:** every server starts and registers all tools even when its token is missing — it only prints a WARNING to stderr and returns `{"error": ...}` at tool-call time. So servers can be wired into `.mcp.json` before keys are obtained.

Token load order (paid servers): env var → `mcp-servers/<server>/mcp_config.json` (field `api_key` or `auth_token`). Multi-tier fallback (Wind→iFind→AkShare) is controlled by `IFIND_DATA_SOURCE_MODE` / wind-mode env vars (`ifind-fallback` default) — see the subdir CLAUDE.md for the full mode table.

Install deps: `pip install -r mcp-servers/<server>/requirements.txt`.

## Skills (`.claude/skills/`)

Progressive-disclosure: only YAML frontmatter is always in context; `SKILL.md` body loads on trigger; `references/*` on demand. Two families coexist:

- **`china-*` (31)** — sell-side IB workflow (DCF, LBO, 3-statement, comps, earnings preview, deck/pptx authoring, GL recon…). Source: `claude-for-financial-services-cn/vertical-plugins/china-finance/skills/`; `agent-plugins/*/skills/` bundle vendored copies — **never edit the bundled copies**, edit in `vertical-plugins/` then run `python scripts/sync-china-skills.py`.
- **buy-side (15)** — esg-screener, quant-factor-screener, portfolio-health-check, undervalued-stock-screener, findata-toolkit-cn, etc. Source: `finskills/China-market/`.
- `wind-data` — Wind AIFin Market install/config/verify entry point.

Toolkit skills (`findata-toolkit-cn`) bundle self-contained Python scripts + their own `requirements.txt` + `config/data_sources.yaml`. Other analysis skills reference a toolkit **by name in prose** — no wiring. Skill data sources are free/keyless: AKShare (A-shares), yfinance / SEC EDGAR / FRED (US).

## Slash commands & analysis prompts

Three user-facing `/` commands in `.claude/commands/`, each binds `$ARGUMENTS` onto a root-level prompt framework and writes a Markdown report to `output/`:

| Command | Prompt framework (repo root) | Output file |
|---|---|---|
| `/analysis-stock [股票+描述]` | `stock-analysis-prompt-cn.md` | `output/{code}_{YYYYMMDD}_深度分析报告.md` |
| `/recommend-stocks [参数]` | `short-term-stock-picks-prompt-cn.md` | `output/{YYYYMMDD}_短周期2周推荐清单.md` |
| `/hot-trends [约束]` | `recommend_module_stocks.md` | `output/{YYYYMMDD}_热门板块*.md` |

**`$ARGUMENTS` passthrough:** substitution happens **only in the command file**, never in the `@`-referenced prompt file (loaded as a static framework). Each command therefore carries an explicit "输入变量绑定" block that parses `$ARGUMENTS` onto the framework's variables — change how args map by editing that block. The prompt frameworks stay generic (`【待填】` + defaults); **never hardcode a stock code into a framework file**.

**Reports:** always written to `output/` (create the dir if missing), never chat-only. Each command's "输出要求" section defines the visual structure (decision dashboard, tables, 🟢🟡🔴 badges, 免责声明).

## Ignoring directories

Claude Code can skip directories so search (Glob/Grep) and reads avoid them:

- **`.gitignore`** — Glob/Grep respect it (skips untracked files there). Lightest option; only affects search, not explicit reads.
- **`.claude/settings.json` `permissions.deny`** — harness-enforced block on Read/Grep/Glob for given paths. Stronger than `.gitignore`.
- This CLAUDE.md — soft guidance only (model obeys voluntarily, no enforcement).

A `.gitignore` entry must match the real directory name exactly — e.g. `claude-for-financial-services-cn/` (note: `financial`, the `finacial` spelling does not match).

## Token safety

`.mcp.json` and `mcp-servers/*/mcp_config.json` hold plaintext API tokens — keep them git-ignored before any commit. For shareable config, use `${VAR}` placeholders + env vars instead of committed secrets.

## Working in `claude-for-financial-services-cn/`

That subdir's CLAUDE.md is authoritative for: the 4 China agents (china-pitch-agent, -market-researcher, -earnings-reviewer, -model-builder), cookbook deploy/sync scripts, and the data-source mode table. `scripts/` exists both at the repo root and inside the subdir (same files).

Key scripts (from root):
- `python scripts/check-china.py` — validate before push
- `python scripts/sync-china-skills.py` — propagate a `vertical-plugins/` skill edit to bundled agent copies
- `python scripts/validate.py <output.json> <schema.json|schema.yaml>` — validate worker output
- `bash scripts/deploy-managed-agent.sh <slug> [--dry-run]` — deploy a managed-agent cookbook
- `python scripts/cn_fetch.py` — free HTTP data channel (新浪榜单 + 腾讯 K线/批量报价) for batch screening & K-line when an MCP field is missing or SSL-blocked; the commands' soft-fail fallback. Handles 腾讯 GBK + Windows SSL quirks internally.
- `python scripts/hot_trend_dig.py` — 龙虎榜 detail mining via AkShare (`stock_lhb_detail_em`); parses 机构/拉萨/游资 signals.
- `python scripts/orchestrate.py` — **reference only** event loop for cross-agent handoffs among the 4 China managed agents (not production).

## Environment gotchas

- Python 3.13 on Windows; `python` is on PATH, `python3` is not.
- Local network can't reach some financial APIs directly: the East Money global-headline endpoint fails SSL verification, and FMP returns 403 (likely geo/IP block). AkShare A-share endpoints work; other overseas/paid endpoints are unverified from here — plan on a proxy.
- Local MCP reachability (verified by the existing commands): **iFind + AkShare + china-news work; Wind needs `WIND_SSL_NO_VERIFY=1`; FMP and East Money push2his fail.** When an MCP field is missing or SSL-blocked, fall back to `python scripts/cn_fetch.py` (新浪/腾讯 HTTP, keyless) or `curl` 东方财富 push2 镜像 (`19/29.push2`) + 腾讯 `qt.gtimg.cn` / `web.ifzq.gtimg.cn`. WebFetch/WebSearch are blocked locally.
