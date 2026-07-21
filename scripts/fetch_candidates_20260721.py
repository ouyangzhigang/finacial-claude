#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""批量获取候选股行情并构建sector-analyst候选池输出."""
import urllib.request, ssl, json, time, sys, os

ctx = ssl._create_unverified_context()

# 根据宏观tailwinds整理的候选股名单，按方向分组
candidates_raw = {
    # 军工/国防安全 (双确认)
    '军工': [
        ('中航沈飞', '600893'), ('中国重工', '601989'), ('航发动力', '002179'),
        ('华丽家族', '600160'), ('晶升股份', '002413'), ('中电兴发', '300007'),
        ('国睿科技', '300638'), ('长城特钢', '002268'), ('航天长峰', '300123'),
        ('剑桥科技', '300629'), ('中航高科', '600862'), ('中航光电', '002013'),
        ('航天电器', '002025'), ('洪都航空', '600316'), ('成飞集成', '002190'),
        ('陕西金叶', '600721'), ('北方导航', '600435'), ('高德红外', '002414'),
        ('中国卫星', '600118'), ('菲利华', '300395'), ('航天彩虹', '002389'),
        ('振华科技', '000733'), ('紫光国微', '002049'), ('火炬电子', '603678'),
        ('上海瀚讯', '300762'), ('七一二', '603712'), ('新余股份', '002997'),
        ('宗申动力', '001696'), ('安达维尔', '300719'), ('纵横股份', '688070'),
    ],
    # 能源资源(石油/有色/稀土) (双确认)
    '能源资源': [
        ('中国海油', '600938'), ('中曼石油', '603619'), ('杰瑞股份', '002353'),
        ('潜能恒信', '300191'), ('中海油服', '601808'), ('海油工程', '600583'),
        ('恒力石化', '600346'), ('荣盛石化', '002493'), ('宝丰能源', '600989'),
        ('银泰黄金', '600993'), ('中金岭南', '002521'), ('章源钨业', '002378'),
        ('厦门钨业', '600549'), ('五矿稀土', '002756'), ('广晟有色', '600259'),
        ('中国铝业', '601600'), ('云铝股份', '000807'), ('江西铜业', '600362'),
        ('洛阳钼业', '603993'), ('西藏矿业', '000762'), ('南山铝业', '002365'),
        ('华友钴业', '603799'), ('天齐锂业', '002466'), ('赣锋锂业', '002460'),
        ('包钢股份', '600010'), ('盛和资源', '600392'),
    ],
    # 数币/跨境支付 (单确认观察级)
    '数币跨境': [
        ('拉卡拉', '300773'), ('广电运通', '002152'), ('新大陆', '000997'),
        ('楚天龙', '003040'), ('御城文化', '600556'), ('飞天诚信', '300386'),
        ('恒宝股份', '002104'), ('东信和平', '002017'), ('宇信科技', '300674'),
        ('长亮科技', '300348'), ('四方精创', '300468'), ('中科软', '603927'),
        ('高伟达', '300465'), ('翠微股份', '603123'), ('新国都', '300130'),
        ('天喻信息', '300205'), ('京北方', '002987'),
    ],
}

# 去重并构建code->info映射
all_stocks = {}
for direction, stock_list in candidates_raw.items():
    for name, code in stock_list:
        all_stocks[code] = {'name': name, 'direction': direction}

total = len(all_stocks)
print(f'候选池共 {total} 只\n')

# 分批查询腾讯报价API(HTTP非SSL)
codes = list(all_stocks.keys())
batch_size = 30
results = {}
failed_codes = []

for i in range(0, total, batch_size):
    batch = codes[i:i+batch_size]
    symbols = ','.join(['sh'+c if c.startswith(('6','9')) else 'sz'+c for c in batch])
    url = f'http://qt.gtimg.cn/q={symbols}'
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        raw = resp.read().decode('gbk', errors='replace')
        lines = raw.strip().split('\n')
        for line in lines:
            if '=' not in line:
                continue
            idx_eq = line.index('=')
            sym_part = line[:idx_eq].replace('v_', '').strip()
            val = line[idx_eq+1:].strip('" \r\n;').strip('" \r\n;')
            parts = val.split('~')
            if len(parts) >= 44:
                try:
                    s_code = sym_part.lower().replace('sh','').replace('sz','').strip()
                    s_name = parts[1] if parts[1] and parts[1] != '-' else all_stocks.get(s_code, {}).get('name', '?')
                    s_price = float(parts[3]) if parts[3] and parts[3] != '-' else 0
                    s_prev_close = float(parts[4]) if len(parts)>4 and parts[4] and parts[4]!='-' else 0
                    s_open = float(parts[5]) if len(parts)>5 and parts[5] and parts[5]!='-' else 0
                    s_volume = float(parts[6]) if len(parts)>6 and parts[6] and parts[6]!='-' else 0
                    s_high = float(parts[41]) if len(parts)>41 and parts[41] and parts[41]!='-' else 0
                    s_low = float(parts[42]) if len(parts)>42 and parts[42] and parts[42]!='-' else 0
                    s_change_pct = float(parts[32]) if len(parts)>32 and parts[32] and parts[32]!='-' else 0
                    s_turnover = float(parts[38]) if len(parts)>38 and parts[38] and parts[38]!='-' else 0
                    s_pe = float(parts[39]) if len(parts)>39 and parts[39] and parts[39]!='-' else None
                    s_market_cap_yi = float(parts[44]) if len(parts)>44 and parts[44] and parts[44]!='-' else 0
                    s_amount_yi = round(float(parts[37])/10000, 2) if len(parts)>37 and parts[37] and parts[37]!='-' else 0

                    results[s_code] = {
                        'name': s_name,
                        'price': round(s_price, 2),
                        'changePct': round(s_change_pct, 2),
                        'marketCapYi': round(s_market_cap_yi, 1),
                        'amountYi': s_amount_yi,
                        'pe': round(s_pe, 1) if s_pe else None,
                        'turnover': round(s_turnover, 2),
                        'open': round(s_open, 2),
                        'high': round(s_high, 2),
                        'low': round(s_low, 2),
                    }
                except (ValueError, IndexError) as e:
                    print(f'解析失败 {s_code}: {e}')
                    pass
        print(f'批次{i//batch_size+1}/{(total+batch_size-1)//batch_size}: OK ({len(batch)} stocks)')
        time.sleep(0.3)
    except Exception as e:
        print(f'批次{i//batch_size+1}失败: {e}')
        failed_codes.extend(batch)
        time.sleep(0.5)

success_count = len(results)
below_40 = sum(1 for r in results.values() if r['price'] > 0 and r['price'] < 40)
above_40 = sum(1 for r in results.values() if r['price'] >= 40)

print(f'\n=== 汇总 ===')
print(f'成功: {success_count}, 缺失: {total - success_count}, 请求失败: {len(failed_codes)}')
print(f'价格<40元: {below_40}, >=40元: {above_40}')

# 按方向打印详细数据
for direction in ['军工', '能源资源', '数币跨境']:
    dirs = [c for c, v in all_stocks.items() if v['direction'] == direction]
    dir_results = {c: results[c] for c in dirs if c in results}
    print(f'\n[{direction}] ({len(dir_results)}/{len(dirs)} 获取成功):')
    sorted_dirs = sorted(dir_results.items(), key=lambda x: x[1]['price'])
    for code, r in sorted_dirs:
        ref_name = all_stocks[code]['name']
        flag = ' **1w不可配**' if r['price'] >= 40 else ''
        src_label = direction
        print(f"  {ref_name}({code}) 价格:{r['price']} 涨跌:{r['changePct']}% 市值:{r['marketCapYi']}亿 PE:{r['pe']} 换手:{r['turnover']}% 成交额:{r['amountYi']}亿 [{src_label}] {flag}")

# 数据质量检查
print(f'\n=== 数据质量检查 ===')
good_caps = [r for r in results.values() if r['marketCapYi'] > 0]
print(f'有市值数据的股票: {len(good_caps)}/{success_count}')
bad_pe = [c for c,r in results.items() if r['pe'] is not None and r['pe'] < 0]
print(f'负PE(亏损): {len(bad_pe)} 只: {[c for c in bad_pe[:10]]}')

# 统计各方向平均涨跌幅
for direction in ['军工', '能源资源', '数币跨境']:
    dirs_r = [(c,r) for c,r in results.items() if all_stocks.get(c,{}).get('direction')==direction]
    if dirs_r:
        avg_chg = sum(r['changePct'] for _,r in dirs_r)/len(dirs_r)
        valid_pe = [r['pe'] for _,r in dirs_r if r['pe']]
        avg_pe = round(sum(valid_pe)/len(valid_pe), 1) if valid_pe else None
        print(f'{direction}: 均涨跌{avg_chg:.2f}% 均PE{avg_pe or "N/A"}')

# ===== 构建最终JSON输出 =====
output_data = {
    'candidates': [],
    'sectorStrengths': [],
    'leaders': [],
    'poolSize': success_count,
}

for direction in ['军工', '能源资源', '数币跨境']:
    dirs = [c for c, v in all_stocks.items() if v['direction'] == direction]
    dir_results = {c: results[c] for c in dirs if c in results}

    # 板块强度估算
    dir_avg = sum(r['changePct'] for r in dir_results.values())/len(dir_results) if dir_results else 0
    dir_amount = sum(r['amountYi'] for r in dir_results.values())

    output_data['sectorStrengths'].append({
        'sector': direction,
        'dayChangePct': round(dir_avg, 2),
        'amount5dEstYi': round(dir_amount * 5, 1),
        'stockCount': len(dir_results),
    })

    # 龙头识别
    if dir_results:
        sorted_by_mkt = sorted(dir_results.items(), key=lambda x: x[1]['marketCapYi'], reverse=True)
        top_cands = [x[0] for x in sorted_by_mkt if x[1]['marketCapYi'] > 0][:3]
        if not top_cands:
            sorted_by_amt = sorted(dir_results.items(), key=lambda x: x[1]['amountYi'], reverse=True)
            top_cands = [x[0] for x in sorted_by_amt[:3]]

        leader_roles = ['龙头', '次龙头', '三龙']
        for idx, lc in enumerate(top_cands):
            if idx < len(leader_roles):
                output_data['leaders'].append({
                    'code': lc,
                    'name': all_stocks[lc]['name'],
                    'sector': direction,
                    'role': leader_roles[idx],
                })

    # 添加候选池成员
    for code, r in dir_results.items():
        source_tags = [direction]
        if r['changePct'] > 3:
            source_tags.append('强势')
        elif r['changePct'] < -5:
            source_tags.append('回调')
        if r['pe'] and r['pe'] < 20 and r['pe'] > 0:
            source_tags.append('低估')

        entry = {
            'code': code,
            'name': all_stocks[code]['name'],
            'sector': direction,
            'source': '|'.join(source_tags),
            'price': r['price'],
            'marketCapYi': r['marketCapYi'],
            'changePct': r['changePct'],
            'pe': r['pe'],
            'turnover': r['turnover'],
            'amountYi': r['amountYi'],
        }
        output_data['candidates'].append(entry)

# 按价格排序(<40优先)
output_data['candidates'].sort(key=lambda x: x['price'] if x['price'] > 0 else 999)

# 一句话总结
dir_stats = {}
for d in ['军工', '能源资源', '数币跨境']:
    dc = [c for c,v in all_stocks.items() if v['direction']==d]
    dr = len([c for c in dc if c in results])
    pc = [c for c in dc if c in results and results[c]['price'] > 0 and results[c]['price'] < 40]
    ac = [c for c in dc if c in results and results[c]['price'] >= 40]
    ap = round(sum(results[c]['price'] for c in pc)/max(len(pc),1), 2) if pc else 'N/A'
    dir_stats[d] = {'total': dr, 'below40': len(pc), 'above40': len(ac), 'avgPriceBelow40': ap}

summary_parts = []
for d in ['军工', '能源资源', '数币跨境']:
    ds = dir_stats[d]
    p = ds['avgPriceBelow40']
    summary_parts.append(f'{d}{ds["total"]}只({p}元均价)<40')

summary = f'候选池{success_count}只: {"|".join(summary_parts)}; <40元标的{below_40}只满足1w配置, >=40元高价{above_40}只标注"1w不可配"'
output_data['summary'] = summary

# 保存为JSON文件
output_dir = 'E:/finacial-invest/data/runs/20260721_short-term-picks'
output_file = f'{output_dir}/sector-analyst.json'

os.makedirs(output_dir, exist_ok=True)

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print(f'\n已写入: {output_file}')
print(f'候选池规模: {output_data["poolSize"]}')
print(f'方向分布: {json.dumps(dir_stats, ensure_ascii=False)}')
print(f'龙头: {[l["name"]+"("+l["code"]+")"+l["role"] for l in output_data["leaders"]]}')
print(f'总结: {summary}')
