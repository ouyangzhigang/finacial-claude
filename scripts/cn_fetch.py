# -*- coding: utf-8 -*-
"""A股短周期选股取数工具(免密钥,HTTP通道)。
通道: 新浪榜单 + 腾讯K线(-L自动跟随) + 腾讯批量报价(GBK)。
MCP/wind/ifind/akshare 在本环境 SSL 证书失败或无网络,故全走 HTTP。
用法见 main()。
"""
import urllib.request, json, sys, time, ssl

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
_CTX = ssl._create_unverified_context()  # 腾讯302→HTTPS证书在Win缺AKI,放行

def _get(url, encoding='utf-8', timeout=25, retry=3, headers=None):
    h = dict(UA); h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    last = None
    for _ in range(retry):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                return r.read().decode(encoding, 'ignore')
        except Exception as e:
            last = e
            time.sleep(0.7)
    raise last

# ---------- 新浪榜单 ----------
def rank(sort='changepercent', num=80, page=1, node='hs_a'):
    url = (f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"Market_Center.getHQNodeData?page={page}&num={num}&sort={sort}&asc=0&node={node}&_s_r_a=auto")
    return json.loads(_get(url))

# ---------- 腾讯K线(前复权日K) ----------
def kline(symbol, datalen=30):
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{datalen},qfq"
    j = json.loads(_get(url))
    arr = j.get('data', {}).get(symbol, {}).get('qfqday')
    return arr or []

# ---------- 短线因子 ----------
def factors(symbol, n=25):
    arr = kline(symbol, n + 5)
    if not arr or len(arr) < 20:
        return None
    rows = [{'date': x[0], 'open': float(x[1]), 'close': float(x[2]),
             'high': float(x[3]), 'low': float(x[4]), 'vol': float(x[5])} for x in arr]
    closes = [r['close'] for r in rows]
    vols = [r['vol'] for r in rows]
    last = rows[-1]
    def mom(d):
        return (closes[-1] - closes[-1 - d]) / closes[-1 - d] * 100 if len(closes) > d else None
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20
    v5 = sum(vols[-5:]) / 5
    v20 = sum(vols[-20:]) / 20
    breakout = last['close'] > ma20 and last['vol'] > v5 * 1.5
    # 20日均成交额估算: vol(手)*100*close
    amt20 = sum(rows[i]['vol'] * 100 * rows[i]['close'] for i in range(-20, 0)) / 20
    # 近5日累计涨幅(用于排除透支)
    m5 = mom(5)
    return {
        'symbol': symbol, 'last': round(last['close'], 2), 'date': last['date'],
        'm5': round(m5, 2) if m5 is not None else None,
        'm10': round(mom(10), 2) if mom(10) is not None else None,
        'm20': round(mom(20), 2) if mom(20) is not None else None,
        'ma5': round(ma5, 2), 'ma10': round(ma10, 2), 'ma20': round(ma20, 2),
        'v5': round(v5, 0), 'v20': round(v20, 0), 'breakout': breakout,
        'amt20_yi': round(amt20 / 1e8, 2),  # 亿元
        'above_ma20': last['close'] > ma20,
        'above_ma5': last['close'] > ma5,
    }

# ---------- 腾讯批量报价(当日快照,GBK) ----------
def quote(symbols):
    q = ','.join(symbols)
    txt = _get(f"http://qt.gtimg.cn/q={q}", encoding='gbk')
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
                'price': float(m[3]), 'prev': float(m[4]), 'open': float(m[5]),
                'vol_hand': float(m[6]) if m[6] else 0,      # 成交量(手)
                'chg': float(m[31]) if m[31] else 0,          # 涨跌额
                'pct': float(m[32]) if m[32] else 0,          # 涨跌幅%
                'high': float(m[33]) if m[33] else 0,
                'low': float(m[34]) if m[34] else 0,
                'amount_yi': round(float(m[37]) / 1e8, 2) if m[37] else 0,  # 成交额(元->亿)
                'turnover': float(m[38]) if m[38] else 0,     # 换手率%
                'pe_ttm': float(m[39]) if m[39] else 0,
                'mktcap_yi': round(float(m[45]) / 1e8, 2) if m[45] else 0,  # 总市值(元->亿)? 待核
                'float_mktcap_yi': round(float(m[44]) / 1e8, 2) if m[44] else 0,  # 流通市值
                'time': m[30],
            }
        except Exception:
            continue
    return out

# ---------- 新浪sinajs批量报价(成交额单位=元,最准) ----------
def sina_quote(symbols):
    q = ','.join(symbols)
    txt = _get(f"http://hq.sinajs.cn/list={q}", encoding='gbk',
               headers={'Referer': 'https://finance.sina.com.cn/'})
    out = {}
    for line in txt.strip().split('\n'):
        line = line.strip().rstrip(';')
        if '="' not in line:
            continue
        prefix = line.split('="')[0]              # var hq_str_sh600519
        scode = prefix.split('_')[-1]             # sh600519
        body = line.split('="', 1)[1].rstrip('"')
        f = body.split(',')
        if len(f) < 10:
            continue
        try:
            out[scode] = {
                'code': scode, 'name': f[0],
                'open': float(f[1]), 'prev': float(f[2]), 'price': float(f[3]),
                'high': float(f[4]), 'low': float(f[5]),
                'vol_hand': float(f[8]) if f[8] else 0,      # 成交量(手)
                'amount_yuan': float(f[9]) if f[9] else 0,   # 成交额(元)
                'date': f[30] if len(f) > 30 else '', 'time': f[31] if len(f) > 31 else '',
            }
        except Exception:
            continue
    return out

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'
    sys.stdout.reconfigure(encoding='utf-8')
    if cmd == 'rank':
        sort = sys.argv[2] if len(sys.argv) > 2 else 'changepercent'
        num = int(sys.argv[3]) if len(sys.argv) > 3 else 80
        d = rank(sort, num)
        for x in d:
            s = x['symbol']
            if s.startswith('bj'):
                continue
            n = x['name']
            if 'ST' in n or '退' in n:
                continue
            try:
                pe = float(x.get('per') or 0)
            except Exception:
                pe = 0
            print(f"{s}\t{n}\t{float(x['trade']):.2f}\t{float(x['changepercent']):.2f}\t"
                  f"{float(x['amount'])/1e8:.2f}\t{float(x['turnoverratio']):.2f}\t"
                  f"{float(x['nmc'])/1e4:.1f}\t{pe:.1f}\t{float(x.get('pb') or 0):.2f}")
    elif cmd == 'factors':
        for sym in sys.argv[2:]:
            f = factors(sym)
            if f:
                print(json.dumps(f, ensure_ascii=False))
            else:
                print(f"{sym}\t数据缺失")
    elif cmd == 'quote':
        syms = sys.argv[2].split(',')
        out = quote(syms)
        print(json.dumps(out, ensure_ascii=False, indent=1))
    elif cmd == 'kline':
        sym = sys.argv[2]
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        print(json.dumps(kline(sym, n), ensure_ascii=False))
    elif cmd == 'squote':
        syms = sys.argv[2].split(',')
        print(json.dumps(sina_quote(syms), ensure_ascii=False, indent=1))
    else:
        print('用法: rank [sort] [num] | factors sym1 sym2 ... | quote sym1,sym2 | kline sym [n]')

if __name__ == '__main__':
    main()
