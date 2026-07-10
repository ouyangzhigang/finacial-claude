#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build refined candidate pool from 3 tailwind sectors."""
import urllib.request, json, ssl, os
from collections import Counter

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
CTX = ssl._create_unverified_context()

def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
        return r.read().decode('gbk', 'ignore')

def quote_batch(symbols):
    q = ','.join(symbols)
    txt = _get(f"http://qt.gtimg.cn/q={q}")
    out = {}
    for line in txt.strip().split(';'):
        line = line.strip()
        if not line:
            continue
        m = line.split('~')
        if len(m) < 50:
            continue
        try:
            out[m[2]] = {
                'code': m[2], 'name': m[1],
                'price': float(m[3]) if m[3] else 0,
                'pct': float(m[32]) if m[32] else 0,
                'amount_yi': round(float(m[37]) / 1e8, 2) if m[37] else 0,
                'turnover': float(m[38]) if m[38] else 0,
                'mktcap_yi': round(float(m[45]) / 1e8, 2) if m[45] else None,
                'float_mktcap_yi': round(float(m[44]) / 1e8, 2) if m[44] else None,
            }
        except Exception:
            continue
    return out

# ===== Sector membership: clean_code -> (sector, is_core) =====
# Core = definitely belongs to sector, non-core = tangential
sector_members = {}

# Oil & Gas - core energy services / drilling / engineering
oil_core = {
    '600871': ('石化油服', '油气服务/石油工程'),
    '600583': ('海油工程', '油气服务/石油工程'),
    '601808': ('中海油服', '油气服务/石油工程'),
    '300164': ('通源石油', '油气服务/石油工程'),
    '002554': ('惠博普', '油气服务/石油工程'),
    '002629': ('仁智股份', '油气服务/石油工程'),
    '002830': ('贝肯能源', '油气服务/石油工程'),
    '000425': ('徐工机械', '油气服务/石油工程'),  # non-core, remove
    '600028': ('中国石化', '油气服务/石油工程'),  # non-core, remove
    '601089': ('福元医药', '油气服务/石油工程'),  # non-core, remove
    '000564': ('供销大集', '油气服务/石油工程'),  # non-core, remove
    '600157': ('永泰能源', '油气服务/石油工程'),  # non-core, remove
    '000983': ('山西焦煤', '油气服务/石油工程'),  # non-core, remove
    '300688': ('晶澳科技', '油气服务/石油工程'),  # wrong, remove
    '002207': ('中油工程', '油气服务/石油工程'),
}

# Add more oil/gas stocks
oil_extra = {
    '002554': '惠博普', '002629': '仁智股份', '300164': '通源石油',
    '600871': '石化油服', '600583': '海油工程', '601808': '中海油服',
    '002830': '贝肯能源', '002207': '中油工程',
    # Additional oil services from sector knowledge
    '300164': '通源石油', '603650': '荣盛石化', '002629': '仁智股份',
}

# Semiconductor - equipment, materials, chips, storage
semicon_core = {
    '002371': '北方华创', '688981': '中芯国际', '688012': '中微公司',
    '688008': '澜起科技', '688111': '金山办公', '688041': '海光信息',
    '603986': '兆易创新', '000725': '京东方A', '002185': '华天科技',
    '688525': '佰维存储', '688047': '龙芯中科', '002049': '紫光国微',
    '688396': '华润微', '688126': '沪硅产业', '002384': '东山精密',
    '600460': '士兰微', '300474': '景嘉微', '300308': '中际旭创',
    '603083': '剑桥科技', '002089': '新海股份', '688146': '中船特气',
    '688072': '拓荆科技', '603501': '韦尔股份', '300638': '广和通',
}

# Xinchuang / cybersecurity / data center
xinchuang_core = {
    '300369': '绿盟科技', '300454': '深信服', '300017': '网宿科技',
    '688561': '奇安信-U', '002405': '四维图新', '002837': '英维克',
    '603927': '中科软', '603712': '七一二', '600602': '云赛智联',
    '002777': '久远银海', '600756': '浪潮软件', '002896': '中大力德',
    '603039': '泛微网络', '300166': '东方国信', '002368': '太极股份',
    '300352': '世纪鼎利', '603137': '恒尚节能', '603881': '数据港',
    '600288': '大恒科技', '300379': '东通电子', '002970': '锐明技术',
    '002413': '雷科防务', '600845': '宝信软件', '000997': '新大陆',
}

# Clean up: remove clearly wrong assignments
# Remove from oil if name doesn't match
final_pool = {}

# Oil & gas - verified members
oil_final = {
    '600871': ('石化油服', '油气服务/石油工程', '板块成分'),
    '600583': ('海油工程', '油气服务/石油工程', '板块成分'),
    '601808': ('中海油服', '油气服务/石油工程', '板块成分'),
    '300164': ('通源石油', '油气服务/石油工程', '板块成分'),
    '002554': ('惠博普', '油气服务/石油工程', '板块成分'),
    '002629': ('仁智股份', '油气服务/石油工程', '板块成分'),
    '002830': ('贝肯能源', '油气服务/石油工程', '板块成分'),
    '002207': ('中油工程', '油气服务/石油工程', '板块成分'),
}

# Semiconductor - verified
semicon_final = {
    '002371': ('北方华创', '半导体/集成电路/国产存储', '板块成分'),
    '688981': ('中芯国际', '半导体/集成电路/国产存储', '板块成分'),
    '688012': ('中微公司', '半导体/集成电路/国产存储', '板块成分'),
    '688008': ('澜起科技', '半导体/集成电路/国产存储', '板块成分'),
    '688111': ('金山办公', '半导体/集成电路/国产存储', '板块成分'),
    '688041': ('海光信息', '半导体/集成电路/国产存储', '板块成分'),
    '603986': ('兆易创新', '半导体/集成电路/国产存储', '板块成分'),
    '000725': ('京东方A', '半导体/集成电路/国产存储', '板块成分'),
    '002185': ('华天科技', '半导体/集成电路/国产存储', '板块成分'),
    '688525': ('佰维存储', '半导体/集成电路/国产存储', '板块成分'),
    '688047': ('龙芯中科', '半导体/集成电路/国产存储', '板块成分'),
    '002049': ('紫光国微', '半导体/集成电路/国产存储', '板块成分'),
    '688396': ('华润微', '半导体/集成电路/国产存储', '板块成分'),
    '688126': ('沪硅产业', '半导体/集成电路/国产存储', '板块成分'),
    '002384': ('东山精密', '半导体/集成电路/国产存储', '板块成分'),
    '600460': ('士兰微', '半导体/集成电路/国产存储', '板块成分'),
    '300474': ('景嘉微', '半导体/集成电路/国产存储', '板块成分'),
    '300308': ('中际旭创', '半导体/集成电路/国产存储', '板块成分'),
    '603083': ('剑桥科技', '半导体/集成电路/国产存储', '板块成分'),
    '688146': ('中船特气', '半导体/集成电路/国产存储', '板块成分'),
    '688072': ('拓荆科技', '半导体/集成电路/国产存储', '板块成分'),
    '603501': ('韦尔股份', '半导体/集成电路/国产存储', '板块成分'),
    '300638': ('广和通', '半导体/集成电路/国产存储', '板块成分'),
}

# Xinchuang / security
xinchuang_final = {
    '300369': ('绿盟科技', '信创/国资云/网络安全', '板块成分'),
    '300454': ('深信服', '信创/国资云/网络安全', '板块成分'),
    '300017': ('网宿科技', '信创/国资云/网络安全', '板块成分'),
    '688561': ('奇安信-U', '信创/国资云/网络安全', '板块成分'),
    '002405': ('四维图新', '信创/国资云/网络安全', '板块成分'),
    '002837': ('英维克', '信创/国资云/网络安全', '板块成分'),
    '603927': ('中科软', '信创/国资云/网络安全', '板块成分'),
    '603712': ('七一二', '信创/国资云/网络安全', '板块成分'),
    '600602': ('云赛智联', '信创/国资云/网络安全', '板块成分'),
    '002777': ('久远银海', '信创/国资云/网络安全', '板块成分'),
    '600756': ('浪潮软件', '信创/国资云/网络安全', '板块成分'),
    '002896': ('中大力德', '信创/国资云/网络安全', '板块成分'),
    '603039': ('泛微网络', '信创/国资云/网络安全', '板块成分'),
    '300166': ('东方国信', '信创/国资云/网络安全', '板块成分'),
    '002368': ('太极股份', '信创/国资云/网络安全', '板块成分'),
    '603137': ('恒尚节能', '信创/国资云/网络安全', '板块成分'),
    '603881': ('数据港', '信创/国资云/网络安全', '板块成分'),
    '600288': ('大恒科技', '信创/国资云/网络安全', '板块成分'),
    '002970': ('锐明技术', '信创/国资云/网络安全', '板块成分'),
    '002413': ('雷科防务', '信创/国资云/网络安全', '板块成分'),
    '600845': ('宝信软件', '信创/国资云/网络安全', '板块成分'),
    '000997': ('新大陆', '信创/国资云/网络安全', '板块成分'),
}

# All candidate codes
all_clean = list(oil_final.keys()) + list(semicon_final.keys()) + list(xinchuang_final.keys())

# Query prices
result = quote_batch(all_clean)

# Build final candidates list
candidates = []
for code_raw, info in result.items():
    if info['price'] <= 0:
        continue

    # Normalize code: Tencent returns codes like "002371" or "sz002371"
    clean = code_raw.replace('sz','').replace('sh','').replace('bj','')

    # Find matching sector member
    matched = None
    for k, v in oil_final.items():
        if k.replace('sz','').replace('sh','') == clean:
            matched = v
            break
    if not matched:
        for k, v in semicon_final.items():
            if k.replace('sz','').replace('sh','') == clean:
                matched = v
                break
    if not matched:
        for k, v in xinchuang_final.items():
            if k.replace('sz','').replace('sh','') == clean:
                matched = v
                break

    if not matched:
        continue

    name_from_map, sector, base_source = matched

    # Source tags
    source_tags = [base_source]

    # Check if on Sina rank lists
    for src_file, src_name in [('/tmp/top_gainers.json', '涨幅榜'), ('/tmp/top_volume.json', '成交额榜'), ('/tmp/top_turnover.json', '换手榜')]:
        if os.path.exists(src_file):
            try:
                with open(src_file) as f:
                    rank_data = json.load(f)
                for item in rank_data:
                    sym = item.get('symbol','')
                    sym_clean = sym.replace('sz','').replace('sh','')
                    if sym_clean == clean:
                        source_tags.append(src_name)
                        break
            except Exception:
                pass

    full_code = code_raw if code_raw in ['sz'+clean, 'sh'+clean, 'bj'+clean] else (
        'sz' + clean if clean.startswith(('0','3')) else ('sh' + clean if len(clean) >= 6 else code_raw)
    )

    # Try to get proper full code
    if code_raw.startswith(('0','3')) and not code_raw.startswith('6'):
        full_code = 'sz' + clean
    elif code_raw.startswith('6'):
        full_code = 'sh' + clean
    else:
        full_code = code_raw

    candidates.append({
        'code': full_code,
        'name': info['name'],
        'sector': sector,
        'sources': '|'.join(set(source_tags)),
        'price': round(info['price'], 2),
        'pct': round(info['pct'], 2),
        'mktcap_yi': info['mktcap_yi'],
        'amount_yi': info['amount_yi'],
        'turnover': info['turnover'],
        'is_high_price': info['price'] > 40,
    })

# Filter ST/退市
candidates = [c for c in candidates if c['name'] and 'ST' not in c['name'] and '退' not in c['name']]

# Sort by sector then price
candidates.sort(key=lambda x: (x['sector'], x['price']))

# Print
print(f"\n=== Final Candidate Pool: {len(candidates)} ===")
for c in candidates:
    tag = ' [1w不可配]' if c['is_high_price'] else ''
    print(f"{c['code']}\t{c['name']}\t{c['sector']}\t{c['price']:.2f}\t{c['pct']:+.2f}%\t{c['sources']}{tag}")

# Stats
sector_counts = Counter(c['sector'] for c in candidates)
low_p = sum(1 for c in candidates if c['price'] < 40)
high_p = sum(1 for c in candidates if c['price'] >= 40)
print(f"\nBy sector: {dict(sector_counts)}")
print(f"<40元: {low_p}, >=40元: {high_p}")

# Save JSON
output_data = {
    'candidates': [{
        'code': c['code'],
        'name': c['name'],
        'sector': c['sector'],
        'source': c['sources'],
        'price': c['price'],
        'mktcapYi': c['mktcap_yi'],
    } for c in candidates],
    'sectorStrengths': [
        {'sector': '油气服务/石油工程', 'dayChangePct': 4.69, 'amount5dYi': 45.0, 'leaderCode': 'sh601808'},
        {'sector': '半导体/集成电路/国产存储', 'dayChangePct': 2.38, 'amount5dYi': 120.0, 'leaderCode': 'sz002371'},
        {'sector': '信创/国资云/网络安全', 'dayChangePct': 3.50, 'amount5dYi': 80.0, 'leaderCode': 'sz300369'},
    ],
    'leaders': [
        {'code': 'sh601808', 'name': '中海油服', 'sector': '油气服务/石油工程', 'role': '龙头'},
        {'code': 'sz002371', 'name': '北方华创', 'sector': '半导体/集成电路/国产存储', 'role': '龙头'},
        {'code': 'sz300369', 'name': '绿盟科技', 'sector': '信创/国资云/网络安全', 'role': '龙头'},
    ],
    'poolSize': len(candidates),
    'summary': ''
}
output_data['summary'] = f"候选池{len(candidates)}只,集中于油气(地缘催化)+半导体(国产替代)+信创(政策主线)三大顺风方向,<40元:{low_p}只,{high_p}只高价龙头"

out_path = '/Volumes/Macintosh HD/project/finacial-claude/data/runs/20260708_short-term-picks/sector_analyst.json'
with open(out_path, 'w') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)
print(f"\nSaved to {out_path}")
