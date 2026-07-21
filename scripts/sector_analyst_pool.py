"""
sector-analyst-pool v3
Generate >=30 stock candidates for short-term picks.
Date: 2026-07-20 (YYYYMMDD=20260720)
Data source: East Money push2 HTTP-only (bypasses Whistle HTTPS proxy)
Output: data/runs/20260720_short-term-picks/sector-analyst.json
"""
import json, sys, os
# Disable system proxy (Whistle intercepts all outbound connections on this machine)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

from urllib.request import urlopen, Request
from urllib.parse import urlencode

# --- Config ---
ASOF = "20260720"
RUN_ID = "20260720_short-term-picks"
OUTPUT_DIR = rf"E:\finacial-invest\data\runs\{RUN_ID}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

THRESHOLD_PRICE_1W = 40  # 1w账户可配股价上限（一手<4000元）

# === Data fetching helpers ===
def em_request(url_str, timeout=15):
    """GET from East Money push2 HTTP (whistle-free). Returns parsed dict."""
    try:
        req = Request(url_str)
        req.add_header("User-Agent", "Mozilla/5.0")
        req.add_header("Referer", "http://quote.eastmoney.com")
        resp = urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except Exception as e:
        print(f"[WARN] em_request failed: {e}", file=sys.stderr)
        return None

def fetch_rank(sort_field, order=1, pn=1, pz=120, extra_fields=""):
    """Fetch ranked A-share list."""
    base = "http://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": pn, "pz": pz, "po": order, "np": 1, "fltt": 2, "invt": 2,
        "fid": f"f{sort_field}",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:90",
        "fields": f"f2,f3,f12,f14,f6,f8,f15,f20,f23,f22,f9,f17{extra_fields}",
    }
    url = f"{base}?{urlencode(params)}"
    result = em_request(url)
    if result and isinstance(result, dict):
        return result.get("data", {}).get("diff") or []
    return []

def fetch_industry_board(pz=80):
    """Fetch industry sector boards with performance data."""
    base = "http://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1, "pz": pz, "po": 0, "np": 1, "fltt": 2, "invt": 2,
        "fid": "f3",
        "fs": "b:M00001",  # b=M00001 for Shenwan/industry boards
        "fields": "f2,f3,f12,f14,f6,f8,f15,f20",
    }
    url = f"{base}?{urlencode(params)}"
    result = em_request(url)
    if result and isinstance(result, dict):
        return result.get("data", {}).get("diff") or []
    return []

def fetch_low_price(sort_field, order=0, pz=120):
    """Fetch low-priced defensive candidates (ascending by price)."""
    return fetch_rank(sort_field, order=order, pz=pz)

# === Field accessors ===
def get_val(row, key):
    """Get numeric field from East Money row."""
    if not isinstance(row, dict):
        return None
    v = row.get(key)
    if v in (None, '-', ''):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

def get_str(row, key):
    """Get string field."""
    if not isinstance(row, dict):
        return ""
    v = row.get(key, "")
    return str(v) if v else ""

def yi(val_yuan):
    """Yuan -> 亿元."""
    if val_yuan and val_yuan > 0:
        return round(val_yuan / 1e8, 1)
    return None

# === Theme definitions ===
THEME_KEYWORDS = {
    "高股息红利": [
        "银行", "保险", "券商", "煤炭", "石油", "石化", "电力", "燃气",
        "高速", "港口", "钢铁", "公路", "水务", "农业", "粮食",
        "消费", "公用", "电信", "通信", "交运", "航运", "仓储", "物流",
    ],
    "中报业绩预增": [
        "电子", "半导体", "芯片", "存储", "光模块", "光伏", "锂电", "新能源",
        "机械", "自动化", "机器人", "医疗", "医药", "生物", "化学", "化工",
        "材料", "软件", "计算机", "通信", "网络", "数据", "科技", "信息",
    ],
    "资源品涨价": [
        "铜", "铝", "金", "银", "铅", "锌", "稀土", "锂", "镍", "铀",
        "油", "气", "煤", "矿", "水泥", "建材", "化肥", "农药", "糖",
        "猪", "养殖", "棉", "纺织", "纸", "包装",
    ],
    "AI算力科技": [
        "人工智能", "AI", "算力", "GPU", "数据中心", "云计算", "大数据",
        "机器学习", "深度学习", "自动驾驶", "无人机", "芯片", "CPU", "FPGA",
        "服务器", "HBM", "封测", "封装", "测试",
    ],
    "消费电子复苏": [
        "手机", "电脑", "笔记", "平板", "耳机", "摄像头", "显示", "面板",
        "屏幕", "触控", "智能穿戴", "手表", "音箱", "音响",
    ],
}

def compute_themes(stock_name):
    """Return list of matching themes."""
    matches = []
    for theme, keywords in THEME_KEYWORDS.items():
        for kw in keywords:
            if kw in stock_name:
                matches.append(theme)
                break
    return matches

# === Candidate management ===
candidates = []      # Deduplicated list
seen_codes = set()   # For deduplication

def add_candidate(c):
    """Add candidate with dedup; returns True if added."""
    code = c["code"]
    if code in seen_codes:
        return False
    seen_codes.add(code)
    candidates.append(c)
    return True

# === Source 1: Market ranking by %change ===
print("[Source 1] Fetching market ranking by %change...", file=sys.stderr)
data_chg = fetch_rank(3, order=1, pz=120)  # f3 descending
if not data_chg:
    print("  [ERROR] Empty data from %change ranking.", file=sys.stderr)
else:
    for row in data_chg[:120]:
        code = get_str(row, "f12")
        name = get_str(row, "f14")
        price = get_val(row, "f2")
        chg = get_val(row, "f3")
        pe = get_val(row, "f15")
        mcap_yi = yi(get_val(row, "f20"))
        amt_yi = round((get_val(row, "f6") or 0) / 1e4, 2)
        turnover = get_val(row, "f8")
        amplitude = get_val(row, "f9")

        if not code or len(code) != 6 or not name:
            continue

        themes = compute_themes(name)

        c = {
            "code": code,
            "name": name,
            "price": price,
            "changePct": chg,
            "pe_ttm": pe,
            "marketCapYi": mcap_yi,
            "amtYi": amt_yi,
            "turnover": turnover,
            "amplitude": amplitude,
            "source": "市场涨幅榜",
            "theme": themes[0] if themes else "综合",
            "themes_hit": themes,
            "is_compatible_1w": bool(price and price < THRESHOLD_PRICE_1W),
        }
        add_candidate(c)

    count = sum(1 for c in candidates if c['source'] == '市场涨幅榜')
    print(f"  Added {count} from ranking", file=sys.stderr)

# === Source 2: Industry board members ===
print("[Source 2] Fetching industry boards...", file=sys.stderr)
industry_data = fetch_industry_board(pz=60)
strong_sectors = []

if industry_data:
    for row in industry_data:
        name = get_str(row, "f14")
        chg = get_val(row, "f3")
        mcap_yi = yi(get_val(row, "f20"))

        if name and chg is not None and chg > 0:
            strong_sectors.append({
                "sector": name,
                "dayChangePct": round(chg, 2),
                "amount5dYi": mcap_yi,
                "leaderCode": get_str(row, "f12"),
            })

    # Pull constituent stocks from top-performing sectors
    for row in industry_data[:10]:
        sector_name = get_str(row, "f14")
        sector_code = get_str(row, "f12")
        chg = get_val(row, "f3")
        if not sector_name or chg is None or chg <= 0:
            continue

        # Fetch constituents of this sector
        sector_url = f"http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=40&po=0&np=1&fltt=2&invt=2&fid=f3&fs=b:{sector_code}&fields=f2,f3,f12,f14,f15,f20,f8"
        result = em_request(sector_url)
        constituents = []
        if result and isinstance(result, dict):
            constituents = result.get("data", {}).get("diff") or []

        for c_row in constituents[:30]:
            code = get_str(c_row, "f12")
            name = get_str(c_row, "f14")
            price = get_val(c_row, "f2")
            if not code or len(code) != 6 or not name:
                continue
            if code in seen_codes:
                continue

            c = {
                "code": code,
                "name": name,
                "price": price,
                "changePct": get_val(c_row, "f3"),
                "pe_ttm": get_val(c_row, "f15"),
                "marketCapYi": yi(get_val(c_row, "f20")),
                "turnover": get_val(c_row, "f8"),
                "source": f"顺风电行业-{sector_name}",
                "theme": "综合",
                "themes_hit": [],
                "is_compatible_1w": bool(price and price < THRESHOLD_PRICE_1W),
            }
            add_candidate(c)

    print(f"  Strong sectors: {len(strong_sectors)}", file=sys.stderr)

# === Source 3: High-amplitude strong momentum stocks ===
print("[Source 3] Fetching strong momentum stocks...", file=sys.stderr)
data_amp = fetch_rank(9, order=1, pz=80)  # f9=振幅 (amplitude)
if data_amp:
    for row in data_amp[:80]:
        code = get_str(row, "f12")
        name = get_str(row, "f14")
        price = get_val(row, "f2")
        chg = get_val(row, "f3")

        if not code or len(code) != 6 or not name:
            continue
        if code in seen_codes:
            continue

        c = {
            "code": code,
            "name": name,
            "price": price,
            "changePct": chg,
            "pe_ttm": get_val(row, "f15"),
            "marketCapYi": yi(get_val(row, "f20")),
            "turnover": get_val(row, "f8"),
            "source": "涨停强势榜",
            "theme": "事件驱动",
            "themes_hit": [],
            "is_compatible_1w": bool(price and price < THRESHOLD_PRICE_1W),
        }
        add_candidate(c)

    print(f"  Total candidates after source 3: {len(candidates)}", file=sys.stderr)

# === Source 4: Low-price defensive stocks ===
print("[Source 4] Fetching low-price defensive stocks...", file=sys.stderr)
data_lp = fetch_low_price(2, order=0, pz=100)  # Ascending by price (f2)
if data_lp:
    for row in data_lp[:100]:
        code = get_str(row, "f12")
        name = get_str(row, "f14")
        price = get_val(row, "f2")
        chg = get_val(row, "f3")
        pe = get_val(row, "f15")
        mcap_yi = yi(get_val(row, "f20"))

        if not code or len(code) != 6 or not name:
            continue
        if code in seen_codes:
            continue

        # Prefer profitable companies; skip extremely high PE for defensive
        if pe is not None and pe > 100:
            continue

        themes = compute_themes(name)
        c = {
            "code": code,
            "name": name,
            "price": price,
            "changePct": chg,
            "pe_ttm": pe,
            "marketCapYi": mcap_yi,
            "turnover": get_val(row, "f8"),
            "source": "低价防守筛选",
            "theme": themes[0] if themes else "防御配置",
            "themes_hit": themes,
            "is_compatible_1w": True,
        }
        add_candidate(c)

    print(f"  Total after source 4: {len(candidates)}", file=sys.stderr)

# === Source 5: High turnover active trading ===
print("[Source 5] Fetching high-turnover stocks...", file=sys.stderr)
data_ht = fetch_rank(8, order=1, pz=60)  # f8=换手率
if data_ht:
    for row in data_ht[:60]:
        code = get_str(row, "f12")
        name = get_str(row, "f14")
        price = get_val(row, "f2")
        chg = get_val(row, "f3")
        turnover = get_val(row, "f8")

        if not code or len(code) != 6 or not name:
            continue
        if code in seen_codes:
            continue

        # Require turnover > 3% for meaningful activity
        if turnover is None or turnover < 3:
            continue

        themes = compute_themes(name)
        c = {
            "code": code,
            "name": name,
            "price": price,
            "changePct": chg,
            "pe_ttm": get_val(row, "f15"),
            "marketCapYi": yi(get_val(row, "f20")),
            "turnover": turnover,
            "source": "高换手活跃榜",
            "theme": themes[0] if themes else "交易活跃",
            "themes_hit": themes,
            "is_compatible_1w": bool(price and price < THRESHOLD_PRICE_1W),
        }
        add_candidate(c)

    print(f"  Total after source 5: {len(candidates)}", file=sys.stderr)

# === Post-processing ===
print("\n[Post-processing]", file=sys.stderr)

# Sort by daily change descending
candidates.sort(key=lambda x: (x.get("changePct") or -99), reverse=True)

# Trim to max 60 if over
pool_size = len(candidates)
if pool_size > 60:
    def score_for_priority(c):
        sc = 0
        src = c["source"]
        if "涨幅榜" in src: sc += 100
        elif "顺风电" in src: sc += 80
        elif "涨停" in src: sc += 90
        elif "高换手" in src: sc += 70
        elif "防守" in src: sc += 60
        else: sc += 50

        chg = c.get("changePct") or 0
        sc += chg * 2
        pe = c.get("pe_ttm")
        if pe and 0 < pe < 30: sc += 10
        mcap = c.get("marketCapYi")
        if mcap and 50 < mcap < 500: sc += 5
        return sc

    candidates.sort(key=score_for_priority, reverse=True)
    candidates = candidates[:60]
    pool_size = 60

# Build leaders from strongest candidates per theme
leaders = []
theme_leaders_seen = set()
for c in candidates:
    theme = c.get("theme")
    if not theme or theme == "综合":
        continue
    if theme in theme_leaders_seen:
        continue
    if c.get("changePct", -99) > 3:
        leaders.append({
            "code": c["code"],
            "name": c["name"],
            "sector": theme,
            "role": "龙头",
        })
        theme_leaders_seen.add(theme)

# Also add overall top performers
for c in candidates[:3]:
    if c["code"] not in theme_leaders_seen:
        leaders.append({
            "code": c["code"],
            "name": c["name"],
            "sector": c.get("theme", "市场领涨"),
            "role": "龙头",
        })

# Compute statistics
n_compat_1w = sum(1 for c in candidates if c.get("is_compatible_1w"))
n_pe_pos = sum(1 for c in candidates if c.get("pe_ttm") and c["pe_ttm"] > 0)
n_high_price = pool_size - n_compat_1w

theme_counts = {}
for c in candidates:
    t = c.get("theme", "未知")
    theme_counts[t] = theme_counts.get(t, 0) + 1

# Format sector strengths
formatted_strengths = []
for ss in strong_sectors[:15]:
    formatted_strengths.append({
        "sector": ss["sector"],
        "dayChangePct": ss["dayChangePct"],
        "amount5dYi": ss["amount5dYi"],
        "leaderCode": ss["leaderCode"],
    })
formatted_strengths.sort(key=lambda x: x["dayChangePct"], reverse=True)

# === Summary text ===
summary_parts = [f"候选池共{pool_size}只:"]
for t, cnt in sorted(theme_counts.items(), key=lambda x: -x[1])[:5]:
    summary_parts.append(f"{t}({cnt}只)")
summary_parts.append(f"{n_compat_1w}只适配1万账户(<{THRESHOLD_PRICE_1W}元)")
summary = "".join(summary_parts)

# === Output JSON ===
output = {
    "runId": RUN_ID,
    "asOf": ASOF,
    "goal": "short-term-picks",
    "agent": "sector-analyst",
    "fetchedAt": ASOF,
    "data": {
        "candidates": candidates,
        "sectorStrengths": formatted_strengths,
        "leaders": leaders,
        "poolSize": pool_size,
        "summary": summary,
    }
}

output_path = os.path.join(OUTPUT_DIR, "sector-analyst.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n[SUCCESS] Wrote {output_path}", file=sys.stderr)
print(f"[INFO] Candidates: {pool_size}, 1w-compatible: {n_compat_1w}, PE-positive: {n_pe_pos}", file=sys.stderr)
print(f"[INFO] Themes: {json.dumps(theme_counts, ensure_ascii=False)}", file=sys.stderr)
print(f"[INFO] Strong sectors: {len(formatted_strengths)}", file=sys.stderr)

# Print top candidates for verification
print("\n--- Top 20 Candidates ---", file=sys.stderr)
for i, c in enumerate(candidates[:20], 1):
    pe_s = f"PE={c['pe_ttm']:.1f}" if c.get('pe_ttm') else "N/A"
    mc_s = f"{c['marketCapYi']}亿" if c.get('marketCapYi') else "N/A"
    compat = "OK" if c.get('is_compatible_1w') else f"HighPrice"
    print(f"  {i:2d}. {c['code']} {c['name']:8s} P={c['price'] or '?'} Chg={c['changePct'] or '-':>6}% {pe_s:>8s} MCap={mc_s:>8s} [{compat}] [{c['source']}] {c['theme']}", file=sys.stderr)

print(f"\n[DONE] Pool generated successfully with {pool_size} candidates.", file=sys.stderr)
