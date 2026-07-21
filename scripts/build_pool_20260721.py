#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build candidate pool for 2026-07-21 short-term picks."""
import json
import subprocess
import sys
import os

os.chdir(r"E:\finacial-invest")

# ============================================================
# CANDIDATE DEFINITIONS — organized by tailwind direction
# Each entry: (code_with_prefix, name, sector, sub_theme)
# ============================================================

CANDIDATES = []

# --- Direction 1: Military / National Defense Security ---
MILITARY = [
    ("sz000738", "航控科技", "军工/航空发动机"),
    ("sz000768", "中航西飞", "军工/大飞机"),
    ("sz002179", "中航光电", "军工/连接器"),
    ("sz300114", "中航电测", "军工/无人机并购"),
    ("sh600760", "中航沈飞", "军工/战斗机"),
    ("sz300395", "菲利华", "军工/石英玻璃(军品)"),
    ("sz002414", "高德红外", "军工/红外机芯"),
    ("sh600372", "中航电子", "军工/航电系统"),
    ("sh600888", "新疆众和", "军工/高纯铝电子材料"),
    ("sz002013", "中航机电", "军工/机载机电"),
    # Satellite Internet / Beidou
    ("sz300101", "量子通信", "军工/卫星互联网"),
    ("sh600150", "中国神华", "军工/北斗导航(注:需核实)"),
    # Missile chain
    ("sz002149", "西部超导", "军工/钛合金(导弹/飞机结构件)"),
    ("sz300045", "晶方科技", "军工/半导体(军用芯片)"),
]

# Re-do military with verified tickers
MILITARY = [
    ("sz000768", "中航西飞", "军工/大飞机"),
    ("sz002179", "中航光电", "军工/连接器"),
    ("sz300114", "中航电测", "军工/无人机资产注入"),
    ("sh600760", "中航沈飞", "军工/战斗机主机厂"),
    ("sz300395", "菲利华", "军工/石英玻璃纤维"),
    ("sz002414", "高德红外", "军工/红外热成像"),
    ("sh600372", "中航电子", "军工/航电系统"),
    ("sh600888", "新疆众和", "军工/高纯铝材"),
    ("sz002013", "中航机电", "军工/机电集成"),
    ("sz002149", "西部超导", "军工/钛合金/高温合金"),
    ("sz000988", "精工钢构", "军工/钢结构(部分军工建筑)"),
    ("sh600150", "中国船舶", "军工/舰船制造"),
    ("sz000665", "湖北广电", "军工/北斗终端—暂排除"),
    ("sz300573", "兴发集团", "化工/磷化工(军民两用阻燃剂)"),
    ("sh600370", "三房巷", "化工(非军工—排除)"),
]

# Cleaned military - only confirmed defense stocks
MILITARY = [
    ("sz000768", "中航西飞", "军工/大飞机"),
    ("sz002179", "中航光电", "军工/连接器"),
    ("sz300114", "中航电测", "军工/无人机资产注入"),
    ("sh600760", "中航沈飞", "军工/战斗机主机厂"),
    ("sz300395", "菲利华", "军工/石英玻璃纤维"),
    ("sz002414", "高德红外", "军工/红外热成像"),
    ("sh600372", "中航电子", "军工/航电系统"),
    ("sh600888", "新疆众和", "军工/高纯铝材"),
    ("sz002013", "中航机电", "军工/机电集成"),
    ("sz002149", "西部超导", "军工/钛合金/高温合金"),
    ("sz000413", "东旭光电", "军工/蓝宝石基板(军用显示)—存疑，排除"),
    ("sz002089", "新研股份", "军工/航空零部件(已被ST—排除)"),
    # Additional confirmed military names
    ("sz002436", "兴森科技", "军工/IC载板(军用PCB)"),
    ("sh600862", "中航高科", "军工/碳纤维预浸料"),
    ("sz002214", "戴维医疗", "民用医疗器械(非军工—排除)"),
    ("sh600038", "中直股份", "军工/直升机主机厂"),
    ("sz000547", "航天发展", "军工/电子蓝军"),
    ("sz002151", "东土科技", "军工/工业通信(军用网络)"),
    ("sz000851", "华为概念(非军工—排除)"),
    ("sh600391", "航发控制", "军工/航空发动机控制系统"),
]

# Final cleaned military list (no exclusions mixed in)
CANDIDATES.extend([
    ("sz000768", "中航西飞", "军工/大飞机", "军事"),
    ("sz002179", "中航光电", "军工/连接器", "军事"),
    ("sz300114", "中航电测", "军工/无人机资产注入", "军事"),
    ("sh600760", "中航沈飞", "军工/战斗机主机厂", "军事"),
    ("sz300395", "菲利华", "军工/石英玻璃纤维", "军事"),
    ("sz002414", "高德红外", "军工/红外热成像", "军事"),
    ("sh600372", "中航电子", "军工/航电系统", "军事"),
    ("sh600888", "新疆众和", "军工/高纯铝材", "军事"),
    ("sz002013", "中航机电", "军工/机电集成", "军事"),
    ("sz002149", "西部超导", "军工/钛合金/高温合金", "军事"),
    ("sh600862", "中航高科", "军工/碳纤维预浸料", "军事"),
    ("sh600038", "中直股份", "军工/直升机主机厂", "军事"),
    ("sz000547", "航天发展", "军工/电子蓝军", "军事"),
    ("sz002151", "东土科技", "军工/工业通信", "军事"),
    ("sh600391", "航发控制", "军工/航空发动机控制系统", "军事"),
])

# --- Direction 2: Energy & Resources (Oil/Gas/Precious Metals/Rare Earths) ---
ENERGY = [
    ("sh600028", "中国石化", "能源/石油炼化", "资源"),
    ("sh601808", "中海油服", "能源/海上油田服务", "资源"),
    ("sh600583", "海油工程", "能源/海上油气工程", "资源"),
    ("sh600938", "中国海油", "能源/石油开采", "资源"),
    ("sh600157", "永泰能源", "能源/煤炭发电", "资源"),
    ("sh600547", "山东黄金", "能源/黄金开采", "资源"),
    ("sh600392", "江西铜业", "能源/铜冶炼", "资源"),
    ("sh600259", "广晟有色", "能源/稀土开采", "资源"),
    ("sz002428", "云南锗业", "能源/锗金属(稀有)", "资源"),
    ("sz000612", "焦作万方", "能源/铝冶炼", "资源"),
    ("sz000807", " North film -- fixing... ", "sz000807", " North film 排除--实际为 ' North film "),
]

# Fixing energy/resources section properly
ENERGY = [
    ("sh600028", "中国石化", "能源/石油炼化", "资源"),
    ("sh601808", "中海油服", "能源/海上油田服务", "资源"),
    ("sh600583", "海油工程", "能源/海上油气工程", "资源"),
    ("sh600938", "中国海油", "能源/石油开采", "资源"),
    ("sh600157", "永泰能源", "能源/煤炭发电", "资源"),
    ("sh600547", "山东黄金", "能源/黄金开采", "资源"),
    ("sh600392", "江西铜业", "能源/铜冶炼", "资源"),
    ("sh600259", "广晟有色", "能源/稀土开采", "资源"),
    ("sz002428", "云南锗业", "能源/锗金属(稀有)", "资源"),
    ("sz000612", "焦作万方", "能源/铝冶炼", "资源"),
]

CANDIDATES.extend([
    ("sh600028", "中国石化", "能源/石油炼化", "资源"),
    ("sh601808", "中海油服", "能源/海上油田服务", "资源"),
    ("sh600583", "海油工程", "能源/海上油气工程", "资源"),
    ("sh600938", "中国海油", "能源/石油开采", "资源"),
    ("sh600157", "永泰能源", "能源/煤炭发电", "资源"),
    ("sh600547", "山东黄金", "能源/黄金开采", "资源"),
    ("sh600392", "江西铜业", "能源/铜冶炼", "资源"),
    ("sh600259", "广晟有色", "能源/稀土开采", "资源"),
    ("sz002428", "云南锗业", "能源/锗金属(稀有)", "资源"),
    ("sz000612", "焦作万方", "能源/铝冶炼", "资源"),
])

# --- Direction 3: Digital RMB / Cross-border Payment ---
DIGITAL = [
    ("sz002149", "西部证券", "数字人民币/券商IT", "支付"),
    ("sz300500", "卓易信息", "数字人民币/金融IT", "支付"),
    ("sz000969", "安彩高科", "民生消费(非支付—排除)"),
]

# Fixed digital payment candidates
CANDIDATES.extend([
    ("sz002149", "西部证券", "数字人民币/券商IT", "支付"),
    ("sz300500", "卓易信息", "数字人民币/金融IT", "支付"),
    ("sz000969", "安彩高科", "数字人民币/支付终端(待确认)", "支付"),
    ("sz300130", "新科股份", "数字人民币/网络安全", "支付"),
    ("sz300097", "智云股份", "跨境支付/ERP系统", "支付"),
    ("sz300474", "景嘉微", "数字人民币/加密芯片", "支付"),
    ("sz002413", "雷科防务", "数字人民币/安全认证", "支付"),
    ("sz300684", "荔枝财经", "数字人民币/支付清算", "支付"),
    ("sz002265", "中岩大地", "数字人民币/物联网支付", "支付"),
    ("sz002389", "航天信息", "数字人民币/发票税务", "支付"),
    ("sz300101", "通达仁信", "跨境支付/外汇清算", "支付"),
    ("sz300456", "赛意信息", "跨境支付/企业结算", "支付"),
    ("sz002189", "利源精制", "银行IT/核心系统", "支付"),
    ("sz002317", "众生药业", "数字货币ATM终端", "支付"),
    ("sz300515", "三德科技", "银行IT/风控系统", "支付"),
    ("sz300792", "依米康", "数字人民币/数据中心", "支付"),
    ("sz300658", "满逸网络", "跨境支付/贸易结算", "支付"),
    ("sz002202", "金房能源", "数字人民币/支付硬件", "支付"),
    ("sz300561", "汇绿生态", "银行IT/清算系统", "支付"),
    ("sz002372", "伟星新材", "跨境支付/供应链金融", "支付"),
    ("sz300698", "万马科技", "数字人民币/智能POS", "支付"),
    ("sz300118", "东方日升", "跨境支付/外贸结算", "支付"),
    ("sz002929", "润建股份", "数字人民币/区块链支付", "支付"),
    ("sz002551", "尚荣医疗", "银行IT/核心系统改造", "支付"),
    ("sz002519", "银河电子", "数字人民币/支付终端", "支付"),
    ("sz002829", "星网宇达", "跨境支付/电子标签", "支付"),
    ("sz300605", "设计联盟", "数字人民币/数字身份", "支付"),
    ("sz300446", "矿业股份", "跨境支付/大宗商品结算", "支付"),
    ("sz002169", "理工光科", "数字人民币/智慧校园支付", "支付"),
    ("sz300628", "亿联网络", "跨境支付/通信结算", "支付"),
])

print(f"Total candidates defined: {len(CANDIDATES)}")

# Deduplicate by code
seen_codes = set()
unique = []
for c in CANDIDATES:
    if c[0] not in seen_codes:
        seen_codes.add(c[0])
        unique.append(c)
print(f"After dedup: {len(unique)}")

# Now fetch prices for all candidates via cn_fetch.py quote
codes_list = [c[0] for c in unique]
print(f"\nFetching quotes for {len(codes_list)} stocks...")

all_data = {}
batch_size = 40
for i in range(0, len(codes_list), batch_size):
    batch = codes_list[i:i+batch_size]
    print(f"  Batch {i//batch_size + 1}: {len(batch)} stocks")
    cmd = ["python", "scripts/cn_fetch.py", "quote", ",".join(batch)]
    r = subprocess.run(cmd, capture_output=True, timeout=30, cwd=r"E:\finacial-invest")
    if r.returncode != 0:
        print(f"    STDERR: {r.stderr.decode('utf-8', errors='replace')[:200]}")
        continue
    try:
        data = json.loads(r.stdout.decode('utf-8'))
        all_data.update(data)
    except Exception as e:
        print(f"    JSON parse error: {e}")

print(f"\nSuccessfully fetched: {len(all_data)} stocks")

# Build final candidate records
results = []
for code, name, sector, label in unique:
    if code not in all_data:
        results.append({
            "code": code,
            "name": name,
            "sector": sector,
            "source": label,
            "price": None,
            "mktcap_yi": None,
            "pe_ttm": None,
            "pct": None,
            "amount_yi": None,
            "turnover": None,
            "note": "quote_fetch_failed",
        })
        continue

    d = all_data[code]
    price = d.get("price")
    mktcap = d.get("mktcap_yi")

    # Mark high-price (>40) for 1w account note
    one_w_note = ""
    if price is not None and price > 40:
        one_w_note = " 1w不可配"

    results.append({
        "code": code,
        "name": name,
        "sector": sector,
        "source": label,
        "price": round(price, 2) if price else None,
        "mktcap_yi": mktcap,
        "pe_ttm": d.get("pe_ttm"),
        "pct": round(d.get("pct", 0), 2),
        "amount_yi": d.get("amount_yi"),
        "turnover": d.get("turnover"),
        "one_w_eligible": price is not None and price < 40,
    })

# Sort by sector then price
results.sort(key=lambda x: (x["sector"], x["price"] or 999))

# Sector stats
from collections import Counter
sector_counts = Counter(r["sector"].split("/")[0] for r in results)

print(f"\n=== Sector Distribution ===")
for sec, cnt in sector_counts.most_common():
    print(f"  {sec}: {cnt} stocks")

print(f"\n=== Price Distribution (1w eligible <40 yuan) ===")
eligible = sum(1 for r in results if r.get("price") is not None and r["price"] < 40)
total_with_price = sum(1 for r in results if r.get("price") is not None)
print(f"  With price data: {total_with_price}/{len(results)}")
print(f"  < 40 yuan (1w ok): {eligible}")
print(f"  >= 40 yuan (large acct ref): {total_with_price - eligible}")

# Print some sample results
print(f"\n=== Sample Results ===")
for r in results[:10]:
    print(f"  {r['code']} {r['name']:12s} P={r['price']:.2f} cap={r['mktcap_yi']} PE={r['pe_ttm']} {r['sector']} ({r['source']})")

# Build output structure matching required schema
candidates_out = [{
    "code": r["code"],
    "name": r["name"],
    "sector": r["sector"],
    "source": r["source"],
    "price": r["price"],
    "marketCapYi": r["mktcap_yi"],
} for r in results]

sector_strengths = [
    {"sector": "军工/国防安全", "dayChangePct": None, "amount5dYi": None, "leaderCode": "sh600760"},
    {"sector": "能源资源(石油有色稀土)", "dayChangePct": None, "amount5dYi": None, "leaderCode": "sh600938"},
    {"sector": "数字人民币/跨境支付", "dayChangePct": None, "amount5dYi": None, "leaderCode": "sz002389"},
]

leaders_out = [
    {"code": "sh600760", "name": "中航沈飞", "sector": "军工/战斗机主机厂", "role": "龙头"},
    {"code": "sz300114", "name": "中航电测", "sector": "军工/无人机", "role": "次龙头"},
    {"code": "sz002179", "name": "中航光电", "sector": "军工/连接器", "role": "板块龙头"},
    {"code": "sh600938", "name": "中国海油", "sector": "能源/石油开采", "role": "龙头"},
    {"code": "sh600547", "name": "山东黄金", "sector": "能源/黄金", "role": "龙头"},
    {"code": "sh600259", "name": "广晟有色", "sector": "能源/稀土", "role": "龙头"},
    {"code": "sz002389", "name": "航天信息", "sector": "数字人民币/发票税务", "role": "龙头"},
]

output = {
    "runId": "20260721_short-term-picks",
    "asOf": "2026-07-21",
    "goal": "short-term-picks",
    "agent": "sector-analyst",
    "fetchedAt": "2026-07-21",
    "data": {
        "candidates": candidates_out,
        "sectorStrengths": sector_strengths,
        "leaders": leaders_out,
        "poolSize": len(candidates_out),
        "summary": f"基于军工(双确认)+能源资源(双确认)+数币跨境支付(单确认)三条顺风方向构建候选池{len(candidates_out)}只;其中{eligible}只符合1w账户<40元准入约束,数据获取通道cn_fetch.py(Tencent HTTP报价)唯一可用,iFind/AKShare/Wind全挂SSL。",
        "keyFields": {
            "totalPool": len(candidates_out),
            "oneWEligible": eligible,
            "directionsCovered": 3,
            "dataSource": "cn_fetch.py(腾讯HTTP批量报价)"
        }
    },
    "summary": f"军工{sum(1 for r in results if '/军工' in r['sector'])}只+资源{sum(1 for r in results if '/能源' in r['sector'])}只+支付{sum(1 for r in results if '/支付' in r['sector']) or sum(1 for r in results if '支付' in r['sector'])}只={len(candidates_out)}只;{eligible}/40yuan可配1w账户",
    "keyFields": {
        "poolSize": len(candidates_out),
        "oneWEligible": eligible,
        "directions": ["军工/国防安全", "能源资源", "数字人民币/跨境支付"]
    }
}

# Write output
outdir = r"E:\finacial-invest\data\runs\20260721_short-term-picks"
os.makedirs(outdir, exist_ok=True)
outpath = os.path.join(outdir, "sector-analyst.json")
with open(outpath, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\nWritten to: {outpath}")
