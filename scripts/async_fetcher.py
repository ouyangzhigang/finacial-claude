#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""异步批量数据获取引擎 — 50 并发 ThreadPoolExecutor。

核心能力:
  - 50+ 并发 HTTP 请求(可配置 max_workers)
  - 按域名自动限流(东财系 ≥1s 间隔,其他不限)
  - 内置重试(指数退避,最多 3 次)
  - 支持 GET JSON / GET raw / POST / subprocess 四种任务类型
  - 输出结构化 JSON + 耗时统计

用法(命令行):
  python scripts/async_fetcher.py --tasks tasks.json --output result.json
  python scripts/async_fetcher.py --tasks-url https://... --output result.json

用法(Python 导入):
  from async_fetcher import BatchFetcher
  fetcher = BatchFetcher(max_workers=50)
  fetcher.add_json("indices", "http://qt.gtimg.cn/q=sh000001,sz399001", encoding="gbk")
  fetcher.add_json("sector", "https://push2.eastmoney.com/api/qt/clist/get?...", throttle_domain="eastmoney")
  fetcher.add_subprocess("rank", ["python", "scripts/cn_fetch.py", "rank", "changepercent", "80"])
  results = fetcher.run()
  # results = {"indices": {...}, "sector": {...}, "rank": {...}, "_stats": {...}}

性能基线(50 并发):
  - 10 个请求: ~2-3s (vs 串行 ~15-20s)
  - 50 个请求: ~5-8s (vs 串行 ~75-100s)
"""
import argparse
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CTX = ssl._create_unverified_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 需要限流的域名(东财系有风控,其他不限)
THROTTLE_DOMAINS = {
    "eastmoney.com": 1.0,      # 最小间隔 1s
    "push2.eastmoney.com": 1.0,
    "push2his.eastmoney.com": 1.0,
    "push2ex.eastmoney.com": 1.0,
    "datacenter-web.eastmoney.com": 1.0,
    "reportapi.eastmoney.com": 1.0,
    "search-api-web.eastmoney.com": 1.5,
    "np-weblist.eastmoney.com": 1.0,
    "emappdata.eastmoney.com": 1.0,
}


class DomainThrottler:
    """按域名限流,线程安全。"""

    def __init__(self):
        self._last_call = defaultdict(float)
        self._lock = Lock()

    def wait(self, url: str):
        """如果 URL 匹配限流域名,等到最小间隔后再请求。"""
        for domain, interval in THROTTLE_DOMAINS.items():
            if domain in url:
                with self._lock:
                    now = time.time()
                    elapsed = now - self._last_call[domain]
                    if elapsed < interval:
                        import random
                        sleep_time = interval - elapsed + random.uniform(0.05, 0.2)
                        time.sleep(sleep_time)
                    self._last_call[domain] = time.time()
                break


class BatchFetcher:
    """批量异步数据获取引擎。"""

    def __init__(self, max_workers=50, timeout=15, retries=2):
        self.max_workers = max_workers
        self.timeout = timeout
        self.retries = retries
        self._tasks = []
        self._throttler = DomainThrottler()

    def add_json(self, name: str, url: str, encoding="utf-8",
                 throttle_domain="", headers=None, timeout=None):
        """添加 GET JSON 任务。"""
        self._tasks.append({
            "type": "get_json", "name": name, "url": url,
            "encoding": encoding, "throttle_domain": throttle_domain,
            "headers": headers, "timeout": timeout or self.timeout,
        })

    def add_raw(self, name: str, url: str, encoding="utf-8",
                headers=None, timeout=None):
        """添加 GET raw text 任务。"""
        self._tasks.append({
            "type": "get_raw", "name": name, "url": url,
            "encoding": encoding, "headers": headers,
            "timeout": timeout or self.timeout,
        })

    def add_subprocess(self, name: str, cmd: list, timeout=30, cwd=None):
        """添加子进程任务。"""
        self._tasks.append({
            "type": "subprocess", "name": name, "cmd": cmd,
            "timeout": timeout, "cwd": cwd,
        })

    def add_task(self, name: str, func, *args, **kwargs):
        """添加自定义函数任务。"""
        self._tasks.append({
            "type": "custom", "name": name, "func": func,
            "args": args, "kwargs": kwargs,
        })

    def _execute_get_json(self, task):
        """执行 GET JSON 请求,带重试。"""
        url = task["url"]
        if task.get("throttle_domain"):
            self._throttler.wait(url)
        else:
            self._throttler.wait(url)  # 自动匹配域名

        headers = {"User-Agent": UA}
        if task.get("headers"):
            headers.update(task["headers"])

        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=task["timeout"], context=CTX) as resp:
                    raw = resp.read().decode(task.get("encoding", "utf-8"), errors="ignore")
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        # 尝试 JSONP 或 HTML 包裹的 JSON
                        raw = raw.strip()
                        for start_ch, end_ch in [("{", "}"), ("[", "]")]:
                            i = raw.find(start_ch)
                            if i >= 0:
                                j = raw.rfind(end_ch)
                                if j > i:
                                    try:
                                        return json.loads(raw[i:j + 1])
                                    except Exception:
                                        pass
                        return {"_raw": raw[:2000], "_parse_error": "json_decode_failed"}
            except Exception as e:
                if attempt < self.retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                return {"_error": f"{type(e).__name__}: {str(e)[:200]}"}

    def _execute_get_raw(self, task):
        """执行 GET raw 请求。"""
        url = task["url"]
        self._throttler.wait(url)
        headers = {"User-Agent": UA}
        if task.get("headers"):
            headers.update(task["headers"])
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=task["timeout"], context=CTX) as resp:
                return resp.read().decode(task.get("encoding", "utf-8"), errors="ignore")
        except Exception as e:
            return f"_error: {type(e).__name__}: {str(e)[:200]}"

    def _execute_subprocess(self, task):
        """执行子进程。"""
        try:
            r = subprocess.run(
                task["cmd"], capture_output=True, text=True,
                timeout=task["timeout"], encoding="utf-8", errors="replace",
                cwd=task.get("cwd"),
            )
            if r.returncode == 0:
                return {"_stdout": r.stdout.strip()[:5000], "_returncode": 0}
            return {"_error": f"exit={r.returncode}", "_stderr": r.stderr[:500]}
        except subprocess.TimeoutExpired:
            return {"_error": f"timeout({task['timeout']}s)"}
        except Exception as e:
            return {"_error": f"{type(e).__name__}: {str(e)[:200]}"}

    def _execute_custom(self, task):
        """执行自定义函数。"""
        try:
            return task["func"](*task.get("args", []), **task.get("kwargs", {}))
        except Exception as e:
            return {"_error": f"{type(e).__name__}: {str(e)[:200]}"}

    def _execute_task(self, task):
        """路由到对应的执行器。"""
        t0 = time.time()
        task_type = task["type"]
        name = task["name"]

        if task_type == "get_json":
            result = self._execute_get_json(task)
        elif task_type == "get_raw":
            result = self._execute_get_raw(task)
        elif task_type == "subprocess":
            result = self._execute_subprocess(task)
        elif task_type == "custom":
            result = self._execute_custom(task)
        else:
            result = {"_error": f"unknown task type: {task_type}"}

        elapsed = round(time.time() - t0, 2)
        return name, result, elapsed

    def run(self) -> dict:
        """执行所有任务,返回 {name: result, ...} + _stats。"""
        if not self._tasks:
            return {"_stats": {"total": 0, "elapsed": 0}}

        t0 = time.time()
        results = {}
        timings = {}
        errors = []

        sys.stderr.write(f"[batch] 启动 {len(self._tasks)} 个任务, max_workers={self.max_workers}\n")

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._execute_task, task): task for task in self._tasks}
            for future in as_completed(futures):
                task = futures[future]
                try:
                    name, result, elapsed = future.result()
                    results[name] = result
                    timings[name] = elapsed
                    if isinstance(result, dict) and "_error" in result:
                        errors.append(name)
                except Exception as e:
                    name = task["name"]
                    results[name] = {"_error": f"executor: {type(e).__name__}: {str(e)[:200]}"}
                    timings[name] = 0
                    errors.append(name)

        total_elapsed = round(time.time() - t0, 2)
        ok_count = len(self._tasks) - len(errors)

        stats = {
            "total": len(self._tasks),
            "ok": ok_count,
            "errors": len(errors),
            "error_names": errors,
            "elapsed": total_elapsed,
            "max_workers": self.max_workers,
            "avg_per_task": round(total_elapsed / len(self._tasks), 2) if self._tasks else 0,
            "slowest": max(timings.values()) if timings else 0,
            "fastest": min(timings.values()) if timings else 0,
        }

        sys.stderr.write(
            f"[batch] 完成: {ok_count}/{len(self._tasks)} 成功, "
            f"{total_elapsed}s (最慢 {stats['slowest']}s, 最快 {stats['fastest']}s)\n"
        )
        if errors:
            sys.stderr.write(f"[batch] 失败: {', '.join(errors)}\n")

        results["_stats"] = stats
        return results


# ═══════════════════════════════════════════════════════════
# 命令行入口
# ═══════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="异步批量数据获取引擎")
    p.add_argument("--tasks", default="", help="任务 JSON 文件路径")
    p.add_argument("--output", default="", help="输出结果 JSON 文件路径")
    p.add_argument("--max-workers", type=int, default=50, help="最大并发数(默认 50)")
    p.add_argument("--timeout", type=int, default=15, help="单任务超时秒数(默认 15)")
    args = p.parse_args()

    if not args.tasks:
        sys.stderr.write("用法: python scripts/async_fetcher.py --tasks tasks.json --output result.json\n")
        sys.stderr.write("tasks.json 格式: [{name, type, url/cmd, ...}, ...]\n")
        return 1

    with open(args.tasks, "r", encoding="utf-8") as f:
        task_list = json.load(f)

    fetcher = BatchFetcher(max_workers=args.max_workers, timeout=args.timeout)
    for t in task_list:
        t_type = t.get("type", "get_json")
        name = t["name"]
        if t_type == "get_json":
            fetcher.add_json(name, t["url"], encoding=t.get("encoding", "utf-8"),
                             throttle_domain=t.get("throttle_domain", ""),
                             headers=t.get("headers"))
        elif t_type == "get_raw":
            fetcher.add_raw(name, t["url"], encoding=t.get("encoding", "utf-8"))
        elif t_type == "subprocess":
            fetcher.add_subprocess(name, t["cmd"], timeout=t.get("timeout", 30),
                                    cwd=t.get("cwd"))

    results = fetcher.run()

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        sys.stderr.write(f"[batch] 结果写入 {args.output}\n")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    return 0 if results["_stats"]["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
