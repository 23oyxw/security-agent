"""导出知识库内容到 Gitee Wiki 格式 — 按分类组织 Markdown 页面."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUTPUT_DIR = Path.home() / "tmp" / "security-agent.wiki"


def export_playbooks():
    """导出 Playbook 知识."""
    from security_agent.knowledge.playbooks import PLAYBOOKS
    lines = []
    lines.append("# 安全运维应急预案 (Playbook)\n")
    lines.append(f"共 {len(PLAYBOOKS)} 条预案\n")

    by_severity = {}
    for p in PLAYBOOKS:
        by_severity.setdefault(p.severity, []).append(p)

    for sev in ("高", "中", "低"):
        pbs = by_severity.get(sev, [])
        if not pbs:
            continue
        lines.append(f"\n## {sev}严重度\n")
        for p in pbs:
            lines.append(f"### {p.id}: {p.title}\n")
            lines.append(f"{p.body}\n")
            lines.append(f"- **标签**: {', '.join(p.threat_tags)}")
            lines.append(f"- **需确认**: {'是' if p.requires_root_confirm else '否'}")
            if p.do_not:
                lines.append(f"- **禁止**: {', '.join(p.do_not)}")
            if p.suggested_actions:
                lines.append(f"- **建议**: {', '.join(p.suggested_actions)}")
            lines.append("")

    (OUTPUT_DIR / "Home.md").write_text("\n".join(lines), encoding="utf-8")
    return len(PLAYBOOKS)


def export_seed_knowledge():
    """导出种子知识库."""
    from security_agent.knowledge.gitee_wiki.seed_knowledge import PRESET_DOCS

    by_category = {}
    for doc in PRESET_DOCS:
        by_category.setdefault(doc.category, []).append(doc)

    count = 0
    for category, docs in by_category.items():
        slug = category.replace(" ", "-").replace("/", "-")
        lines = []
        lines.append(f"# {category}\n")
        for doc in docs:
            lines.append(f"## {doc.title}\n")
            lines.append(doc.content)
            lines.append(f"\n---\n**标签**: {' '.join(doc.tags)}\n")
            count += 1

        (OUTPUT_DIR / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")

    return count


def export_boundary_knowledge():
    """导出边界对抗知识."""
    try:
        from security_agent.knowledge.boundary_wiki import export_boundary_to_markdown
        result = export_boundary_to_markdown(path=OUTPUT_DIR / "边界对抗数据.md")
        return 1 if result else 0
    except Exception as e:
        print(f"  边界知识跳过: {e}")
        return 0


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    n_playbooks = export_playbooks()
    print(f"  Playbook: {n_playbooks} 条 → Home.md")

    n_seed = export_seed_knowledge()
    print(f"  种子知识: {n_seed} 篇 → 按分类分文件")

    n_boundary = export_boundary_knowledge()
    print(f"  边界对抗: {n_boundary} 篇")

    total = sum(1 for _ in OUTPUT_DIR.glob("*.md"))
    print(f"\n总计: {total} 个 Wiki 页面 → {OUTPUT_DIR}")
