"""能力装箱测试 — CapabilityRegistry + Guard + ToolBox + FlowBox + PluginBox."""

from __future__ import annotations


# ---- CapabilityGuard ----

def test_guard_call_success():
    """Guard 保护的成功调用."""
    from security_agent.capability.guard import CapabilityGuard
    g = CapabilityGuard()
    result = g.call("test:echo", lambda x: x.upper(), "hello", timeout=5)
    assert result.ok is True
    assert result.data == "HELLO"
    assert result.breaker_state == "closed"


def test_guard_call_failure():
    """Guard 保护的失败调用."""
    from security_agent.capability.guard import CapabilityGuard
    g = CapabilityGuard()

    def fail():
        raise ValueError("boom")

    result = g.call("test:fail", fail, timeout=5, max_retries=0)
    assert result.ok is False
    assert "boom" in result.error


def test_guard_breaker_opens():
    """连续失败 → 熔断器打开."""
    from security_agent.capability.guard import CapabilityGuard
    g = CapabilityGuard()

    def fail():
        raise ValueError("boom")

    for _ in range(6):
        g.call("test:breaker", fail, timeout=5, max_retries=0)

    result = g.call("test:breaker", lambda: "ok", timeout=5)
    assert result.ok is False
    assert "熔断器已打开" in result.error


def test_guard_reset():
    """reset 后熔断器恢复."""
    from security_agent.capability.guard import CapabilityGuard
    g = CapabilityGuard()

    def fail():
        raise ValueError("boom")

    for _ in range(6):
        g.call("test:reset", fail, timeout=5, max_retries=0)

    g.reset("test:reset")
    result = g.call("test:reset", lambda: "ok", timeout=5)
    assert result.ok is True


def test_guard_retry():
    """重试机制：第 2 次成功."""
    from security_agent.capability.guard import CapabilityGuard
    g = CapabilityGuard()

    call_count = [0]

    def flaky():
        call_count[0] += 1
        if call_count[0] < 2:
            raise ValueError("flaky")
        return "recovered"

    result = g.call("test:flaky", flaky, timeout=5, max_retries=2)
    assert result.ok is True
    assert result.data == "recovered"
    assert result.retries >= 1


def test_guard_status():
    """status() 返回完整信息."""
    from security_agent.capability.guard import CapabilityGuard
    g = CapabilityGuard()
    g.call("test:s1", lambda: "a", timeout=5)
    g.call("test:s2", lambda: "b", timeout=5)
    s = g.status()
    assert s["total_breakers"] >= 2


# ---- CapabilityRegistry ----

def test_registry_exists():
    """CapabilityRegistry 可以实例化."""
    from security_agent.capability import CapabilityRegistry
    caps = CapabilityRegistry()
    assert caps.tools is not None
    assert caps.flows is not None
    assert caps.plugins is not None


def test_registry_status():
    """status() 返回完整总览."""
    from security_agent.capability import CapabilityRegistry
    caps = CapabilityRegistry()
    s = caps.status()
    assert "tools" in s
    assert "flows" in s
    assert "plugins" in s


def test_tool_box_list():
    """ToolBox 列出工具."""
    from security_agent.capability import CapabilityRegistry
    caps = CapabilityRegistry()
    tools = caps.tools.list_all()
    assert isinstance(tools, list)


def test_flow_box_list():
    """FlowBox 列出工作流."""
    from security_agent.capability import CapabilityRegistry
    caps = CapabilityRegistry()
    flows = caps.flows.list_all()
    assert isinstance(flows, list)
    assert len(flows) >= 1  # 至少有内置的 5 个


def test_plugin_box_status():
    """PluginBox 状态."""
    from security_agent.capability import CapabilityRegistry
    caps = CapabilityRegistry()
    status = caps.plugins.status()
    assert "servers_count" in status
    assert "tools_count" in status


# ---- 装箱 vs 散落对比 ----

def test_unified_entry_point():
    """验证：主线只需 import CapabilityRegistry 一个入口."""
    # 模拟主线代码
    from security_agent.capability import CapabilityRegistry

    caps = CapabilityRegistry()

    # 工具
    tools = caps.tools.list_all()
    # 工作流
    flows = caps.flows.list_all()
    # 插件
    plugins = caps.plugins.list_servers()

    # 全部可用
    assert isinstance(tools, list)
    assert isinstance(flows, list)
    assert isinstance(plugins, list)


# ---- 运行入口 ----

if __name__ == "__main__":
    import traceback

    tests = [
        ("test_guard_call_success", test_guard_call_success),
        ("test_guard_call_failure", test_guard_call_failure),
        ("test_guard_breaker_opens", test_guard_breaker_opens),
        ("test_guard_reset", test_guard_reset),
        ("test_guard_retry", test_guard_retry),
        ("test_guard_status", test_guard_status),
        ("test_registry_exists", test_registry_exists),
        ("test_registry_status", test_registry_status),
        ("test_tool_box_list", test_tool_box_list),
        ("test_flow_box_list", test_flow_box_list),
        ("test_plugin_box_status", test_plugin_box_status),
        ("test_unified_entry_point", test_unified_entry_point),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS {name}")
            passed += 1
        except Exception:
            print(f"  FAIL {name}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{len(tests)} passed ({failed} failed)")
    if failed == 0:
        print("  ALL PASS - Capability boxing verified!")
    print(f"{'='*60}")
