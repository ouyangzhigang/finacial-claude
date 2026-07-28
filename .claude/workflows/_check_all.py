import os, re

def check_braces(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
    brace = 0; paren = 0; bracket = 0
    in_single = False; in_double = False; in_template = False
    in_line = False; in_block = False
    i = 0
    while i < len(code):
        ch = code[i]; ch2 = code[i:i+2] if i+1 < len(code) else ''
        if in_line:
            if ch == '\n': in_line = False
            i += 1; continue
        if in_block:
            if ch2 == '*/': in_block = False; i += 2; continue
            i += 1; continue
        if in_single:
            if ch == '\\' and i+1 < len(code): i += 2; continue
            if ch == "'": in_single = False
            i += 1; continue
        if in_double:
            if ch == '\\' and i+1 < len(code): i += 2; continue
            if ch == '"': in_double = False
            i += 1; continue
        if in_template:
            if ch == '\\' and i+1 < len(code): i += 2; continue
            if ch == '`': in_template = False
            i += 1; continue
        if ch == "'" and not in_double and not in_template: in_single = True
        elif ch == '"' and not in_single and not in_template: in_double = True
        elif ch == '`' and not in_single and not in_double: in_template = True
        elif ch2 == '//' and not in_single and not in_double and not in_template: in_line = True; i += 2; continue
        elif ch2 == '/*' and not in_single and not in_double and not in_template: in_block = True; i += 2; continue
        if ch == '{': brace += 1
        if ch == '}': brace -= 1
        if ch == '(': paren += 1
        if ch == ')': paren -= 1
        if ch == '[': bracket += 1
        if ch == ']': bracket -= 1
        i += 1
    ok = brace == 0 and paren == 0 and bracket == 0
    return ok, brace, paren, bracket

for f in sorted(os.listdir('.claude/workflows')):
    if f.endswith('.js') and not f.endswith('.bak'):
        path = '.claude/workflows/' + f
        ok, brace, paren, bracket = check_braces(path)
        status = 'OK' if ok else f'BROKEN (brace={brace} paren={paren} bracket={bracket})'
        print(f'{f}: {status}')

# Quick check for hot-trends governor prompt
print()
with open('.claude/workflows/hot-trends.js', 'r', encoding='utf-8') as f:
    content = f.read()
if '`综合全链写热门板块潜力股报告' in content:
    print('Governor prompt: template literal OK')
if '`⚠️ 只运行命令不调试' in content:
    print('Hard_gate prompt: template literal OK')
if 'const PREFETCH = `' in content:
    print('PREFETCH: template literal OK')
remaining = len(re.findall(r'\+asOf\+', content))
print(f'Remaining +asOf+ patterns: {remaining}')
remaining2 = len(re.findall(r'\+RD\+', content))
print(f'Remaining +RD+ patterns: {remaining2}')