#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Workflow 进度追踪模块 — 供 workflow 内部调用,写入 _progress.json。

用法(在 workflow 中):
  from workflow_progress import WorkflowProgress

  progress = WorkflowProgress(run_id, phases=["数据预取", "宏观定调", ...])
  progress.start_phase("数据预取", agent="prefetch")
  progress.update_details("16端点, 4成功+12备胎")
  progress.complete_phase(summary="13s完成")
  progress.start_phase("宏观定调", agent="macro-strategist")
  progress.add_warning("东财IP被封, 使用备胎源")
  ...
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path


class WorkflowProgress:
    """Workflow 进度追踪器"""

    def __init__(self, run_id, phases=None):
        """
        初始化进度追踪器

        Args:
            run_id: Workflow 运行 ID (如 "20260716_short-term-picks")
            phases: 阶段名称列表 (如 ["数据预取", "宏观定调", ...])
        """
        self.run_id = run_id
        self.run_dir = Path(f"data/runs/{run_id}")
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.progress_file = self.run_dir / "_progress.json"

        # 初始化进度结构
        self.progress = {
            "runId": run_id,
            "startTime": datetime.now().isoformat(),
            "currentPhase": None,
            "currentAgent": None,
            "phases": [],
            "errors": [],
            "warnings": [],
        }

        # 预填充阶段信息
        if phases:
            for phase_name in phases:
                self.progress["phases"].append({
                    "name": phase_name,
                    "status": "pending",
                    "startTime": None,
                    "endTime": None,
                    "duration": None,
                    "details": None,
                    "summary": None,
                    "currentAgent": None,
                    "error": None,
                })

        self.save()

    def start_phase(self, phase_name, agent=None):
        """开始一个阶段"""
        self.progress["currentPhase"] = phase_name
        self.progress["currentAgent"] = agent

        # 找到对应阶段并更新
        for phase in self.progress["phases"]:
            if phase["name"] == phase_name:
                phase["status"] = "running"
                phase["startTime"] = datetime.now().isoformat()
                phase["currentAgent"] = agent
                break

        self.save()

    def update_details(self, details):
        """更新当前阶段的详细信息"""
        current = self.progress["currentPhase"]
        for phase in self.progress["phases"]:
            if phase["name"] == current:
                phase["details"] = details
                break
        self.save()

    def update_agent(self, agent):
        """更新当前 agent"""
        self.progress["currentAgent"] = agent
        current = self.progress["currentPhase"]
        for phase in self.progress["phases"]:
            if phase["name"] == current:
                phase["currentAgent"] = agent
                break
        self.save()

    def complete_phase(self, summary=None, duration=None):
        """完成当前阶段"""
        current = self.progress["currentPhase"]
        for phase in self.progress["phases"]:
            if phase["name"] == current:
                phase["status"] = "completed"
                phase["endTime"] = datetime.now().isoformat()
                phase["summary"] = summary

                # 计算耗时
                if phase["startTime"]:
                    try:
                        start_dt = datetime.fromisoformat(phase["startTime"])
                        elapsed = int((datetime.now() - start_dt).total_seconds())
                        if duration is None:
                            if elapsed < 60:
                                phase["duration"] = f"{elapsed}s"
                            elif elapsed < 3600:
                                phase["duration"] = f"{elapsed // 60}min {elapsed % 60}s"
                            else:
                                phase["duration"] = f"{elapsed // 3600}h {(elapsed % 3600) // 60}min"
                        else:
                            phase["duration"] = duration
                    except:
                        pass
                break

        self.progress["currentPhase"] = None
        self.progress["currentAgent"] = None
        self.save()

    def fail_phase(self, error_msg):
        """标记当前阶段失败"""
        current = self.progress["currentPhase"]
        for phase in self.progress["phases"]:
            if phase["name"] == current:
                phase["status"] = "failed"
                phase["endTime"] = datetime.now().isoformat()
                phase["error"] = error_msg
                break

        self.progress["errors"].append(f"[{current}] {error_msg}")
        self.save()

    def add_error(self, error_msg):
        """添加错误(不关联到特定阶段)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.progress["errors"].append(f"[{timestamp}] {error_msg}")
        self.save()

    def add_warning(self, warning_msg):
        """添加警告"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.progress["warnings"].append(f"[{timestamp}] {warning_msg}")
        self.save()

    def save(self):
        """保存进度到文件"""
        try:
            with open(self.progress_file, "w", encoding="utf-8") as f:
                json.dump(self.progress, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # 静默失败,不影响 workflow
            pass

    def get_progress(self):
        """获取当前进度数据"""
        return self.progress.copy()


# 便捷函数(供 workflow 直接调用)
_progress_instance = None


def init_progress(run_id, phases):
    """初始化全局进度追踪器"""
    global _progress_instance
    _progress_instance = WorkflowProgress(run_id, phases)
    return _progress_instance


def get_progress():
    """获取全局进度追踪器"""
    return _progress_instance


def start_phase(phase_name, agent=None):
    """开始阶段"""
    if _progress_instance:
        _progress_instance.start_phase(phase_name, agent)


def update_details(details):
    """更新详细信息"""
    if _progress_instance:
        _progress_instance.update_details(details)


def update_agent(agent):
    """更新 agent"""
    if _progress_instance:
        _progress_instance.update_agent(agent)


def complete_phase(summary=None, duration=None):
    """完成阶段"""
    if _progress_instance:
        _progress_instance.complete_phase(summary, duration)


def fail_phase(error_msg):
    """阶段失败"""
    if _progress_instance:
        _progress_instance.fail_phase(error_msg)


def add_error(error_msg):
    """添加错误"""
    if _progress_instance:
        _progress_instance.add_error(error_msg)


def add_warning(warning_msg):
    """添加警告"""
    if _progress_instance:
        _progress_instance.add_warning(warning_msg)
