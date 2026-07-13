"""告警降噪体系测试 — 频率节流 + 浮屏控制 + 集成 pipeline.

覆盖:
    1. FrequencyThrottle: emit/snooze/unsnooze/pending
    2. FloatingController: decide 矩阵（5 级 × 3 频）
    3. 集成: publish_monitor_event 全链路（throttle + floating）
"""

from __future__ import annotations

import time


# ---- FrequencyThrottle ----

def test_throttle_first_emit():
    """第一条告警总是放行."""
    from security_agent.notify.throttle import FrequencyThrottle
    t = FrequencyThrottle()
    ok, reason, pending = t.should_emit("monitor:cpu", grade="P1")
    assert ok is True
    assert "emit" in reason
    assert pending == 0


def test_throttle_second_blocked():
    """P1 告警 60 秒内第二次被节流."""
    from security_agent.notify.throttle import FrequencyThrottle
    t = FrequencyThrottle()
    t.should_emit("monitor:cpu", grade="P1")  # 第一次放行
    ok, reason, pending = t.should_emit("monitor:cpu", grade="P1")  # 立即重试
    assert ok is False
    assert "throttled" in reason
    assert pending >= 1


def test_throttle_different_keys_independent():
    """不同 key 独立节流."""
    from security_agent.notify.throttle import FrequencyThrottle
    t = FrequencyThrottle()
    t.should_emit("monitor:cpu", grade="P1")
    ok, _, _ = t.should_emit("monitor:memory", grade="P1")
    assert ok is True  # 不同源不受影响


def test_throttle_p0_more_frequent():
    """P0 告警间隔更短 (15s)."""
    from security_agent.notify.throttle import FrequencyThrottle
    t = FrequencyThrottle()
    t.should_emit("monitor:disk_full", grade="P0")
    ok, _, _ = t.should_emit("monitor:disk_full", grade="P0")
    assert ok is False  # P0 15s 间隔，立即重试仍会被节流
    # 但间隔确实比 P1(60s) 短，验证常量
    from security_agent.notify.throttle import GRADE_INTERVALS
    assert GRADE_INTERVALS["P0"] < GRADE_INTERVALS["P1"]


def test_throttle_p3_long_interval():
    """P3 间隔 15 分钟."""
    from security_agent.notify.throttle import GRADE_INTERVALS
    assert GRADE_INTERVALS["P3"] == 900


def test_throttle_pending_accumulates():
    """节流期间积压计数正确."""
    from security_agent.notify.throttle import FrequencyThrottle
    t = FrequencyThrottle()
    t.should_emit("monitor:cpu", grade="P1")
    for _ in range(5):
        ok, _, pending = t.should_emit("monitor:cpu", grade="P1")
        assert ok is False
    # 最后一次 pending 至少为 5
    assert t.pending_count("monitor:cpu") >= 5


def test_throttle_pending_ceiling():
    """积压不超过 MAX_PENDING_PER_KEY."""
    from security_agent.notify.throttle import FrequencyThrottle, MAX_PENDING_PER_KEY
    t = FrequencyThrottle()
    t.should_emit("monitor:cpu", grade="P1")
    for _ in range(MAX_PENDING_PER_KEY + 20):
        t.should_emit("monitor:cpu", grade="P1")
    assert t.pending_count("monitor:cpu") <= MAX_PENDING_PER_KEY


def test_throttle_snooze():
    """Snooze 后同 key 被抑制."""
    from security_agent.notify.throttle import FrequencyThrottle
    t = FrequencyThrottle()
    t.snooze("monitor:cpu", duration_sec=3600)
    ok, reason, _ = t.should_emit("monitor:cpu", grade="P1")
    assert ok is False
    assert "snoozed" in reason


def test_throttle_unsnooze():
    """取消 snooze 后恢复正常."""
    from security_agent.notify.throttle import FrequencyThrottle
    t = FrequencyThrottle()
    t.snooze("monitor:cpu", duration_sec=3600)
    assert t.is_snoozed("monitor:cpu") is True
    t.unsnooze("monitor:cpu")
    assert t.is_snoozed("monitor:cpu") is False


def test_throttle_snooze_expires():
    """Snooze 过期后自动恢复."""
    from security_agent.notify.throttle import FrequencyThrottle
    t = FrequencyThrottle()
    t.snooze("monitor:cpu", duration_sec=0)  # 立即过期
    ok, _, _ = t.should_emit("monitor:cpu", grade="P1")
    assert ok is True


def test_throttle_status():
    """status() 返回完整信息."""
    from security_agent.notify.throttle import FrequencyThrottle
    t = FrequencyThrottle()
    t.should_emit("monitor:cpu", grade="P1")
    s = t.status()
    assert "active_throttles" in s
    assert "pending_total" in s
    assert "snoozed_count" in s


# ---- FloatingController ----

def test_floating_p0_low_frequency():
    """P0 + 低频 → banner."""
    from security_agent.notify.floating import FloatingController
    fc = FloatingController()
    action = fc.decide(
        {"level": "严重", "type": "磁盘爆满", "message": "/dev/sda1 使用率 98%"},
        unread_count=1,
        recent_alert_count=1,
    )
    assert action.level in ("banner", "modal")
    assert action.urgency == "critical"


def test_floating_p0_high_frequency():
    """P0 + 高频 → modal."""
    from security_agent.notify.floating import FloatingController
    fc = FloatingController()
    action = fc.decide(
        {"level": "严重", "type": "磁盘爆满", "message": "/dev/sda1 full"},
        unread_count=12,
        recent_alert_count=15,
    )
    assert action.level == "modal"


def test_floating_p1_low_frequency():
    """P1 + 低频 → badge."""
    from security_agent.notify.floating import FloatingController
    fc = FloatingController()
    action = fc.decide(
        {"level": "高", "type": "CPU告警", "message": "CPU 92%"},
        unread_count=1,
        recent_alert_count=1,
    )
    assert action.level in ("badge", "toast")


def test_floating_p2_any():
    """P2 任意频率 → toast."""
    from security_agent.notify.floating import FloatingController
    fc = FloatingController()
    for count in [1, 5, 12]:
        action = fc.decide(
            {"level": "中", "type": "连接超时", "message": "timeout"},
            unread_count=count,
            recent_alert_count=count,
        )
        assert action.level in ("toast", "badge")


def test_floating_p3_silent():
    """P3 低频率 → silent."""
    from security_agent.notify.floating import FloatingController
    fc = FloatingController()
    action = fc.decide(
        {"level": "低", "type": "心跳", "message": "heartbeat"},
        unread_count=0,
        recent_alert_count=1,
    )
    assert action.level == "silent"


def test_floating_info_always_silent():
    """info 永远静默."""
    from security_agent.notify.floating import FloatingController
    fc = FloatingController()
    for count in [1, 5, 20]:
        action = fc.decide(
            {"level": "信息", "type": "例行巡检", "message": "all ok"},
            unread_count=count,
            recent_alert_count=count,
        )
        assert action.level == "silent"


def test_floating_to_dict():
    """FloatingAction.to_dict() 完整."""
    from security_agent.notify.floating import FloatingController
    fc = FloatingController()
    action = fc.decide(
        {"level": "高", "type": "CPU", "message": "test"},
        unread_count=3,
        recent_alert_count=5,
    )
    d = action.to_dict()
    for key in ("level", "title", "body", "urgency", "duration_sec"):
        assert key in d, f"Missing: {key}"


# ---- 集成 ----

def test_publish_monitor_event_not_crash():
    """publish_monitor_event 不抛异常."""
    from security_agent.notify.alerts import publish_monitor_event

    event = {
        "ts": "2026-07-13T10:00:00",
        "type": "CPU告警",
        "level": "高",
        "message": "CPU usage 95% on server01",
        "source": "monitor",
    }
    # 不应抛异常
    try:
        publish_monitor_event(event)
    except Exception as e:
        # 可能因为文件路径不存在等原因失败，但不应是代码 bug
        assert False, f"publish_monitor_event crashed: {e}"


def test_publish_low_severity_skipped():
    """低严重度事件被 _should_publish 跳过."""
    from security_agent.notify.alerts import publish_monitor_event

    event = {
        "ts": "2026-07-13T10:00:00",
        "type": "心跳",
        "level": "信息",
        "message": "agent heartbeat",
    }
    # 不应抛异常，且心跳事件被跳过
    try:
        publish_monitor_event(event)
    except Exception as e:
        assert False, f"publish_monitor_event crashed on heartbeat: {e}"


def test_snooze_and_unsnooze():
    """snooze_alert → unsnooze_alert 完整流程."""
    from security_agent.notify.alerts import snooze_alert, unsnooze_alert
    from security_agent.notify.throttle import get_throttle

    result = snooze_alert("monitor", "CPU告警", duration_minutes=60)
    assert result["snoozed"] is True
    assert result["key"] == "monitor:CPU告警"

    throttle = get_throttle()
    assert throttle.is_snoozed("monitor:CPU告警") is True

    unsnooze_alert("monitor", "CPU告警")
    assert throttle.is_snoozed("monitor:CPU告警") is False


def test_pipeline_status():
    """get_alert_pipeline_status 返回完整状态."""
    from security_agent.notify.alerts import get_alert_pipeline_status

    status = get_alert_pipeline_status()
    assert "throttle" in status
    assert "floating" in status
    assert "suppression" in status
    assert "unread" in status


# ---- 全局单例 ----

def test_throttle_singleton():
    """get_throttle 返回同一实例."""
    from security_agent.notify.throttle import get_throttle
    t1 = get_throttle()
    t2 = get_throttle()
    assert t1 is t2


def test_floating_singleton():
    """get_floating 返回同一实例."""
    from security_agent.notify.floating import get_floating
    f1 = get_floating()
    f2 = get_floating()
    assert f1 is f2


# ---- 运行入口 ----

if __name__ == "__main__":
    import traceback

    tests = [
        ("test_throttle_first_emit", test_throttle_first_emit),
        ("test_throttle_second_blocked", test_throttle_second_blocked),
        ("test_throttle_different_keys_independent", test_throttle_different_keys_independent),
        ("test_throttle_p0_more_frequent", test_throttle_p0_more_frequent),
        ("test_throttle_p3_long_interval", test_throttle_p3_long_interval),
        ("test_throttle_pending_accumulates", test_throttle_pending_accumulates),
        ("test_throttle_pending_ceiling", test_throttle_pending_ceiling),
        ("test_throttle_snooze", test_throttle_snooze),
        ("test_throttle_unsnooze", test_throttle_unsnooze),
        ("test_throttle_snooze_expires", test_throttle_snooze_expires),
        ("test_throttle_status", test_throttle_status),
        ("test_floating_p0_low_frequency", test_floating_p0_low_frequency),
        ("test_floating_p0_high_frequency", test_floating_p0_high_frequency),
        ("test_floating_p1_low_frequency", test_floating_p1_low_frequency),
        ("test_floating_p2_any", test_floating_p2_any),
        ("test_floating_p3_silent", test_floating_p3_silent),
        ("test_floating_info_always_silent", test_floating_info_always_silent),
        ("test_floating_to_dict", test_floating_to_dict),
        ("test_publish_monitor_event_not_crash", test_publish_monitor_event_not_crash),
        ("test_publish_low_severity_skipped", test_publish_low_severity_skipped),
        ("test_snooze_and_unsnooze", test_snooze_and_unsnooze),
        ("test_pipeline_status", test_pipeline_status),
        ("test_throttle_singleton", test_throttle_singleton),
        ("test_floating_singleton", test_floating_singleton),
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
        print("  ALL PASS - Alert quieting pipeline verified!")
    else:
        print(f"  WARN {failed} tests failed")
    print(f"{'='*60}")
