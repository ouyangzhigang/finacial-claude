#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Workflow 进度更新 CLI — 供 workflow 通过 Bash 调用。

用法:
  python scripts/update_progress.py --run-id xxx --init --phases "数据预取,宏观定调,候选池"
  python scripts/update_progress.py --run-id xxx --start-phase "数据预取" --agent prefetch
  python scripts/update_progress.py --run-id xxx --update-details "16端点, 4成功"
  python scripts/update_progress.py --run-id xxx --complete-phase --summary "13s完成"
  python scripts/update_progress.py --run-id xxx --fail-phase --error "连接超时"
  python scripts/update_progress.py --run-id xxx --add-warning "东财IP被封"
  python scripts/update_progress.py --run-id xxx --add-error "MCP调用失败"
"""
import argparse
import json
import sys
from pathlib import Path

# 导入进度追踪模块
sys.path.insert(0, str(Path(__file__).parent))
from workflow_progress import WorkflowProgress


def main():
    parser = argparse.ArgumentParser(description="Workflow 进度更新 CLI")
    parser.add_argument("--run-id", required=True, help="Workflow run ID")

    # 操作类型
    parser.add_argument("--init", action="store_true", help="初始化进度追踪")
    parser.add_argument("--start-phase", help="开始阶段")
    parser.add_argument("--complete-phase", action="store_true", help="完成当前阶段")
    parser.add_argument("--fail-phase", action="store_true", help="标记当前阶段失败")
    parser.add_argument("--update-details", help="更新详细信息")
    parser.add_argument("--update-agent", help="更新当前 agent")
    parser.add_argument("--add-warning", help="添加警告")
    parser.add_argument("--add-error", help="添加错误")

    # 参数
    parser.add_argument("--phases", help="阶段列表(逗号分隔)")
    parser.add_argument("--agent", help="Agent 名称")
    parser.add_argument("--summary", help="阶段完成摘要")
    parser.add_argument("--error", help="错误信息")

    args = parser.parse_args()

    # 加载或创建进度追踪器
    run_dir = Path(f"data/runs/{args.run_id}")
    progress_file = run_dir / "_progress.json"

    if args.init:
        # 初始化
        if not args.phases:
            print("❌ --init 需要 --phases 参数", file=sys.stderr)
            return 1

        phases = [p.strip() for p in args.phases.split(",")]
        progress = WorkflowProgress(args.run_id, phases)
        print(f"✅ 初始化完成: {len(phases)} 个阶段")
        return 0

    # 其他操作需要先加载现有进度
    if not progress_file.exists():
        print(f"❌ 进度文件不存在: {progress_file}", file=sys.stderr)
        print("提示: 先使用 --init 初始化", file=sys.stderr)
        return 1

    # 加载进度
    with open(progress_file, "r", encoding="utf-8") as f:
        progress_data = json.load(f)

    # 重建 WorkflowProgress 实例
    progress = WorkflowProgress.__new__(WorkflowProgress)
    progress.run_id = args.run_id
    progress.run_dir = run_dir
    progress.progress_file = progress_file
    progress.progress = progress_data

    # 执行操作
    if args.start_phase:
        progress.start_phase(args.start_phase, agent=args.agent)
        print(f"✅ 开始阶段: {args.start_phase}")

    elif args.complete_phase:
        progress.complete_phase(summary=args.summary)
        print(f"✅ 完成阶段")

    elif args.fail_phase:
        error_msg = args.error or "未知错误"
        progress.fail_phase(error_msg)
        print(f"❌ 阶段失败: {error_msg}")

    elif args.update_details:
        progress.update_details(args.update_details)
        print(f"✅ 更新详情")

    elif args.update_agent:
        progress.update_agent(args.update_agent)
        print(f"✅ 更新 Agent: {args.update_agent}")

    elif args.add_warning:
        progress.add_warning(args.add_warning)
        print(f"⚠️  添加警告")

    elif args.add_error:
        progress.add_error(args.add_error)
        print(f"❌ 添加错误")

    else:
        print("❌ 未指定操作", file=sys.stderr)
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
