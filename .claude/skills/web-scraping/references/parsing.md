# Parsing 深度参考（Selector）

`page` 即 `Selector`（来自 `scrapling.parser`），CSS / XPath / BeautifulSoup 风格通用。自适应元素定位是杀手锏。

## 选择方法

```python
page.css('.quote .text::text').getall()        # CSS + 伪元素取文本（Scrapy 风格）
page.css('.quote').css('.text::text').get()     # 链式
page.xpath('//div[@class="quote"]')             # XPath
page.find_all('div', class_='quote')            # BeautifulSoup 风格
page.find_all('div', {'class': 'quote'})
page.find_all(['div'], class_='quote')
page.find_all(class_='quote')
page.find_by_text('买入', tag='td')             # 按文本定位（金融表格常用）
```

- `.get()` 取首个；`.getall()` 取全部；`.extract_first()` 同 `.get()`
- 伪元素 `::text` 取文本、`::attr(href)` 取属性

## 自适应定位（页面改版自动重定位）

```python
# 首次抓取时 auto_save 记录元素特征指纹
products = page.css('.product', auto_save=True)
# 之后站点改版，原选择器失效，传 adaptive=True 用相似度算法找回
products = page.css('.product', adaptive=True)
```

原理：记录元素的多维特征（标签、结构、文本、属性、相对位置），选择器失效时按相似度重新定位。比 AutoScraper 快约 5 倍（官方基准）。

## DOM 导航

```python
first = page.css('.quote')[0]
first.parent                 # 父节点
first.next_sibling           # 下一兄弟节点
first.below_elements()       # 下方元素
first.find_similar()         # 结构相似的同类元素（批量抓同构卡片）
```

## 纯本地解析

不抓网络，直接解析已有 HTML，API 完全一致：

```python
from scrapling.parser import Selector
page = Selector("<html>...</html>")
page.css('h1::text').get()
```

## 文本处理

- `::text` 伪元素 + `.getall()`
- `.clean_text` / 内置正则
- 金融表格常用：`find_by_text('买入价', tag='td')` 定位单元格，再 `.next_sibling` 取相邻值
