#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""投资分析报告邮件通知——workflow 完成后自动发送报告摘要到邮箱。

用法:
  python scripts/notify_email.py --run-id 20260714_short-term-picks
  python scripts/notify_email.py --run-id 20260714_short-term-picks --dry-run  # 只生成不发

配置: config/email_config.yaml (gitignored)
  smtp:
    host: smtp.qq.com
    port: 465
    user: your_qq@qq.com
    auth_code: your_authorization_code  # QQ邮箱授权码,非登录密码
  recipients:                           # 支持多个收件人
    - email1@qq.com
    - email2@gmail.com
  sender_name: 投资分析助手
"""
import argparse
import glob
import json
import os
import re
import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

try:
    import markdown as md_lib
except ImportError:
    md_lib = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CONFIG_PATHS = [
    "config/email_config.yaml",
    "config/email_config.yml",
    os.path.expanduser("~/.finacial_invest_email.yaml"),
]


def load_config():
    """加载邮件配置(yaml 或 json)"""
    for path in CONFIG_PATHS:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                if path.endswith((".yaml", ".yml")):
                    if yaml:
                        return yaml.safe_load(f)
                    else:
                        # 简易 yaml 解析(无 pyyaml 时)
                        return _simple_yaml_load(f.read())
                else:
                    return json.load(f)
    return None


def _simple_yaml_load(text):
    """极简 yaml 解析(支持扁平+一层嵌套+列表项)"""
    result = {}
    current_section = None
    current_list = None
    for line in text.split("\n"):
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        # 列表项: "  - value" 或 "- value"
        list_match = re.match(r'^(\s*)-\s+(.+)', stripped)
        if list_match and current_section:
            val = list_match.group(2).strip()
            if not isinstance(result.get(current_section), list):
                result[current_section] = result.get(current_section, [])
                if isinstance(result[current_section], dict):
                    # section 之前是 dict,转为 list(丢弃 dict 内容)
                    result[current_section] = []
            result[current_section].append(val)
            continue
        if stripped.startswith("  "):
            if current_section and isinstance(result.get(current_section), dict):
                key, _, val = stripped.strip().partition(":")
                result[current_section][key.strip()] = val.strip()
        else:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val:
                result[key] = val
                current_section = None
            else:
                result[key] = {}
                current_section = key
    return result


def _find_final_json(run_id):
    """查找 final.json 文件路径"""
    exact = os.path.join("data/runs", run_id, "final.json")
    if os.path.exists(exact):
        return exact
    for d in sorted(Path("data/runs").glob(f"*{run_id}*")):
        candidate = d / "final.json"
        if candidate.exists():
            return str(candidate)
    return None


def _find_report_file(final_data, run_id):
    """多路查找报告文件: data.path → envelope.reportPath → glob output/"""
    data = final_data.get("data", final_data)
    envelope = final_data.get("envelope", {})

    for candidate in [data.get("path", ""), envelope.get("reportPath", "")]:
        if candidate and os.path.exists(candidate):
            return candidate

    # glob fallback
    date_str = envelope.get("asOf", run_id[:8])
    goal = envelope.get("goal", "")
    patterns = []
    if goal:
        patterns.append(f"output/{date_str}_{goal}*.md")
    patterns.extend([f"output/{date_str}*.md", f"output/*{date_str}*.md"])
    for pat in patterns:
        matches = sorted(glob.glob(pat))
        if matches:
            return matches[-1]
    return ""


def load_run_data(run_id):
    """加载 final.json + 报告"""
    final_path = _find_final_json(run_id)
    if not final_path:
        return None, None, None

    with open(final_path, "r", encoding="utf-8") as f:
        final_data = json.load(f)

    report_path = _find_report_file(final_data, run_id)
    report_content = ""
    if report_path and os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            report_content = f.read()

    data = final_data.get("data", final_data)
    return data, report_content, report_path


def format_html_email(data, report_content, report_path):
    """生成 HTML 邮件内容"""
    one_line = data.get("oneLineConclusion", "无结论")
    confidence = data.get("confidence", "未知")
    total_pos = data.get("totalPosition", "未知")
    topN = data.get("topN", [])
    key_risks = data.get("keyRisks", [])
    goal = data.get("goal", data.get("runId", "投资分析"))

    # 置信度颜色
    conf_colors = {"高": "#22c55e", "中": "#f59e0b", "低": "#ef4444"}
    conf_color = conf_colors.get(confidence, "#6b7280")

    # TopN 表格
    topN_rows = ""
    for i, item in enumerate(topN[:10], 1):
        code = item.get("code", "")
        name = item.get("name", "")
        role = item.get("role", item.get("suggestedPosition", ""))
        position = item.get("position", item.get("suggestedPosition", ""))
        topN_rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #e5e7eb;text-align:center">{i}</td>
          <td style="padding:8px;border:1px solid #e5e7eb;font-weight:bold">{code}</td>
          <td style="padding:8px;border:1px solid #e5e7eb">{name}</td>
          <td style="padding:8px;border:1px solid #e5e7eb">{role}</td>
          <td style="padding:8px;border:1px solid #e5e7eb">{position}</td>
        </tr>"""

    # 风险列表
    risks_html = ""
    for r in key_risks[:5]:
        if isinstance(r, str):
            risks_html += f"<li style='margin:4px 0'>{r}</li>"
        elif isinstance(r, dict):
            risks_html += f"<li style='margin:4px 0'>{r.get('text', r.get('summary', str(r)))}</li>"

    # 完整报告:markdown → 带样式的 HTML 嵌入正文
    report_html = ""
    if report_content:
        if md_lib:
            raw_html = md_lib.markdown(
                report_content,
                extensions=["tables", "fenced_code", "toc", "nl2br"],
            )
        else:
            # 无 markdown 库时降级:简单替换
            raw_html = report_content.replace("\n", "<br>")
        # emoji 着色
        raw_html = raw_html.replace("🟢", '<span style="color:#22c55e">🟢</span>')
        raw_html = raw_html.replace("🟡", '<span style="color:#f59e0b">🟡</span>')
        raw_html = raw_html.replace("🔴", '<span style="color:#ef4444">🔴</span>')
        report_html = f"""
    <div style="margin-top:32px">
      <h2 style="color:#111827;border-bottom:2px solid #3b82f6;padding-bottom:8px;margin-bottom:16px">
        📄 完整报告
      </h2>
      <div style="font-size:14px;line-height:1.8;color:#374151">
        <style>
          .report-body h1 {{ font-size:20px; color:#111827; border-bottom:2px solid #e5e7eb; padding-bottom:6px; margin-top:24px; }}
          .report-body h2 {{ font-size:17px; color:#374151; border-bottom:1px solid #e5e7eb; padding-bottom:4px; margin-top:20px; }}
          .report-body h3 {{ font-size:15px; color:#4b5563; margin-top:16px; }}
          .report-body h4 {{ font-size:14px; color:#6b7280; margin-top:12px; }}
          .report-body table {{ border-collapse:collapse; width:100%; margin:12px 0; font-size:13px; }}
          .report-body th {{ background:#f3f4f6; padding:6px 10px; border:1px solid #d1d5db; text-align:left; font-weight:600; }}
          .report-body td {{ padding:6px 10px; border:1px solid #e5e7eb; }}
          .report-body tr:nth-child(even) {{ background:#f9fafb; }}
          .report-body code {{ background:#f3f4f6; padding:1px 4px; border-radius:3px; font-size:12px; color:#dc2626; }}
          .report-body pre {{ background:#1f2937; color:#e5e7eb; padding:14px; border-radius:8px; overflow-x:auto; font-size:12px; }}
          .report-body pre code {{ background:transparent; color:#e5e7eb; padding:0; }}
          .report-body blockquote {{ border-left:4px solid #3b82f6; padding:8px 16px; margin:12px 0; background:#eff6ff; color:#1e40af; border-radius:0 6px 6px 0; }}
          .report-body strong {{ color:#111827; }}
          .report-body hr {{ border:none; border-top:1px solid #e5e7eb; margin:20px 0; }}
          .report-body ul, .report-body ol {{ padding-left:24px; }}
          .report-body li {{ margin:4px 0; }}
          .report-body a {{ color:#2563eb; text-decoration:underline; }}
        </style>
        <div class="report-body">{raw_html}</div>
      </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
            max-width:680px;margin:0 auto;padding:20px;background:#f3f4f6">

  <div style="background:white;border-radius:12px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,0.1)">

    <!-- 头部 -->
    <div style="border-bottom:2px solid #e5e7eb;padding-bottom:16px;margin-bottom:20px">
      <h2 style="margin:0;color:#111827">🎯 投资分析报告已生成</h2>
      <p style="color:#6b7280;margin:8px 0 0">{goal}</p>
      <p style="color:#9ca3af;margin:4px 0 0;font-size:12px">{time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <!-- 一句话结论 -->
    <div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:16px;border-radius:0 8px 8px 0;
                margin-bottom:20px">
      <p style="margin:0;font-size:16px;font-weight:600;color:#1e40af">{one_line}</p>
    </div>

    <!-- 状态卡片 -->
    <div style="display:flex;gap:12px;margin-bottom:20px">
      <div style="flex:1;background:#f9fafb;padding:12px;border-radius:8px;text-align:center">
        <div style="font-size:12px;color:#6b7280">置信度</div>
        <div style="font-size:20px;font-weight:bold;color:{conf_color}">{confidence}</div>
      </div>
      <div style="flex:1;background:#f9fafb;padding:12px;border-radius:8px;text-align:center">
        <div style="font-size:12px;color:#6b7280">总仓位</div>
        <div style="font-size:20px;font-weight:bold;color:#374151">{total_pos}</div>
      </div>
      <div style="flex:1;background:#f9fafb;padding:12px;border-radius:8px;text-align:center">
        <div style="font-size:12px;color:#6b7280">推荐数</div>
        <div style="font-size:20px;font-weight:bold;color:#374151">{len(topN)}</div>
      </div>
    </div>

    <!-- TopN 表格 -->
    {f'''
    <div style="margin-bottom:20px">
      <h3 style="color:#374151;margin-bottom:12px">📊 Top {len(topN)} 推荐</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <thead>
          <tr style="background:#f3f4f6">
            <th style="padding:8px;border:1px solid #e5e7eb">#</th>
            <th style="padding:8px;border:1px solid #e5e7eb">代码</th>
            <th style="padding:8px;border:1px solid #e5e7eb">名称</th>
            <th style="padding:8px;border:1px solid #e5e7eb">角色</th>
            <th style="padding:8px;border:1px solid #e5e7eb">仓位</th>
          </tr>
        </thead>
        <tbody>{topN_rows}</tbody>
      </table>
    </div>
    ''' if topN else ''}

    <!-- 关键风险 -->
    {f'''
    <div style="margin-bottom:20px">
      <h3 style="color:#374151;margin-bottom:8px">⚠️ 关键风险</h3>
      <ul style="color:#6b7280;padding-left:20px">{risks_html}</ul>
    </div>
    ''' if risks_html else ''}

    <!-- 完整报告 -->
    {report_html}

    <!-- 底部 -->
    <div style="margin-top:24px;padding-top:16px;border-top:1px solid #e5e7eb;
                font-size:12px;color:#9ca3af;text-align:center">
      <p>📁 报告文件: <code>{report_path or 'N/A'}</code></p>
      <p>⚠️ 本报告不构成投资建议,据此操作风险自负。</p>
      <p>由投资分析助手自动生成 | {time.strftime('%Y-%m-%d')}</p>
    </div>

  </div>
</body>
</html>"""

    return html


def _resolve_recipients(config, user):
    """解析收件人列表(支持 recipients 列表 / recipient 字符串 / 逗号分隔)"""
    raw = config.get("recipients", config.get("recipient", user))
    if isinstance(raw, str):
        return [r.strip() for r in raw.split(",") if r.strip()]
    if isinstance(raw, list):
        return [r.strip() for r in raw if isinstance(r, str) and r.strip()]
    return [user] if user else []


def send_email(config, subject, html_content):
    """发送邮件(支持多收件人,完整报告嵌入 HTML 正文)"""
    smtp_cfg = config.get("smtp", {})
    host = smtp_cfg.get("host", "smtp.qq.com")
    port = int(smtp_cfg.get("port", 465))
    user = smtp_cfg.get("user", "")
    auth_code = smtp_cfg.get("auth_code", smtp_cfg.get("password", ""))
    sender_name = config.get("sender_name", "投资分析助手")

    recipients = _resolve_recipients(config, user)
    if not user or not auth_code:
        sys.stderr.write("错误: SMTP user 或 auth_code 未配置\n")
        return False
    if not recipients:
        sys.stderr.write("错误: 无收件人地址\n")
        return False

    # 构建邮件(纯 HTML 正文,无附件)
    msg = MIMEMultipart("mixed")
    msg["From"] = formataddr((str(Header(sender_name, "utf-8")), user))
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # 发送
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()

        server.login(user, auth_code)
        server.sendmail(user, recipients, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        sys.stderr.write(f"发送失败: {type(e).__name__}: {e}\n")
        return False


def main():
    p = argparse.ArgumentParser(description="投资分析报告邮件通知")
    p.add_argument("--run-id", required=True, help="运行 ID (如 20260714_short-term-picks)")
    p.add_argument("--dry-run", action="store_true", help="只生成邮件内容,不发送")
    p.add_argument("--output-html", default="", help="输出 HTML 到文件(调试用)")
    args = p.parse_args()

    # 加载配置
    config = load_config()
    if not config and not args.dry_run:
        sys.stderr.write(
            "错误: 未找到邮件配置文件\n"
            "请创建 config/email_config.yaml,模板:\n"
            "  smtp:\n"
            "    host: smtp.qq.com\n"
            "    port: 465\n"
            "    user: your_qq@qq.com\n"
            "    auth_code: your_authorization_code\n"
            "  recipients:\n"
            "    - your_email1@qq.com\n"
            "    - your_email2@gmail.com\n"
            "  sender_name: 投资分析助手\n"
        )
        return 2

    # 加载运行数据
    data, report_content, report_path = load_run_data(args.run_id)
    if not data:
        sys.stderr.write(f"错误: 未找到运行数据 data/runs/*{args.run_id}*/final.json\n")
        return 2

    # 生成邮件
    one_line = data.get("oneLineConclusion", data.get("data", {}).get("oneLineConclusion", "投资分析报告"))
    confidence = data.get("confidence", data.get("data", {}).get("confidence", ""))
    goal = data.get("goal", args.run_id)
    subject = f"📊 {goal} | 置信度:{confidence} | {time.strftime('%m/%d')}"

    # 处理嵌套 data
    flat_data = data.get("data", data)
    # 合并顶层字段
    for key in ["oneLineConclusion", "topN", "totalPosition", "confidence", "keyRisks"]:
        if key not in flat_data and key in data:
            flat_data[key] = data[key]

    html = format_html_email(flat_data, report_content, report_path)

    if args.output_html:
        with open(args.output_html, "w", encoding="utf-8") as f:
            f.write(html)
        sys.stderr.write(f"HTML 已写入 {args.output_html}\n")

    if args.dry_run:
        print(html[:2000])
        print(f"\n... (dry-run, 共 {len(html)} 字符)")
        return 0

    # 发送
    raw_rec = config.get("recipients", config.get("recipient", "?"))
    rec_display = ", ".join(raw_rec) if isinstance(raw_rec, list) else str(raw_rec)
    sys.stderr.write(f"[notify] 发送邮件到 {rec_display}...\n")
    ok = send_email(config, subject, html)
    if ok:
        print(f"notify: 邮件发送成功 → {rec_display}")
        return 0
    else:
        print(f"notify: 邮件发送失败")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
