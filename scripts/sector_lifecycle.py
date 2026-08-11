#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""板块生命周期探测器——判断板块在启动期/发酵期/高潮期/退潮期。

宗旨:解决8-07/8-10把"已涨完退潮的电网"误判为"刚发酵接力板块"的病根。
没有板块生命周期判断,缩量+未涨被统一读成"蓄势待涨",实际是"退潮阴跌"。

数据源(复用 market_radar.py):
  - 板块排名: fetch_sector_ranking(concept/industry) → 板块涨跌幅+涨跌家数+成交额
  - 涨停池: fetch_zt_pool → 连板高度(lianban)+所属板块(hybk)+炸板次数(zbc)
  组合: 涨停梯队(龙头连板高度+涨停数)+涨跌家数分化+板块涨幅 → 4阶段判断

四阶段判定(当日信号为主,不依赖历史K线):
  - 启动期: 板块涨幅>2%, 涨停1-3只(龙头首板/2连), 涨>跌
  - 发酵期: 板块涨幅>3%, 涨停3-8只(连板梯队2-4连), 涨多跌少
  - 高潮期: 板块涨幅>4%, 涨停>8只(高连板/一字), 几乎全涨
  - 退潮期: 板块涨幅<1%或跌, 龙头连板断/炸板, 涨少跌多 ← 8-03电网8-07即此阶段

verdict:
  - deployable(启动/发酵期): 跟风flat票判真蓄势,可选
  - leader_only(高潮期): 只选龙头,跟风补涨空间小
  - veto(退潮期): 硬否决,不进候选池(缩量=撤退非蓄势)
  - unclear(数据不足): 降权观察

用法:
  python scripts/sector_lifecycle.py --board 特高压,AIDC,创新药  # 指定板块
  python scripts/sector_lifecycle.py --top 30                     # 自动取前30热门板块
  python scripts/sector_lifecycle.py --board 特高压 --json         # JSON供agent引用
"""
import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
sys.path.insert(0, "scripts")
try:
    import market_radar as mr
except Exception as e:
    sys.stderr.write(f"market_radar 导入失败: {e}\n")
    mr = None


def _normalize(name):
    """板块名归一化(去空格/大小写)用于模糊匹配。"""
    return (name or "").replace(" ", "").replace("概念", "").strip()


def _board_zt_stats(board_name, zt_pool):
    """从涨停池按所属板块分组,取该板块涨停数+最高连板+炸板数。

    涨停池 hybk 字段含板块名(如"特高压,智能电网"),一只票可能属多板块。
    """
    norm_target = _normalize(board_name)
    zt_count = 0
    max_lianban = 0
    zhaban_count = 0  # 炸板次数(开板次数>0且最终封住=炸板回封;这里计 zbc>0)
    leaders = []
    for item in zt_pool:
        hybk = item.get("hybk", "") or ""
        # 板块名包含匹配(涨停池 hybk 可能是 "特高压,智能电网" 多板块串)
        hybk_norm = _normalize(hybk)
        if norm_target and norm_target in hybk_norm:
            zt_count += 1
            lbc = item.get("lianban") or 0
            try:
                lbc_i = int(lbc) if lbc else 0
                if lbc_i > max_lianban:
                    max_lianban = lbc_i
                if lbc_i >= 2:
                    leaders.append({"name": item.get("name", ""), "lianban": lbc_i})
            except (ValueError, TypeError):
                pass
            zbc = item.get("zbc") or 0
            try:
                if int(zbc) > 0:
                    zhaban_count += 1
            except (ValueError, TypeError):
                pass
    leaders.sort(key=lambda x: x["lianban"], reverse=True)
    return {
        "zt_count": zt_count,
        "max_lianban": max_lianban,
        "zhaban_count": zhaban_count,
        "leaders": leaders[:3],  # 前3龙头
    }


def _find_sector_info(board_name, sector_ranking):
    """在板块排名里模糊匹配板块名,返回板块涨跌幅+涨跌家数+成交额。

    东财涨停池 hybk 常被截断到4字(如"汽车零部"实为"汽车零部件"),
    故用双向包含+前4字前缀匹配兜底。
    """
    norm_target = _normalize(board_name)
    if not norm_target:
        return None
    target_prefix = norm_target[:4]  # 截断匹配用
    for s in sector_ranking:
        if not isinstance(s, dict):
            continue
        name = _normalize(s.get("name", ""))
        if not name:
            continue
        if norm_target in name or name in norm_target:
            return s
        # 前缀匹配(hybk截断时):板块名前4字 == hybk前4字
        if target_prefix and name[:4] == target_prefix:
            return s
    return None


def _classify_phase(sector_info, zt_stats):
    """综合板块涨幅+涨停梯队+涨跌家数分化 → 4阶段判断。

    判定逻辑(按优先级):
      退潮期: 板块跌 OR (涨幅<1% AND 涨停≤1 AND 涨≤跌) → 龙头滞涨跟风杀跌
      高潮期: 涨停≥8 AND 涨幅>4 AND 涨远多于跌 → 全板块齐涨到中后排
      发酵期: 涨停3-8 OR max连板2-4 AND 涨幅>2 AND 涨>跌 → 连板梯队跟风跟涨
      启动期: 涨停1-3 AND 涨幅>1 AND 涨>跌 → 龙头首板/2连初动
      unclear: 数据不足(涨停0且板块涨幅小)
    """
    change_pct = None
    up_count = 0
    down_count = 0
    amount = None
    if sector_info:
        try:
            change_pct = float(sector_info.get("changePct") or 0)
        except (ValueError, TypeError):
            change_pct = 0
        up_count = sector_info.get("upCount") or 0
        down_count = sector_info.get("downCount") or 0
        try:
            up_count = float(up_count)
            down_count = float(down_count)
        except (ValueError, TypeError):
            up_count = down_count = 0
        amount = sector_info.get("amount")

    zt_count = zt_stats["zt_count"]
    max_lb = zt_stats["max_lianban"]
    zhaban = zt_stats["zhaban_count"]
    total_ud = up_count + down_count
    up_ratio = up_count / total_ud if total_ud > 0 else 0.5

    phase = "unclear"
    verdict = "unclear"
    reason = ""

    # 退潮期: 板块跌 或 涨幅小+龙头滞涨+涨少跌多
    # (板块涨幅已知时)
    info_missing = change_pct is None
    if (change_pct is not None and change_pct < 0) or (
        change_pct is not None and change_pct < 1.0
        and zt_count <= 1
        and up_ratio < 0.5
    ):
        phase = "退潮期"
        verdict = "veto"
        reason = f"板块涨幅{change_pct:+.2f}%+涨停{zt_count}只+涨跌比{up_ratio:.2f}(涨少跌多)=龙头滞涨跟风杀跌退潮"
    # 高潮期: 涨停≥8 且 涨幅>4 且 涨远多于跌
    elif zt_count >= 8 and change_pct is not None and change_pct > 4 and up_ratio > 0.7:
        phase = "高潮期"
        verdict = "leader_only"
        reason = f"涨停{zt_count}只+板块涨幅{change_pct:+.2f}%+涨跌比{up_ratio:.2f}=全板块齐涨到中后排,跟风补涨空间小只选龙头"
    # 发酵期: 涨停3-8 或 max连板2-4 且 涨幅>2 且 涨>跌
    # (板块涨幅已知)
    elif (3 <= zt_count < 8 or 2 <= max_lb <= 4) and change_pct is not None and change_pct > 2 and up_ratio > 0.5:
        phase = "发酵期"
        verdict = "deployable"
        reason = f"涨停{zt_count}只(连板梯队max{max_lb}连)+板块涨幅{change_pct:+.2f}%+涨多跌少=连板梯队跟风跟涨,跟风flat票真蓄势将补涨"
    # 启动期: 涨停1-3 且 涨幅>1 且 涨>跌
    # (板块涨幅已知)
    elif 1 <= zt_count <= 3 and change_pct is not None and change_pct > 1 and up_ratio > 0.5:
        phase = "启动期"
        verdict = "deployable"
        reason = f"涨停{zt_count}只(龙头初动max{max_lb}连)+板块涨幅{change_pct:+.2f}%+涨多跌少=板块刚启动,龙头首板/2连跟风票flat将补涨"
    # ⬇ 板块涨幅未知(板块排名未匹配到,纯靠涨停池判断)⬇
    # 发酵期(涨停梯队为主): 涨停≥3 或 max连板≥2,板块涨幅未核验
    elif info_missing and (zt_count >= 3 or max_lb >= 2):
        phase = "发酵期"
        verdict = "deployable"
        reason = f"涨停{zt_count}只(连板梯队max{max_lb}连)+板块涨幅未核验=涨停梯队确认发酵,跟风flat票真蓄势将补涨(板块涨幅待核验)"
    # 启动期(涨停梯队为主): 涨停1-2
    elif info_missing and 1 <= zt_count <= 2:
        phase = "启动期"
        verdict = "deployable"
        reason = f"涨停{zt_count}只(max{max_lb}连)+板块涨幅未核验=龙头初动可能启动,跟风票flat待补涨(板块涨幅待核验)"
    else:
        phase = "unclear"
        verdict = "unclear"
        reason = f"涨停{zt_count}只+板块涨幅{change_pct}+涨跌比{up_ratio:.2f}=信号不足无法定性阶段,降权观察"

    # 炸板警示: 有炸板=板块分歧,即使发酵期也降权
    if zhaban > 0 and verdict == "deployable":
        reason += f";⚠️炸板{zhaban}次=板块分歧,降权观察"

    return {
        "phase": phase,
        "verdict": verdict,
        "reason": reason,
        "metrics": {
            "changePct": round(change_pct, 2) if change_pct is not None else None,
            "ztCount": zt_count,
            "maxLianban": max_lb,
            "zhabanCount": zhaban,
            "upCount": up_count,
            "downCount": down_count,
            "upRatio": round(up_ratio, 2),
            "amount": amount,
        },
        "leaders": zt_stats["leaders"],
    }


def audit_board(board_name, sector_ranking, zt_pool):
    """对单板块做生命周期判断。返回 {board, phase, verdict, reason, metrics, leaders}。"""
    sector_info = _find_sector_info(board_name, sector_ranking)
    zt_stats = _board_zt_stats(board_name, zt_pool)
    result = _classify_phase(sector_info, zt_stats)
    result["board"] = board_name
    result["sectorInfoFound"] = sector_info is not None
    return result


def audit_all_from_ztpool(sector_ranking, zt_pool):
    """从涨停池自动聚合所有板块(不依赖输入板块名)。

    涨停池 hybk 字段含涨停票所属板块(如"医疗服务"/"医药商业")。
    按 hybk 分组算每板块涨停数+最高连板+炸板数,再 join 板块排名涨幅。
    优点:不依赖agent猜东财标准板块名,直接从实际涨停票聚合出活跃板块。
    """
    from collections import defaultdict
    grouped = defaultdict(list)
    for item in zt_pool:
        hybk = item.get("hybk", "") or ""
        # hybk 可能被截断(如"汽车零部")或为多板块串,按逗号/空格拆分取每个
        for raw in hybk.replace("，", ",").split(","):
            b = raw.strip()
            if b:
                grouped[b].append(item)
    results = []
    for board_name, items in grouped.items():
        zt_stats = {
            "zt_count": len(items),
            "max_lianban": 0,
            "zhaban_count": 0,
            "leaders": [],
        }
        for it in items:
            lbc = it.get("lianban") or 0
            try:
                lbc_i = int(lbc) if lbc else 0
                if lbc_i > zt_stats["max_lianban"]:
                    zt_stats["max_lianban"] = lbc_i
                if lbc_i >= 2:
                    zt_stats["leaders"].append({"name": it.get("name", ""), "lianban": lbc_i})
            except (ValueError, TypeError):
                pass
            zbc = it.get("zbc") or 0
            try:
                if int(zbc) > 0:
                    zt_stats["zhaban_count"] += 1
            except (ValueError, TypeError):
                pass
        zt_stats["leaders"].sort(key=lambda x: x["lianban"], reverse=True)
        zt_stats["leaders"] = zt_stats["leaders"][:3]
        sector_info = _find_sector_info(board_name, sector_ranking)
        r = _classify_phase(sector_info, zt_stats)
        r["board"] = board_name
        r["sectorInfoFound"] = sector_info is not None
        results.append(r)
    # 按涨停数降序(最活跃板块在前)
    results.sort(key=lambda x: x["metrics"]["ztCount"], reverse=True)
    return results


def main():
    p = argparse.ArgumentParser(description="板块生命周期探测器(启动/发酵/高潮/退潮)")
    p.add_argument("--board", default="", help="板块名(逗号分隔,如 特高压,AIDC,创新药)")
    p.add_argument("--top", type=int, default=0, help="自动取前N热门板块(不指定board时用)")
    p.add_argument("--auto", action="store_true", help="从涨停池自动聚合所有活跃板块(主用法,不依赖输入板块名)")
    p.add_argument("--json", action="store_true", help="JSON输出(供agent引用)")
    args = p.parse_args()

    if not mr:
        print("market_radar 导入失败,无法取数据" if not args.json else
              json.dumps({"_error": "market_radar import failed"}, ensure_ascii=False))
        return

    # 取板块排名(概念+行业) + 涨停池
    sector_ranking = []
    for mtype in ["concept", "industry"]:
        try:
            r = mr.fetch_sector_ranking(mtype, top=80)
            if isinstance(r, list):
                sector_ranking.extend(r)
        except Exception as e:
            sys.stderr.write(f"[sector_lifecycle] {mtype}板块排名取数失败: {e}\n")
    try:
        zt_pool = mr.fetch_zt_pool()
    except Exception as e:
        sys.stderr.write(f"[sector_lifecycle] 涨停池取数失败: {e}\n")
        zt_pool = []

    if not sector_ranking and not zt_pool:
        print("板块排名+涨停池均取数失败" if not args.json else
              json.dumps({"_error": "all data sources failed"}, ensure_ascii=False))
        return

    # 确定要判断的板块列表
    if args.auto:
        # 从涨停池自动聚合所有活跃板块(主用法)
        results = audit_all_from_ztpool(sector_ranking, zt_pool)
    elif args.board:
        boards = [b.strip() for b in args.board.replace("，", ",").split(",") if b.strip()]
        results = [audit_board(b, sector_ranking, zt_pool) for b in boards]
    elif args.top > 0:
        # 取涨幅前N板块自动判断
        ranked = sorted([s for s in sector_ranking if isinstance(s, dict) and s.get("changePct") is not None],
                        key=lambda x: float(x.get("changePct") or 0), reverse=True)
        boards = [s.get("name", "") for s in ranked[:args.top]]
        results = [audit_board(b, sector_ranking, zt_pool) for b in boards]
    else:
        p.print_help()
        return

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            v_map = {"deployable": "✅可部署", "leader_only": "🔶只选龙头", "veto": "❌硬否决(退潮)", "unclear": "⚪降权观察"}
            print(f"=== {r['board']} [{r['phase']}/{v_map.get(r['verdict'],'?')}] ===")
            print(f"  {r['reason']}")
            m = r["metrics"]
            print(f"  涨幅{m['changePct']}% | 涨停{m['ztCount']}只 | 最高{m['maxLianban']}连 | 炸板{m['zhabanCount']} | 涨{m['upCount']}/跌{m['downCount']} | 成交额{m['amount']}")
            if r["leaders"]:
                leads = ", ".join(f"{l['name']}{l['lianban']}连" for l in r["leaders"])
                print(f"  龙头: {leads}")
            print()


if __name__ == "__main__":
    main()
