"""深度研究 Skill — 多源信息聚合与安全分析.

功能:
- CVE 漏洞深度研究（NVD API + 知识库关联）
- 安全威胁情报查询
- 蓝队知识库深度检索
- 系统配置合规性分析
- 生成研究报告
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from security_agent.skills.base import SkillBase, SkillMeta, ToolDef

logger = logging.getLogger(__name__)

REPORT_DIR = Path("data/research")


class DeepResearchSkill(SkillBase):
    """深度研究 — 多源安全信息聚合与分析."""

    def __init__(self):
        REPORT_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="deep_research",
            display_name="深度研究",
            description="CVE 漏洞研究、威胁情报查询、蓝队知识库检索、合规分析、研究报告生成",
            version="1.0.0",
            tags=("research", "cve", "threat-intel", "compliance", "ai"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="research_cve",
                description="深度研究 CVE 漏洞：查 NVD 数据库 + 知识库关联 + 影响评估",
                parameters={
                    "type": "object",
                    "properties": {
                        "cve_id": {"type": "string", "description": "CVE 编号，如 CVE-2024-6387"},
                    },
                    "required": ["cve_id"],
                },
                handler=self.research_cve,
            ),
            ToolDef(
                name="research_threat",
                description="安全威胁情报查询：关键词检索多源情报（知识库 + 蓝队规则 + Sigma 规则）",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "威胁关键词，如 'SSH 暴力破解'、'挖矿木马'"},
                    },
                    "required": ["query"],
                },
                handler=self.research_threat,
            ),
            ToolDef(
                name="research_compliance",
                description="系统配置合规性分析（安全基线检查）",
                parameters={
                    "type": "object",
                    "properties": {
                        "scope": {
                            "type": "string",
                            "description": "检查范围",
                            "enum": ["ssh", "network", "file_perms", "services", "all"],
                            "default": "all",
                        },
                    },
                    "required": [],
                },
                handler=self.research_compliance,
            ),
            ToolDef(
                name="research_generate_report",
                description="生成深度研究报告（整合所有研究成果，输出 Markdown 报告）",
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "研究主题"},
                        "include_cve": {"type": "boolean", "description": "是否包含 CVE 分析", "default": True},
                        "include_compliance": {"type": "boolean", "description": "是否包含合规分析", "default": True},
                    },
                    "required": ["topic"],
                },
                handler=self.generate_report,
            ),
        ]

    async def research_cve(self, cve_id: str) -> str:
        """研究 CVE 漏洞."""
        import subprocess

        result: dict[str, Any] = {"cve_id": cve_id, "sources": [], "timestamp": time.time()}

        # 1. 从 NVD API 查询
        try:
            proc = subprocess.run(
                ["curl", "-s", "--max-time", "10",
                 f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"],
                capture_output=True, text=True, timeout=15,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                data = json.loads(proc.stdout)
                vulns = data.get("vulnerabilities", [])
                if vulns:
                    cve_data = vulns[0].get("cve", {})
                    desc_list = cve_data.get("descriptions", [])
                    desc = next((d["value"] for d in desc_list if d.get("lang") == "en"), "")
                    metrics = cve_data.get("metrics", {})
                    cvss = "未知"
                    for key in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
                        if key in metrics and metrics[key]:
                            cvss_data = metrics[key][0].get("cvssData", {})
                            cvss = f"{cvss_data.get('baseScore', '?')} ({cvss_data.get('baseSeverity', '?')})"
                            break
                    result["sources"].append({
                        "source": "NVD",
                        "description": desc[:500],
                        "cvss": cvss,
                        "published": cve_data.get("published", ""),
                    })
        except Exception as e:
            result["sources"].append({"source": "NVD", "error": str(e)})

        # 2. 本地知识库关联
        try:
            from security_agent.retrieval.hybrid import search_knowledge
            hits = search_knowledge(cve_id, top_k=3)
            if hits:
                result["knowledge_matches"] = [
                    {"title": h["title"], "score": h["score"], "excerpt": h["excerpt"][:200]}
                    for h in hits
                ]
        except Exception as e:
            result["knowledge_matches"] = [{"error": str(e)}]

        # 3. Sigma 规则关联
        result["sigma_rules"] = self._search_sigma_rules(cve_id)

        if not result["sources"]:
            result["sources"].append({"source": "local", "note": "NVD 查询失败，仅提供本地分析"})

        return json.dumps(result, ensure_ascii=False, default=str)

    async def research_threat(self, query: str) -> str:
        """多源威胁情报查询."""
        result: dict[str, Any] = {"query": query, "timestamp": time.time()}

        # 1. 知识库检索
        try:
            from security_agent.retrieval.hybrid import search_knowledge
            hits = search_knowledge(query, top_k=5)
            result["knowledge_base"] = [
                {"title": h["title"], "score": h["score"], "excerpt": h["excerpt"][:300]}
                for h in hits
            ]
        except Exception as e:
            result["knowledge_base"] = [{"error": str(e)}]

        # 2. Sigma 规则
        result["sigma_rules"] = self._search_sigma_rules(query)

        # 3. 蓝队 playbook
        try:
            from security_agent.knowledge.playbooks import get_playbooks_by_threat
            playbooks = get_playbooks_by_threat(query)
            result["playbooks"] = [
                {"name": p.name, "steps_count": len(p.steps)} for p in playbooks[:3]
            ]
        except Exception:
            result["playbooks"] = []

        # 4. 汇总
        total_sources = sum(
            len(v) for v in result.values() if isinstance(v, list)
        )
        result["summary"] = f"共找到 {total_sources} 条关联信息"

        return json.dumps(result, ensure_ascii=False, default=str)

    async def research_compliance(self, scope: str = "all") -> str:
        """系统合规性检查."""
        import subprocess

        checks: list[dict[str, Any]] = []

        def _run_check(name: str, cmd: str, pass_cond: str = ""):
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                checks.append({
                    "check": name,
                    "output": r.stdout.strip()[:300],
                    "ok": r.returncode == 0,
                })
            except Exception as e:
                checks.append({"check": name, "error": str(e), "ok": False})

        if scope in ("ssh", "all"):
            _run_check("SSH 密码认证", "grep -E '^PasswordAuthentication' /etc/ssh/sshd_config 2>/dev/null || echo '未配置'")
            _run_check("SSH Root 登录", "grep -E '^PermitRootLogin' /etc/ssh/sshd_config 2>/dev/null || echo '未配置'")
            _run_check("SSH 空密码", "grep -E '^PermitEmptyPasswords' /etc/ssh/sshd_config 2>/dev/null || echo '未配置'")

        if scope in ("network", "all"):
            _run_check("监听端口列表", "ss -tlnp 2>/dev/null | head -20 || netstat -tlnp | head -20")
            _run_check("防火墙状态", "ufw status 2>/dev/null || iptables -L -n 2>/dev/null | head -10")

        if scope in ("file_perms", "all"):
            _run_check("关键目录权限", "ls -ld /etc /var/log /root 2>/dev/null")
            _run_check("SUID 文件检查", "find / -perm -4000 -type f 2>/dev/null | head -10")

        if scope in ("services", "all"):
            _run_check("不必要的服务", "systemctl list-units --type=service --state=running 2>/dev/null | head -15")
            _run_check("内核参数", "sysctl net.ipv4.ip_forward net.ipv4.conf.all.accept_redirects 2>/dev/null")

        passed = sum(1 for c in checks if c.get("ok"))
        total = len(checks)

        return json.dumps({
            "scope": scope,
            "total_checks": total,
            "passed": passed,
            "failed": total - passed,
            "compliance_rate": f"{passed * 100 // total}%" if total else "N/A",
            "checks": checks,
        }, ensure_ascii=False, default=str)

    async def generate_report(self, topic: str, include_cve: bool = True,
                              include_compliance: bool = True) -> str:
        """生成深度研究报告."""
        report_parts = [f"# 深度安全研究报告: {topic}\n"]
        report_parts.append(f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 威胁情报
        threat_data = json.loads(await self.research_threat(topic))
        report_parts.append("## 1. 威胁情报分析\n")
        for item in threat_data.get("knowledge_base", [])[:3]:
            if "title" in item:
                report_parts.append(f"- **{item['title']}**: {item.get('excerpt', '')[:150]}")
        report_parts.append("")

        # CVE
        if include_cve:
            report_parts.append("## 2. 相关漏洞分析\n")
            report_parts.append("通过知识库和 Sigma 规则关联的安全漏洞：\n")
            for rule in threat_data.get("sigma_rules", [])[:5]:
                report_parts.append(f"- {rule.get('title', 'N/A')}: {rule.get('description', '')[:100]}")
            report_parts.append("")

        # 合规检查
        if include_compliance:
            compliance = json.loads(await self.research_compliance("all"))
            report_parts.append("## 3. 系统合规检查\n")
            report_parts.append(f"合规率: {compliance['compliance_rate']} "
                                f"({compliance['passed']}/{compliance['total_checks']})\n")
            for check in compliance.get("checks", []):
                status = "✅" if check.get("ok") else "⚠️"
                report_parts.append(f"- {status} {check['check']}")
            report_parts.append("")

        report_parts.append("## 4. 建议措施\n")
        report_parts.append("1. 及时更新受影响组件版本")
        report_parts.append("2. 检查并加固系统安全配置")
        report_parts.append("3. 启用监控告警与日志审计")
        report_parts.append("4. 参考知识库中的应急响应预案")

        report_text = "\n".join(report_parts)

        # 保存报告
        safe_topic = topic.replace("/", "_").replace(" ", "_")[:30]
        report_path = REPORT_DIR / f"report_{safe_topic}_{int(time.time())}.md"
        report_path.write_text(report_text, "utf-8")

        return json.dumps({
            "ok": True,
            "topic": topic,
            "report_path": str(report_path),
            "report_preview": report_text[:2000],
            "total_lines": len(report_text.split("\n")),
        }, ensure_ascii=False)

    def _search_sigma_rules(self, query: str) -> list[dict[str, Any]]:
        """在 Sigma 规则中搜索匹配."""
        results = []
        try:
            from security_agent.rules import sigma_loader
            rules = sigma_loader.load_rules()
            query_lower = query.lower()
            for rule in rules[:100]:  # 限制扫描量
                title = rule.get("title", "").lower()
                desc = rule.get("description", "").lower()
                if query_lower in title or query_lower in desc:
                    results.append({
                        "title": rule.get("title", ""),
                        "level": rule.get("level", ""),
                        "description": rule.get("description", "")[:150],
                    })
                if len(results) >= 5:
                    break
        except Exception:
            pass
        return results

    def get_rules(self) -> list[str]:
        return [
            "深度研究: 处理未知威胁时应先查询知识库和情报源，不要凭经验猜测",
            "CVE 优先级: CVSS >= 9.0 的 CVE 应立即处理，7.0-8.9 应在24小时内处理",
            "合规检查: 关键系统应每周执行一次安全基线检查",
            "研究报告: 重大安全事件应生成研究报告存档",
        ]


# ---- 全局实例 ----
skill_instance = DeepResearchSkill()
