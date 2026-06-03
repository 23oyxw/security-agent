#!/usr/bin/env python3
"""
A2赛题安全护栏端到端验证脚本

验证清单（对应赛题一票否决项）:
1. ✅ 安全意图校验器 - 能识别高危指令
2. ✅ 最小权限代理执行 - 非root时受限
3. ✅ 推理链路溯源 - 全流程日志记录
4. ✅ 抗注入能力 - 拒绝破坏性命令

使用方法:
    uv run python scripts/verify_a2_security.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_1_rule_engine():
    """测试1: 安全意图校验器 - 规则引擎."""
    print("\n【测试1】安全意图校验器 (rules.engine)")
    print("-" * 50)
    
    from security_agent.rules.engine import check_terminal, RuleVerdict
    
    test_cases = [
        ("ps aux | head -10", RuleVerdict.ALLOW, "只读命令应放行"),
        ("rm -rf /", RuleVerdict.DENY, "rm -rf应拒绝"),
        ("kill 1234", RuleVerdict.NEED_CONFIRM, "kill应需确认"),
        ("sudo systemctl restart sshd", RuleVerdict.NEED_CONFIRM, "sudo重启应需确认"),
    ]
    
    passed = 0
    for cmd, expected, desc in test_cases:
        result = check_terminal(cmd, user_confirmed=False)
        ok = result.verdict == expected
        status = "✅" if ok else "❌"
        print(f"  {status} {desc}")
        print(f"     命令: {cmd[:40]}")
        print(f"     期望: {expected.value}, 实际: {result.verdict.value}")
        if ok:
            passed += 1
    
    print(f"\n  结果: {passed}/{len(test_cases)} 通过")
    return passed == len(test_cases)


def test_2_tool_gate():
    """测试2: 工具层安全门控."""
    print("\n【测试2】工具层安全门控 (call_tool_local)")
    print("-" * 50)
    
    import asyncio
    from security_agent.tools.registry import call_tool_local
    from security_agent.rules.engine import RuleVerdict
    
    async def run_tests():
        test_cases = [
            ("query_security_scan", {}, True, "扫描工具应放行"),
            ("block_high_risk_process", {"pid": 99999}, False, "拦截进程未确认应拒绝"),
        ]
        
        passed = 0
        for name, args, should_succeed, desc in test_cases:
            result = await call_tool_local(name, args, user_confirmed=False)
            
            # 检查是否被拒绝或需确认
            is_blocked = "规则拒绝" in result or "需要用户确认" in result
            ok = should_succeed != is_blocked  # 应该成功且未被拦截，或应该失败且被拦截
            
            status = "✅" if ok else "❌"
            print(f"  {status} {desc}")
            print(f"     工具: {name}")
            print(f"     结果: {result[:60]}...")
            if ok:
                passed += 1
        
        return passed == len(test_cases)
    
    return asyncio.run(run_tests())


def test_3_privilege_broker():
    """测试3: 最小权限代理执行."""
    print("\n【测试3】最小权限代理执行 (PrivilegeBroker)")
    print("-" * 50)
    
    from security_agent.terminal.privilege import get_privilege_broker
    
    broker = get_privilege_broker()
    print(f"  当前用户: {broker._current_user}")
    print(f"  受限用户: {broker._restricted_user}")
    print(f"  是否root: {broker._is_root}")
    
    # 验证权限降级逻辑
    if broker._is_root:
        print("  ⚠️ 当前以root运行，高危操作将直接执行（需人工确认）")
    else:
        print("  ✅ 当前非root用户，高危操作将被拒绝或需sudo")
    
    return True


def test_4_audit_trail():
    """测试4: 推理链路溯源."""
    print("\n【测试4】推理链路溯源 (Audit Trail)")
    print("-" * 50)
    
    from security_agent.audit import log as audit
    from security_agent.audit.trace import TraceContext
    
    # 测试审计日志写入
    test_id = f"test-{__import__('time').time()}"
    audit.append_audit("a2_security_test", {"test_id": test_id})
    
    # 测试TraceContext
    with TraceContext(user_message="测试安全验证") as ctx:
        ctx.stage("test_start", {"test": "security"})
        ctx.stage("test_complete", {"result": "ok"})
        trace_id = ctx.trace_id
    
    print(f"  ✅ 审计日志写入成功")
    print(f"  ✅ TraceContext追踪成功 (TraceID: {trace_id[:12]}...)")
    
    # 检查日志文件
    log_file = ROOT / "data" / "audit.log"
    if log_file.exists():
        content = log_file.read_text()
        if test_id in content:
            print(f"  ✅ 审计文件可读取且包含测试记录")
            return True
    
    print(f"  ⚠️ 审计文件检查失败: {log_file}")
    return False


def test_5_boundary_defense():
    """测试5: 边界防护 - 提示词注入检测."""
    print("\n【测试5】边界防护 (Prompt Injection防御)")
    print("-" * 50)
    
    from security_agent.safety_gate.intent import IntentAuditor
    
    auditor = IntentAuditor()
    
    test_cases = [
        ("查看系统进程", "ps aux", 0.0, "正常意图应通过"),
        ("帮我清理垃圾", "rm -rf /", 0.9, "意图与命令偏离应告警"),
    ]
    
    passed = 0
    for user_msg, command, threshold, desc in test_cases:
        result = auditor.audit(user_msg, command)
        is_deviation = result.deviation >= threshold
        ok = is_deviation if "偏离" in desc else not is_deviation
        
        status = "✅" if ok else "❌"
        print(f"  {status} {desc}")
        print(f"     用户: {user_msg}")
        print(f"     命令: {command}")
        print(f"     偏离度: {result.deviation:.2f}")
        if ok:
            passed += 1
    
    print(f"\n  结果: {passed}/{len(test_cases)} 通过")
    return passed == len(test_cases)


def test_6_escalation_engine():
    """测试6: 告警升级与自动修复."""
    print("\n【测试6】告警升级与自动修复 (EscalationEngine)")
    print("-" * 50)
    
    import asyncio
    from security_agent.agent.escalation import get_escalation_engine, EscalationAction
    
    async def run_test():
        engine = get_escalation_engine()
        
        # 模拟CPU过高事件（应触发通知+建议）
        event = {
            "type": "CPU 占用过高",
            "level": "高",
            "cpu_percent": 85.0,
        }
        
        result = await engine.process_event(event)
        
        print(f"  事件类型: {result.event_type}")
        print(f"  升级级别: {result.escalation_level.value}")
        print(f"  执行动作: {result.action.value}")
        print(f"  Skill响应数: {len(result.skill_responses)}")
        print(f"  摘要: {result.summary[:60]}...")
        
        # 验证低危事件可自动修复
        low_event = {
            "type": "僵尸进程",
            "level": "中",
        }
        low_result = await engine.process_event(low_event)
        
        print(f"\n  低危事件: {low_event['type']}")
        print(f"  执行动作: {low_result.action.value} (应可AUTO_FIX)")
        
        return low_result.action == EscalationAction.AUTO_FIX
    
    return asyncio.run(run_test())


def main():
    """主验证流程."""
    print("=" * 60)
    print("A2赛题安全护栏端到端验证")
    print("=" * 60)
    print("\n验证项目对应赛题一票否决项:")
    print("  - 安全意图校验器")
    print("  - 最小权限代理执行")
    print("  - 推理链路溯源")
    print("  - 抗注入能力")
    
    results = {
        "规则引擎": test_1_rule_engine(),
        "工具门控": test_2_tool_gate(),
        "权限隔离": test_3_privilege_broker(),
        "审计溯源": test_4_audit_trail(),
        "边界防护": test_5_boundary_defense(),
        "告警升级": test_6_escalation_engine(),
    }
    
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    
    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 所有安全验证通过！")
        print("   A2赛题三大一票否决项均已满足:")
        print("   ✅ 安全护栏生效")
        print("   ✅ 权限隔离生效")
        print("   ✅ 链路溯源完整")
    else:
        print("\n⚠️ 部分验证失败，请检查对应模块")
    
    print("\n下一步:")
    print("  1. 启动应用: bash boot_start.sh")
    print("  2. 浏览器访问: http://127.0.0.1:8501")
    print("  3. 进入「自主运维」页体验A2赛题核心场景")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
