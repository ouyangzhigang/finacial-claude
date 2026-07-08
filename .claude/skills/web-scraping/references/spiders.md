# Spiders 深度参考（并发爬虫）

Scrapy 风格的爬虫框架：并发、多 session、暂停恢复、代理轮换、robots.txt、流式输出。

## 基本 Spider

```python
from scrapling.spiders import Spider, Request, Response

class QuotesSpider(Spider):
    name = "quotes"
    start_urls = ["https://quotes.toscrape.com/"]
    concurrent_requests = 10
    robots_txt_obey = True        # 自动遵守 robots.txt
    download_delay = 0.5          # 礼貌延时

    async def parse(self, response: Response):
        for q in response.css('.quote'):
            yield {"text": q.css('.text::text').get(), "author": q.css('.author::text').get()}
        nxt = response.css('.next a')
        if nxt:
            yield response.follow(nxt[0].attrib['href'])

result = QuotesSpider().start()
print(f"Scraped {len(result.items)} quotes")
result.items.to_json("quotes.json")    # 或 to_jsonl
```

## 多 session（一个 spider 内混用 HTTP + stealth）

```python
from scrapling.spiders import Spider, Request, Response
from scrapling.fetchers import FetcherSession, AsyncStealthySession

class MultiSessionSpider(Spider):
    name = "multi"
    start_urls = ["https://example.com/"]

    def configure_sessions(self, manager):
        manager.add("fast", FetcherSession(impersonate="chrome"))
        manager.add("stealth", AsyncStealthySession(headless=True), lazy=True)

    async def parse(self, response: Response):
        for link in response.css('a::attr(href)').getall():
            if "protected" in link:
                yield Request(link, sid="stealth")
            else:
                yield Request(link, sid="fast", callback=self.parse)
```

## 规则爬虫（CrawlSpider + LinkExtractor）

```python
from scrapling.spiders import CrawlSpider, CrawlRule, LinkExtractor

class BlogCrawler(CrawlSpider):
    name = "blog"
    start_urls = ["https://example.com"]
    def rules(self):
        return [
            CrawlRule(LinkExtractor(allow=r"/posts/"), callback=self.parse_post),
            CrawlRule(LinkExtractor(allow=r"/page/\d+/")),  # 跟翻页，无回调
        ]
    async def parse_post(self, response):
        yield {"title": response.css("h1::text").get()}
```

`LinkExtractor` 支持 allow/deny（正则）、restrict_css、canonicalize。站点地图驱动用 `SitemapSpider`（同 rules() API，自动从 robots.txt 取 Sitemap 指令）。

## 暂停 / 恢复

```python
QuotesSpider(crawldir="./crawl_data").start()
```

Ctrl+C 优雅暂停，进度自动存档；再跑同 `crawldir` 即续。

## 开发模式（缓存响应，免反复打服务器）

```python
class MySpider(Spider):
    name = "dev"
    development_mode = True              # 缓存到 .scrapling_cache/{name}/
    # development_cache_dir = "./cache"  # 自定义
```

调 `parse()` 逻辑时第一跑缓存响应，之后重放，不重打目标。**别带此发布。**

## 流式输出

```python
async for item in spider.stream():
    process(item)   # 实时拿数据，配实时统计
```

## 代理轮换

`ProxyRotator`：cyclic 或自定义策略，跨所有 session 类型，支持单请求代理覆盖。

## 被封检测

自动检测并重试被封请求，可自定义判定逻辑。
