#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
validate_run.py — P1-1: run 目录 companion JSON 契约校验
========================================================
对 data/runs/{runId}/ 各 JSON 校验非空 + key 存在 + code 对齐, 输出 _validation.json 红黄绿。
workflow 量化引擎 phase 后调用, 红则 governor 标"数据不可信"。

verdict:
  red    — 有 missing/empty/parse_fail (数据不可信, governor 应标置信度低)
  yellow — schema_violation (key 不对齐, 因子维度可能死)
  green  — 全 ok

用法:
  python scripts/validate_run.py --run-id 20260728_short-term-picks
"""
import json, os, sys, argparse

# 各 companion JSON 的契约 (P1-1 固化, 改 schema 前先改此 + 下游 parser)
CONTRACTS = {
    'factor_scores.json': {
        'required_top': ['stocks'],
        'required_item': ['symbol', 'composite_score', 'raw_factors'],
    },
    'fundamentals-analyst.json': {
        # 顶层: data.all[] / data.passed[] / data.pass[] / data.allSorted[] 至少一个有票
        'list_keys': ['all', 'passed', 'pass', 'allSorted', 'downgraded', 'vetoed'],
        'required_item': ['code', 'roe', 'peTtm'],  # 扁平结构 (P1-1 固化)
    },
    'capital_scores.json': {
        'min_dict_entries': 1,  # {code: score}
    },
    'sentiment_scores.json': {
        'required_top': ['stocks'],
        'required_item': ['code', 'social_heat'],
    },
    'supply_risk.json': {
        'min_dict_entries': 1,
    },
    'technical-liquidity.json': {
        'list_keys': ['pass', 'allSorted', 'passed', 'all'],
        'required_item': ['code', 'avgAmount20d'],
    },
    'timing_scores.json': {
        'required_top': ['stocks'],
        'required_item': ['code', 'timing_score'],
    },
}


def load(path):
    if not os.path.exists(path):
        return None, 'missing'
    raw = open(path, 'rb').read()
    if not raw.strip():
        return None, 'empty'
    try:
        return json.loads(raw.decode('utf-8', 'ignore')), 'ok'
    except Exception as e:
        return None, f'parse_fail: {e}'


def validate_file(name, spec, data_dir):
    p = os.path.join(data_dir, name)
    data, status = load(p)
    result = {'file': name, 'status': status, 'details': {}}
    if status != 'ok':
        return result  # missing/empty/parse_fail

    d = data.get('data', data) if isinstance(data, dict) else data

    # list_keys 契约: 至少一个 key 是非空 list, 且首项含 required_item
    if spec.get('list_keys'):
        found = None
        for k in spec['list_keys']:
            v = d.get(k) if isinstance(d, dict) else None
            if isinstance(v, list) and v:
                found = k
                break
        if not found:
            result['status'] = 'schema_violation'
            result['details']['reason'] = f'none of {spec["list_keys"]} is non-empty list'
            return result
        for k in spec.get('required_item', []):
            if not isinstance(d[found][0], dict) or k not in d[found][0]:
                result['status'] = 'schema_violation'
                result['details']['missing_item_key'] = k
                result['details']['list_key'] = found
                return result
        result['details']['list_key'] = found
        result['details']['count'] = len(d[found])
        return result

    # required_top 契约: 顶层有该 key, 且其 list 首项含 required_item
    if spec.get('required_top'):
        top_key = spec['required_top'][0]
        if not isinstance(d, dict) or top_key not in d:
            result['status'] = 'schema_violation'
            result['details']['missing_top'] = top_key
            return result
        items = d.get(top_key, [])
        if isinstance(items, list) and items:
            for k in spec.get('required_item', []):
                if not isinstance(items[0], dict) or k not in items[0]:
                    result['status'] = 'schema_violation'
                    result['details']['missing_item_key'] = k
                    return result
        result['details']['count'] = len(items) if isinstance(items, list) else 0

    # min_dict_entries 契约: dict 至少 N 项
    if spec.get('min_dict_entries'):
        n = len(d) if isinstance(d, dict) else 0
        if n < spec['min_dict_entries']:
            result['status'] = 'schema_violation'
            result['details']['reason'] = f'dict entries {n} < {spec["min_dict_entries"]}'
            return result
        result['details']['count'] = n

    return result


def main():
    ap = argparse.ArgumentParser(description='run 目录 companion JSON 契约校验')
    ap.add_argument('--run-id', required=True, help='运行 ID, 如 20260728_short-term-picks')
    args = ap.parse_args()
    data_dir = f'data/runs/{args.run_id}'
    if not os.path.isdir(data_dir):
        print(f'❌ run 目录不存在: {data_dir}', file=sys.stderr)
        sys.exit(1)

    results = [validate_file(name, spec, data_dir) for name, spec in CONTRACTS.items()]
    statuses = [r['status'] for r in results]

    if any(s in ('missing', 'empty', 'parse_fail') for s in statuses):
        verdict = 'red'
    elif any(s == 'schema_violation' for s in statuses):
        verdict = 'yellow'
    else:
        verdict = 'green'

    out = {
        'run_id': args.run_id,
        'verdict': verdict,
        'files': results,
        'summary': f'{verdict}: {sum(1 for s in statuses if s == "ok")}/{len(statuses)} ok',
    }
    out_path = os.path.join(data_dir, '_validation.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f'校验完成 → {out_path}')
    print(f'  整体: {verdict} ({out["summary"]})')
    for r in results:
        print(f'  {r["file"]:30s} {r["status"]:16s} {r.get("details", {})}')


if __name__ == '__main__':
    main()
