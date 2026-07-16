#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Workflow 实时监测仪表盘 — 观测 workflow 内部状态,不占用上下文。

用法:
  python scripts/workflow_monitor.py --watch              # 自动监测最新 workflow
  python scripts/workflow_monitor.py --run-id xxx         # 监测指定 workflow
  python scripts/workflow_monitor.py --run-id xxx --once  # 单次查看(不刷新)

输出: 实时刷新的终端仪表盘(类似 htop)
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def find_latest_run():
    """查找最新的 workflow 运行目录"""
    runs_dir = Path("data/runs")
    if not runs_dir.exists():
        return None

    # 找所有包含 _progress.json 的目录
    progress_files = list(runs_dir.glob("*/_progress.json"))
    if not progress_files:
        return None

    # 按修改时间排序,取最新
    latest = max(progress_files, key=lambda p: p.stat().st_mtime)
    return latest.parent


def load_progress(run_dir):
    """加载进度文件"""
    progress_file = run_dir / "_progress.json"
    if not progress_file.exists():
        return None

    try:
        with open(progress_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


def format_duration(seconds):
    """格式化耗时"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}min {seconds % 60}s"
    else:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}min"


def render_dashboard(progress, run_id):
    """渲染仪表盘"""
    # 清屏
    print("\033[2J\033[H", end="")

    # 标题
    print("=" * 80)
    print(f"  Workflow 实时监测仪表盘")
    print(f"  Run ID: {run_id}")
    print(f"  刷新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    if "error" in progress:
        print(f"❌ 错误: {progress['error']}")
        return

    # 基本信息
    start_time = progress.get("startTime", "N/A")
    current_phase = progress.get("currentPhase", "N/A")
    current_agent = progress.get("currentAgent", "N/A")

    # 计算总耗时
    if start_time != "N/A":
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            elapsed = int((datetime.now() - start_dt.replace(tzinfo=None)).total_seconds())
            elapsed_str = format_duration(elapsed)
        except:
            elapsed_str = "N/A"
    else:
        elapsed_str = "N/A"

    print(f"📊 总耗时: {elapsed_str}")
    print(f"🎯 当前阶段: {current_phase}")
    print(f"🤖 当前 Agent: {current_agent}")
    print()

    # 阶段进度
    phases = progress.get("phases", [])
    if phases:
        print("📈 阶段进度:")
        print("-" * 80)

        for i, phase in enumerate(phases, 1):
            name = phase.get("name", f"Phase {i}")
            status = phase.get("status", "pending")
            duration = phase.get("duration", "")
            details = phase.get("details", "")
            summary = phase.get("summary", "")

            # 状态图标
            if status == "completed":
                icon = "✅"
                time_str = f"({duration})" if duration else ""
                info = summary or details or ""
            elif status == "running":
                icon = "🔄"
                time_str = "(运行中...)"
                info = f"Agent: {phase.get('currentAgent', 'N/A')}"
            elif status == "failed":
                icon = "❌"
                time_str = ""
                info = phase.get("error", "")
            else:
                icon = "⏳"
                time_str = ""
                info = ""

            print(f"{icon} {i}. {name} {time_str}")
            if info:
                print(f"   └─ {info}")

        print()

    # 错误和警告
    errors = progress.get("errors", [])
    warnings = progress.get("warnings", [])

    if errors:
        print("❌ 错误:")
        for err in errors[-5:]:  # 只显示最近5个
            print(f"  • {err}")
        print()

    if warnings:
        print("⚠️  警告:")
        for warn in warnings[-5:]:
            print(f"  • {warn}")
        print()

    # 底部提示
    print("=" * 80)
    print("按 Ctrl+C 退出监测")
    print("=" * 80)


def watch_mode(run_dir, run_id):
    """监视模式:每2秒刷新"""
    try:
        while True:
            progress = load_progress(run_dir)
            if progress:
                render_dashboard(progress, run_id)
            else:
                print(f"⏳ 等待进度文件: {run_dir / '_progress.json'}")

            time.sleep(2)
    except KeyboardInterrupt:
        print("\n\n👋 监测已退出")


def once_mode(run_dir, run_id):
    """单次查看模式"""
    progress = load_progress(run_dir)
    if progress:
        render_dashboard(progress, run_id)
    else:
        print(f"❌ 未找到进度文件: {run_dir / '_progress.json'}")


def main():
    parser = argparse.ArgumentParser(description="Workflow 实时监测仪表盘")
    parser.add_argument("--run-id", help="指定 workflow run ID")
    parser.add_argument("--watch", action="store_true", help="持续监视模式(默认)")
    parser.add_argument("--once", action="store_true", help="单次查看模式")
    args = parser.parse_args()

    # 确定 run 目录
    if args.run_id:
        run_dir = Path(f"data/runs/{args.run_id}")
        run_id = args.run_id
    else:
        run_dir = find_latest_run()
        if not run_dir:
            print("❌ 未找到任何 workflow 运行记录")
            print("提示: 先运行一个 workflow,然后再执行监测命令")
            return 1
        run_id = run_dir.name

    if not run_dir.exists():
        print(f"❌ Run 目录不存在: {run_dir}")
        return 1

    # 运行模式
    if args.once:
        once_mode(run_dir, run_id)
    else:
        watch_mode(run_dir, run_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
