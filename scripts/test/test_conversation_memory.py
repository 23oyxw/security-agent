#!/usr/bin/env python3
"""
对话历史持久化集成测试
"""

import os
import sys
import tempfile
import json
from datetime import datetime

# 添加项目路径
sys.path.insert(0, "/home/oy0/security-agent")

# 设置测试环境变量
os.environ["LLM_API_KEY"] = "test_key"
os.environ["AUTONOMOUS_API_KEY"] = "test_key"

def test_conversation_memory():
    """测试ConversationMemory基本功能"""
    print("测试1: ConversationMemory基本功能")
    
    from security_agent.memory.conversation_memory import ConversationMemory
    
    # 使用临时数据库
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name
    
    try:
        memory = ConversationMemory(test_db)
        
        # 测试添加消息
        session_id = "test_session_001"
        memory.add_message(session_id, "system", "你是安全运维助手")
        memory.add_message(session_id, "user", "检查系统状态")
        memory.add_message(session_id, "assistant", "系统运行正常")
        
        # 测试获取消息
        messages = memory.get_messages(session_id)
        assert len(messages) == 3, f"期望3条消息，实际{len(messages)}条"
        
        # 测试LLM格式
        llm_messages = memory.get_history_for_llm(session_id)
        assert len(llm_messages) == 3, f"期望3条LLM消息，实际{len(llm_messages)}条"
        
        # 测试统计
        stats = memory.get_conversation_stats(session_id)
        assert stats["message_count"] == 3, f"期望3条统计，实际{stats['message_count']}条"
        
        print("  ✅ ConversationMemory基本功能测试通过")
        return True
        
    finally:
        if os.path.exists(test_db):
            os.unlink(test_db)


def test_persistence():
    """测试持久化功能"""
    print("\n测试2: 持久化功能")
    
    from security_agent.memory.conversation_memory import ConversationMemory
    
    # 使用临时数据库
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name
    
    try:
        # 第一次实例
        memory1 = ConversationMemory(test_db)
        session_id = "test_persistence_001"
        
        memory1.add_message(session_id, "user", "第一条消息")
        memory1.add_message(session_id, "assistant", "第一条回复")
        
        # 第二次实例（模拟重启）
        memory2 = ConversationMemory(test_db)
        messages = memory2.get_messages(session_id)
        
        assert len(messages) == 2, f"期望2条消息，实际{len(messages)}条"
        assert messages[0]["content"] == "第一条消息", "消息内容不匹配"
        
        print("  ✅ 持久化功能测试通过")
        return True
        
    finally:
        if os.path.exists(test_db):
            os.unlink(test_db)


def test_brain_integration():
    """测试brain.py集成"""
    print("\n测试3: brain.py集成")
    
    try:
        from security_agent.agent.brain import AgentBrain
        
        # 检查类是否有记忆相关属性
        # 由于需要API调用，我们只检查类定义
        
        # 检查方法是否存在
        assert hasattr(AgentBrain, '_load_history_from_db'), "缺少_load_history_from_db方法"
        assert hasattr(AgentBrain, '_save_message_to_db'), "缺少_save_message_to_db方法"
        
        print("  ✅ brain.py集成测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ brain.py集成测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("="*60)
    print("对话历史持久化集成测试")
    print("="*60)
    
    测试结果 = []
    
    # 执行测试
    测试结果.append(("ConversationMemory基本功能", test_conversation_memory()))
    测试结果.append(("持久化功能", test_persistence()))
    测试结果.append(("brain.py集成", test_brain_integration()))
    
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
    
    if 通过数 == len(测试结果):
        print("🎉 所有测试通过！")
        return 0
    else:
        print("⚠️ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
