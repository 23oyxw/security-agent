# 🚀 快速启动指南

## 方法1: 使用启动脚本（推荐）

```bash
cd /home/oy0/security-agent
bash start_streamlit.sh
```

## 方法2: 使用uv直接启动

```bash
cd /home/oy0/security-agent
uv run streamlit run streamlit_app.py
```

## 方法3: 使用boot脚本

```bash
cd /home/oy0/security-agent
bash boot_start.sh
```

## 访问界面

启动后，在浏览器中打开:
- 本地: http://localhost:8501
- 远程: http://<你的IP>:8501

## 常见问题

### 1. 端口被占用
```bash
# 查看占用端口的进程
lsof -i :8501
# 杀死进程
kill -9 <PID>
```

### 2. 权限问题
确保使用uv环境运行：
```bash
uv sync
uv run streamlit run streamlit_app.py
```

### 3. 模块导入错误
设置PYTHONPATH：
```bash
export PYTHONPATH="/home/oy0/security-agent:$PYTHONPATH"
```

## 实时同步功能

系统支持以下实时同步功能：
- ✅ 系统状态实时监控
- ✅ 风险指标实时更新
- ✅ 追踪数据实时刷新
- ✅ 健康检查实时执行
