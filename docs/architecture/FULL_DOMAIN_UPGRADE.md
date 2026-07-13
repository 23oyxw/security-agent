# 生产级全域智能运维 Agent 架构升级方案

> **版本**：v0.9.0-design · **日期**：2026-07-13  
> **定位**：[FINAL_ARCHITECTURE.md](FINAL_ARCHITECTURE.md) §八的 **技术实现附录** — 从「演示级」到「生产级」的架构演进  
> **上游依赖**：[EXPERIENCE_DRIVEN_DESIGN.md](EXPERIENCE_DRIVEN_DESIGN.md) 定义的接口契约（本文是接口的实现方案）  
> **执行计划**：[MASTER_PLAN.md §11](MASTER_PLAN.md) 的 6 Step 路线  
> **原则**：**由浅入深、有理有据、贯穿架构** — 每个模块先分析当前问题，再给出设计理由，最后落到代码路径

---

## 问题诊断：当前 6 大模块的真实水平

| 模块 | 当前级别 | 核心缺陷 |
|------|----------|----------|
| 🏖️ 沙箱 | **演示级** | 有 setuid/rlimit，但无 namespace 隔离、无网络隔离、无 seccomp、无文件审计 |
| 📄 文件/文档系统 | **不存在** | SnapshotManager 只是 cp 备份，无版本化、无文档解析、无语义索引 |
| 🧠 文档智能 | **不存在** | 只有 30 条硬编码 Playbook，Gitee Wiki 单向拉取，无文档 pipeline |
| 💻 终端智能 | **基础级** | 能做预执行风险检查+后执行 PID 验证，但无上下文感知、无学习能力 |
| 🚨 告警系统 | **中等级** | 有去重+衍生抑制+动态阈值，但无关联引擎、无频率节流、无浮屏控制 |
| 🛡️ 对抗边界 | **基础级** | 有权限跃迁探针+边界测试，但无 Fuzzing、无对抗训练 pipeline |
| 📚 知识库 | **基础级** | 30+ Playbook + TF-IDF，但无一致性校验、无防污染、无自动抽取 |

---

## 一、全域沙箱：从 setuid 到 7 层隔离

### 1.1 当前问题

`sandbox.py` 的隔离手段只有两个：
- `setuid/setgid` — 换用户执行（Unix only，Windows 完全跳过）
- `rlimit` — CPU/内存/文件/进程数限制

**这不是沙箱，这只是"换个低权限用户跑命令"。** 真正的沙箱需要：

### 1.2 7 层隔离设计（由浅入深）

```
Layer 0: setuid/setgid          ← 已有，保留
Layer 1: rlimit 资源限制         ← 已有，保留
Layer 2: chroot / pivot_root    ← 文件系统隔离（已有接口未实现）
Layer 3: mount namespace        ← 私有 /tmp、/dev、/proc 挂载点
Layer 4: network namespace      ← 禁止/限制外连
Layer 5: seccomp-bpf            ← 系统调用白名单
Layer 6: cgroup v2              ← CPU/内存/IO 精确控制 + 审计
```

```
┌─────────────────────────────────────────────────────────┐
│                 SandboxRequest                          │
│  command, risk_level, timeout, allowed_network,         │
│  writable_paths, readonly_paths, max_file_mb            │
└──────────────────────┬──────────────────────────────────┘
                       │
         ┌─────────────▼──────────────┐
         │  SandboxProfile.choose()   │  ← 根据 risk_level 自动选层
         │  READONLY     → L0+L1     │
         │  REVERSIBLE   → L0-L3     │
         │  IRREVERSIBLE → L0-L6     │
         │  CRITICAL     → DENY      │
         └─────────────┬──────────────┘
                       │
    ┌──────────────────▼───────────────────┐
    │         SandboxExecutorV2            │
    │                                      │
    │  pre_exec:                           │
    │    1. create_mount_ns()              │
    │    2. create_network_ns()            │
    │    3. setup_seccomp_filter()         │
    │    4. apply_cgroup_limits()          │
    │    5. setup_overlay_fs()  ← 写时复制│
    │                                      │
    │  exec: unshare + clone + execve      │
    │                                      │
    │  post_exec:                          │
    │    1. diff_filesystem()   ← 审计变更 │
    │    2. record_syscalls()              │
    │    3. collect_network_log()          │
    └──────────────────────────────────────┘
```

### 1.3 文件系统写时复制（Overlay FS）

**为什么需要**：当前 `SnapshotManager` 是"先 cp 备份全目录 → 执行 → 失败则 cp 恢复"。这在生产环境有两个致命问题：
1. 大目录 cp 耗时太久（/var/log 可能有几十 GB）
2. 执行成功后的文件变更完全不可追溯

**设计**：使用 Linux overlayfs（麒麟 V11 内核 5.10+ 原生支持）：

```python
class OverlaySandbox:
    """写时复制沙箱 — 所有写操作落到 upperdir，原始文件不变。
    
    执行完毕后：
      - 成功 → 检查 upperdir 变更，生成 FileChangeReport，可选择 merge
      - 失败 → 直接删除 upperdir，零回滚成本
    """
    def setup(self, lower: Path, upper: Path, work: Path):
        """mount -t overlay overlay -o lowerdir={lower},upperdir={upper},workdir={work} {target}"""
    
    def diff(self) -> FileChangeReport:
        """对比 lower 和 upper，生成变更清单"""
    
    def commit(self):
        """将 upper 变更合并回 lower（需 L2 审批）"""
    
    def rollback(self):
        """删除 upper（零成本，无需 cp 恢复）"""
```

### 1.4 系统调用过滤（Seccomp-BPF）

**为什么需要**：`rm -rf /` 即使在受限用户下也能删掉该用户有权限的所有文件。Seccomp 可以在内核层拦截危险系统调用。

```python
# 白名单模式：只允许安全系统调用
READONLY_SYSCALLS = {
    "read", "write", "openat", "close", "stat", "fstat",
    "lseek", "mmap", "munmap", "brk", "rt_sigaction",
    "rt_sigprocmask", "ioctl", "pread64", "pwrite64",
    "readv", "writev", "access", "pipe", "select",
    "sched_yield", "nanosleep", "alarm", "getpid",
    "getuid", "getgid", "exit", "exit_group",
    # 网络只读
    "connect", "sendto", "recvfrom",  # 限制目标地址
}

DANGEROUS_SYSCALLS = {
    "unlink", "unlinkat",     # 删除文件
    "rename", "renameat",     # 重命名
    "chmod", "fchmod",        # 改权限
    "mount", "umount2",       # 挂载操作
    "reboot", "shutdown",     # 系统操作
    "ptrace",                  # 进程注入
    "init_module", "delete_module",  # 内核模块
}
```

### 1.5 实现路径

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| P0 | OverlayFS 写时复制 + FileChangeReport | **立即** |
| P0 | mount namespace 隔离 /tmp | **立即** |
| P1 | seccomp-bpf 系统调用过滤 | 高 |
| P1 | cgroup v2 资源限制（替代 rlimit） | 高 |
| P2 | network namespace + iptables 规则 | 中 |
| P2 | 沙箱预热池（复用 namespace 减少启动延迟） | 中 |

---

## 二、文件系统与文档智能

### 2.1 当前问题

项目没有真正的文档系统。`SnapshotManager` 只是文件级 cp，`Playbook` 是硬编码 Python 常量。

### 2.2 三层文档架构

```
┌──────────────────────────────────────────────────────┐
│ L3: 智能文档层                                        │
│  DocumentAgent: 解析 → 索引 → 问答 → 知识抽取         │
│  支持格式: .md .pdf .docx .log .conf .json .xml       │
├──────────────────────────────────────────────────────┤
│ L2: 版本化文件层                                       │
│  FileVersionManager: 写前快照 + 增量 diff + 回滚      │
│  FileAuditTrail: 谁在何时改了什么，diff 是什么        │
├──────────────────────────────────────────────────────┤
│ L1: 安全文件操作层                                     │
│  SafeFileOps: 所有文件操作经 SafetyGate + OverlayFS   │
│  FileChangeDetector: inotify + 周期性扫描             │
└──────────────────────────────────────────────────────┘
```

### 2.3 文档智能 Pipeline

```python
class DocumentPipeline:
    """文档智能处理流水线"""
    
    def ingest(self, path: Path) -> Document:
        """1. 格式检测 → 解析 → 结构化"""
        # PDF → pdfplumber → Markdown
        # DOCX → python-docx → Markdown  
        # LOG → regex 结构化 → JSON
        # CONF → AST 解析 → 键值对
    
    def chunk(self, doc: Document) -> list[Chunk]:
        """2. 语义分块 — 按段落/章节/逻辑单元切分"""
        # 不是固定 512 token 切分，而是按文档结构切
    
    def embed(self, chunks: list[Chunk]) -> list[Vector]:
        """3. 向量化 — 计算嵌入"""
        # 本地模型优先（BGE-small-zh），fallback OpenAI embedding
    
    def index(self, chunks: list[Chunk], vectors: list[Vector]):
        """4. 索引 — HNSW 向量索引 + BM25 关键词索引"""
        # 双路检索，合并排序
    
    def cross_reference(self, doc: Document) -> list[Reference]:
        """5. 交叉引用 — 自动发现文档间关联"""
        # "此配置项在 /etc/security/limits.conf 也有定义"
```

### 2.4 版本化文件操作

```python
@dataclass
class FileVersion:
    """每次写操作自动创建版本"""
    version_id: str       # uuid
    file_path: str
    parent_version: str   # 前一版本 ID
    diff_type: str        # "full" | "incremental"
    diff: str             # unified diff
    created_by: str       # agent_id 或 user_id
    created_at: str
    operation: str        # "modify" | "create" | "delete"
    trace_id: str
    
class FileVersionManager:
    def write(self, path: Path, content: bytes) -> FileVersion:
        """写操作：自动 diff 前一版本 → 存储增量 → 创建新版本"""
    
    def read(self, path: Path, version_id: str | None = None) -> bytes:
        """读操作：默认最新，可指定历史版本"""
    
    def history(self, path: Path) -> list[FileVersion]:
        """变更历史"""
    
    def rollback(self, path: Path, version_id: str) -> FileVersion:
        """回滚到指定版本"""
```

### 2.5 实现路径

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| P0 | FileVersionManager + 增量 diff 存储 | **立即** |
| P0 | SafeFileOps 接入 OverlayFS | **立即** |
| P1 | DocumentPipeline（PDF/DOCX/LOG 解析） | 高 |
| P1 | 双路检索（HNSW + BM25） | 高 |
| P2 | 自动交叉引用发现 | 中 |
| P2 | 文档变更通知 → 自动重新索引 | 中 |

---

## 三、终端智能模块

### 3.1 当前问题

`executor.py` 的 `run_terminal_sync` 是一个"无状态执行器"：收到命令 → 风险评估 → 执行 → 返回结果。它不理解上下文、不会学习、不会主动建议。

### 3.2 五阶段终端智能

```
用户输入 → ┌───────────┐ → ┌───────────┐ → ┌───────────┐ → ┌──────────┐ → ┌──────────┐
           │ 1.上下文   │   │ 2.预执行   │   │ 3.安全执行 │   │4.后验证  │   │5.学习归档│
           │   感知     │ → │   分析     │ → │   沙箱    │ → │   审计   │ → │   回流   │
           └───────────┘   └───────────┘   └───────────┘   └──────────┘   └──────────┘
```

### 3.3 各阶段设计

**阶段 1：上下文感知**

```python
class TerminalContext:
    """在每次命令执行前，自动采集当前上下文"""
    
    def gather(self) -> ContextSnapshot:
        return ContextSnapshot(
            # 系统状态
            cwd=os.getcwd(),
            current_user=pwd.getpwuid(os.getuid()).pw_name,
            load_avg=psutil.getloadavg(),
            mem_available=psutil.virtual_memory().available,
            disk_free=shutil.disk_usage(os.getcwd()).free,
            
            # 会话状态
            recent_commands=self._recent_commands(n=5),     # 最近 5 条命令
            recent_outputs=self._recent_outputs(n=5),        # 最近 5 条输出
            failed_count=self._recent_failure_count(),       # 最近失败次数
            session_duration=self._session_elapsed(),        # 会话时长
            
            # 文件状态
            modified_files=self._recently_modified_files(),  # 最近被修改的文件
            open_fds=self._open_file_descriptors(),          # 当前进程打开的文件
            
            # 安全状态
            safety_gate_status=get_safety_gate().status(),  # 安全闸门状态
            pending_alerts=get_unread_alert_count(),        # 未读告警
        )
```

**阶段 2：预执行分析**

```python
class PreExecutionAnalyzer:
    """命令执行前的多维分析"""
    
    def analyze(self, command: str, context: ContextSnapshot) -> PreExecReport:
        return PreExecReport(
            # 静态分析
            command_type=self._classify(command),       # 观测/修改/删除/网络/权限
            affected_paths=self._extract_paths(command),# 受影响的文件路径
            required_permissions=self._required_caps(command),  # 需要的权限
            estimated_impact=self._estimate_blast_radius(command, context),
            
            # 动态分析
            dry_run_result=self._dry_run_in_sandbox(command),   # 沙箱预演
            similar_past=self._find_similar_executions(command),# 相似历史命令
            past_success_rate=self._success_rate(similar_past), # 历史成功率
            
            # 风险评分
            risk_score=self._calculate_risk(command, context, dry_run_result),
            risk_factors=self._explain_risk(risk_score),        # 可解释的风险因子
        )
```

**阶段 3：安全执行（连接全域沙箱）**

```python
class IntelligentExecutor:
    """智能终端执行器 — 融合上下文+预分析+沙箱"""
    
    def execute(self, command: str, context: ContextSnapshot) -> ExecResult:
        # 1. 预分析
        pre = self.pre_analyzer.analyze(command, context)
        
        # 2. 自动建议（如果风险高）
        if pre.risk_score > 0.7:
            safer_alternatives = self._suggest_safer_alternatives(command, pre)
            # 例: "检测到 rm -rf /var/log/*，建议改为 logrotate 或先 tar 备份"
        
        # 3. 选择合适的沙箱 Profile
        profile = SandboxProfile.choose(pre.risk_score, pre.command_type)
        
        # 4. 在沙箱中执行（含 OverlayFS）
        result = self.sandbox.run(command, profile=profile)
        
        # 5. 生成可审计的 FileChangeReport
        changes = self.sandbox.diff_filesystem()
        
        return ExecResult(result=result, pre_analysis=pre, file_changes=changes)
```

**阶段 4：后执行验证**

```python
class PostExecutionVerifier:
    """执行后验证 —— 防止幻觉和误操作"""
    
    def verify(self, expected: PreExecReport, actual: ExecResult) -> VerifyReport:
        checks = []
        
        # 检查 1：PID/进程号是否真实存在（防止 LLM 幻觉）
        for pid_claim in self._extract_pids(actual.stdout):
            if not psutil.pid_exists(pid_claim):
                checks.append(Check.FAIL(f"PID {pid_claim} 不存在（可能为 LLM 幻觉）"))
        
        # 检查 2：文件路径是否真实
        for path_claim in self._extract_paths(actual.stdout):
            if not Path(path_claim).exists():
                checks.append(Check.WARN(f"路径 {path_claim} 不存在"))
        
        # 检查 3：操作结果是否与预期一致
        if expected.affected_paths and actual.file_changes:
            unexpected = set(actual.file_changes.paths) - set(expected.affected_paths)
            if unexpected:
                checks.append(Check.WARN(f"意外修改了文件: {unexpected}"))
        
        # 检查 4：副作用检测（端口被占用、服务被停止等）
        side_effects = self._detect_side_effects(actual)
        
        return VerifyReport(checks=checks, side_effects=side_effects, passed=all(c.ok for c in checks))
```

**阶段 5：学习归档**

```python
class ExecutionLearner:
    """从每次执行中学习，持续优化"""
    
    def learn(self, pre: PreExecReport, actual: ExecResult, verify: VerifyReport):
        # 1. 更新命令模板库（成功命令的模式提取）
        if actual.ok and verify.passed:
            self._update_command_template(pre.command, pre.command_type)
        
        # 2. 更新风险模型（如果预判和实际不符）
        if pre.risk_score > 0.5 and actual.ok:
            self._adjust_risk_model(pre.command_type, downward=True)
        
        # 3. 记录到知识库（可复用的操作经验）
        self._archive_to_knowledge_base(pre, actual, verify)
```

### 3.4 实现路径

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| P0 | TerminalContext 上下文采集 | **立即** |
| P0 | PreExecutionAnalyzer 预分析（含沙箱 dry-run） | **立即** |
| P1 | PostExecutionVerifier 增强（含文件变更交叉验证） | 高 |
| P1 | ExecutionLearner 学习归档 | 高 |
| P2 | 命令自动补全 + 更安全替代方案建议 | 中 |

---

## 四、告警降噪体系

### 4.1 当前问题

`alert_aggregator.py` 已经做了两件事：
- **衍生抑制**：磁盘爆满 → 自动抑制后续的"服务宕机""进程异常退出"等衍生告警
- **窗口去重**：5 分钟内同类型告警合并

但这还不够。生产环境的告警风暴有更多维度。

### 4.2 五层告警降噪

```
原始事件流
    │
    ▼
┌─────────────────────────────────────────────┐
│ Layer 1: 频率节流 (Rate Limiting)            │
│ 每个 (source, type) 组合: 最少间隔 30s       │
│ 超过频率的事件: 计数但不推送                  │
├─────────────────────────────────────────────┤
│ Layer 2: 窗口去重 (Window Dedup)             │
│ 5分钟窗口内同 key 合并 — 已有 ✅              │
├─────────────────────────────────────────────┤
│ Layer 3: 衍生抑制 (Derivative Suppress)       │
│ 根因事件触发后抑制衍生告警 — 已有 ✅          │
├─────────────────────────────────────────────┤
│ Layer 4: 关联聚合 (Correlation Aggregation)  │
│ 跨源关联: A 主机的 CPU 告警 + B 主机的相同告警│
│ → 聚合为 "集群 CPU 异常"                      │
├─────────────────────────────────────────────┤
│ Layer 5: 智能分级 (Smart Escalation)         │
│ 低频 → 仅日志 · 中频 → 浮屏 · 高频 → 桌面通知│
│ 持续未处理 → 自动升级严重度                   │
└─────────────────────────────────────────────┘
```

### 4.3 频率节流器

```python
class FrequencyThrottle:
    """每个告警类型独立节流，防止单源刷屏"""
    
    def __init__(self):
        self._last_emit: dict[str, float] = {}      # key → 上次发射时间
        self._pending_counts: dict[str, int] = {}    # key → 积压计数
        self._min_interval: dict[str, float] = {     # 最少间隔（秒）
            "P0": 15,   # 致命告警可以频繁
            "P1": 60,   # 严重告警每分钟最多1条
            "P2": 300,  # 中等告警每5分钟
            "P3": 900,  # 低等告警每15分钟
        }
    
    def should_emit(self, alert: Alert) -> tuple[bool, str]:
        key = f"{alert.source}:{alert.type}"
        grade = alert.grade
        min_interval = self._min_interval.get(grade, 300)
        
        now = time.time()
        last = self._last_emit.get(key, 0)
        
        if now - last >= min_interval:
            # 可以发射，带上积压计数
            pending = self._pending_counts.pop(key, 0)
            self._last_emit[key] = now
            return True, f"emit (suppressed {pending} in window)"
        else:
            # 节流，增加积压计数
            self._pending_counts[key] = self._pending_counts.get(key, 0) + 1
            return False, f"throttled (next allowed in {min_interval - (now - last):.0f}s)"
```

### 4.4 跨源关联引擎

```python
class CorrelationEngine:
    """多源告警关联分析"""
    
    # 关联规则（可扩展）
    CORRELATION_RULES = [
        {
            "name": "multi_host_same_type",
            "condition": lambda alerts: (
                len(set(a.host for a in alerts)) >= 3 and
                len(set(a.type for a in alerts)) == 1
            ),
            "action": "aggregate_to_cluster_alert",
            "new_title": "集群 {type} 异常（{count} 台主机）",
        },
        {
            "name": "time_cascade",
            "condition": lambda alerts: (
                # A 发生后 60s 内 B 发生，且 A→B 在因果图中
                any(a.type in CAUSAL_GRAPH.get(b.type, set()) for a, b in pairs(alerts))
            ),
            "action": "mark_as_cascade",
            "root_cause": "...",
        },
    ]
    
    def correlate(self, recent: list[Alert]) -> CorrelationResult:
        """分析最近告警的关联关系"""
```

### 4.5 浮屏控制

```python
class FloatingNotificationController:
    """浮屏通知的智能控制 —— 不是每条告警都弹窗"""
    
    FLOATING_RULES = {
        # (未读告警数, 最近告警严重度) → 浮屏行为
        (range(0, 3),   "P0"):  "toast",       # 少量 P0: Toast 3秒
        (range(0, 3),   "P1"):  "silent",      # 少量 P1: 仅侧栏角标
        (range(3, 10),  "P0"):  "banner",      # 中量 P0: 顶部横幅
        (range(3, 10),  "P1"):  "toast",       # 中量 P1: Toast
        (range(10, 999),any):   "modal",        # 大量: 模态框提醒
    }
    
    def decide(self, unread_count: int, highest_severity: str) -> FloatingAction:
        """根据当前状态决定浮屏策略"""
```

### 4.6 实现路径

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| P0 | FrequencyThrottle 频率节流器 | **立即** |
| P0 | FloatingNotificationController 浮屏控制 | **立即** |
| P0 | 告警分类从 8 种硬编码 → 可注册扩展 | **立即** |
| P1 | CorrelationEngine 跨源关联 | 高 |
| P1 | 告警历史分析（识别周期性假告警） | 高 |
| P2 | 告警升级策略（30 分钟未处理 → 升级严重度） | 中 |

---

## 五、对抗边界韧性

### 5.1 当前问题

`boundary_wiki.py` + `demo/boundary.py` 有基础的权限跃迁探针和边界测试，但缺少系统性。

### 5.2 四层对抗韧性

```
┌──────────────────────────────────────────────────┐
│ Layer 4: 对抗训练 (Adversarial Training)          │
│ 定期用新对抗样本微调检测模型                       │
├──────────────────────────────────────────────────┤
│ Layer 3: 边界 Fuzzing (Boundary Fuzzing)          │
│ 自动生成边界测试用例 → 沙箱执行 → 检测穿透         │
├──────────────────────────────────────────────────┤
│ Layer 2: 探针网格 (Probe Grid)                    │
│ 权限跃迁探针 + 文件逃逸探针 + 网络穿透探针         │
├──────────────────────────────────────────────────┤
│ Layer 1: 基线锚定 (Baseline Anchor)               │
│ 系统正常行为基线 → 任何偏离 → 告警                 │
└──────────────────────────────────────────────────┘
```

### 5.3 边界 Fuzzing 框架

```python
class BoundaryFuzzer:
    """自动化边界测试用例生成和执行"""
    
    MUTATION_STRATEGIES = [
        "path_traversal",        # ../../../etc/shadow
        "command_injection",     # cmd && malicious
        "env_injection",         # LD_PRELOAD=/malicious.so
        "symlink_escape",        # 符号链接逃逸
        "fd_leak",              # 文件描述符泄漏
        "time_of_check_to_time_of_use",  # TOCTOU 竞态
        "privilege_confusion",  # 权限混淆
    ]
    
    def generate_cases(self, base_command: str, count: int = 100) -> list[TestCase]:
        """基于变异策略生成测试用例"""
    
    def execute_batch(self, cases: list[TestCase]) -> list[TestResult]:
        """在隔离沙箱中批量执行，检测穿透"""
    
    def penetration_detected(self, result: TestResult) -> bool:
        """判断是否发生了沙箱穿透"""
        # 检测指标：
        # 1. 是否访问了不应访问的文件
        # 2. 是否建立了不应存在的网络连接
        # 3. 是否提升了权限
        # 4. 是否修改了系统配置
```

### 5.4 探针网格

```python
# 三类探针，定时在沙箱中运行
PROBE_GRID = {
    "privilege": [
        ("setuid_backdoor", "检测异常 setuid 二进制"),
        ("sudo_bypass", "检测 sudo 配置缺陷"),
        ("capability_leak", "检测进程 capabilities 泄漏"),
        ("container_escape", "检测容器逃逸路径"),
    ],
    "filesystem": [
        ("symlink_race", "符号链接竞态条件"),
        ("mount_escape", "挂载点逃逸"),
        ("procfs_leak", "/proc 信息泄漏"),
        ("tmp_poisoning", "/tmp 投毒攻击"),
    ],
    "network": [
        ("raw_socket", "原始套接字创建"),
        ("packet_injection", "数据包注入"),
        ("dns_tunneling", "DNS 隧道检测"),
        ("arp_spoofing", "ARP 欺骗检测"),
    ],
}
```

### 5.5 实现路径

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| P0 | 探针网格自动化（12 探针定时运行） | **立即** |
| P1 | BoundaryFuzzer 变异生成 + 批量执行 | 高 |
| P1 | 穿透检测告警联动（穿透 → 立即 P0 告警） | 高 |
| P2 | 对抗训练 pipeline（收集穿透案例 → 微调模型） | 中 |

---

## 六、知识库健壮性

### 6.1 当前问题

30 条硬编码 Playbook + TF-IDF 索引 + Gitee Wiki 单向同步。三个致命弱点：
1. **一致性**：没有机制保证 Playbook 之间不矛盾
2. **防污染**：Wiki 被恶意修改后，系统照单全收
3. **新鲜度**：Playbook 不会自动过期或更新

### 6.2 四维强化

```python
class KnowledgeGuard:
    """知识库健康守护"""
    
    def check_consistency(self) -> list[ConsistencyIssue]:
        """一致性检查"""
        issues = []
        for p1, p2 in itertools.combinations(PLAYBOOKS, 2):
            # 检查 1: 同一 threat_tag 下的 do_not 和 suggested_actions 不能矛盾
            if p1.threat_tags == p2.threat_tags:
                if any(a in p2.suggested_actions for a in p1.do_not):
                    issues.append(ConsistencyIssue.CONTRADICTION(p1, p2))
            
            # 检查 2: 关键词重叠度 > 80% 但建议动作矛盾 → 标记
            overlap = len(set(p1.keywords) & set(p2.keywords)) / len(set(p1.keywords) | set(p2.keywords))
            if overlap > 0.8:
                conflicts = self._find_action_conflicts(p1, p2)
                if conflicts:
                    issues.append(ConsistencyIssue.POTENTIAL_CONFLICT(p1, p2, conflicts))
        return issues
    
    def verify_wiki_integrity(self) -> IntegrityReport:
        """Wiki 完整性验证"""
        # 1. 哈希校验：对比上次同步的哈希，检测篡改
        # 2. 结构校验：必要字段是否存在
        # 3. 内容校验：是否有明显的注入攻击（JS/HTML 标签等）
        # 4. 来源校验：Git commit author 是否在信任列表中
    
    def check_freshness(self) -> list[StaleKnowledge]:
        """新鲜度检查"""
        # 1. Playbook 引用命令在系统中是否还存在
        # 2. 引用的文件路径是否还存在
        # 3. 基于最近告警数据，哪些 Playbook 从未被触发（可能过时）
        # 4. 哪些 threat_tag 最近高频出现但没有对应 Playbook（知识缺口）
    
    def auto_extract(self, incident: IncidentReport) -> PlaybookDraft:
        """从安全事件中自动抽取知识"""
        # 1. 分析事件的根因、处置步骤、结果
        # 2. 生成 Playbook 草稿
        # 3. 标记为 "待审核"
        # 4. 人工确认后加入知识库
```

### 6.3 知识验证闭环

```
事件发生 → 匹配 Playbook → 执行建议动作
    │                           │
    │         ┌─────────────────┘
    │         ▼
    │    动作有效？ 
    │    ├─ YES → 强化该 Playbook 权重
    │    └─ NO  → 标记 Playbook 可能过时
    │              │
    │              ▼
    │         自动生成修正建议 → 人工审核 → 更新 Playbook
    │                                        │
    └────────────────────────────────────────┘
             知识回流闭环
```

### 6.4 实现路径

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| P0 | KnowledgeGuard.consistency_check() | **立即** |
| P0 | Wiki 同步完整性验证（哈希+结构+内容） | **立即** |
| P1 | 知识新鲜度检查 + 自动过期标记 | 高 |
| P1 | 事件→知识自动抽取 pipeline | 高 |
| P2 | 知识反馈闭环（动作有效性追踪） | 中 |

---

## 七、总路线图

```
Phase 0 (立即 — 本周)
├── 全域沙箱: OverlayFS + mount namespace
├── 终端智能: TerminalContext + PreExecutionAnalyzer  
├── 告警降噪: FrequencyThrottle + FloatingNotificationController
├── 文档系统: FileVersionManager + SafeFileOps
├── 知识库: consistency_check + wiki integrity verify
└── 边界韧性: 探针网格定时运行

Phase 1 (高优 — 2 周内)
├── 全域沙箱: seccomp-bpf + cgroup v2
├── 终端智能: PostExecutionVerifier 增强 + ExecutionLearner
├── 告警降噪: CorrelationEngine 跨源关联  
├── 文档系统: DocumentPipeline 解析+索引
├── 知识库: freshness check + auto_extract
└── 边界韧性: BoundaryFuzzer

Phase 2 (中优 — 1 月内)
├── 全域沙箱: network namespace + 沙箱预热池
├── 终端智能: 命令建议 + 自动补全
├── 告警降噪: 升级策略 + 周期性假告警识别
├── 文档系统: 交叉引用 + 变更通知
├── 知识库: 反馈闭环
└── 边界韧性: 对抗训练 pipeline
```

---

## 八、代码组织

```
security_agent/
├── sandbox/                    # 全域沙箱（从 terminal/ 独立出来）
│   ├── __init__.py
│   ├── profile.py              # SandboxProfile 自动选层
│   ├── overlay.py              # OverlayFS 写时复制
│   ├── namespace.py            # mount/network/pid namespace 管理
│   ├── seccomp.py              # seccomp-bpf 过滤规则
│   ├── cgroup.py               # cgroup v2 资源控制
│   ├── fuzzer.py               # BoundaryFuzzer 边界测试
│   └── probes.py               # 探针网格
│
├── filesystem/                 # 文件系统层（新建）
│   ├── __init__.py
│   ├── version_manager.py      # FileVersionManager
│   ├── safe_ops.py              # SafeFileOps
│   ├── change_detector.py       # inotify + 周期性扫描
│   └── audit_trail.py           # 文件变更审计
│
├── document/                   # 文档智能（新建）
│   ├── __init__.py
│   ├── pipeline.py             # DocumentPipeline
│   ├── parsers/                # 格式解析器
│   │   ├── pdf.py
│   │   ├── docx.py
│   │   ├── log_parser.py
│   │   └── conf_parser.py
│   ├── chunker.py              # 语义分块
│   ├── embedder.py             # 向量化
│   └── indexer.py              # HNSW + BM25 双路索引
│
├── terminal/                   # 原有终端模块（增强）
│   ├── executor.py             # → IntelligentExecutor
│   ├── context.py              # TerminalContext（新增）
│   ├── pre_analyzer.py         # PreExecutionAnalyzer（新增）
│   ├── post_verifier.py        # PostExecutionVerifier（增强）
│   ├── learner.py              # ExecutionLearner（新增）
│   ├── sandbox.py              # → 迁移到 sandbox/，保留兼容接口
│   └── privilege.py            # 保留
│
├── notify/                     # 告警系统（增强）
│   ├── alert_aggregator.py     # 已有，保留
│   ├── throttle.py             # FrequencyThrottle（新增）
│   ├── correlator.py           # CorrelationEngine（新增）
│   ├── floating.py             # FloatingNotificationController（新增）
│   ├── alerts.py               # 已有，增强
│   └── webhook.py              # 已有
│
└── knowledge/                  # 知识库（增强）
    ├── playbooks.py            # 已有，增强（动态加载）
    ├── guard.py                # KnowledgeGuard（新增）
    ├── freshness.py            # 新鲜度检查（新增）
    ├── auto_extract.py         # 自动知识抽取（新增）
    └── gitee_wiki/             # 已有，增强（完整性验证）
```

---

*设计完成日期：2026-07-13 · 下一步：Phase 0 详细实现计划*
