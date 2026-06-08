# HCIE + 蓝队开源项目 全维度架构优化方案

## 一、优化总览

基于 HCIE 三层运维架构（采集层→管控层→执行层→安全审计层）和蓝队开源项目知识，
对现有 A2 Agent 进行以下四大模块升级：

```
┌─────────────────────────────────────────────────────────┐
│                   用户自然语言交互层                       │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ 安全护栏  │  │ 知识库   │  │ MCP插件  │  │ 审计溯源  │ │
│  │ (升级版)  │  │ (增强版)  │  │ (HCIE化) │  │ (全链路)  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
├─────────────────────────────────────────────────────────┤
│                    HCIE 传统运维底座                       │
│  采集层(探针) → 管控层(Ansible化) → 执行层(沙箱) → 审计层 │
└─────────────────────────────────────────────────────────┘
```

## 二、安全护栏升级（Safety Gate 2.0）

### 2.1 现有架构问题
- 规则引擎仅靠正则匹配，缺少 Sigma 规则集成
- 无 IOC 威胁情报自动匹配
- 无文件完整性监控（AIDE/Tripwire）
- 无内核安全参数检查
- 无 WebShell 检测能力

### 2.2 升级方案

#### 新增模块：`security_agent/safety_gate/blue_team_rules/`

```
blue_team_rules/
├── __init__.py
├── sigma_bridge.py        # Sigma 规则转换与匹配引擎
├── ioc_matcher.py         # IOC 威胁情报自动匹配
├── webshell_detector.py   # WebShell 检测（YARA + 特征）
├── file_integrity.py      # 文件完整性监控（AIDE 风格）
├── kernel_hardening.py    # 内核安全参数检查
└── auditd_rules.py        # auditd 审计规则配置
```

#### 升级三层防御引擎

**L1 静态风险评估** 新增规则：
- Sigma 规则匹配（覆盖 Web 攻击/横向移动/提权）
- IOC 威胁情报匹配（IP/Domain/Hash）
- WebShell 特征检测
- 内核安全基线检查

**L2 动态意图审计** 增强：
- 蓝队攻击链意图识别（侦察→利用→提权→横向→窃取）
- 异常行为模式检测（非工作时间操作/异常地域登录）

**L3 受限执行环境** 增强：
- 文件完整性基线校验（执行前/后对比）
- auditd 关键路径审计规则自动配置
- SELinux/AppArmor 上下文强制校验

### 2.3 新增 Playbook 规则（已实现 30+ 条蓝队剧本）

已在 `playbooks.py` 中新增：
- PB-BT-HUNT-01/02: ThreatHunter 入侵排查
- PB-BT-SIGMA-01/02: Sigma 检测规则
- PB-BT-SCAN-01: 巡风资产扫描
- PB-BT-KB-01: 蓝队应急响应知识库
- PB-BT-API-01/02: API 限流与熔断
- PB-BT-LOG-01/02: 日志异常检测与关联分析
- PB-BT-IR-01: 完整应急响应流程
- PB-BT-WAF-01/02: WebShell 检测与 WAF 部署
- PB-BT-AUDIT-01/02: auditd 审计与文件完整性
- PB-BT-SYS-01/02: 内核安全与 SELinux 加固
- PB-BT-NET-03: iptables 安全策略
- PB-BT-IDS-01: Suricata/Snort IDS 部署
- PB-BT-TI-01/02: IOC 威胁情报与 YARA 规则

## 三、知识库升级（Knowledge 2.0）

### 3.1 现有架构问题
- 仅靠 playbooks 静态知识，缺少动态学习能力
- 无蓝队技能训练模块
- 无自动化知识爬取更新

### 3.2 升级方案

#### 蓝队知识自动爬取（已实现）
`blue_team_crawler.py` 支持：
- 从 Gitee/GitHub 拉取 7 个蓝队开源项目
- LLM 自动分析提取蓝队技能
- 生成训练场景和优化建议
- 每日轮转训练场景

#### 知识库三层架构
```
知识库 (Knowledge)
├── L1: 安全处置剧本 (Playbooks) — 30+ 条结构化规则
│   ├── 传统安全规则 (PB-MISDELETE/PB-EXFIL/PB-PORT 等)
│   └── 蓝队开源知识 (PB-BT-HUNT/PB-BT-SIGMA/PB-BT-SCAN 等)
├── L2: 蓝队技能库 (BlueTeam Skills) — 从开源项目提取
│   ├── 入侵排查技能 (ThreatHunter)
│   ├── 检测规则技能 (Sigma)
│   ├── 资产扫描技能 (xunfeng)
│   ├── 应急响应技能 (Security-Awesome)
│   ├── API 安全技能 (slowapi/pybreaker)
│   └── 日志分析技能 (logdetective)
└── L3: 训练场景库 (Training Scenarios) — 每日轮转
    ├── 初级: SSH暴力破解/API限流配置
    ├── 中级: WebShell清理/Sigma规则编写/日志关联分析
    └── 高级: Rootkit排查/攻击链检测/级联故障防御
```

## 四、MCP 插件 HCIE 化

### 4.1 插件分类（HCIE 模块化设计）

```
MCP 插件体系
├── 系统管理插件 (system_manager)
│   ├── 进程管理 (process)
│   ├── 服务管理 (service)
│   ├── 用户管理 (user)
│   └── 文件系统 (filesystem)
├── 网络运维插件 (network_ops)
│   ├── 端口扫描 (port_scan)
│   ├── 连接分析 (connection)
│   ├── 防火墙管理 (firewall)
│   └── DNS 检查 (dns)
├── 安全审计插件 (security_audit)
│   ├── 日志分析 (log_analysis)
│   ├── 入侵检测 (ids)
│   ├── 文件完整性 (integrity)
│   └── 威胁情报 (threat_intel)
└── 磁盘管理插件 (disk_manager)
    ├── 空间分析 (space)
    ├── IO 监控 (io_monitor)
    └── 备份恢复 (backup)
```

### 4.2 插件执行流程（HCIE 四步机制）

```
LLM 输出指令
    ↓
① 安全校验器（规则+Sigma+IOC）拦截高危参数
    ↓
② 沙箱预执行模拟结果
    ↓
③ 最小权限账号真实执行
    ↓
④ 出错自动回滚配置
```

## 五、前端 UI 升级

### 5.1 安全门禁页新增功能
- 蓝队训练场景展示（每日轮转）
- 三层防御实时状态仪表盘
- 审批队列可视化
- 知识库检索增强（支持标签/严重度过滤）

### 5.2 知识库页新增功能
- 蓝队技能分类展示
- 训练场景交互式演练
- 开源项目知识图谱

## 六、实施路线图

### Phase 1: 知识库增强 ✅ (已完成)
- [x] 30+ 条蓝队 Playbook 规则
- [x] 蓝队开源项目爬取器
- [x] 每日训练场景轮转

### Phase 2: 安全护栏升级 (进行中)
- [ ] Sigma 规则桥接引擎
- [ ] IOC 威胁情报匹配
- [ ] WebShell 检测模块
- [ ] 文件完整性监控
- [ ] 内核安全基线检查

### Phase 3: MCP 插件 HCIE 化
- [ ] 插件分类重构
- [ ] 四步执行机制
- [ ] 配置版本管理
- [ ] 一键回滚增强

### Phase 4: 前端 UI 升级
- [ ] 蓝队训练场景页面
- [ ] 安全仪表盘增强
- [ ] 知识图谱可视化
