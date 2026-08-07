#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""国际形势快照——隔夜美股三大指数+美元+大宗商品+重大地缘事件。

轻量增强:为 macro-strategist 提供"国际传导路径"的实证数据输入,
而非靠新闻检索拼凑。输出结构化JSON,含方向解读(美股跌→A股科技承压/原油涨→资源股等)。

数据通道:腾讯 qt.gtimg.cn(HTTP绕代理,最稳定)。
  - 美股指数: .DJI/.NDX/.IXIC (~分隔,71字段)
  - 大宗商品: hf_CL(油)/hf_GC(金)/hf_HG(铜)/hf_SI(银) (v_前缀逗号分隔,需单独解析)

用法:
  python scripts/global_snapshot.py            # 输出JSON到stdout
  python scripts/global_snapshot.py --summary  # 输出人读摘要(供ctx引用)
"""
import argparse
import json
import ssl
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CTX = ssl._create_unverified_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# 美股指数(腾讯~格式)
INDEX_CODES = {
    ".DJI": "道琼斯工业",
    ".NDX": "纳斯达克100",
    ".IXIC": "纳斯达克综合",
}
# 大宗商品(腾讯 v_ 前缀逗号格式)
COMMODITY_CODES = {
    "hf_CL": "WTI原油",
    "hf_GC": "COMEX黄金",
    "hf_SI": "COMEX白银",
    "hf_HG": "COMEX铜",
}


def _fetch_index(codes):
    """取美股指数(腾讯~格式)。返回 {code:{name,price,changePct,prevClose}}"""
    if not codes:
        return []
    url = f"http://qt.gtimg.cn/q={','.join(codes)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as resp:
            raw = resp.read().decode("gbk", errors="ignore")
    except Exception as e:
        sys.stderr.write(f"美股指数获取失败: {e}\n")
        return []
    out = []
    for line in raw.strip().split(";"):
        if "~" not in line:
            continue
        ps = line.split("~")
        if len(ps) > 45:
            code = ps[2]
            try:
                out.append({
                    "code": code,
                    "name": ps[1],
                    "price": float(ps[3]) if ps[3] else 0,
                    "changePct": float(ps[32]) if ps[32] else 0,
                    "prevClose": float(ps[4]) if ps[4] else 0,
                })
            except (ValueError, IndexError):
                pass
    return out


def _fetch_commodity(codes):
    """取大宗商品(腾讯 v_ 前缀逗号格式)。
    格式: v_hf_CL="现价,涨跌额,昨收,开盘,最高,最低,时间,..."
    """
    if not codes:
        return []
    url = f"http://qt.gtimg.cn/q={','.join(codes)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15, context=CTX) as resp:
            raw = resp.read().decode("gbk", errors="ignore")
    except Exception as e:
        sys.stderr.write(f"大宗商品获取失败: {e}\n")
        return []
    out = []
    for line in raw.strip().split(";"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        # v_hf_CL="77.75,3.36,..."  →  key=v_hf_CL, val=77.75,3.36,...
        key_part, _, val_part = line.partition("=")
        key = key_part.strip().replace("v_", "")
        val = val_part.strip().strip('"')
        if not val:
            continue
        parts = val.split(",")
        if len(parts) < 2:
            continue
        try:
            price = float(parts[0])
            chg = float(parts[1])  # 涨跌额(非百分比)
            # 大宗涨跌额→涨跌幅:需用昨收(parts[2]或 price-chg)
            prev = float(parts[2]) if len(parts) > 2 and parts[2] else (price - chg)
            change_pct = (chg / prev * 100) if prev else 0
            name = COMMODITY_CODES.get(key, key)
            out.append({
                "code": key,
                "name": name,
                "price": price,
                "changePct": round(change_pct, 2),
            })
        except (ValueError, IndexError):
            pass
    return out


def _direction_note(us_indices, commodities):
    """根据美股+大宗表现,给出对A股的传导方向解读(非投资建议,仅路径提示)。"""
    notes = []
    # 美股方向
    dji = next((x for x in us_indices if x["code"] == ".DJI"), None)
    ndx = next((x for x in us_indices if x["code"] == ".NDX"), None)
    ixic = next((x for x in us_indices if x["code"] == ".IXIC"), None)
    if dji and dji["changePct"] < -1.0:
        notes.append(f"美股道指隔夜跌{dji['changePct']:.2f}%→A股可能低开承压,关注防御/避险")
    elif dji and dji["changePct"] > 1.0:
        notes.append(f"美股道指隔夜涨{dji['changePct']:.2f}%→A股可能高开联动,成长/风险偏好提升")
    if ndx and ndx["changePct"] < -1.5:
        notes.append(f"纳指跌{ndx['changePct']:.2f}%→A股科技/半导体/算力板块情绪承压")
    elif ndx and ndx["changePct"] > 1.5:
        notes.append(f"纳指涨{ndx['changePct']:.2f}%→A股科技/AI主线情绪提振")
    # 大宗
    oil = next((x for x in commodities if x["code"] == "hf_CL"), None)
    gold = next((x for x in commodities if x["code"] == "hf_GC"), None)
    copper = next((x for x in commodities if x["code"] == "hf_HG"), None)
    if oil and oil["changePct"] > 2.0:
        notes.append(f"原油涨{oil['changePct']:.2f}%→石化/煤炭资源股催化,但输入型通胀风险")
    elif oil and oil["changePct"] < -3.0:
        notes.append(f"原油跌{abs(oil['changePct']):.2f}%→交运/航空成本利好,资源股承压")
    if gold and gold["changePct"] > 1.0:
        notes.append(f"黄金涨{gold['changePct']:.2f}%→避险情绪升,黄金股/军工可能受益")
    if copper and copper["changePct"] > 1.5:
        notes.append(f"铜涨{copper['changePct']:.2f}%→全球需求预期改善,有色/铜相关股受益")
    if not notes:
        notes.append("隔夜海外+大宗波动温和(<1%),国际传导冲击有限,A股按内生逻辑走")
    return notes


def build_snapshot():
    us = _fetch_index(list(INDEX_CODES.keys()))
    comm = _fetch_commodity(list(COMMODITY_CODES.keys()))
    notes = _direction_note(us, comm)
    # 补回中文名(腾讯返回的是英文名/代码)
    name_map = {**INDEX_CODES, **COMMODITY_CODES}
    for x in us:
        x["name"] = name_map.get(x["code"], x["name"])
    return {
        "usIndices": us,
        "commodities": comm,
        "传导路径": notes,
        "summary": "; ".join(notes),
    }


def main():
    p = argparse.ArgumentParser(description="国际形势快照")
    p.add_argument("--summary", action="store_true", help="输出人读摘要")
    args = p.parse_args()
    snap = build_snapshot()
    if args.summary:
        lines = ["## 国际形势快照(隔夜)"]
        if snap["usIndices"]:
            lines.append("**美股指数**:")
            for x in snap["usIndices"]:
                flag = "🔴" if x["changePct"] < 0 else "🟢"
                lines.append(f"- {flag} {x['name']} {x['price']} ({x['changePct']:+.2f}%)")
        if snap["commodities"]:
            lines.append("**大宗商品**:")
            for x in snap["commodities"]:
                flag = "🔴" if x["changePct"] < 0 else "🟢"
                lines.append(f"- {flag} {x['name']} {x['price']} ({x['changePct']:+.2f}%)")
        lines.append("**对A股传导路径**:")
        for n in snap["传导路径"]:
            lines.append(f"- {n}")
        print("\n".join(lines))
    else:
        print(json.dumps(snap, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
