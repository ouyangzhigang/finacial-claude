@echo off
set PYTHONIOENCODING=utf-8
cd /d E:\finacial-invest
python scripts\factor_engine.py --codes 002241,300433,002273,002600,002456,002952,300735,300607,002698,300024,002294,600196,002202 --data-dir data\runs\YYYYMMDD_short-term-picks --json "{\"regime\":\"ranging\"}" --output data\runs\YYYYMMDD_short-term-picks\factor_scores.json 2>&1
