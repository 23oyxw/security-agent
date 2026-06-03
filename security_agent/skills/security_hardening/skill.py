"""安全加固 Skill — SSH 审计、防火墙管理、漏洞扫描、基线合规检查."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from security_agent import config
from security_agent.skills.base import SkillBase, SkillMeta, ToolDef
from security_agent.security.redact import redact_text
from security_agent.timeutil import now_iso


# ---- SSH 安全检查项 ----
SSH_CHECKS: dict[str, dict[str, Any]] = {
    "root_login": {
        "key": "PermitRootLogin",
        "expected": "no",
        "severity": "严重",
        "description": "禁止 root 直接 SSH 登录",
    },
    "password_auth": {
        "key": "PasswordAuthentication",
        "expected": "no",
        "severity": "高",
        "description": "建议禁用密码认证，仅用密钥",
    },
    "empty_passwords": {
        "key": "PermitEmptyPasswords",
        "expected": "no",
        "severity": "严重",
        "description": "禁止空密码登录",
    },
    "x11_forwarding": {
        "key": "X11Forwarding",
        "expected": "no",
        "severity": "低",
        "description": "关闭 X11 转发减少攻击面",
    },
    "max_auth_tries": {
        "key": "MaxAuthTries",
        "expected": "3",
        "severity": "中",
        "description": "限制最大认证尝试次数",
        "check": lambda v: int(v) <= 4,
    },
    "protocol": {
        "key": "Protocol",
        "expected": "2",
        "severity": "严重",
        "description": "仅使用 SSH 协议 v2",
        "optional": True,  # OpenSSH 7.4+ 默认 v2，可能不显式配置
    },
    "client_alive_interval": {
        "key": "ClientAliveInterval",
        "expected": "300",
        "severity": "低",
        "description": "设置客户端保活间隔",
        "check": lambda v: int(v) > 0,
    },
    "login_grace_time": {
        "key": "LoginGraceTime",
        "expected": "60",
        "severity": "中",
        "description": "限制登录超时时间",
        "check": lambda v: int(v) <= 120,
    },
}


def _run_cmd(cmd: str, timeout: int = 10) -> tuple[int, str, str]:
    """执行 shell 命令，返回 (exit_code, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as exc:
        return -1, "", str(exc)


def _parse_sshd_config(path: str = "/etc/ssh/sshd_config") -> dict[str, str]:
    """解析 sshd_config，返回 key-value 字典."""
    config_map: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return config_map
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                config_map[parts[0]] = parts[1]
    except (PermissionError, OSError):
        pass
    return config_map


def _check_authorized_keys() -> list[dict[str, Any]]:
    """检查 authorized_keys 文件."""
    issues: list[dict[str, Any]] = []
    key_files = [
        "/root/.ssh/authorized_keys",
        "/home/*/.ssh/authorized_keys",
    ]
    import glob

    for pattern in key_files:
        for path in glob.glob(pattern):
            p = Path(path)
            if not p.exists():
                continue
            try:
                stat = p.stat()
                mode = oct(stat.st_mode)[-3:]
                if mode not in ("600", "644"):
                    issues.append({
                        "file": path,
                        "issue": f"权限 {mode}，应为 600 或 644",
                        "severity": "高",
                    })
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                non_empty = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
                if not non_empty:
                    issues.append({
                        "file": path,
                        "issue": "authorized_keys 文件存在但为空",
                        "severity": "低",
                    })
                # 检查弱密钥类型
                for line in non_empty:
                    parts = line.split()
                    if len(parts) >= 2:
                        key_type = parts[0]
                        if key_type in ("ssh-rsa", "ssh-dss"):
                            issues.append({
                                "file": path,
                                "issue": f"使用较弱的密钥类型: {key_type}，建议 ed25519 或 ecdsa",
                                "severity": "中",
                            })
            except (PermissionError, OSError):
                continue
    return issues


class SecurityHardeningSkill(SkillBase):
    """安全加固 Skill — SSH 审计、防火墙审查、漏洞扫描、基线合规."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="security_hardening",
            display_name="安全加固",
            description="SSH 安全审计、防火墙规则审查、漏洞扫描、CIS 基线合规检查",
            version="1.0.0",
            tags=("hardening", "ssh", "firewall", "vulnerability", "compliance"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="hardening_ssh_audit",
                description="SSH 安全审计：检查 sshd_config 配置、authorized_keys 权限、弱密钥类型",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_ssh_audit,
            ),
            ToolDef(
                name="hardening_firewall_audit",
                description="防火墙规则审查：iptables/nftables/ufw 当前规则与安全建议",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_firewall_audit,
            ),
            ToolDef(
                name="hardening_vulnerability_scan",
                description="漏洞扫描：检查系统包更新、已知 CVE、过期软件",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_vulnerability_scan,
            ),
            ToolDef(
                name="hardening_baseline_check",
                description="CIS 基线合规检查：文件权限、用户账户、服务配置等",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_baseline_check,
            ),
            ToolDef(
                name="hardening_full_scan",
                description="综合安全加固扫描：SSH + 防火墙 + 漏洞 + 基线一键检查",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_full_scan,
            ),
        ]

    def get_rules(self) -> list[str]:
        return [
            "安全加固扫描为只读操作，不修改任何配置",
            "加固建议需说明影响范围和操作步骤，不自动执行",
            "涉及 SSH/防火墙配置变更必须人工确认",
        ]

    def get_playbooks(self):
        from security_agent.knowledge.playbooks import Playbook

        return [
            Playbook(
                "HB-SSH-01",
                "SSH 安全配置基线",
                "PermitRootLogin=no, PasswordAuthentication=no, MaxAuthTries≤3, "
                "仅允许 ed25519/ecdsa 密钥，禁用 X11Forwarding。",
                ("privilege", "port_exposure"),
                "高",
                True,
                ("ssh", "sshd", "密钥", "登录"),
                ("直接修改 sshd_config 不重启验证",),
                ("备份 sshd_config", "改后 systemctl reload sshd", "保持一个已登录会话"),
            ),
            Playbook(
                "HB-FW-01",
                "防火墙最小放行原则",
                "仅开放业务必需端口，默认拒绝所有入站；0.0.0.0 监听的数据库端口应改为 127.0.0.1。",
                ("port_exposure",),
                "高",
                False,
                ("防火墙", "iptables", "nftables", "ufw"),
                ("iptables -F 清空所有规则",),
                ("先记录现有规则", "逐步收紧", "保留 SSH 端口"),
            ),
        ]

    # ---- SSH 审计 ----

    def ssh_audit(self) -> dict[str, Any]:
        """SSH 安全审计."""
        issues: list[dict[str, Any]] = []
        sshd_config = _parse_sshd_config()

        for check_id, check in SSH_CHECKS.items():
            key = check["key"]
            if key not in sshd_config:
                if not check.get("optional"):
                    issues.append({
                        "check": check_id,
                        "key": key,
                        "status": "未配置",
                        "severity": check["severity"],
                        "description": check["description"],
                        "recommendation": f"建议设置 {key} = {check['expected']}",
                    })
                continue

            value = sshd_config[key]
            custom_check = check.get("check")
            if custom_check:
                try:
                    ok = custom_check(value)
                except (ValueError, TypeError):
                    ok = False
            else:
                ok = value.lower() == check["expected"].lower()

            if not ok:
                issues.append({
                    "check": check_id,
                    "key": key,
                    "current_value": value,
                    "expected": check["expected"],
                    "status": "不合规",
                    "severity": check["severity"],
                    "description": check["description"],
                    "recommendation": f"将 {key} 从 {value} 改为 {check['expected']}",
                })

        # authorized_keys 检查
        key_issues = _check_authorized_keys()
        issues.extend(key_issues)

        # SSH 服务状态
        ssh_running = False
        try:
            for proc in psutil.process_iter(["name"]):
                if proc.info.get("name") in ("sshd", "sshd-session"):
                    ssh_running = True
                    break
        except Exception:
            pass

        return {
            "timestamp": now_iso(),
            "ssh_running": ssh_running,
            "config_path": "/etc/ssh/sshd_config",
            "config_parsed": bool(sshd_config),
            "total_checks": len(SSH_CHECKS),
            "issues": issues,
            "issue_count": len(issues),
            "critical_count": sum(1 for i in issues if i.get("severity") == "严重"),
        }

    # ---- 防火墙审计 ----

    def firewall_audit(self) -> dict[str, Any]:
        """防火墙规则审查."""
        results: dict[str, Any] = {
            "timestamp": now_iso(),
            "firewall_type": "unknown",
            "rules": [],
            "issues": [],
        }

        # 检测防火墙类型
        fw_type, rules_output = _detect_firewall()
        results["firewall_type"] = fw_type
        results["rules_raw"] = rules_output[:3000]

        # 检查暴露端口
        exposed = []
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == "LISTEN" and conn.laddr:
                    ip = conn.laddr.ip
                    port = conn.laddr.port
                    if ip in ("0.0.0.0", "::"):
                        exposed.append({
                            "port": port,
                            "bind": ip,
                            "pid": conn.pid,
                            "risky": port in config.EXPOSED_RISKY_PORTS,
                        })
        except psutil.AccessDenied:
            results["issues"].append({"issue": "权限不足，无法查看完整网络连接", "severity": "中"})

        results["exposed_ports"] = exposed
        risky_exposed = [p for p in exposed if p["risky"]]
        if risky_exposed:
            results["issues"].append({
                "issue": f"发现 {len(risky_exposed)} 个高危端口对外暴露",
                "severity": "严重",
                "ports": [p["port"] for p in risky_exposed],
                "recommendation": "将绑定地址改为 127.0.0.1 或通过防火墙限制来源 IP",
            })

        # 基本规则分析
        if fw_type == "none":
            results["issues"].append({
                "issue": "未检测到活跃的防火墙",
                "severity": "高",
                "recommendation": "建议启用 ufw 或 iptables 基本规则",
            })

        return results

    # ---- 漏洞扫描 ----

    def vulnerability_scan(self) -> dict[str, Any]:
        """漏洞扫描 — 检查系统包更新和已知问题."""
        vulns: list[dict[str, Any]] = []

        # 1. 检查可更新的安全包
        rc, out, err = _run_cmd("apt list --upgradable 2>/dev/null | head -50", timeout=30)
        if rc == 0 and out:
            lines = [l.strip() for l in out.splitlines() if l.strip() and "Listing..." not in l]
            security_updates = [l for l in lines if "security" in l.lower() or "-security" in l.lower()]
            if security_updates:
                vulns.append({
                    "type": "安全更新",
                    "severity": "高",
                    "count": len(security_updates),
                    "details": security_updates[:10],
                    "recommendation": "执行 apt upgrade 更新安全补丁",
                })
            if lines:
                vulns.append({
                    "type": "可用更新",
                    "severity": "中",
                    "count": len(lines),
                    "details": lines[:10],
                })

        # 2. 检查过期 Python 包
        rc, out, err = _run_cmd("pip list --outdated 2>/dev/null | head -20", timeout=15)
        if rc == 0 and out:
            lines = [l.strip() for l in out.splitlines() if l.strip() and "---" not in l and "Package" not in l]
            if lines:
                vulns.append({
                    "type": "过期 Python 包",
                    "severity": "低",
                    "count": len(lines),
                    "details": lines[:10],
                })

        # 3. 检查 SUID/SGID 异常文件
        rc, out, err = _run_cmd(
            "find / -perm /6000 -type f 2>/dev/null | head -30", timeout=15
        )
        suid_files = []
        if rc == 0 and out:
            suid_files = [l.strip() for l in out.splitlines() if l.strip()]
            # 检查非标准路径下的 SUID 文件
            suspicious_suid = [
                f for f in suid_files
                if not any(f.startswith(p) for p in ("/usr/bin", "/usr/sbin", "/usr/lib", "/bin", "/sbin"))
            ]
            if suspicious_suid:
                vulns.append({
                    "type": "可疑 SUID 文件",
                    "severity": "高",
                    "count": len(suspicious_suid),
                    "details": suspicious_suid[:10],
                    "recommendation": "检查非标准路径下的 SUID 文件是否合法",
                })

        # 4. 检查 /tmp 下可疑文件
        rc, out, err = _run_cmd(
            "find /tmp -type f -executable 2>/dev/null | head -10", timeout=10
        )
        if rc == 0 and out:
            tmp_exec = [l.strip() for l in out.splitlines() if l.strip()]
            if tmp_exec:
                vulns.append({
                    "type": "/tmp 可执行文件",
                    "severity": "中",
                    "count": len(tmp_exec),
                    "details": tmp_exec[:10],
                    "recommendation": "检查 /tmp 下可执行文件是否为恶意程序",
                })

        # 5. 检查内核版本
        rc, out, _ = _run_cmd("uname -r")
        kernel = out if rc == 0 else "unknown"

        return {
            "timestamp": now_iso(),
            "kernel": kernel,
            "vulnerabilities": vulns,
            "total_issues": len(vulns),
            "critical_count": sum(1 for v in vulns if v.get("severity") in ("严重", "高")),
        }

    # ---- 基线合规检查 ----

    def baseline_check(self) -> dict[str, Any]:
        """CIS 基线合规检查."""
        checks: list[dict[str, Any]] = []

        # 1. 关键文件权限
        critical_files = {
            "/etc/passwd": {"expected_mode": "644", "description": "用户信息文件"},
            "/etc/shadow": {"expected_mode": "640", "description": "密码哈希文件"},
            "/etc/group": {"expected_mode": "644", "description": "组信息文件"},
            "/etc/gshadow": {"expected_mode": "640", "description": "组密码文件"},
            "/etc/ssh/sshd_config": {"expected_mode": "600", "description": "SSH 配置文件"},
        }
        for path, info in critical_files.items():
            p = Path(path)
            if not p.exists():
                continue
            try:
                mode = oct(p.stat().st_mode)[-3:]
                ok = mode == info["expected_mode"]
                checks.append({
                    "category": "文件权限",
                    "item": path,
                    "current": mode,
                    "expected": info["expected_mode"],
                    "status": "合规" if ok else "不合规",
                    "severity": "高" if not ok else "信息",
                    "description": info["description"],
                })
            except (PermissionError, OSError):
                checks.append({
                    "category": "文件权限",
                    "item": path,
                    "status": "无法检查",
                    "severity": "低",
                })

        # 2. 用户账户检查
        try:
            with open("/etc/passwd") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) < 7:
                        continue
                    username, _, uid, _, _, _, shell = parts
                    uid = int(uid)
                    # 检查 UID=0 的非 root 用户
                    if uid == 0 and username != "root":
                        checks.append({
                            "category": "用户账户",
                            "item": username,
                            "status": "不合规",
                            "severity": "严重",
                            "description": f"非 root 用户 {username} 拥有 UID=0（超级用户权限）",
                        })
                    # 检查空密码（需要读 shadow，可能无权限）
                    # 检查无效 shell
                    if shell in ("/bin/false", "/usr/sbin/nologin"):
                        continue  # 正常
        except (PermissionError, OSError):
            checks.append({"category": "用户账户", "item": "/etc/passwd", "status": "无法读取", "severity": "低"})

        # 3. 服务检查
        risky_services = ["telnet", "rsh", "rlogin", "vsftpd", "tftp"]
        for svc in risky_services:
            rc, out, _ = _run_cmd(f"systemctl is-active {svc} 2>/dev/null")
            if rc == 0 and "active" in out:
                checks.append({
                    "category": "服务配置",
                    "item": svc,
                    "status": "不合规",
                    "severity": "高",
                    "description": f"高风险服务 {svc} 正在运行",
                    "recommendation": f"systemctl stop {svc} && systemctl disable {svc}",
                })

        # 4. 内核安全参数
        sysctl_checks = {
            "net.ipv4.ip_forward": {"expected": "0", "desc": "IP 转发（非路由器应关闭）"},
            "net.ipv4.conf.all.accept_redirects": {"expected": "0", "desc": "ICMP 重定向"},
            "net.ipv4.conf.all.send_redirects": {"expected": "0", "desc": "发送 ICMP 重定向"},
            "net.ipv4.conf.all.accept_source_route": {"expected": "0", "desc": "源路由"},
            "net.ipv4.conf.all.log_martians": {"expected": "1", "desc": "记录异常包"},
            "kernel.randomize_va_space": {"expected": "2", "desc": "ASLR 地址随机化"},
        }
        for param, info in sysctl_checks.items():
            rc, out, _ = _run_cmd(f"sysctl -n {param} 2>/dev/null")
            if rc == 0 and out:
                ok = out.strip() == info["expected"]
                checks.append({
                    "category": "内核参数",
                    "item": param,
                    "current": out.strip(),
                    "expected": info["expected"],
                    "status": "合规" if ok else "不合规",
                    "severity": "中" if not ok else "信息",
                    "description": info["desc"],
                })

        # 5. cron 权限
        cron_dirs = ["/etc/crontab", "/etc/cron.d", "/etc/cron.daily", "/etc/cron.hourly"]
        for cron_path in cron_dirs:
            p = Path(cron_path)
            if p.exists():
                try:
                    mode = oct(p.stat().st_mode)[-3:]
                    if mode not in ("600", "644", "700", "755"):
                        checks.append({
                            "category": "Cron 权限",
                            "item": cron_path,
                            "current": mode,
                            "status": "不合规",
                            "severity": "中",
                            "description": f"Cron 路径权限 {mode} 过于宽松",
                        })
                except (PermissionError, OSError):
                    pass

        compliant = sum(1 for c in checks if c["status"] == "合规")
        non_compliant = sum(1 for c in checks if c["status"] == "不合规")
        total = len(checks)

        return {
            "timestamp": now_iso(),
            "total_checks": total,
            "compliant": compliant,
            "non_compliant": non_compliant,
            "compliance_rate": round(compliant / total * 100, 1) if total else 0,
            "checks": checks,
            "critical_issues": [c for c in checks if c.get("severity") == "严重"],
        }

    # ---- 综合扫描 ----

    def full_scan(self) -> dict[str, Any]:
        """综合安全加固扫描."""
        return {
            "timestamp": now_iso(),
            "ssh_audit": self.ssh_audit(),
            "firewall_audit": self.firewall_audit(),
            "vulnerability_scan": self.vulnerability_scan(),
            "baseline_check": self.baseline_check(),
        }

    # ---- 工具处理器 ----

    async def _tool_ssh_audit(self) -> str:
        return json.dumps(self.ssh_audit(), ensure_ascii=False, indent=2, default=str)

    async def _tool_firewall_audit(self) -> str:
        return json.dumps(self.firewall_audit(), ensure_ascii=False, indent=2, default=str)

    async def _tool_vulnerability_scan(self) -> str:
        return json.dumps(self.vulnerability_scan(), ensure_ascii=False, indent=2, default=str)

    async def _tool_baseline_check(self) -> str:
        return json.dumps(self.baseline_check(), ensure_ascii=False, indent=2, default=str)

    async def _tool_full_scan(self) -> str:
        return json.dumps(self.full_scan(), ensure_ascii=False, indent=2, default=str)


def _detect_firewall() -> tuple[str, str]:
    """检测活跃的防火墙类型并返回规则文本."""
    # ufw
    rc, out, _ = _run_cmd("ufw status verbose 2>/dev/null")
    if rc == 0 and "active" in out.lower():
        return "ufw", out

    # firewalld
    rc, out, _ = _run_cmd("firewall-cmd --state 2>/dev/null")
    if rc == 0 and "running" in out.lower():
        rc2, out2, _ = _run_cmd("firewall-cmd --list-all 2>/dev/null")
        return "firewalld", out2 if rc2 == 0 else out

    # nftables
    rc, out, _ = _run_cmd("nft list ruleset 2>/dev/null")
    if rc == 0 and out:
        return "nftables", out[:3000]

    # iptables
    rc, out, _ = _run_cmd("iptables -L -n 2>/dev/null")
    if rc == 0 and out:
        # 检查是否有非默认规则
        if "ACCEPT" in out or "DROP" in out or "REJECT" in out:
            return "iptables", out[:3000]
        return "iptables_empty", out[:3000]

    return "none", "未检测到活跃的防火墙"


# ---- 全局实例 ----
skill_instance = SecurityHardeningSkill()