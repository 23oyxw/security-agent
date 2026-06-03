#!/usr/bin/env python3
"""
安全运维代理 - A2赛题修复验证脚本
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, "/home/oy0/security-agent")

def test_perception():
    """测试环境感知层"""
    print("测试1: 环境感知层")
    try:
        from security_agent.agent import perception
        if hasattr(perception, 'get_system_context'):
            context = perception.get_system_context()
            if context and len(context) > 100:
                print("  ✅ 环境感知层工作正常")
                print(f"     上下文长度: {len(context)} 字符")
                return True
            else:
                print("  ❌ 环境感知层返回空内容")
                return False
        else:
            print("  ❌ get_system_context函数不存在")
            return False
    except Exception as e:
        print(f"  ❌ 环境感知层测试失败: {e}")
        return False

def test_trace_context():
    """测试TraceContext"""
    print("\n测试2: TraceContext集成")
    try:
        from security_agent.audit.trace import TraceContext
        
        # 创建一个简单的追踪
        trace = TraceContext(user_message="测试消息")
        trace.__enter__()
        
        # 记录阶段
        trace.stage("test_stage", {"test": "data"})
        
        # 退出追踪
        trace.__exit__(None, None, None)
        
        print("  ✅ TraceContext工作正常")
        return True
    except Exception as e:
        print(f"  ❌ TraceContext测试失败: {e}")
        return False

def test_brain_integration():
    """测试brain.py集成"""
    print("\n测试3: brain.py集成")
    try:
        # 检查brain.py文件
        brain_path = "/home/oy0/security-agent/security_agent/agent/brain.py"
        with open(brain_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        检查项 = [
            ("TraceContext导入", "from security_agent.audit.trace import TraceContext"),
            ("TraceContext创建", "trace_ctx = TraceContext"),
            ("阶段记录", "trace_ctx.stage"),
            ("__exit__调用", "trace_ctx.__exit__"),
        ]
        
        通过 = 0
        for 描述, 关键词 in 检查项:
            if 关键词 in content:
                print(f"  ✅ {描述}")
                通过 += 1
            else:
                print(f"  ❌ {描述}")
        
        return 通过 >= 3
    except Exception as e:
        print(f"  ❌ brain.py集成测试失败: {e}")
        return False

def test_tool_registry():
    """测试工具注册"""
    print("\n测试4: 工具注册")
    try:
        from security_agent.tools.registry import TOOL_REGISTRY
        工具数量 = len(TOOL_REGISTRY)
        print(f"  ✅ 工具注册表工作正常")
        print(f"     工具数量: {工具数量}")
        
        # 显示前几个工具
        工具列表 = list(TOOL_REGISTRY.keys())[:5]
        print(f"     前5个工具: {工具列表}")
        return 工具数量 > 0
    except Exception as e:
        print(f"  ❌ 工具注册测试失败: {e}")
        return False

def test_knowledge_base():
    """测试知识库"""
    print("\n测试5: 知识库")
    try:
        知识库路径 = "/home/oy0/security-agent/security_agent/knowledge"
        if os.path.exists(知识库路径):
            playbooks_path = os.path.join(知识库路径, "playbooks.py")
            if os.path.exists(playbooks_path):
                print("  ✅ 知识库存在")
                
                # 读取playbooks.py
                with open(playbooks_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 查找类定义
                import re
                类定义 = re.findall(r'class\s+(\w+)', content)
                print(f"     剧本类: {类定义[:3]}")
                return True
            else:
                print("  ❌ playbooks.py不存在")
                return False
        else:
            print("  ❌ 知识库目录不存在")
            return False
    except Exception as e:
        print(f"  ❌ 知识库测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("="*60)
    print("安全运维代理 - A2赛题修复验证")
    print("="*60)
    
    测试结果 = []
    
    # 执行测试
    测试结果.append(("环境感知层", test_perception()))
    测试结果.append(("TraceContext集成", test_trace_context()))
    测试结果.append(("brain.py集成", test_brain_integration()))
    测试结果.append(("工具注册", test_tool_registry()))
    测试结果.append(("知识库", test_knowledge_base()))
    
    # 总结
    print("\n" + "="*60)
    print("测试总结:")
    print("-"*40)
    
    通过数 = 0
    for 名称, 结果 in 测试结果:
        状态 = "✅ 通过" if 结果 else "❌ 失败"
        print(f"  {名称}: {状态}")
        if 结果:
            通过数 += 1
    
    print("\n" + "="*60)
    print(f"测试结果: {通过数}/{len(测试结果)} 通过")
    
    if 通过数 >= 4:
        print("🎉 A2赛题修复验证通过！")
        return 0
    else:
        print("⚠️ 部分测试失败，需要检查")
        return 1

if __name__ == "__main__":
    sys.exit(main())
