"""本地风险演练与规则边界测试（仅用于演示/测试，不执行真实攻击）."""

from security_agent.demo.evaluator import run_detection_calibration
from security_agent.demo.fixture_catalog import DETECTION_FIXTURES, FIXTURE_CATEGORIES
from security_agent.demo.service import DemoService, get_demo_service

__all__ = [
    "DemoService",
    "get_demo_service",
    "run_detection_calibration",
    "DETECTION_FIXTURES",
    "FIXTURE_CATEGORIES",
]
