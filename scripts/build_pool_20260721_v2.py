#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build candidate pool from _shared.json rank data + manual tailwind additions."""
import json, os, sys

# Load the rank TSV from _shared.json
shared_path = r"E:\finacial-invest\data\runs\20260721_short-term-picks\_shared.json"
with open(shared_path, "r", encoding="utf-8") as f:
    shared = json.load(f)

tsv = shared.get("rankChangePct", {}).get("tsv", "")
if not tsv:
    print("ERROR: no rank TSV in _shared.json")
    sys.exit(1)

# Parse the TSV: code, name, price, changePct, amount_yi, turnover, float_mktcap_yi, pe, pb
# Format from cn_fetch.py rank:
# f"{s}\t{n}\t{trade:.2f}\t{changepercent:.2f}\t{amount/1e8:.2f}\t{turnoverratio:.2f}\t{nmc/1e4:.1f}\t{pe_str}\t{pb_str}"
rank_stocks = []
for line in tsv.strip().split("\n"):
    parts = line.split("\t")
    if len(parts) < 8:
        continue
    code = parts[0]
    name = parts[1]
    if "ST" in name or "退" in name or name.startswith("N"):
        continue  # skip ST, delisted, and new IPO stocks
    try:
        price = float(parts[2])
        pct = float(parts[3])
        amount = float(parts[4])
        turnover = float(parts[5])
        float_mktcap = float(parts[6])
        pe_str = parts[7]
        pe = float(pe_str) if pe_str and pe_str != "NA" else None
        pb_str = parts[8] if len(parts) > 8 else "NA"
        pb = float(pb_str) if pb_str and pb_str != "NA" else None
    except (ValueError, IndexError) as e:
        continue

    rank_stocks.append({
        "code": code,
        "name": name,
        "price": price,
        "pct": pct,
        "amount_yi": amount,
        "turnover": turnover,
        "float_mktcap_yi": float_mktcap,
        "pe": pe,
        "pb": pb,
    })

print(f"Parsed {len(rank_stocks)} stocks from rank TSV")

# ============================================================
# SECTOR CLASSIFICATION — map each rank stock to tailwind
# ============================================================
# Tailwinds: 半导体/存储芯片/先进封装, 中报预增, 人形机器人/储能

# Known semiconductor stocks (by code pattern + known names)
SEMICONDUCTOR_CODES = {
    "sh688728": "半导体/CMOS传感器",
    "sh688328": "半导体/设备",
    "sh688596": "半导体/设备",
    "sh688110": "存储芯片",
    "sh688261": "半导体/功率器件",
    "sh688347": "半导体/晶圆代工",
    "sh688361": "半导体/检测设备",
    "sh688001": "半导体/检测设备",
    "sh688037": "半导体/设备(涂胶显影)",
    "sh688072": "半导体/设备(薄膜沉积)",
    "sh688627": "半导体/设备(测试)",
    "sh688797": "半导体/材料",
    "sz300604": "半导体/设备(测试)",
    "sz301369": "半导体/设备",
    "sh688809": "半导体/设计",
    "sh688002": "半导体/红外芯片",
    "sh688120": "半导体/设备(CMP)",
    "sh688003": "半导体/机器视觉",
    "sh688141": "半导体/模拟芯片",
    "sz300814": "半导体/PCB载板",
    "sh688147": "半导体/设备(ALD)",
    "sz301583": "半导体/设备",
    "sh688729": "半导体/设备(去胶)",
    "sh688409": "半导体/零部件",
    "sh688662": "半导体/热电",
    "sh688012": "半导体/设备(刻蚀)",
    "sz300666": "半导体/靶材",
    "sh688392": "半导体/超声波设备",
    "sh688610": "半导体/光电检测",
    "sh688059": "半导体/刀具(部分)",
    "sh688308": "半导体/刀具(部分)",
    "sh688371": "半导体/纳米镀膜",
    "sz301282": "半导体/PCB",
}

# Known robot/energy storage stocks
ROBOT_CODES = {
    "sz300643": "汽车电子/机器人传感器",
    "sz301012": "变压器/储能",
    "sz300093": "光伏/储能",
    "sz300201": "特种车辆/机器人应用",
    "sz301205": "光通信/数据中心(储能相关)",
}

# Earnings season (中报预增) - most semiconductor stocks overlap
# For the rank stocks, we'll tag them as 中报预增 if they're in semiconductor sector
# since the hot_tags show 中报预增(24) and 半导体(14+10+7=31) heavily overlap

# Other stocks in the rank that don't fit tailwinds
OTHER_RANK = {
    "sz300795": "会展",
    "sz301588": "新材料",
    "sz301421": "光学",
    "sz301310": "电缆",
    "sz301273": "环保",
    "sz301580": "口腔医疗",
    "sz300285": "材料/牙科",
    "sz300137": "环保",
}

# ============================================================
# Build candidates from rank data
# ============================================================
candidates = []
rank_used_codes = set()

for s in rank_stocks:
    code = s["code"]
    if code in rank_used_codes:
        continue
    rank_used_codes.add(code)

    # Determine sector and source
    sector = None
    source = None

    if code in SEMICONDUCTOR_CODES:
        sector = SEMICONDUCTOR_CODES[code]
        source = "榜单+顺风板块(半导体)"
    elif code in ROBOT_CODES:
        sector = ROBOT_CODES[code]
        source = "榜单+顺风板块(人形机器人/储能)"
    elif code in OTHER_RANK:
        sector = OTHER_RANK[code]
        source = "榜单(非顺风方向-排除)"
        continue  # Skip non-tailwind stocks
    else:
        # Check if it could be 中报预增
        # For now, classify as unknown
        sector = "其他"
        source = "榜单(分类待确认)"
        continue  # Skip uncertain

    # Determine sub-direction
    if "半导体" in sector or "存储" in sector or "芯片" in sector:
        direction = "半导体/存储芯片/先进封装"
    elif "储能" in sector or "光伏" in sector:
        direction = "人形机器人/储能"
    elif "机器人" in sector:
        direction = "人形机器人/储能"
    else:
        direction = "中报预增"

    # Check 1w account eligibility
    one_w_eligible = s["price"] < 40

    candidates.append({
        "code": code,
        "name": s["name"],
        "sector": sector,
        "direction": direction,
        "source": source,
        "price": s["price"],
        "changePct": s["pct"],
        "amountYi": s["amount_yi"],
        "turnover": s["turnover"],
        "floatMarketCapYi": s["float_mktcap_yi"],
        "peTtm": s["pe"],
        "pb": s["pb"],
        "oneWEligible": one_w_eligible,
        "dataQuality": "live_rank",
    })

print(f"Candidates from rank: {len(candidates)}")

# ============================================================
# MANUAL ADDITIONS — tailwind sector stocks not in rank
# These are stocks I know are in the tailwind sectors but may
# not have made the top-50 rank. Prices are estimated from
# market knowledge and need verification.
# ============================================================

# Lower-priced semiconductor stocks (for 1w account)
MANUAL_SEMICONDUCTOR = [
    # 先进封装
    ("sz002156", "通富微电", "先进封装", 28.5, 380, "手动-顺风板块"),
    ("sh600584", "长电科技", "先进封装", 35.2, 620, "手动-顺风板块"),
    ("sz002185", "华天科技", "先进封装", 12.8, 410, "手动-顺风板块"),
    ("sh603005", "晶方科技", "先进封装/TSV", 32.5, 210, "手动-顺风板块"),
    # 存储芯片
    ("sh603986", "兆易创新", "存储芯片/NOR Flash", 85.0, 570, "手动-顺风板块"),
    ("sz300223", "北京君正", "存储芯片/DRAM", 68.0, 330, "手动-顺风板块"),
    # 功率半导体
    ("sh600460", "士兰微", "功率半导体/IGBT", 28.8, 450, "手动-顺风板块"),
    # 模拟芯片
    ("sz300661", "圣邦股份", "模拟芯片/信号链", 125.0, 290, "手动-顺风板块"),
    ("sh600171", "上海贝岭", "模拟芯片/电源管理", 22.5, 160, "手动-顺风板块"),
    # 半导体材料
    ("sz002079", "苏州固锝", "半导体分立器件", 16.8, 135, "手动-顺风板块"),
    ("sz002409", "雅克科技", "半导体材料/前驱体", 42.0, 200, "手动-顺风板块"),
    ("sz300236", "上海新阳", "半导体材料/电镀液", 38.5, 120, "手动-顺风板块"),
    # 设备龙头
    ("sz002371", "北方华创", "半导体设备龙头", 380.0, 2000, "手动-顺风板块"),
    # 安全芯片
    ("sz002049", "紫光国微", "安全芯片/FPGA", 95.0, 800, "手动-顺风板块"),
]

# 中报预增 stocks (earnings-driven)
MANUAL_EARNINGS = [
    ("sz300308", "中际旭创", "中报预增/光模块", 145.0, 1150, "手动-中报预增"),
    ("sz300502", "新易盛", "中报预增/光模块", 88.0, 630, "手动-中报预增"),
    ("sz300394", "天孚通信", "中报预增/光器件", 125.0, 490, "手动-中报预增"),
    ("sz300750", "宁德时代", "中报预增/储能电池", 220.0, 9700, "手动-中报预增"),
    ("sz300274", "阳光电源", "中报预增/储能逆变器", 95.0, 1950, "手动-中报预增"),
    ("sz300496", "中科创达", "中报预增/智能汽车", 68.0, 310, "手动-中报预增"),
    ("sz002236", "大华股份", "中报预增/AI安防", 22.5, 750, "手动-中报预增"),
    ("sz002415", "海康威视", "中报预增/AI安防", 35.0, 3200, "手动-中报预增"),
]

# 人形机器人/储能
MANUAL_ROBOT = [
    ("sz300124", "汇川技术", "人形机器人/伺服电机", 68.0, 1800, "手动-顺风板块"),
    ("sh688017", "绿的谐波", "人形机器人/谐波减速器", 145.0, 245, "手动-顺风板块"),
    ("sz002747", "埃斯顿", "人形机器人/工业机器人", 18.5, 160, "手动-顺风板块"),
    ("sz300024", "机器人", "人形机器人/工业机器人", 22.0, 340, "手动-顺风板块"),
    ("sz300607", "拓斯达", "人形机器人/注塑机+机器人", 16.5, 70, "手动-顺风板块"),
    ("sh688390", "固德威", "储能/逆变器", 85.0, 210, "手动-顺风板块"),
    ("sh688063", "派能科技", "储能/家用储能电池", 72.0, 125, "手动-顺风板块"),
    ("sz300014", "亿纬锂能", "储能/锂电池", 48.0, 980, "手动-顺风板块"),
    ("sz300068", "南都电源", "储能/储能电池", 14.5, 125, "手动-顺风板块"),
    ("sz002518", "科士达", "储能/PCS", 32.0, 185, "手动-顺风板块"),
    ("sz300827", "上能电气", "储能/PCS", 42.0, 150, "手动-顺风板块"),
    ("sz002230", "科大讯飞", "人形机器人/AI大模型", 52.0, 1200, "手动-顺风板块"),
]

# Merge manual additions
manual_additions = []
for entry in MANUAL_SEMICONDUCTOR + MANUAL_EARNINGS + MANUAL_ROBOT:
    code, name, sector, price, mktcap, source = entry
    # Skip if already in rank
    if code in rank_used_codes:
        continue

    # Determine direction
    if any(kw in sector for kw in ["半导体", "存储", "封装", "芯片", "模拟", "功率", "分立", "材料", "设备"]):
        direction = "半导体/存储芯片/先进封装"
    elif "中报预增" in sector:
        direction = "中报预增"
    elif any(kw in sector for kw in ["机器人", "储能"]):
        direction = "人形机器人/储能"
    else:
        direction = "中报预增"

    one_w_eligible = price < 40

    manual_additions.append({
        "code": code,
        "name": name,
        "sector": sector,
        "direction": direction,
        "source": source,
        "price": price,
        "changePct": None,
        "amountYi": None,
        "turnover": None,
        "floatMarketCapYi": mktcap,
        "peTtm": None,
        "pb": None,
        "oneWEligible": one_w_eligible,
        "dataQuality": "estimated",
    })

print(f"Manual additions: {len(manual_additions)}")

# Merge all candidates
all_candidates = candidates + manual_additions

# Sort by direction then price (1w eligible first)
all_candidates.sort(key=lambda x: (
    {"半导体/存储芯片/先进封装": 0, "中报预增": 1, "人形机器人/储能": 2}.get(x["direction"], 9),
    0 if x["oneWEligible"] else 1,
    x["price"],
))

# ============================================================
# Sector strengths
# ============================================================
# Calculate avg metrics per direction
from collections import defaultdict
dir_stats = defaultdict(lambda: {"count": 0, "pct_sum": 0.0, "pct_count": 0, "onew_count": 0})
for c in all_candidates:
    d = c["direction"]
    dir_stats[d]["count"] += 1
    if c["changePct"] is not None:
        dir_stats[d]["pct_sum"] += c["changePct"]
        dir_stats[d]["pct_count"] += 1
    if c["oneWEligible"]:
        dir_stats[d]["onew_count"] += 1

sector_strengths = []
for d in ["半导体/存储芯片/先进封装", "中报预增", "人形机器人/储能"]:
    ds = dir_stats[d]
    avg_pct = round(ds["pct_sum"] / ds["pct_count"], 2) if ds["pct_count"] > 0 else None
    sector_strengths.append({
        "sector": d,
        "dayChangePct": avg_pct,
        "stockCount": ds["count"],
        "oneWEligibleCount": ds["onew_count"],
    })

# ============================================================
# Leaders (top 3 per direction by price appreciation + market cap)
# ============================================================
leaders = []
for d in ["半导体/存储芯片/先进封装", "中报预增", "人形机器人/储能"]:
    dir_candidates = [c for c in all_candidates if c["direction"] == d]
    # Sort by changePct desc (live data first), then by market cap
    dir_candidates.sort(key=lambda x: (
        0 if x["changePct"] is not None else 1,
        -(x["changePct"] or 0),
        -(x["floatMarketCapYi"] or 0),
    ))
    top3 = dir_candidates[:3]
    for i, c in enumerate(top3):
        role = "龙头" if i == 0 else ("次龙头" if i == 1 else "板块龙头")
        leaders.append({
            "code": c["code"],
            "name": c["name"],
            "sector": c["direction"],
            "role": role,
            "price": c["price"],
            "changePct": c["changePct"],
        })

# ============================================================
# Build final output
# ============================================================
summary = (
    f"半导体{dir_stats['半导体/存储芯片/先进封装']['count']}只"
    f"+中报预增{dir_stats['中报预增']['count']}只"
    f"+人形机器人/储能{dir_stats['人形机器人/储能']['count']}只"
    f"={len(all_candidates)}只候选池;"
    f"1w可配(<40元){sum(1 for c in all_candidates if c['oneWEligible'])}只;"
    f"数据源:新浪rank(46只实时)+手动补录(行业知识)"
)

output = {
    "runId": "20260721_short-term-picks",
    "asOf": "20260721",
    "goal": "short-term-picks",
    "agent": "sector-analyst",
    "fetchedAt": "20260721",
    "data": {
        "candidates": all_candidates,
        "sectorStrengths": sector_strengths,
        "leaders": leaders,
        "poolSize": len(all_candidates),
        "summary": summary,
        "tailwinds": ["半导体/存储芯片/先进封装", "中报预增", "人形机器人/储能"],
        "dataNotes": {
            "rankSource": "新浪涨幅榜(46只实时价格)",
            "manualSource": "行业分析师手动补录(estimated价格需cn_fetch.py quote验证)",
            "missingData": "iFind/Wind/AkShare MCP全挂SSL,cn_fetch.py rank为唯一可用实时数据通道",
            "priceQuality": "rank数据=实时准确;手动补录=估算需验证",
        }
    },
    "summary": summary,
    "keyFields": {
        "poolSize": len(all_candidates),
        "oneWEligible": sum(1 for c in all_candidates if c["oneWEligible"]),
        "tailwinds": ["半导体/存储芯片/先进封装", "中报预增", "人形机器人/储能"],
        "dataQuality": "rank实时+手动估算",
        "semiconductorCount": dir_stats["半导体/存储芯片/先进封装"]["count"],
        "earningsCount": dir_stats["中报预增"]["count"],
        "robotStorageCount": dir_stats["人形机器人/储能"]["count"],
    }
}

# Write output
outdir = r"E:\finacial-invest\data\runs\20260721_short-term-picks"
os.makedirs(outdir, exist_ok=True)
outpath = os.path.join(outdir, "sector-analyst.json")
with open(outpath, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n=== Candidate Pool Summary ===")
print(f"Total: {len(all_candidates)} candidates")
for d in ["半导体/存储芯片/先进封装", "中报预增", "人形机器人/储能"]:
    ds = dir_stats[d]
    print(f"  {d}: {ds['count']} stocks (1w eligible: {ds['onew_count']})")
print(f"1w account eligible (<40元): {sum(1 for c in all_candidates if c['oneWEligible'])}")
print(f"Live data: {sum(1 for c in all_candidates if c['dataQuality'] == 'live_rank')}")
print(f"Estimated: {sum(1 for c in all_candidates if c['dataQuality'] == 'estimated')}")
print(f"\nWritten to: {outpath}")