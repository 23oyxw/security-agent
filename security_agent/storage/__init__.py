"""存储管理模块"""

from security_agent.storage.trace_storage import (
    TraceStorage,
    get_trace_storage
)

from security_agent.storage.gate_storage import (
    GateStorage,
    get_gate_storage
)

__all__ = [
    "TraceStorage",
    "get_trace_storage",
    "GateStorage",
    "get_gate_storage"
]
