"""网络运维技能 — 端口扫描、连接分析、防火墙管理、DNS 检查."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from security_agent.skills.base import SkillBase, SkillMeta, ToolDef


class NetworkOpsSkill(SkillBase):
    """网络运维 Skill — 端口扫描、连接分析、防火墙规则查看、DNS 检查."""

    name = "network_ops"
    display_name = "网络运维"

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="network_ops",
            display_name="网络运维",
            description="端口扫描、连接分析、防火墙管理、DNS 检查",
            version="1.0.0",
            tags=("network", "ports", "firewall", "dns", "ops"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="net_scan_ports",
                description="扫描本地监听端口：TCP/UDP 端口列表、进程信息、暴露端口检测",
                parameters={
                    "type": "object",
                    "properties": {"host": {"type": "string", "description": "目标主机", "default": "127.0.0.1"}},
                    "required": [],
                },
                handler=self._scan_ports,
            ),
            ToolDef(
                name="net_analyze_connections",
                description="分析网络连接：状态分布、ESTABLISHED 比例、高频外部 IP、可疑连接",
                parameters={
                    "type": "object",
                    "properties": {"min_count": {"type": "integer", "description": "高频阈值", "default": 10}},
                    "required": [],
                },
                handler=self._analyze_connections,
            ),
            ToolDef(
                name="net_firewall_status",
                description="检查防火墙状态：iptables + ufw + firewalld",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._firewall_status,
            ),
            ToolDef(
                name="net_firewall_rules",
                description="列出 iptables 防火墙规则（只读）",
                parameters={
                    "type": "object",
                    "properties": {"table": {"type": "string", "enum": ["filter", "nat", "mangle"], "default": "filter"}},
                    "required": [],
                },
                handler=self._firewall_rules,
            ),
            ToolDef(
                name="net_check_dns",
                description="检查域名 DNS 解析",
                parameters={
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string", "description": "域名"},
                        "nameserver": {"type": "string", "description": "指定 DNS", "default": ""},
                    },
                    "required": ["domain"],
                },
                handler=self._check_dns,
            ),
        ]

    def get_playbooks(self) -> list:
        return []

    def get_rules(self) -> list[str]:
        return ["检测 0.0.0.0 暴露端口", "ESTABLISHED 连接占比 < 30% 告警"]

    async def on_alert(self, event: dict[str, Any]) -> dict[str, Any] | None:
        if event.get("type") == "exposed_port":
            return {"skill": "network_ops", "action": "review_firewall", "message": f"端口 {event.get('port')} 暴露在 0.0.0.0"}
        return None

    async def healthcheck(self) -> dict[str, Any]:
        return {"status": "ok", "skill": "network_ops"}

    # ---- Handlers ----

    async def _scan_ports(self, host: str = "127.0.0.1") -> str:
        results = []
        try:
            out = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=10)
            for line in out.stdout.split("\n")[1:]:
                parts = line.split()
                if len(parts) < 4:
                    continue
                state, local = parts[0], parts[3] if len(parts) > 3 else ""
                process = parts[-1] if len(parts) >= 6 else ""
                if ":" in local:
                    addr, port_str = local.rsplit(":", 1)
                    try:
                        port = int(port_str)
                    except ValueError:
                        continue
                    results.append({"port": port, "protocol": "tcp", "state": state, "address": addr, "process": process[:100]})
            out2 = subprocess.run(["ss", "-ulnp"], capture_output=True, text=True, timeout=10)
            for line in out2.stdout.split("\n")[1:]:
                parts = line.split()
                if len(parts) < 4:
                    continue
                local = parts[3] if len(parts) > 3 else ""
                process = parts[-1] if len(parts) >= 6 else ""
                if ":" in local:
                    addr, port_str = local.rsplit(":", 1)
                    try:
                        port = int(port_str)
                    except ValueError:
                        continue
                    results.append({"port": port, "protocol": "udp", "state": "listen", "address": addr, "process": process[:100]})
            exposed = [r for r in results if r.get("address") in ("0.0.0.0", "*", "::") and r["port"] in (22, 23, 3389, 5432, 6379, 27017, 3306)]
            return json.dumps({"host": host, "total_open": len(results), "exposed_ports": exposed, "ports": sorted(results, key=lambda x: x["port"])}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _analyze_connections(self, min_count: int = 10) -> str:
        try:
            out = subprocess.run(["ss", "-tan"], capture_output=True, text=True, timeout=10)
            states, ips = {}, {}
            for line in out.stdout.split("\n")[1:]:
                parts = line.split()
                if len(parts) < 5:
                    continue
                state = parts[0]
                states[state] = states.get(state, 0) + 1
                peer = parts[4] if len(parts) > 4 else ""
                if ":" in peer:
                    ip = peer.rsplit(":", 1)[0]
                    if ip not in ("0.0.0.0", "*", "127.0.0.1", "::1", "::"):
                        ips[ip] = ips.get(ip, 0) + 1
            total = sum(states.values()) or 1
            high_freq = sorted([(ip, cnt) for ip, cnt in ips.items() if cnt >= min_count], key=lambda x: -x[1])[:10]
            suspicious = [{"ip": ip, "count": cnt} for ip, cnt in high_freq if cnt >= 50]
            return json.dumps({
                "total": total, "state_distribution": states,
                "established_pct": round(states.get("ESTAB", 0) / total * 100, 1),
                "high_frequency": [{"ip": ip, "count": cnt} for ip, cnt in high_freq],
                "suspicious": suspicious,
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _firewall_status(self) -> str:
        result = {}
        try:
            out = subprocess.run(["iptables", "-L", "INPUT", "-n"], capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                policy = "UNKNOWN"
                for line in out.stdout.split("\n"):
                    if "Chain INPUT (policy" in line:
                        policy = line.split("policy")[1].strip().rstrip(")")
                        break
                result["iptables"] = {"active": True, "input_policy": policy}
            else:
                result["iptables"] = {"active": False}
        except FileNotFoundError:
            result["iptables"] = {"active": False}
        try:
            out = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=5)
            result["ufw"] = {"active": "active" in out.stdout.lower()}
        except FileNotFoundError:
            result["ufw"] = {"active": False}
        try:
            out = subprocess.run(["firewall-cmd", "--state"], capture_output=True, text=True, timeout=5)
            result["firewalld"] = {"active": out.returncode == 0}
        except FileNotFoundError:
            result["firewalld"] = {"active": False}
        return json.dumps({"firewalls": result}, ensure_ascii=False, indent=2)

    async def _firewall_rules(self, table: str = "filter") -> str:
        try:
            out = subprocess.run(["iptables", "-t", table, "-L", "-n", "-v"], capture_output=True, text=True, timeout=10)
            if out.returncode != 0:
                return json.dumps({"error": out.stderr.strip()}, ensure_ascii=False)
            rules = [{"raw": line.strip()} for line in out.stdout.split("\n") if line.strip() and not line.startswith("Chain")]
            return json.dumps({"table": table, "count": len(rules), "rules": rules[:50]}, ensure_ascii=False, indent=2)
        except FileNotFoundError:
            return json.dumps({"error": "iptables 未安装"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _check_dns(self, domain: str, nameserver: str = "") -> str:
        try:
            cmd = ["nslookup", domain]
            if nameserver:
                cmd = ["nslookup", domain, nameserver]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            addresses = list(set(re.findall(r"Address:\s*(\d+\.\d+\.\d+\.\d+)", out.stdout)))
            return json.dumps({"domain": domain, "resolved": len(addresses) > 0, "addresses": addresses}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"domain": domain, "error": str(e)}, ensure_ascii=False)


skill_instance = NetworkOpsSkill()
