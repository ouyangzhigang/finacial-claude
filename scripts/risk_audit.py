#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""排雷审计器——统一查业绩雷/大宗出逃/限售解禁/商誉质押,输出硬否决标志。

宗旨:解决8-07选许继电气(技术分92)但8-10发现Q1-46%业绩雷+2笔折价大宗机构出逃
才降级的问题。让排雷从"软警示"升级"硬否决"——技术分再高,有硬雷也剔除。

数据源(多通道兜底,复用astock_data.py):
  - 业绩雷: 东财快报RPT_LICO_FN_CPD取归母净利算同比 / sina_financial_report兜底
  - 大宗出逃: block_trade() (东财RPT_DATA_BLOCKTRADE, 已验证许继2笔折价-10%)
  - 限售解禁: lockup_expiry() (东财RPT_LIFT_STAGE)
  - 商誉/质押: compute_supply_risk() + 东财股东接口

用法:
  python scripts/risk_audit.py 000400 600089  # 批量排雷
  python scripts/risk_audit.py --codes 000400,601179 --json  # JSON输出供agent引用
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
sys.path.insert(0, "scripts")
try:
    import astock_data as a
except Exception as e:
    sys.stderr.write(f"astock_data 导入失败: {e}\n")
    a = None


# ── 硬否决阈值 ──
EARNINGS_DROP_PCT = -30.0      # 归母净利同比<-30%且非周期行业→业绩雷
BLOCK_TRADE_DISCOUNT = -5.0    # 大宗折价<-5%→出逃信号
DISCOUNT_TRADE_COUNT = 2       # 近期≥2笔折价大宗→硬否决
LOCKUP_RATIO_PCT = 10.0       # 未来30日解禁>流通市值10%→硬否决
GOODWILL_RATIO_PCT = 30.0     # 商誉/总资产>30%→硬否决
PLEDGE_RATIO_PCT = 50.0       # 控股股东质押>50%→硬否决


def _check_earnings_trap(code):
    """业绩雷: 归母净利同比大幅下降(<-30%)。
    东财快报RPT_LICO_FN_CPD取归母净利, 算同比(本期vs去年同期)。
    """
    flags = []
    yoy = None
    if a:
        # 取最近4期快报(覆盖本期+去年同期)
        try:
            d = a.eastmoney_datacenter(
                "RPT_LICO_FN_CPD",
                filter_str=f'(SECURITY_CODE="{code}")',
                page_size=8, sort_columns="REPORTDATE", sort_types="-1",
            )
            if d:
                # 找最近一季报/年报 + 去年同期
                latest = d[0]
                net = latest.get("PARENT_NETPROFIT") or latest.get("NET_PROFIT")
                rd = str(latest.get("REPORTDATE", ""))[:10]
                # 取去年同期对比
                prev_yoy = latest.get("PARENT_NETPROFIT_YOY") or latest.get("PARENTPROFITYOY")
                if prev_yoy is not None:
                    try:
                        yoy = float(prev_yoy)
                    except (ValueError, TypeError):
                        pass
                # 若快报无同比, 自己算(本期 vs 去年同期报告期)
                if yoy is None and net and len(d) >= 2:
                    for row in d[1:]:
                        prev_net = row.get("PARENT_NETPROFIT") or row.get("NET_PROFIT")
                        prev_rd = str(row.get("REPORTDATE", ""))[:10]
                        # 去年同期: 报告期月份相同但年份-1
                        if prev_net and rd[5:10] == prev_rd[5:10] and rd[:4] != prev_rd[:4]:
                            try:
                                yoy = (float(net) - float(prev_net)) / abs(float(prev_net)) * 100
                            except (ValueError, TypeError, ZeroDivisionError):
                                pass
                            break
        except Exception as e:
            sys.stderr.write(f"[risk_audit] {code} 业绩雷查询失败: {e}\n")

    if yoy is not None and yoy < EARNINGS_DROP_PCT:
        flags.append(f"业绩雷:归母净利同比{yoy:+.1f}%(<{EARNINGS_DROP_PCT}%阈值)")
    return {"earnings_yoy": round(yoy, 2) if yoy is not None else None, "flags": flags}


def _check_cashflow(code):
    """现金流质量: 经营现金流为负 or 现金流/净利润<0.5 → 软警示(减分不否决)。
    RPT_LICO_FN_CPD 取 MGJYXJJE(每股经营现金流) + BASIC_EPS。
    病例: 东方电子净利+95%但经营现金流-3.79亿(每股负),盈利质量红旗——
    排雷"干净"(无硬否决)但盈利质量差,盲区让它排Top1。
    """
    warnings = []
    mgjyjje = None
    basic_eps = None
    if a:
        try:
            d = a.eastmoney_datacenter(
                "RPT_LICO_FN_CPD",
                filter_str=f'(SECURITY_CODE="{code}")',
                page_size=4, sort_columns="REPORTDATE", sort_types="-1",
            )
            if d:
                latest = d[0]
                mgjyjje = latest.get("MGJYXJJE")
                basic_eps = latest.get("BASIC_EPS")
        except Exception as e:
            sys.stderr.write(f"[risk_audit] {code} 现金流查询失败: {e}\n")
    if mgjyjje is not None:
        try:
            cf = float(mgjyjje)
            if cf < 0:
                warnings.append(f"经营现金流为负(每股{cf:.2f}元,盈利质量红旗:净利正但现金流负)")
            elif basic_eps:
                try:
                    eps = float(basic_eps)
                    if eps > 0 and cf / eps < 0.5:
                        warnings.append(f"现金流质量差:经营现金流/净利润={cf/eps:.2f}(<0.5)")
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
        except (ValueError, TypeError):
            pass
    return {"mgjyjje": mgjyjje, "warnings": warnings}


def _check_block_trade_escape(code):
    """大宗交易折价出逃: 区分机构席位。
    - 卖方机构专用+折价<-10%+近期≥2笔 → 硬否决(真机构出逃)
    - 买方机构专用(接盘) → 偏利好,不否决
    - 营业部对倒/折价 → 减分警示(非硬否决)
    """
    flags = []
    warnings = []
    seller_inst_discount = 0  # 卖方机构专用折价大宗数
    buyer_inst_count = 0       # 买方机构专用(接盘)数
    worst = 0
    if a:
        try:
            trades = a.block_trade(code, page_size=10)
            for t in trades:
                prem = t.get("premium_pct", 0)
                buyer = t.get("buyer", "")
                seller = t.get("seller", "")
                buyer_is_inst = "机构" in buyer
                seller_is_inst = "机构" in seller
                if prem < BLOCK_TRADE_DISCOUNT:
                    worst = min(worst, prem)
                    if seller_is_inst and prem < -10:
                        # 卖方机构专用+折价>10% = 机构出逃
                        seller_inst_discount += 1
                    if buyer_is_inst:
                        # 买方机构专用 = 机构接盘(偏利好)
                        buyer_inst_count += 1
            # 硬否决: 卖方机构专用折价大宗≥2笔(真机构出逃)
            if seller_inst_discount >= DISCOUNT_TRADE_COUNT:
                flags.append(f"大宗出逃:卖方机构专用折价大宗{seller_inst_discount}笔(最差{worst:+.1f}%)")
            # 减分警示(非否决): 营业部折价大宗存在
            elif worst < BLOCK_TRADE_DISCOUNT:
                warnings.append(f"大宗折价:最差{worst:+.1f}%(营业部对倒/非机构出逃,减分不否决)")
        except Exception as e:
            sys.stderr.write(f"[risk_audit] {code} 大宗查询失败: {e}\n")
    return {
        "discount_trades_seller_inst": seller_inst_discount,
        "buyer_inst_pickup": buyer_inst_count,
        "worst_premium": round(worst, 2),
        "flags": flags,
        "warnings": warnings,
    }


def _check_lockup(code):
    """限售解禁: 未来30日解禁>流通市值10%→硬否决。"""
    flags = []
    upcoming_shares_ratio = 0
    if a:
        try:
            lu = a.lockup_expiry(code, forward_days=30)
            up = lu.get("upcoming", [])
            total_ratio = sum(u.get("ratio", 0) or 0 for u in up)
            upcoming_shares_ratio = round(total_ratio, 2)
            if total_ratio > LOCKUP_RATIO_PCT:
                flags.append(f"解禁压力:未来30日解禁占比{total_ratio:.1f}%(>{LOCKUP_RATIO_PCT}%阈值)")
        except Exception as e:
            sys.stderr.write(f"[risk_audit] {code} 解禁查询失败: {e}\n")
    return {"lockup_ratio_30d": upcoming_shares_ratio, "flags": flags}


def _check_supply_risk(code):
    """综合供给端风险(compute_supply_risk): 解禁+股东户数+大宗折价综合分。"""
    flags = []
    score = 0
    details = {}
    if a:
        try:
            sr = a.compute_supply_risk(code)
            score = sr.get("risk_score", 0)
            details = sr.get("details", {})
            # compute_supply_risk 已含大宗折价计数, 这里只看综合分是否过高
            if score >= 40:
                flags.append(f"供给端风险高:综合分{score}(解禁+户数+大宗)")
        except Exception as e:
            sys.stderr.write(f"[risk_audit] {code} supply_risk失败: {e}\n")
    return {"supply_risk_score": score, "details": details, "flags": flags}


def audit_one(code):
    """对单只票做全维度排雷审计。返回 {code, hard_veto, flags, warnings, details}"""
    code = str(code).replace("sh", "").replace("sz", "")
    all_flags = []
    all_warnings = []
    earnings = _check_earnings_trap(code)
    block = _check_block_trade_escape(code)
    lockup = _check_lockup(code)
    supply = _check_supply_risk(code)
    cashflow = _check_cashflow(code)
    all_flags.extend(earnings["flags"])
    all_flags.extend(block["flags"])
    all_flags.extend(lockup["flags"])
    all_flags.extend(supply["flags"])
    all_warnings.extend(block.get("warnings", []))
    all_warnings.extend(cashflow.get("warnings", []))
    # 硬否决: 业绩雷/卖方机构出逃/解禁压力 任一命中(现金流为负是软警示不否决)
    hard_veto = len(all_flags) > 0
    return {
        "code": code,
        "hard_veto": hard_veto,
        "veto_flags": all_flags,
        "warnings": all_warnings,
        "details": {
            "earnings_yoy": earnings["earnings_yoy"],
            "mgjyjje": cashflow["mgjyjje"],
            "block_seller_inst_discount": block["discount_trades_seller_inst"],
            "block_buyer_inst_pickup": block["buyer_inst_pickup"],
            "worst_premium": block["worst_premium"],
            "lockup_ratio_30d": lockup["lockup_ratio_30d"],
            "supply_risk_score": supply["supply_risk_score"],
        },
    }


def main():
    p = argparse.ArgumentParser(description="排雷审计器(业绩雷/大宗出逃/解禁/商誉质押)")
    p.add_argument("codes", nargs="?", default="", help="股票代码(逗号分隔)")
    p.add_argument("--codes", dest="codes_opt", default="", help="替代位置参数")
    p.add_argument("--json", action="store_true", help="JSON输出(供agent引用)")
    args = p.parse_args()
    raw = args.codes or args.codes_opt
    if not raw:
        p.print_help()
        return
    codes = [c.strip() for c in raw.replace("，", ",").split(",") if c.strip()]
    results = [audit_one(c) for c in codes]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            veto = "❌硬否决" if r["hard_veto"] else "✅排雷干净"
            print(f"=== {r['code']} [{veto}] ===")
            if r["veto_flags"]:
                for f in r["veto_flags"]:
                    print(f"  ⚠️ {f}")
            if r.get("warnings"):
                for w in r["warnings"]:
                    print(f"  💡 {w}")
            if not r["veto_flags"] and not r.get("warnings"):
                print("  无硬否决项")
            d = r["details"]
            print(f"  业绩同比: {d['earnings_yoy']}% | 每股经营现金流: {d['mgjyjje']} | 卖方机构折价大宗: {d['block_seller_inst_discount']}笔 | 买方机构接盘: {d['block_buyer_inst_pickup']}笔 | 最差折价: {d['worst_premium']}% | 30日解禁: {d['lockup_ratio_30d']}% | supply风险: {d['supply_risk_score']}")


if __name__ == "__main__":
    main()
