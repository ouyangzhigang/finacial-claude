# -*- coding: utf-8 -*-
"""深核: 业绩趋势 + 商誉排雷 (sina财报三表)"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
from astock_data import sina_financial_report

PICKS = ["002407","300319","002805","603386","603078","002579","002134","300285","300037"]

def run():
    out = {}
    for code in PICKS:
        lrb = sina_financial_report(code, "lrb")  # 利润表
        fzb = sina_financial_report(code, "fzb")  # 资产负债表
        # 提取净利润/营收同比趋势
        income = []
        for it in lrb[:6]:
            income.append({
                "报告期": it.get("报告期"),
                "净利润": it.get("净利润"),
                "净利润同比": it.get("净利润同比增长率") or it.get("净利润_同比"),
                "营业收入": it.get("营业收入"),
                "营收同比": it.get("营业收入同比增长率") or it.get("营业收入_同比"),
                "扣非净利润": it.get("扣除非经常性损益后的净利润"),
            })
        bs = []
        for it in fzb[:3]:
            bs.append({
                "报告期": it.get("报告期"),
                "商誉": it.get("商誉"),
                "净资产": it.get("归属于母公司股东权益合计") or it.get("股东权益合计"),
                "应收账款": it.get("应收账款"),
                "总资产": it.get("资产总计"),
                "负债合计": it.get("负债合计"),
            })
        out[code] = {"income": income, "balance": bs}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return out

if __name__ == "__main__":
    run()
