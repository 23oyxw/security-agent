"""导出 MCP 工具目录到 Gitee Wiki — 丰富度维度证据."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = Path.home() / "tmp" / "security-agent.wiki"


def build_catalog():
    """扫描所有 Skill 生成工具目录."""
    import importlib, pkgutil, os

    skills_dir = ROOT / "security_agent" / "skills"
    tools = []

    # 扫描 skills 目录
    for item in sorted(skills_dir.iterdir()):
        if item.is_dir() and not item.name.startswith("_") and not item.name.startswith("flows"):
            skill_py = item / "skill.py"
            if not skill_py.exists():
                # 检查单个 skill 文件
                for f in item.glob("*.py"):
                    if f.name != "__init__.py":
                        skill_py = f
                        break
            if skill_py and skill_py.exists():
                content = skill_py.read_text(encoding="utf-8", errors="replace")
                # 提取函数名作为工具名
                import re
                funcs = re.findall(r'async def (\w+)\(', content)
                desc_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
                desc = desc_match.group(1).strip()[:200] if desc_match else ""
                tools.append({
                    "name": item.name,
                    "functions": funcs,
                    "description": desc,
                    "path": str(skill_py.relative_to(ROOT)),
                })

    # 扫描单文件 skills
    for f in sorted(skills_dir.glob("*_skill.py")):
        content = f.read_text(encoding="utf-8", errors="replace")
        funcs = re.findall(r'async def (\w+)\(', content)
        desc_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        desc = desc_match.group(1).strip()[:200] if desc_match else ""
        tools.append({
            "name": f.stem,
            "functions": funcs,
            "description": desc,
            "path": str(f.relative_to(ROOT)),
        })

    # 扫描 flows
    flows_dir = skills_dir / "flows"
    if flows_dir.is_dir():
        content = (flows_dir / "runner.py").read_text(encoding="utf-8", errors="replace")
        import re
        flows = re.findall(r'FLOW_REGISTRY\["(\w+)"\]', content)
        tools.append({
            "name": "flows (L2 工作流)",
            "functions": flows,
            "description": "6 个 L2 确定性工作流",
            "path": "skills/flows/runner.py",
        })

    return tools


if __name__ == "__main__":
    import re

    tools = build_catalog()

    lines = []
    lines.append("# MCP 工具目录 (Tool Catalog)\n")
    lines.append(f"**总计**: {sum(len(t['functions']) for t in tools)} 个工具 · {len(tools)} 个 Skill 包\n")
    lines.append("> 四大工具簇: metrics · logs · repair · dispatch\n")

    # 按簇分类
    cluster_map = {
        "metrics": ["healthcheck", "monitor", "system_info", "cpu_tuning"],
        "logs": ["log_analyzer", "audit", "trace"],
        "repair": ["security_hardening", "system_cleanup", "disk_manager", "incident_responder", "config_manager"],
        "dispatch": ["network_ops", "process", "terminal", "memory_priority"],
    }

    assigned = set()
    for cluster, names in cluster_map.items():
        lines.append(f"\n## {cluster} ({'指标采集' if cluster == 'metrics' else '日志处理' if cluster == 'logs' else '故障修复' if cluster == 'repair' else '资源调度'})\n")
        for name in names:
            for t in tools:
                if name in t["name"] or t["name"] in name:
                    if t["name"] not in assigned:
                        lines.append(f"### {t['name']}\n")
                        if t["description"]:
                            lines.append(f"{t['description']}\n")
                        for fn in t["functions"]:
                            lines.append(f"- `{fn}()`")
                        lines.append("")
                        assigned.add(t["name"])

    # 未分类的
    leftover = [t for t in tools if t["name"] not in assigned]
    if leftover:
        lines.append("\n## 其他\n")
        for t in leftover:
            lines.append(f"### {t['name']}\n")
            if t["description"]:
                lines.append(f"{t['description']}\n")
            for fn in t["functions"]:
                lines.append(f"- `{fn}()`")
            lines.append("")

    lines.append(f"\n---\n*生成时间: 2026-07-15 · MCP 评分维度证据*")

    (OUTPUT_DIR / "MCP工具目录.md").write_text("\n".join(lines), encoding="utf-8")
    total_funcs = sum(len(t["functions"]) for t in tools)
    print(f"MCP工具目录: {len(tools)} Skills, {total_funcs} 工具")
    print(f"Output: {OUTPUT_DIR / 'MCP工具目录.md'}")