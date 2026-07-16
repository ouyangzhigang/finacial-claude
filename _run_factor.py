#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Wrapper to run factor_engine.py"""
import subprocess, sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(r'E:\finacial-invest')
result = subprocess.run([
    sys.executable, 'scripts/factor_engine.py',
    '--codes', '002241,300433,002273,002600,002456,002952,300735,300607,002698,300024,002294,600196,002202',
    '--data-dir', 'data/runs/YYYYMMDD_short-term-picks',
    '--json', '{"regime":"ranging"}',
    '--output', 'data/runs/YYYYMMDD_short-term-picks/factor_scores.json',
], capture_output=True, text=True, encoding='utf-8')
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
sys.exit(result.returncode)
