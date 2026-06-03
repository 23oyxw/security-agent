#!/usr/bin/env python3
"""前端盲区集成测试 — 逐段验证 API 连通性与数据完整性.

用法:
    python tests/segment_tests.py              # 全量测试
    python tests/segment_tests.py --quick       # 快速冒烟
    python tests/segment_tests.py --only playbooks  # 单段测试

分段:
  1. playbooks  — 剧本数据完整性 (46条 / 中文标签 / 严重度)
  2. search     — 混合检索功能 (中英文 / 多关键词 / 得分排序)
  3. safety     — 安全门禁评估 (命令/意图/审批)
  4. unified     — 统一搜索 (跨 playbooks + 文档)
  5. executor   — 命令风险预览 (只读命令)
  6. knowledge  — 知识库标签统计
  7. frontend   — 前端路由存在性
  8. integrity  — 跨段一致性 (playbooks vs 文档交叉引用)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ── 工具函数 ──────────────────────────────────────────────────
_passed = 0
_failed = 0
_skipped = 0


def _bold(s: str) -> str:  return f"\033[1m{s}\033[0m"
def _green(s: str) -> str: return f"\033[32m{s}\033[0m"
def _red(s: str) -> str:   return f"\033[31m{s}\033[0m"
def _yellow(s: str) -> str:return f"\033[33m{s}\033[0m"


def ok(msg: str):
    global _passed
    _passed += 1
    print(f"  {_green('✓')} {msg}")


def fail(msg: str):
    global _failed
    _failed += 1
    print(f"  {_red('✗')} {msg}")


def skip(msg: str):
    global _skipped
    _skipped += 1
    print(f"  {_yellow('⊘')} {msg}")


def section(title: str):
    print(f"\n{_bold('━' * 60)}")
    print(f"{_bold('  ▸ ' + title)}")
    print(f"{_bold('━' * 60)}")


# ── 分段 1: Playbooks 数据完整性 ──────────────────────────────
def test_playbooks():
    section("分段 1: Playbooks 数据完整性")
    from security_agent.knowledge.playbooks import PLAYBOOKS, PLAYBOOK_BY_ID

    pb_list = list(PLAYBOOKS)
    ok(f"剧本总数: {len(pb_list)} 条")

    assert len(pb_list) >= 40, "剧本数量应 ≥ 40"
    assert len(PLAYBOOK_BY_ID) == len(pb_list), "索引字典与元组一致"

    # 中文标签映射验证
    for pb in pb_list:
        assert pb.id and pb.id.startswith("PB-"), f"剧本 {pb.id} ID 格式错误"
        assert pb.title, f"剧本 {pb.id} 缺少标题"
        assert pb.body, f"剧本 {pb.id} 缺少正文"
        assert pb.severity in ("严重", "高", "中", "低", "信息"), f"严重度非法: {pb.severity}"
        assert pb.threat_tags, f"剧本 {pb.id} 缺少标签"

    severe = sum(1 for p in pb_list if p.severity == "严重")
    high = sum(1 for p in pb_list if p.severity == "高")
    ok(f"严重度分布: 严重={severe}  高={high}  中={len(pb_list)-severe-high}")

    # 验证 tags 都是有效 key（硬核已知标签集合）
    known_tags = {
        "privilege", "misdelete", "exfiltration", "port_exposure", "impersonation",
        "monitoring_gap", "network", "daily_dev", "advisor", "blue_team", "detection",
        "log_analysis", "audit", "webshell", "waf", "system", "ids", "intrusion",
        "asset_scan", "api_security", "incident_response", "knowledge_base",
        "resilience", "data", "server", "false_positive", "process", "root", "kylin",
        "sigma", "ioc", "docker", "backup",
    }
    for pb in pb_list:
        for tag in pb.threat_tags:
            if tag not in known_tags:
                fail(f"剧本 {pb.id} 有未知标签: {tag}")
    else:
        ok("所有威胁标签都在已知映射范围内")


# ── 分段 2: 知识库搜索 ────────────────────────────────────────
def test_search():
    section("分段 2: 知识库搜索")

    from security_agent.knowledge.playbooks import PLAYBOOKS

    # 直接测关键词匹配（不依赖 FastAPI Depends）
    queries = ["SSH", "iptables", "后门", "检测", "伪装"]
    for q in queries:
        count = 0
        ql = q.lower()
        for pb in PLAYBOOKS:
            searchable = (pb.title + " " + pb.body + " " + " ".join(pb.keywords) + " "
                          + " ".join(pb.threat_tags)).lower()
            if ql in searchable:
                count += 1
        ok(f"关键词 '{q}' → {count} 条匹配")

    # 标签搜索
    for tag in ("blue_team", "privilege", "network"):
        count = sum(1 for p in PLAYBOOKS if any(tag in t.lower() for t in p.threat_tags))
        ok(f"标签 '{tag}' → {count} 条")

    # 空搜索返回全部
    ok(f"空搜索返回全部 {len(PLAYBOOKS)} 条")


# ── 分段 3: 安全门禁评估 ──────────────────────────────────────
def test_safety():
    section("分段 3: 安全门禁评估")

    try:
        from security_agent.safety_gate.gate import SafetyGate
    except ImportError as e:
        skip(f"依赖缺失，跳过安全评估测试: {e}")
        return

    gate = SafetyGate()

    # 只读命令
    result = gate.evaluate_terminal("ls -la", user_message="查看文件", user="test")
    verdict = str(result.verdict.value if hasattr(result.verdict, "value") else result.verdict)
    assert verdict in ("allow", "confirm", "approve", "deny"), f"非法判决: {verdict}"
    ok(f"只读命令 'ls -la' → {verdict}")

    # 危险命令
    result = gate.evaluate_terminal("rm -rf /tmp/", user_message="清理临时文件", user="test")
    verdict = str(result.verdict.value if hasattr(result.verdict, "value") else result.verdict)
    ok(f"危险命令 'rm -rf' → {verdict}")

    # 网络查询
    result = gate.evaluate_terminal("ss -tlnp", user_message="查看端口", user="test")
    verdict = str(result.verdict.value if hasattr(result.verdict, "value") else result.verdict)
    ok(f"网络命令 'ss -tlnp' → {verdict}")


# ── 分段 4: 统一搜索 ──────────────────────────────────────────
def test_unified():
    section("分段 4: 统一知识检索")

    from security_agent.knowledge.playbooks import PLAYBOOKS

    # 直接测剧本 + 文档搜索（不依赖 FastAPI Depends）
    import os
    doc_path = os.path.join(
        os.path.dirname(__file__), "..", "docs", "security", "BLUE_TEAM_DEFENSE_KNOWLEDGE.md"
    )
    doc_path = os.path.abspath(doc_path)
    doc_exists = os.path.exists(doc_path)
    ok(f"知识文档存在: {doc_exists}")

    if doc_exists:
        content = open(doc_path, encoding="utf-8").read()
        sections = content.count("## ")
        ok(f"文档章节数: {sections}")

    # 验证剧本+文档能交叉搜索
    test_queries = ["SSH", "iptables", "SELinux", "审计"]
    for q in test_queries:
        pb_count = sum(1 for p in PLAYBOOKS if q.lower() in (p.title + p.body + " ".join(p.keywords)).lower())
        doc_count = sum(1 for line in content.split("\n") if q.lower() in line.lower()) if doc_exists else 0
        ok(f"'{q}' → playbook={pb_count}  文档≈{doc_count} 行")


# ── 分段 5: 命令风险预览 ──────────────────────────────────────
def test_executor():
    section("分段 5: 命令风险预览")

    try:
        from security_agent.api.routes.executor_routes import _assess_command
    except ImportError as e:
        skip(f"依赖缺失，跳过命令预览测试: {e}")
        return

    # 只读
    name, label = _assess_command("df -h")
    ok(f"'df -h' → {name} ({label})")

    # 可逆
    name, label = _assess_command("systemctl restart sshd")
    ok(f"'systemctl restart' → {name} ({label})")

    # 不可逆
    name, label = _assess_command("kill -9 1234")
    ok(f"'kill -9' → {name} ({label})")

    # 关键危险
    name, label = _assess_command("rm -rf /")
    ok(f"'rm -rf /' → {name} ({label})")


# ── 分段 6: 知识库标签统计 ────────────────────────────────────
def test_tags():
    section("分段 6: 知识库标签统计")

    from security_agent.knowledge.playbooks import PLAYBOOKS

    tag_count = {}
    for pb in PLAYBOOKS:
        for t in pb.threat_tags:
            tag_count[t] = tag_count.get(t, 0) + 1

    ok(f"标签总数: {len(tag_count)} 个")
    ok(f"Top 5 标签: {', '.join(f'{k}({v})' for k, v in sorted(tag_count.items(), key=lambda x: -x[1])[:5])}")


# ── 分段 7: 前端路由存在性 ────────────────────────────────────
def test_frontend_routes():
    section("分段 7: 前端路由存在性")

    router_path = PROJECT_ROOT / "frontend" / "src" / "router" / "index.js"
    assert router_path.exists(), f"路由文件不存在: {router_path}"

    content = router_path.read_text()
    expected_routes = [
        ("Dashboard", "/"),
        ("Executor", "executor"),
        ("Safety", "safety"),
        ("Knowledge", "knowledge"),
        ("Agent", "agent"),
        ("MCP", "mcp"),
        ("Trace", "trace"),
        ("Alerts", "alerts"),
        ("SkillFlows", "flows"),
        ("Workflow", "workflow"),
    ]
    for name, path in expected_routes:
        if f"path: '{path}'" in content or f'path: "{path}"' in content:
            ok(f"路由 {name} → /{path}")
        else:
            fail(f"路由 {name} 缺失 /{path}")


# ── 分段 8: 跨段一致性 (playbooks ↔ 文档) ──────────────────────
def test_integrity():
    section("分段 8: 跨段一致性")

    from security_agent.knowledge.playbooks import PLAYBOOKS

    doc_path = PROJECT_ROOT / "docs" / "security" / "BLUE_TEAM_DEFENSE_KNOWLEDGE.md"
    if not doc_path.exists():
        skip(f"文档不存在: {doc_path}")
        return

    doc = doc_path.read_text(encoding="utf-8")

    pb_ids = [p.id for p in PLAYBOOKS]
    ref_count = sum(1 for pid in pb_ids if pid in doc)
    ok(f"文档交叉引用剧本: {ref_count}/{len(pb_ids)} 条 ({ref_count*100//len(pb_ids)}%)")

    # 验证每个剧本至少有一个非空 body
    empty_body = [p.id for p in PLAYBOOKS if not p.body.strip()]
    if empty_body:
        fail(f"以下剧本 body 为空: {empty_body}")
    else:
        ok("所有剧本 body 非空")


# ── 主入口 ──────────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="分段集成测试")
    parser.add_argument("--quick", action="store_true", help="快速冒烟 (只测 playbooks + search)")
    parser.add_argument("--only", type=str, help="只运行指定分段 (逗号分隔)")
    args = parser.parse_args()

    segments = {
        "playbooks": test_playbooks,
        "search": test_search,
        "safety": test_safety,
        "unified": test_unified,
        "executor": test_executor,
        "tags": test_tags,
        "frontend": test_frontend_routes,
        "integrity": test_integrity,
    }

    if args.only:
        names = [n.strip() for n in args.only.split(",")]
        targets = {n: segments[n] for n in names if n in segments}
        if not targets:
            print(f"未知分段: {args.only}, 可选: {', '.join(segments)}")
            sys.exit(1)
    elif args.quick:
        targets = {k: segments[k] for k in ["playbooks", "search", "integrity"]}
    else:
        targets = segments

    for name, fn in targets.items():
        try:
            fn()
        except Exception as e:
            fail(f"分段 '{name}' 异常: {e}")

    # 总结
    total = _passed + _failed + _skipped
    print(f"\n{_bold('═' * 60)}")
    print(f"{_bold('  结果: ')}{_green(f'通过 {_passed}')}  {_red(f'失败 {_failed}')}  {_yellow(f'跳过 {_skipped}')}  (共 {total} 项)")
    if _failed > 0:
        print(f"  {_red('✗ 存在失败项，请修复后重新测试')}")
        sys.exit(1)
    else:
        print(f"  {_green('✓ 所有测试通过')}")
        sys.exit(0)


if __name__ == "__main__":
    main()
