"""安全知识库 — 结构化剧本，供检索 grounding，降低幻觉与误操作."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Playbook:
    id: str
    title: str
    body: str
    threat_tags: tuple[str, ...]
    severity: str
    requires_root_confirm: bool
    keywords: tuple[str, ...]
    do_not: tuple[str, ...] = ()
    suggested_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "threat_tags": list(self.threat_tags),
            "severity": self.severity,
            "requires_root_confirm": self.requires_root_confirm,
            "keywords": list(self.keywords),
            "do_not": list(self.do_not),
            "suggested_actions": list(self.suggested_actions),
        }


# 30+ 条：覆盖误删、伪装窃密、端口暴露、权限、监控盲区、人性化处置
PLAYBOOKS: tuple[Playbook, ...] = (
    Playbook(
        "PB-MISDELETE-01",
        "拦截进程前必须二次确认",
        "任何 kill/block 前应先 list_processes 或 get_process_detail，核对 PID、用户、命令行。"
        "开发中的 streamlit/python/node 常被误判；演练诱饵 decoy 可安全停止。",
        ("misdelete", "process"),
        "高",
        False,
        ("误删", "kill", "拦截", "进程", "确认"),
        ("未核对 PID 就 block", "批量 kill 开发服务"),
        ("核对 cmdline 与业务归属", "优先 stop 而非 kill -9", "记录审计"),
    ),
    Playbook(
        "PB-MISDELETE-02",
        "高危工具名不等于恶意",
        "grep/cat 日志中出现 nmap/nc 多为检索关键字；官方 decoy 路径可豁免。"
        "应结合进程树、网络连接、文件变更综合判断。",
        ("misdelete", "false_positive"),
        "中",
        False,
        ("误报", "nmap", "nc", "grep", "日志"),
        ("仅因命令行含工具名就终止",),
        ("运行 detection_calibration 校准", "查看完整 cmdline", "对比监控事件时间线"),
    ),
    Playbook(
        "PB-EXFIL-01",
        "伪装与窃密进程特征",
        "警惕：异常外连、监听高端口、进程名仿系统（sshd2）、工作目录在 /tmp、"
        "cmdline 含 base64|curl|wget 管道、无对应软件包。",
        ("exfiltration", "impersonation", "process"),
        "严重",
        False,
        ("窃密", "伪装", "外连", "base64", "反弹"),
        ("未取证就删进程",),
        ("保留 PID 与连接快照", "查 /proc/PID/fd", "对照审计与 auth.log"),
    ),
    Playbook(
        "PB-EXFIL-02",
        "敏感文件外传路径",
        "关注对 /etc/shadow、.ssh/id_rsa、业务数据库配置的读取与外传；"
        "tar+curl、scp 到未知 IP 需告警。",
        ("exfiltration", "data"),
        "严重",
        True,
        ("外传", "shadow", "ssh", "密钥", "scp"),
        ("在未确认下 chmod 放宽权限",),
        ("check_sensitive_paths", "收紧权限", "轮换密钥"),
    ),
    Playbook(
        "PB-PORT-01",
        "端口暴露与对外监听",
        "0.0.0.0 或 :: 上监听数据库/Redis/调试口（6379/9200/4444）属高风险；"
        "应仅内网或 localhost 绑定。",
        ("port_exposure", "network"),
        "高",
        False,
        ("端口", "暴露", "监听", "6379", "redis", "0.0.0.0"),
        ("直接 iptables -F",),
        ("check_exposed_ports", "ss -tlnp 复核", "防火墙最小放行"),
    ),
    Playbook(
        "PB-PORT-02",
        "SSH/RDP 暴露面",
        "22/3389 对公网开放需强认证与 fail2ban；非标准端口不能替代弱口令。",
        ("port_exposure", "network"),
        "高",
        False,
        ("ssh", "3389", "rdp", "22", "公网"),
        (),
        ("限制来源 IP", "禁用密码仅密钥", "审查 authorized_keys"),
    ),
    Playbook(
        "PB-ROOT-01",
        "root 增删改查须人工确认",
        "涉及 sudo/su、useradd/userdel、chmod/chown、写 /etc、iptables、systemctl stop 等"
        "一律 NEED_CONFIRM，界面勾选后方可执行。",
        ("privilege", "root"),
        "严重",
        True,
        ("root", "sudo", "权限", "userdel", "chmod"),
        ("Agent 自动 sudo", "未确认执行写操作",),
        ("展示命令与影响范围", "双人复核高危变更", "写审计"),
    ),
    Playbook(
        "PB-ROOT-02",
        "只读 root 观测允许",
        "sudo systemctl status、sudo cat /var/log、sudo ss -tlnp 等只读排查可自动；"
        "与写操作严格区分。",
        ("privilege", "root"),
        "低",
        False,
        ("只读", "sudo", "status", "journalctl"),
        ("把只读命令与写操作混在同一脚本",),
        ("拆分观测与变更步骤",),
    ),
    Playbook(
        "PB-MON-01",
        "监控无死角检查清单",
        "除进程外应覆盖：新监听端口、敏感文件 mtime、auth.log 失败登录、"
        "异常 cron、新 systemd unit。建议常开 monitor 并设 5s 刷新。",
        ("monitoring_gap",),
        "中",
        False,
        ("监控", "盲区", "cron", "systemd", "auth"),
        ("仅依赖单次扫描",),
        ("start_monitor", "定期 run_full_security_check", "审计导出"),
    ),
    Playbook(
        "PB-MON-02",
        "高危后持续跟踪",
        "告警后 15 分钟内复查进程是否复活、端口是否重开、同 IP 多连接。",
        ("monitoring_gap", "process"),
        "中",
        False,
        ("复发", "持久化", "跟踪"),
        (),
        ("二次扫描对比", "记录事件时间线",),
    ),
    Playbook(
        "PB-DEV-01",
        "日常开发进程白名单意识",
        "streamlit、uv、docker、node、java、postgres 等为正常栈；"
        "告警时先问「是否本人在跑 CI/控制台」。",
        ("misdelete", "daily_dev"),
        "低",
        False,
        ("开发", "streamlit", "docker", "node"),
        ("杀掉正在演示的控制台",),
        ("确认端口 8501 占用者", "用 get_process_detail"),
    ),
    Playbook(
        "PB-DEV-02",
        "改检测规则后跑校准",
        "修改 HIGH_RISK 或规则引擎后必须 run_detection_calibration，保持 66 例全绿。",
        ("false_positive", "daily_dev"),
        "低",
        False,
        ("校准", "fixture", "误报"),
        (),
        ("scripts/demo_risk.py calibration",),
    ),
    Playbook(
        "PB-KYLIN-01",
        "银河麒麟与 kysec",
        "部分脚本 source 被拦截；用 boot_start.sh 单文件启动。"
        "pkexec/sudo 弹窗需用户在场，Agent 不得代替点击确认。",
        ("privilege", "kylin"),
        "中",
        True,
        ("麒麟", "kysec", "pkexec", "kylin"),
        ("绕过 kysec 执行未签名脚本",),
        ("使用项目 boot 脚本", "root 操作走 UI 确认",),
    ),
    Playbook(
        "PB-NET-01",
        "异常外连研判",
        "内网主机连境外 443/4444 需关联进程；LISTEN 与 ESTABLISHED 分开看。",
        ("exfiltration", "network"),
        "高",
        False,
        ("外连", "established", "c2"),
        (),
        ("list_network_connections", "对照 PID", "必要时临时封禁需确认",),
    ),
    Playbook(
        "PB-NET-02",
        "反向 shell 迹象",
        "nc -e、bash -i、/dev/tcp 等模式高危；先隔离网络再处置。",
        ("exfiltration", "network"),
        "严重",
        True,
        ("反弹", "shell", "nc -e", "/dev/tcp"),
        ("未断网就杀进程导致证据丢失",),
        ("保存连接与 cmdline", "断网", "再 block",),
    ),
    Playbook(
        "PB-PERM-01",
        "敏感路径可写",
        "/etc/passwd、shadow、.ssh 可写多为配置错误或入侵；"
        "非 root 可写 shadow 必须立即收紧。",
        ("privilege", "data"),
        "严重",
        True,
        ("权限", "shadow", "passwd", "可写"),
        ("chmod 777 修复",),
        ("check_sensitive_paths", "恢复权限", "查变更时间",),
    ),
    Playbook(
        "PB-AUDIT-01",
        "审计与可追溯",
        "block、terminal、自主任务均写 audit.log；"
        "建议定期导出，事故时按时间线复盘。",
        ("monitoring_gap",),
        "低",
        False,
        ("审计", "日志", "追溯"),
        (),
        ("get_audit_log", "报告中心导出",),
    ),
    Playbook(
        "PB-ADVICE-01",
        "人性化回复结构",
        "先一句话结论（安全/有风险/需确认），再列 1-3 条依据（工具输出/知识库条目），"
        "最后给可执行建议与「请勿」事项；禁止编造未调工具的数据。",
        ("advisor",),
        "信息",
        False,
        ("建议", "结论", "依据", "幻觉"),
        ("编造 PID 或端口", "无依据断言已被入侵",),
        ("引用检索到的 PB-* 编号", "标明需用户确认的操作",),
    ),
    Playbook(
        "PB-ADVICE-02",
        "处置优先级",
        "严重：断网/隔离 → 保全证据 → 用户确认后处置；"
        "高：确认后 block；中低：观察或排期修复。",
        ("advisor",),
        "信息",
        False,
        ("优先级", "处置", "隔离"),
        ("一次性执行所有建议",),
        ("按 severity 排序", "每步可回滚",),
    ),
    Playbook(
        "PB-IMPERSON-01",
        "进程名伪装",
        "名为 [kworker]、sshd 但路径在 /tmp 或 /dev/shm 多为伪装；"
        "用 readlink /proc/PID/exe 核实。",
        ("impersonation", "process"),
        "严重",
        False,
        ("伪装", "kworker", "sshd", "tmp"),
        ("信任进程名 alone",),
        ("get_process_detail", "核对 exe 路径",),
    ),
    Playbook(
        "PB-CRON-01",
        "持久化 cron/systemd",
        "新出现未知 cron、~/.config/systemd/user 下可疑 unit 需查创建时间与内容。",
        ("monitoring_gap", "impersonation"),
        "高",
        True,
        ("cron", "systemd", "持久化"),
        ("直接删系统 cron",),
        ("cat unit 内容", "确认后禁用",),
    ),
    Playbook(
        "PB-DOCKER-01",
        "容器逃逸与特权容器",
        "--privileged、挂载 /、docker.sock 暴露宿主机风险；"
        "生产避免 privileged。",
        ("privilege", "daily_dev"),
        "高",
        False,
        ("docker", "privileged", "逃逸"),
        (),
        ("docker inspect 查 Privileged", "限制 sock 权限",),
    ),
    Playbook(
        "PB-LLM-01",
        "检索 grounding 防幻觉",
        "回答前必须 search_security_knowledge 或已有工具结果；"
        "知识库无依据时明确说「需进一步扫描」。",
        ("advisor", "false_positive"),
        "信息",
        False,
        ("检索", "向量", "grounding", "幻觉"),
        ("编造校准通过率", "虚构 CVE",),
        ("引用 PB 编号与工具输出",),
    ),
    Playbook(
        "PB-PORT-03",
        "数据库默认端口",
        "3306/5432/27017/9200 对 0.0.0.0 监听且弱口令=极高风险。",
        ("port_exposure", "network"),
        "严重",
        False,
        ("mysql", "redis", "mongodb", "elasticsearch", "3306"),
        (),
        ("check_exposed_ports", "改 bind-address", "强密码",),
    ),
    Playbook(
        "PB-BACKUP-01",
        "误删恢复",
        "删进程/文件前确认备份与可重启性；"
        "生产数据库/配置先快照。",
        ("misdelete",),
        "高",
        True,
        ("备份", "恢复", "快照"),
        ("无备份执行 rm",),
        ("确认备份窗口", "用 stop 代替 kill",),
    ),
    Playbook(
        "PB-SCAN-01",
        "综合体检节奏",
        "上线前、变更后、每周 run_full_security_check；"
        "与 calibration 区分：前者查实盘，后者验证规则。",
        ("monitoring_gap", "daily_dev"),
        "低",
        False,
        ("体检", "扫描", "周期"),
        (),
        ("run_full_security_check", "生成 HTML 报告",),
    ),
    Playbook(
        "PB-TERMINAL-01",
        "终端白名单边界",
        "观测类 ps/ss/df 自动；kill/sudo 写操作需确认；"
        "rm -rf、管道 bash 一律拒绝。",
        ("privilege", "misdelete"),
        "高",
        True,
        ("终端", "白名单", "sudo"),
        ("echo|python 绕过执行",),
        ("test_terminal_boundaries",),
    ),
    Playbook(
        "PB-EXFIL-03",
        "DNS/ICMP 隧道",
        "异常 DNS 查询频率、大块 TXT 记录可能为隧道；"
        "需网络层 IDS 与主机进程关联。",
        ("exfiltration", "network"),
        "高",
        False,
        ("dns", "隧道", "icmp"),
        (),
        ("抓包时段分析", "查异常进程",),
    ),
    Playbook(
        "PB-HOST-01",
        "主机沦陷应急",
        "怀疑沦陷时：断网 → 保全内存/连接/日志 → 改密钥 → 复盘入侵路径；"
        "恢复业务前跑 full_drill + calibration。",
        ("exfiltration", "advisor"),
        "严重",
        True,
        ("沦陷", "应急", "断网", "取证"),
        ("未取证就重装",),
        ("隔离", "保全证据", "全量扫描",),
    ),
    Playbook(
        "PB-LLM-02",
        "多维数据含义",
        "检索维度：威胁类型、严重度、是否需 root 确认、建议/禁止动作；"
        "与实盘 scan/monitor/端口 交叉验证。",
        ("advisor",),
        "信息",
        False,
        ("多维", "向量", "标签", "metadata"),
        (),
        ("按标签筛选 search", "结合 check_exposed_ports",),
    ),
    Playbook(
        "PB-REDACT-01",
        "敏感信息自动打码",
        "界面、审计、终端输出、工具返回均经 redact：password/token/sk-/Bearer/auth 登录行；"
        "展示前打码，避免密码泄露到报告或聊天记录。",
        ("advisor", "privilege"),
        "中",
        False,
        ("打码", "脱敏", "密码", "token"),
        ("在聊天中粘贴明文密码",),
        ("日志导出前已打码", "勿关闭脱敏",),
    ),
    Playbook(
        "PB-UI-01",
        "界面确认勾选",
        "自主运维页「允许高危终端」未勾选时，kill/sudo 必须拒绝；"
        "与用户口头确认不等同于 UI 确认。",
        ("privilege", "misdelete"),
        "严重",
        True,
        ("确认", "勾选", "UI"),
        ("口头确认代替勾选",),
        ("勾选后再执行", "审计记录 confirmed=true",),
    ),
)

PLAYBOOK_BY_ID = {p.id: p for p in PLAYBOOKS}
