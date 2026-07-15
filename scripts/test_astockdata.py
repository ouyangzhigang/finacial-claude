#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""a-stock-data 连通性测试"""
import sys

print("=" * 50)
print("a-stock-data 连通性测试")
print("=" * 50)

# Test 1: mootdx
print("\n[1] mootdx (通达信 TCP 7709)")
try:
    import socket
    from mootdx.quotes import Quotes
    for ip in ['119.97.185.59', '124.70.133.119', '116.205.183.150']:
        try:
            with socket.create_connection((ip, 7709), timeout=5):
                print(f"  TCP {ip}:7709 OK")
                c = Quotes.factory(market='std', server=(ip, 7709))
                q = c.quotes(symbol=['600519'])
                if q is not None and len(q) > 0:
                    print(f"  600519 price={q.iloc[0]['price']} vol={q.iloc[0]['vol']}")
                print("  ✅ mootdx WORKING")
                break
        except Exception as e:
            print(f"  TCP {ip}:7709 FAIL: {e}")
except ImportError:
    print("  ❌ mootdx not installed")

# Test 2: Tencent
print("\n[2] 腾讯财经 (HTTP)")
try:
    import urllib.request
    req = urllib.request.Request(
        'https://qt.gtimg.cn/q=sh600519,sz000858',
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode('gbk')
    for line in data.strip().split(';'):
        if '"' in line:
            vals = line.split('"')[1].split('~')
            if len(vals) > 46:
                print(f"  {vals[1]}({vals[2]}): price={vals[3]} PE={vals[39]} PB={vals[46]} mcap={vals[44]}yi")
    print("  ✅ 腾讯 WORKING")
except Exception as e:
    print(f"  ❌ 腾讯 FAIL: {e}")

# Test 3: THS hot reason
print("\n[3] 同花顺热点 (HTTP)")
try:
    import requests
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{today}/orderby/date/orderway/desc/charset/GBK/"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    d = r.json()
    rows = d.get("data") or []
    print(f"  当日强势股: {len(rows)} 只")
    if rows:
        for row in rows[:3]:
            print(f"    {row.get('name','')} {row.get('code','')} +{row.get('zhangfu',0)}% | {row.get('reason','')[:40]}")
    print("  ✅ 同花顺热点 WORKING")
except Exception as e:
    print(f"  ❌ 同花顺热点 FAIL: {e}")

# Test 4: Eastmoney ZT pool
print("\n[4] 东财涨停池 (push2ex)")
try:
    from datetime import date
    today = date.today().strftime("%Y%m%d")
    url = f"https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=10&sort=fbt:asc&date={today}"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}, timeout=10)
    d = r.json()
    pool = (d.get("data") or {}).get("pool") or []
    print(f"  涨停池: {len(pool)} 只 (date={today})")
    for p in pool[:3]:
        print(f"    {p.get('n','')} {p.get('c','')} | {p.get('lbc',0)}连板 | {p.get('hybk','')}")
    print("  ✅ 东财涨停池 WORKING")
except Exception as e:
    print(f"  ❌ 东财涨停池 FAIL: {e}")

print("\n" + "=" * 50)
print("测试完成")
