"""故障响应 Skill — 根因分析决策树、自愈脚本、处置流程编排."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import psutil

from security_agent import config
from security_agent.skills.base import SkillBase, SkillMeta, ToolDef
from security_agent.timeutil import now_iso


class IncidentSeverity(str, Enum):
    P1 = "P1-紧急"   # 系统不可用
    P2 = "P2-严重"   # 核心功能受损
    P3 = "P3-一般"   # 非核心功能受损
    P4 = "P4-低"     # 告警/预防


class AutoAction(str, Enum):
    AUTO_FIX = "auto_fix"           # 自动修复（低风险）
    AUTO_ISOLATE = "auto_isolate"   # 自动隔离（如断网）
    HUMAN_CONFIRM = "human_confirm" # 需人工确认
    HUMAN_ONLY = "human_only"       # 仅人工处理


@dataclass
class IncidentDiagnosis:
    """故障诊断结果."""

    incident_type: str
    severity: IncidentSeverity
    auto_action: AutoAction
    root_cause: str
    evidence: list[str]
    recommended_steps: list[str]
    auto_fix_available: bool
    auto_fix_command: str = ""
    estimated_recovery_time: str = ""
    knowledge_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_type": self.incident_type,
            "severity": self.severity.value,
            "auto_action": self.auto_action.value,
            "root_cause": self.root_cause,
            "evidence": self.evidence,
            "recommended_steps": self.recommended_steps,
            "auto_fix_available": self.auto_fix_available,
            "auto_fix_command": self.auto_fix_command,
            "estimated_recovery_time": self.estimated_recovery_time,
            "knowledge_refs": self.knowledge_refs,
        }


# ---- 根因分析决策树 ----

def _run_cmd(cmd: str, timeout: int = 10) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def diagnose_high_cpu() -> IncidentDiagnosis:
    """CPU 过高根因分析."""
    evidence: list[str] = []
    top_procs: list[dict[str, Any]] = []

    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent"]):
        try:
            info = proc.info
            cpu = info.get("cpu_percent") or 0
            if cpu > 5:
                cmdline = ""
                try:
                    cmdline = " ".join(proc.cmdline()[:5])
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                top_procs.append({**info, "cmdline": cmdline[:100]})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    top_procs.sort(key=lambda p: p.get("cpu_percent", 0), reverse=True)
    top_procs = top_procs[:5]

    if top_procs:
        evidence.append(f"Top CPU 进程: {top_procs[0].get('name')} (PID {top_procs[0].get('pid')}) CPU={top_procs[0].get('cpu_percent')}%")

    # 判断根因
    top = top_procs[0] if top_procs else {}
    top_name = (top.get("name") or "").lower()
    business_procs = {"java", "python", "python3", "node", "nginx", "gunicorn", "uvicorn", "streamlit", "postgres", "mysqld", "redis-server"}

    if top_name in business_procs:
        root_cause = f"业务进程 {top.get('name')} (PID {top.get('pid')}) CPU 占用过高"
        auto_action = AutoAction.HUMAN_CONFIRM
        steps = [
            f"确认 {top.get('name')} 是否在执行正常业务（如批量任务、编译）",
            "如属正常负载，考虑扩容或优化",
            "如属异常（死循环等），确认后可重启",
        ]
        auto_fix = False
        fix_cmd = ""
    elif top_name in ("nmap", "masscan", "hydra", "sqlmap"):
        root_cause = f"疑似攻击工具 {top.get('name')} (PID {top.get('pid')}) CPU 异常"
        auto_action = AutoAction.AUTO_ISOLATE
        steps = [
            f"高危进程 {top.get('name')} (PID {top.get('pid')}) 正在消耗 CPU",
            "建议立即终止并保留证据",
            "检查是否有关联的网络连接",
        ]
        auto_fix = True
        fix_cmd = f"kill -TERM {top.get('pid')}"
    else:
        root_cause = f"进程 {top.get('name')} (PID {top.get('pid')}) CPU 占用异常"
        auto_action = AutoAction.HUMAN_CONFIRM
        steps = [
            f"检查 {top.get('name')} 的命令行和用途",
            "如非必要进程可终止",
            "持续观察是否复发",
        ]
        auto_fix = False
        fix_cmd = ""

    return IncidentDiagnosis(
        incident_type="high_cpu",
        severity=IncidentSeverity.P2 if len(top_procs) > 0 and (top_procs[0].get("cpu_percent") or 0) > 90 else IncidentSeverity.P3,
        auto_action=auto_action,
        root_cause=root_cause,
        evidence=evidence,
        recommended_steps=steps,
        auto_fix_available=auto_fix,
        auto_fix_command=fix_cmd,
        estimated_recovery_time="1-5 分钟" if auto_fix else "需人工评估",
        knowledge_refs=["PB-MISDELETE-01", "PB-DEV-01"],
    )


def diagnose_high_memory() -> IncidentDiagnosis:
    """内存过高根因分析."""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    evidence = [
        f"内存使用率: {mem.percent}% ({mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB)",
        f"Swap 使用率: {swap.percent}%",
    ]

    # 找内存大户
    top_procs: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "username"]):
        try:
            m = proc.memory_info()
            if m.rss > 100 * 1024 * 1024:  # > 100MB
                top_procs.append({
                    "pid": proc.pid,
                    "name": proc.info.get("name"),
                    "rss_mb": m.rss // (1024**2),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    top_procs.sort(key=lambda p: p["rss_mb"], reverse=True)
    if top_procs:
        evidence.append(f"内存大户: {top_procs[0]['name']} (PID {top_procs[0]['pid']}) RSS={top_procs[0]['rss_mb']}MB")

    oom_risk = mem.percent > 90 or swap.percent > 80
    return IncidentDiagnosis(
        incident_type="high_memory",
        severity=IncidentSeverity.P2 if oom_risk else IncidentSeverity.P3,
        auto_action=AutoAction.HUMAN_CONFIRM,
        root_cause=f"内存使用率 {mem.percent}%，{'OOM 风险高' if oom_risk else '偏高但可控'}",
        evidence=evidence,
        recommended_steps=[
            "排查内存大户进程是否正常",
            "检查是否存在内存泄漏",
            "如 OOM 风险高，考虑重启内存大户或增加 swap",
            "长期方案：扩容内存或优化应用",
        ],
        auto_fix_available=False,
        estimated_recovery_time="需人工评估",
        knowledge_refs=["PB-MON-01"],
    )


def diagnose_disk_full() -> IncidentDiagnosis:
    """磁盘满根因分析."""
    disk = psutil.disk_usage("/")
    evidence = [f"根分区使用率: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"]

    # 找大目录
    large_dirs: list[dict[str, Any]] = []
    for d in ["/var/log", "/tmp", "/var/cache", "/home", "/var/lib/docker"]:
        if Path(d).exists():
            rc, out, _ = _run_cmd(f"du -sh {d} 2>/dev/null", timeout=5)
            if rc == 0 and out:
                size = out.split()[0]
                large_dirs.append({"dir": d, "size": size})
    if large_dirs:
        evidence.append(f"大目录: {', '.join(d['dir'] + '=' + d['size'] for d in large_dirs[:3])}")

    # 可自动清理的
    auto_cleanable = [d for d in large_dirs if d["dir"] in ("/var/log", "/tmp", "/var/cache")]

    return IncidentDiagnosis(
        incident_type="disk_full",
        severity=IncidentSeverity.P1 if disk.percent > 95 else IncidentSeverity.P2,
        auto_action=AutoAction.HUMAN_CONFIRM,
        root_cause=f"磁盘使用率 {disk.percent}%，{'即将满' if disk.percent > 95 else '偏高'}",
        evidence=evidence,
        recommended_steps=[
            "检查 /var/log 日志文件大小，可 logrotate 清理",
            "清理 /tmp 临时文件",
            "检查 Docker 镜像和容器占用",
            "排查大文件: find / -size +100M -type f",
        ],
        auto_fix_available=bool(auto_cleanable),
        auto_fix_command="journalctl --vacuum-size=200M && find /tmp -mtime +7 -delete",
        estimated_recovery_time="5-15 分钟",
        knowledge_refs=["PB-BACKUP-01"],
    )


def diagnose_service_down(service_name: str = "") -> IncidentDiagnosis:
    """服务不可用根因分析."""
    evidence: list[str] = []
    suspect_service = service_name

    # 检查常见服务
    services_to_check = ["nginx", "apache2", "sshd", "docker", "postgres", "mysql", "redis"]
    if suspect_service:
        services_to_check = [suspect_service] + services_to_check

    down_services: list[str] = []
    for svc in services_to_check:
        rc, out, _ = _run_cmd(f"systemctl is-active {svc} 2>/dev/null")
        if rc != 0 or "active" not in out:
            if rc != 4:  # 4 = unit not found
                down_services.append(svc)

    if down_services:
        evidence.append(f"未运行的服务: {', '.join(down_services)}")
        # 查看最近的失败日志
        rc, out, _ = _run_cmd(f"journalctl -u {down_services[0]} --no-pager -n 10 2>/dev/null", timeout=5)
        if out:
            evidence.append(f"{down_services[0]} 最近日志:\n{out[:500]}")

    target = down_services[0] if down_services else (suspect_service or "unknown")
    return IncidentDiagnosis(
        incident_type="service_down",
        severity=IncidentSeverity.P2,
        auto_action=AutoAction.AUTO_FIX if target in ("nginx", "docker") else AutoAction.HUMAN_CONFIRM,
        root_cause=f"服务 {target} 未运行",
        evidence=evidence,
        recommended_steps=[
            f"检查 {target} 状态: systemctl status {target}",
            f"查看日志: journalctl -u {target} -n 50",
            f"尝试重启: systemctl restart {target}",
            "如重启失败，检查配置文件语法",
        ],
        auto_fix_available=target in ("nginx", "docker", "apache2"),
        auto_fix_command=f"systemctl restart {target}",
        estimated_recovery_time="1-3 分钟",
        knowledge_refs=["PB-MON-01", "PB-MON-02"],
    )


def diagnose_network_issue() -> IncidentDiagnosis:
    """网络异常根因分析."""
    evidence: list[str] = []

    # 检查连接数
    try:
        conns = psutil.net_connections(kind="inet")
        established = sum(1 for c in conns if c.status == "ESTABLISHED")
        listening = sum(1 for c in conns if c.status == "LISTEN")
        time_wait = sum(1 for c in conns if c.status == "TIME_WAIT")
        evidence.append(f"连接数: ESTABLISHED={established}, LISTEN={listening}, TIME_WAIT={time_wait}")
        if time_wait > 500:
            evidence.append(f"TIME_WAIT 过高 ({time_wait})，可能有连接泄漏")
    except psutil.AccessDenied:
        evidence.append("权限不足，无法查看完整连接")

    # 检查 DNS
    rc, out, _ = _run_cmd("host baidu.com 2>/dev/null", timeout=5)
    if rc != 0:
        evidence.append("DNS 解析失败")

    return IncidentDiagnosis(
        incident_type="network_issue",
        severity=IncidentSeverity.P3,
        auto_action=AutoAction.HUMAN_CONFIRM,
        root_cause="网络连接异常",
        evidence=evidence,
        recommended_steps=[
            "检查网络接口: ip addr show",
            "检查路由: ip route",
            "检查 DNS: cat /etc/resolv.conf",
            "检查防火规则是否误拦",
        ],
        auto_fix_available=False,
        estimated_recovery_time="需人工排查",
        knowledge_refs=["PB-NET-01", "PB-NET-02"],
    )


# ---- 自愈脚本库 ----
SELF_HEAL_SCRIPTS: dict[str, dict[str, Any]] = {
    "clear_tmp": {
        "name": "清理临时文件",
        "command": "find /tmp -type f -mtime +7 -delete 2>/dev/null",
        "risk": "低",
        "description": "删除 /tmp 下超过 7 天的文件",
        "auto_ok": True,
    },
    "rotate_logs": {
        "name": "日志轮转",
        "command": "journalctl --vacuum-size=200M",
        "risk": "低",
        "description": "清理 journal 日志到 200MB",
        "auto_ok": True,
    },
    "clear_cache": {
        "name": "清理包缓存",
        "command": "apt-get clean 2>/dev/null",
        "risk": "低",
        "description": "清理 apt 包缓存",
        "auto_ok": True,
    },
    "restart_nginx": {
        "name": "重启 Nginx",
        "command": "systemctl restart nginx",
        "risk": "中",
        "description": "重启 Nginx 服务",
        "auto_ok": False,
    },
    "restart_docker": {
        "name": "重启 Docker",
        "command": "systemctl restart docker",
        "risk": "中",
        "description": "重启 Docker 服务（会影响容器）",
        "auto_ok": False,
    },
}


class IncidentResponderSkill(SkillBase):
    """故障响应 Skill — 根因分析、自愈脚本、处置流程编排."""

    @property
    def meta(self) -> SkillMeta:
        return SkillMeta(
            name="incident_responder",
            display_name="故障响应",
            description="自动根因分析、自愈脚本执行、告警关联诊断、处置流程编排",
            version="1.0.0",
            tags=("incident", "diagnosis", "self-heal", "response"),
        )

    def get_tools(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="incident_diagnose",
                description="自动诊断故障类型：检测 CPU/内存/磁盘/服务/网络异常并给出根因分析",
                parameters={
                    "type": "object",
                    "properties": {
                        "hint": {
                            "type": "string",
                            "description": "故障提示（如 high_cpu / disk_full / service:nginx）",
                            "default": "",
                        }
                    },
                    "required": [],
                },
                handler=self._tool_diagnose,
            ),
            ToolDef(
                name="incident_self_heal",
                description="执行自愈脚本（清理临时文件、日志轮转等低风险操作）",
                parameters={
                    "type": "object",
                    "properties": {
                        "script": {
                            "type": "string",
                            "description": "自愈脚本 ID: clear_tmp / rotate_logs / clear_cache",
                        }
                    },
                    "required": ["script"],
                },
                handler=self._tool_self_heal,
            ),
            ToolDef(
                name="incident_list_scripts",
                description="列出所有可用的自愈脚本",
                parameters={"type": "object", "properties": {}, "required": []},
                handler=self._tool_list_scripts,
            ),
            ToolDef(
                name="incident_response_plan",
                description="根据告警事件生成完整的处置方案（含步骤、风险、回滚）",
                parameters={
                    "type": "object",
                    "properties": {
                        "event_json": {
                            "type": "string",
                            "description": "告警事件 JSON",
                        }
                    },
                    "required": ["event_json"],
                },
                handler=self._tool_response_plan,
            ),
        ]

    def get_playbooks(self):
        from security_agent.knowledge.playbooks import Playbook

        return [
            Playbook(
                "HI-RECOVER-01",
                "故障恢复标准流程",
                "1. 保全证据（进程/连接/日志快照）→ 2. 评估影响范围 → 3. 选择处置方案 → 4. 执行（自动或确认） → 5. 验证恢复 → 6. 记录复盘",
                ("advisor",),
                "信息",
                False,
                ("恢复", "流程", "自愈", "应急"),
                ("跳过证据保全直接处置",),
                ("先快照再操作", "每步验证", "保留回滚能力"),
            ),
            Playbook(
                "HI-SELFHEAL-01",
                "自愈脚本安全边界",
                "仅允许低风险自动修复：清理 /tmp、日志轮转、包缓存清理。"
                "重启服务、杀进程、修改配置必须人工确认。",
                ("misdelete",),
                "中",
                True,
                ("自愈", "自动修复", "清理", "轮转"),
                ("自动重启数据库", "自动删除用户数据",),
                ("清理前确认无重要临时文件", "日志轮转不影响审计"),
            ),
        ]

    def get_rules(self) -> list[str]:
        return [
            "自愈操作仅限低风险（清理临时文件、日志轮转），高风险操作需人工确认",
            "故障诊断必须先保全证据再建议处置",
            "根因分析结论必须附带证据（进程快照、日志片段、指标数据）",
        ]

    # ---- 核心功能 ----

    def auto_diagnose(self, hint: str = "") -> IncidentDiagnosis:
        """自动诊断 — 根据 hint 或自动检测异常."""
        # 有明确 hint
        if hint:
            h = hint.lower().strip()
            if "cpu" in h:
                return diagnose_high_cpu()
            if "memory" in h or "mem" in h or "内存" in h:
                return diagnose_high_memory()
            if "disk" in h or "磁盘" in h:
                return diagnose_disk_full()
            if h.startswith("service:"):
                return diagnose_service_down(h.split(":", 1)[1])
            if "network" in h or "网络" in h:
                return diagnose_network_issue()

        # 自动检测
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        if cpu > 85:
            return diagnose_high_cpu()
        if mem.percent > 90:
            return diagnose_high_memory()
        if disk.percent > 90:
            return diagnose_disk_full()

        # 检查服务
        rc, out, _ = _run_cmd("systemctl is-active nginx 2>/dev/null")
        if rc != 0 and "inactive" in out:
            return diagnose_service_down("nginx")

        # 检查 OOM 最近记录
        rc, out, _ = _run_cmd("dmesg | grep -i 'out of memory' | tail -3 2>/dev/null", timeout=5)
        if out:
            return IncidentDiagnosis(
                incident_type="oom_recent",
                severity=IncidentSeverity.P2,
                auto_action=AutoAction.HUMAN_CONFIRM,
                root_cause="最近发生过 OOM Kill",
                evidence=[out[:300]],
                recommended_steps=[
                    "检查被 kill 的进程",
                    "分析内存使用趋势",
                    "考虑增加内存或 swap",
                ],
                auto_fix_available=False,
                knowledge_refs=["PB-MON-02"],
            )

        return IncidentDiagnosis(
            incident_type="no_incident",
            severity=IncidentSeverity.P4,
            auto_action=AutoAction.AUTO_FIX,
            root_cause="当前未检测到明显异常",
            evidence=[
                f"CPU={cpu}%, Memory={mem.percent}%, Disk={disk.percent}%",
            ],
            recommended_steps=["系统状态正常，建议持续监控"],
            auto_fix_available=False,
        )

    def execute_self_heal(self, script_id: str) -> dict[str, Any]:
        """执行自愈脚本."""
        script = SELF_HEAL_SCRIPTS.get(script_id)
        if not script:
            return {"ok": False, "error": f"未知脚本: {script_id}", "available": list(SELF_HEAL_SCRIPTS.keys())}

        if not script["auto_ok"]:
            return {
                "ok": False,
                "error": f"脚本 {script_id} 风险为 {script['risk']}，需人工确认后执行",
                "command": script["command"],
            }

        rc, out, err = _run_cmd(script["command"], timeout=30)
        return {
            "ok": rc == 0,
            "script_id": script_id,
            "name": script["name"],
            "exit_code": rc,
            "stdout": out[:1000],
            "stderr": err[:500],
            "timestamp": now_iso(),
        }

    def generate_response_plan(self, event: dict[str, Any]) -> dict[str, Any]:
        """根据告警事件生成处置方案."""
        etype = str(event.get("type", ""))
        level = str(event.get("level", ""))
        message = str(event.get("message", ""))

        # 先做诊断
        hint = ""
        if "CPU" in etype:
            hint = "high_cpu"
        elif "内存" in message.lower() or "oom" in message.lower():
            hint = "high_memory"
        elif "磁盘" in message or "disk" in message.lower():
            hint = "disk_full"
        elif "进程" in etype:
            hint = ""
        elif "端口" in etype or "监听" in etype:
            hint = "network"

        diagnosis = self.auto_diagnose(hint)
        plan_steps: list[dict[str, Any]] = []

        # Step 1: 证据保全
        plan_steps.append({
            "step": 1,
            "action": "保全证据",
            "description": "记录当前系统状态快照",
            "risk": "无",
            "auto": True,
            "commands": ["health_full_check", "list_processes"],
        })

        # Step 2: 根因分析
        plan_steps.append({
            "step": 2,
            "action": "根因分析",
            "description": diagnosis.root_cause,
            "risk": "无",
            "auto": True,
            "evidence": diagnosis.evidence,
        })

        # Step 3-N: 处置步骤
        for i, step_desc in enumerate(diagnosis.recommended_steps, 3):
            plan_steps.append({
                "step": i,
                "action": step_desc,
                "risk": "需评估",
                "auto": False,
            })

        # 最后: 验证恢复
        plan_steps.append({
            "step": len(plan_steps) + 1,
            "action": "验证恢复",
            "description": "复查指标确认恢复正常",
            "risk": "无",
            "auto": True,
        })

        return {
            "timestamp": now_iso(),
            "event": event,
            "diagnosis": diagnosis.to_dict(),
            "plan": plan_steps,
            "total_steps": len(plan_steps),
            "auto_fix_steps": sum(1 for s in plan_steps if s.get("auto")),
            "human_steps": sum(1 for s in plan_steps if not s.get("auto")),
        }

    # ---- 告警回调 ----

    async def on_alert(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """响应告警 — 自动诊断并生成处置方案."""
        level = str(event.get("level", ""))
        if level not in ("严重", "高"):
            return None

        plan = self.generate_response_plan(event)
        diagnosis = plan.get("diagnosis", {})

        return {
            "action": "incident_response",
            "plan_summary": {
                "type": diagnosis.get("incident_type"),
                "severity": diagnosis.get("severity"),
                "root_cause": diagnosis.get("root_cause"),
                "auto_fix_available": diagnosis.get("auto_fix_available"),
                "total_steps": plan.get("total_steps"),
            },
            "recommendation": f"故障类型: {diagnosis.get('incident_type')}，"
            f"建议先保全证据再{'自动修复' if diagnosis.get('auto_fix_available') else '人工处置'}",
        }

    # ---- 工具处理器 ----

    async def _tool_diagnose(self, hint: str = "") -> str:
        result = self.auto_diagnose(hint)
        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    async def _tool_self_heal(self, script: str = "") -> str:
        result = self.execute_self_heal(script)
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def _tool_list_scripts(self) -> str:
        return json.dumps(
            {
                "scripts": {
                    k: {kk: vv for kk, vv in v.items() if kk != "command"}
                    for k, v in SELF_HEAL_SCRIPTS.items()
                }
            },
            ensure_ascii=False,
            indent=2,
        )

    async def _tool_response_plan(self, event_json: str = "{}") -> str:
        try:
            event = json.loads(event_json)
        except json.JSONDecodeError:
            event = {"type": "unknown", "message": event_json}
        plan = self.generate_response_plan(event)
        return json.dumps(plan, ensure_ascii=False, indent=2, default=str)


# ---- 全局实例 ----
skill_instance = IncidentResponderSkill()