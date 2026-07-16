#!/bin/sh
export PYTHONIOENCODING=utf-8
cd /e/finacial-invest
PY=$(which python 2>/dev/null || which python3 2>/dev/null)
exec $PY scripts/factor_engine.py \
  --codes 002241,300433,002273,002600,002456,002952,300735,300607,002698,300024,002294,600196,002202 \
  --data-dir data/runs/YYYYMMDD_short-term-picks \
  --json '{"regime":"ranging"}' \
  --output data/runs/YYYYMMDD_short-term-picks/factor_scores.json
