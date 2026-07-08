# CLI 参考（scrapling extract / shell）

免写代码直接抓。**命令行抓取务必加 `--ai-targeted`** 防 prompt injection（只取正文、清隐元素；浏览器命令还自动挡广告省 token）。

## extract 命令组

子命令：get / post / put / delete（HTTP） | fetch（Playwright） | stealthy-fetch（反爬）。

输出格式由文件扩展名决定：`.md`=HTML 转 Markdown（文档/新闻首选）、`.txt`=纯文本、`.html`=原始 HTML、其他=原文。

### 选哪个子命令
- `get`：简单站、博客、新闻
- `fetch`：现代 web app、动态内容
- `stealthy-fetch`：受保护站、Cloudflare、反爬

不确定从 `get` 起步；空内容或被挡升 `fetch`，再升 `stealthy-fetch`。后两者速度接近。

### HTTP 选项（get/post/put/delete 共享）
- `-H, --headers "Key: Value"`：请求头（可多次）
- `--cookies "n1=v1; n2=v2"`：cookie
- `--timeout N`：秒（默认 30）
- `--proxy "http://user:pass@host:port"`：代理
- `-s, --css-selector SEL`：只取匹配片段（省 token）
- `-p, --params "k=v"`：查询参数（可多次）
- `--follow-redirects/--no-follow-redirects`：跟重定向（默认 safe，拒内部 IP）
- `--verify/--no-verify`：SSL 校验（默认 True）
- `--impersonate chrome`：TLS 指纹（可逗号分隔随机）
- `--stealthy-headers/--no-stealthy-headers`：浏览器头（默认 True）
- `--ai-targeted`：只取正文，防 prompt injection
- post/put 额外：`-d, --data "k=v"` 表单；`-j, --json` JSON 体

### 浏览器选项（fetch / stealthy-fetch 共享）
`--headless/--no-headless`、`--disable-resources/--enable-resources`、`--network-idle/--no-network-idle`、`--real-chrome/--no-real-chrome`、`--timeout N`（毫秒，默认 30000）、`--wait N`、`-s/--css-selector`、`--wait-selector SEL`、`--proxy URL`、`-H/--extra-header`、`--dns-over-https/--no-dns-over-https`、`--block-ads/--no-block-ads`、`--ai-targeted`。

stealthy-fetch 独有：`--block-webrtc`、`--solve-cloudflare`、`--allow-webgl/--block-webgl`、`--hide-canvas/--show-canvas`。fetch 独有：`--locale`。

### 示例
```bash
scrapling extract get "https://news.site.com" news.md --ai-targeted
scrapling extract get "https://site.com" out.md -s "article" --ai-targeted
scrapling extract fetch "https://app.site.com" page.md --network-idle --ai-targeted
scrapling extract fetch "https://site.com" data.txt --wait-selector ".content-loaded"
scrapling extract stealthy-fetch "https://nopecha.com/demo/cloudflare" data.txt --solve-cloudflare -s "#padded_content a"
```

## 交互式 shell
`scrapling shell` —— 内置 IPython，把 curl 命令转 Scrapling 请求、浏览器里看结果，加速写脚本。

## 安装浏览器依赖
```bash
scrapling install
scrapling install --force
```
