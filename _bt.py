# -*- coding: utf-8 -*-
"""2日窗口短线因子回测:站上MA20且close>MA5时,持有2日的胜率/均收/最差单笔。
用法: python _bt.py sz300748 sh600497 ..."""
import sys
sys.path.insert(0, 'scripts')
import cn_fetch as cf

SYMS = sys.argv[1:]
print("符号\t信号数\t2日胜率\t均收%\t最差单笔%\t末价\t最近5信号收益")
for sym in SYMS:
    arr = cf.kline(sym, 80)
    if not arr or len(arr) < 25:
        print(f"{sym}\t数据不足"); continue
    rows = [{'d': x[0], 'c': float(x[2]), 'v': float(x[5])} for x in arr]
    closes = [r['c'] for r in rows]; vols = [r['v'] for r in rows]
    wins = tot = 0; rets = []; recent5 = []
    for i in range(20, len(rows) - 2):
        ma20 = sum(closes[i-20:i]) / 20
        ma5 = sum(closes[i-5:i]) / 5
        v5 = sum(vols[i-5:i]) / 5
        sig = closes[i] > ma20 and closes[i] > ma5  # 站上MA20且在MA5之上
        if sig:
            r = (closes[i+2] / closes[i] - 1) * 100
            rets.append(r); tot += 1
            if r > 0: wins += 1
            recent5.append((rows[i]['d'], round(r, 2)))
    if tot > 0:
        wr = wins/tot*100
        avg = sum(rets)/tot
        worst = min(rets)
        last5 = recent5[-5:]
        print(f"{sym}\t{tot}\t{wr:.1f}\t{avg:.2f}\t{worst:.2f}\t{closes[-1]:.2f}\t{last5}")
    else:
        print(f"{sym}\t0信号\t-\t-\t-\t{closes[-1]:.2f}\t-")
