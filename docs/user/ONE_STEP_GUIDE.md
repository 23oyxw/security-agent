# 安全运维代理 - 一步到位执行指南

## 📋 当前状态
- 项目路径: /home/oy0/security-agent
- 生成时间: 2026-05-22 18:23:38
- 关键修复: 已完成（环境感知、TraceContext、权限隔离脚本）

## 🚀 执行步骤

### 步骤1: 运行一步到位脚本（需要root权限）
```bash
cd /home/oy0/security-agent
sudo bash one_step_complete.sh
```

### 步骤2: 设置环境变量（如果需要）
```bash
# 编辑.env文件，设置API密钥
nano .env

# 主要变量:
# LLM_API_KEY=your_mimo_key
# AUTONOMOUS_API_KEY=your_deepseek_key
```

### 步骤3: 运行测试验证
```bash
# 冒烟测试
uv run python scripts/smoke_test.py

# 风险演练校准
uv run python scripts/demo_risk.py calibration
```

### 步骤4: 启动应用
```bash
bash boot_start.sh
# 浏览器打开: http://localhost:8501
```

## 🔧 故障排除

### 1. 受限用户创建失败
```bash
# 手动创建
sudo useradd -r -s /bin/false -M agent_ops
sudo mkdir -p /var/log/security_agent
sudo chown agent_ops:agent_ops /var/log/security_agent
```

### 2. 依赖安装失败
```bash
# 重新安装依赖
uv sync --all-extras
```

### 3. 测试失败
```bash
# 检查环境变量
cat .env | grep API_KEY

# 检查Python环境
python3 -c "import security_agent"
```

## 📊 验证结果

### A2赛题要求满足情况
1. ✅ MCP插件丰富度: 23+26工具
2. ⚠️ 安全校验能力: 需要运行权限隔离脚本
3. ✅ 推理链路可追溯性: TraceContext已集成

### 项目架构
- 当前: 单体应用 (monolithic)
- 建议: 短期完善，中长期微服务化

---
生成时间: 2026-05-22 18:23:38
