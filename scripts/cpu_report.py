#!/usr/bin/env python3
"""CPU 占用报表生成器 — AIOps 测试用。

生成带时间戳的 HTML 报告，包含：
- 当前全局 CPU 使用率（单核和多核聚合）
- 每个核心的使用率详情
- Top 15 进程（按 CPU% 排序）
- 系统负载信息
- 压测模式检测（自动识别是否处于压测状态）

用法:
  uv run python scripts/cpu_report.py
  或双击触发脚本 scripts/stress_cpu.sh --multi
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 确保能找到 security_agent 包（无论从 scripts/ 还是项目根目录执行）
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psutil

from security_agent import config
from security_agent.timeutil import TZ_LABEL, format_display, now_filename_ts


def _get_loadavg() -> str:
    """获取系统负载平均值."""
    try:
        lavg = os.getloadavg()
        return f"{lavg[0]:.2f}, {lavg[1]:.2f}, {lavg[2]:.2f}"
    except (AttributeError, OSError):
        return "N/A (非 Linux 或无权限)"


def _get_cpu_details() -> dict:
    """获取详细的 CPU 信息."""
    cpu_count = psutil.cpu_count()
    cpu_count_physical = psutil.cpu_count(logical=False)

    # 获取每个核心的使用率
    per_cpu = psutil.cpu_percent(interval=0.5, percpu=True)

    # 计算统计信息
    avg_usage = sum(per_cpu) / len(per_cpu) if per_cpu else 0
    max_usage = max(per_cpu) if per_cpu else 0
    min_usage = min(per_cpu) if per_cpu else 0

    # 识别高负载核心（>80%）
    hot_cores = [(i, usage) for i, usage in enumerate(per_cpu) if usage > 80]

    return {
        "count_logical": cpu_count,
        "count_physical": cpu_count_physical,
        "per_cpu": per_cpu,
        "avg_usage": avg_usage,
        "max_usage": max_usage,
        "min_usage": min_usage,
        "hot_cores": hot_cores,
    }


def _detect_stress_mode() -> str:
    """检测当前是否处于压测模式."""
    # 检查是否有压测进程在运行
    stress_found = False
    dd_found = False
    dd_count = 0

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = proc.info.get("name", "")
            cmdline = " ".join(proc.info.get("cmdline", []))

            if name == "stress" or "stress" in cmdline:
                stress_found = True

            if name == "dd" and "/dev/zero" in cmdline:
                dd_found = True
                dd_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if stress_found:
        return f"stress 工具（可能多核）"
    elif dd_found:
        if dd_count > 1:
            return f"dd 多核模式（{dd_count} 个进程）"
        else:
            return "dd 单核模式"
    else:
        return "未检测到压测"


def generate_cpu_report() -> Path:
    """生成并保存 CPU 报告，返回文件路径."""
    ts = now_filename_ts()
    filename = f"cpu_report_{ts}.html"
    report_path = config.REPORTS_DIR / filename

    # 采集数据
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_details = _get_cpu_details()
    loadavg = _get_loadavg()
    now_str = format_display(datetime.now().isoformat(), "%Y-%m-%d %H:%M:%S")
    stress_mode = _detect_stress_mode()

    # CPU 信息
    cpu_count = cpu_details["count_logical"]
    cpu_count_physical = cpu_details["count_physical"]

    # 构建每个核心的使用率可视化
    cores_html = ""
    per_cpu = cpu_details["per_cpu"]
    cols = 4 if cpu_count <= 8 else 8  # 根据核心数决定每行显示多少个

    cores_html += '<div style="display: grid; grid-template-columns: repeat(' + str(cols) + ', 1fr); gap: 8px; margin: 16px 0;">'
    for i, usage in enumerate(per_cpu):
        # 根据使用率选择颜色
        if usage > 80:
            color = "#f87171"  # 红色
            bg = "#450a0a"
        elif usage > 50:
            color = "#fb923c"  # 橙色
            bg = "#451a03"
        elif usage > 20:
            color = "#60a5fa"  # 蓝色
            bg = "#172554"
        else:
            color = "#4ade80"  # 绿色
            bg = "#052e16"

        cores_html += f'''
        <div style="background: {bg}; border-radius: 6px; padding: 8px; text-align: center;">
            <div style="font-size: 0.75rem; color: #94a3b8;">Core {i}</div>
            <div style="font-size: 1.2rem; font-weight: 600; color: {color};">{usage:.1f}%</div>
            <div style="background: #334155; height: 4px; border-radius: 2px; margin-top: 4px;">
                <div style="background: {color}; width: {usage}%; height: 100%; border-radius: 2px;"></div>
            </div>
        </div>
        '''
    cores_html += '</div>'

    # Top 进程
    procs: list[dict] = []
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            cmd = " ".join(proc.cmdline()[:8]) if proc.cmdline() else ""
            info["cmdline"] = cmd[:80]
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    procs.sort(key=lambda p: (p.get("cpu_percent") or 0, p.get("memory_percent") or 0), reverse=True)
    top_procs = procs[:15]

    # 构建进程表格
    rows_html = ""
    for i, p in enumerate(top_procs, 1):
        cpu = p.get("cpu_percent") or 0
        mem = p.get("memory_percent") or 0

        # 高亮高 CPU 进程
        cpu_class = "cpu-high" if cpu > 50 else "cpu-medium" if cpu > 20 else "cpu-low"

        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td>{p.get('pid', '-')}</td>
            <td>{p.get('name', '-')}</td>
            <td>{p.get('username', '-')}</td>
            <td><span class="cpu-bar {cpu_class}" style="width:{min(cpu,100)}%"></span> {cpu:.1f}%</td>
            <td>{mem:.1f}%</td>
            <td class="cmd">{p.get('cmdline', '')}</td>
        </tr>
        """

    # 压测状态显示
    stress_alert = ""
    if "多核" in stress_mode or "stress" in stress_mode:
        stress_alert = f'''
        <div class="stress-badge stress-multi">
            🔥 压测检测: {stress_mode}
        </div>
        '''
    elif "单核" in stress_mode:
        stress_alert = f'''
        <div class="stress-badge stress-single">
            ⚡ 压测检测: {stress_mode}
        </div>
        '''

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>CPU 占用报告 · {ts}</title>
<style>
body {{ font-family: "Segoe UI", system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin:0; padding: 2rem; }}
h1 {{ color: #60a5fa; border-bottom: 2px solid #1e40af; padding-bottom: .5rem; }}
h2 {{ color: #93c5fd; margin-top: 1.5rem; }}
h3 {{ color: #94a3b8; font-size: 1rem; margin-top: 1rem; }}
.metric {{ font-size: 2.5rem; font-weight: 700; color: #f87171; }}
.card {{ background: #1e2937; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.3); }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: .6rem .8rem; text-align: left; border-bottom: 1px solid #334155; }}
th {{ background: #1e40af; color: #bfdbfe; font-weight: 600; }}
tr:hover {{ background: #1e3a5f; }}
.cpu-bar {{ display: inline-block; height: 8px; background: linear-gradient(90deg, #f87171, #fb923c); border-radius: 4px; vertical-align: middle; margin-right: .4rem; }}
.cpu-high {{ background: linear-gradient(90deg, #ef4444, #f87171); }}
.cpu-medium {{ background: linear-gradient(90deg, #fbbf24, #f59e0b); }}
.cpu-low {{ background: linear-gradient(90deg, #22c55e, #4ade80); }}
.cmd {{ font-family: ui-monospace, monospace; font-size: .85rem; color: #94a3b8; max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.footer {{ margin-top: 2rem; font-size: .8rem; color: #64748b; border-top: 1px solid #334155; padding-top: 1rem; }}
.stress-badge {{ display: inline-block; padding: 8px 16px; border-radius: 6px; font-weight: 600; margin-bottom: 12px; }}
.stress-multi {{ background: linear-gradient(90deg, #dc2626, #ef4444); color: white; }}
.stress-single {{ background: linear-gradient(90deg, #ea580c, #f97316); color: white; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0; }}
.stat-item {{ background: #0f172a; padding: 12px; border-radius: 8px; }}
.stat-label {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; }}
.stat-value {{ font-size: 1.5rem; font-weight: 600; color: #e2e8f0; }}
</style>
</head>
<body>
<div class="card">
  <h1>🖥️ CPU 占用报告</h1>
  <p><strong>生成时间：</strong>{now_str}（{TZ_LABEL}）</p>
  {stress_alert}

  <div class="stats-grid">
    <div class="stat-item">
      <div class="stat-label">全局 CPU 使用率</div>
      <div class="stat-value" style="color: {'#f87171' if cpu_percent > 80 else '#fb923c' if cpu_percent > 50 else '#60a5fa'}">{cpu_percent:.1f}%</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">物理核心 / 逻辑核心</div>
      <div class="stat-value">{cpu_count_physical} / {cpu_count}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">负载平均 (1/5/15 min)</div>
      <div class="stat-value" style="font-size: 1rem; font-family: monospace;">{loadavg}</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">平均核心使用率</div>
      <div class="stat-value" style="color: {'#f87171' if cpu_details['avg_usage'] > 80 else '#4ade80'}">{cpu_details['avg_usage']:.1f}%</div>
    </div>
  </div>
</div>

<div class="card">
  <h2>各核心使用率详情</h2>
  {cores_html}
  <p style="font-size: 0.85rem; color: #64748b; margin-top: 8px;">
    🔴 高负载 (>80%) 🟠 中负载 (50-80%) 🔵 低负载 (20-50%) 🟢 空闲 (<20%)
  </p>
</div>

<div class="card">
  <h2>Top 15 进程（按 CPU 排序）</h2>
  <table>
    <thead>
      <tr><th>#</th><th>PID</th><th>进程名</th><th>用户</th><th>CPU</th><th>内存</th><th>命令行</th></tr>
    </thead>
    <tbody>
      {rows_html or '<tr><td colspan="7">暂无进程数据</td></tr>'}
    </tbody>
  </table>
</div>

<div class="card">
  <h2>压测工具说明</h2>
  <p>本报告由 <code>scripts/cpu_report.py</code> 自动生成。</p>
  <p>压测命令参考：</p>
  <ul>
    <li><strong>单核压测：</strong><code>bash scripts/stress_cpu.sh</code></li>
    <li><strong>多核压测：</strong><code>bash scripts/stress_cpu.sh --multi</code></li>
    <li><strong>自定义时长：</strong><code>bash scripts/stress_cpu.sh --duration 30</code></li>
    <li><strong>仅看报告：</strong><code>bash scripts/stress_cpu.sh --report-only</code></li>
    <li><strong>清理残留：</strong><code>bash scripts/cleanup_stress.sh</code></li>
  </ul>
  <p style="color: #94a3b8; font-size: 0.9rem;">
    若需连续监控，请在「系统监控」页启动监控后观察事件流。
  </p>
</div>

<div class="footer">
  银河麒麟智能安全运维 Agent · AIOps 演示报表 · 支持多核压测检测<br>
  生成路径: {report_path}
</div>
</body>
</html>
"""

    report_path.write_text(html, encoding="utf-8")

    # 同时生成 JSON 数据供其他工具使用
    json_path = report_path.with_suffix(".json")
    json_data = {
        "timestamp": ts,
        "cpu": {
            "percent": cpu_percent,
            "count_logical": cpu_count,
            "count_physical": cpu_count_physical,
            "per_cpu": per_cpu,
            "avg_usage": cpu_details["avg_usage"],
            "max_usage": cpu_details["max_usage"],
        },
        "loadavg": loadavg,
        "stress_mode": stress_mode,
        "top_processes": [
            {
                "pid": p.get("pid"),
                "name": p.get("name"),
                "username": p.get("username"),
                "cpu_percent": p.get("cpu_percent"),
                "memory_percent": p.get("memory_percent"),
            }
            for p in top_procs
        ],
    }
    json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return report_path


if __name__ == "__main__":
    path = generate_cpu_report()
    print(f"[cpu_report] 已生成: {path}")
    print(f"[cpu_report] JSON 数据: {path.with_suffix('.json')}")
    print(f"可用浏览器打开: {path}")
