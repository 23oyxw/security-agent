"""Fallback 机制 — 主模型失败时自动切换到备用模型.

无需 LiteLLM，在应用层实现自动回退。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from openai import OpenAI, APIError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_log,
    after_log,
)

from security_agent import config
from security_agent.resilience.budget import get_request_budget
from security_agent.resilience.circuit import (
    CircuitOpenError,
    get_circuit,
    reset_circuit,
    reset_circuits_prefix,
)

import logging
logger = logging.getLogger(__name__)


def _alternate_model_name(model: str) -> str | None:
    """API 拒绝当前 model id 时的同厂商备选."""
    m = model.lower()
    if config.using_litellm_proxy():
        if m in ("mimo-v2.5-pro", "mimo-v2.5", "mimo-chat"):
            return "mimo-fast"
        if m == "mimo-fast":
            return "mimo-chat"
        return None
    if m == "mimo-v2.5-pro":
        return "mimo-v2.5"
    if m in ("mimo-v2.5", "mimo-v2.5-pro"):
        return "mimo-v2.5"
    return None


def _llm_retry_decorator(max_attempts: int = 3):
    """tenacity 重试装饰器 — 指数退避 + 仅重试临时性错误."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (APIError, APITimeoutError, ConnectionError, TimeoutError)
        ),
        before=before_log(logger, logging.DEBUG),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )


@dataclass
class FallbackConfig:
    """Fallback 配置."""

    primary_model: str
    fallback_model: str
    fallback_base_url: str
    fallback_api_key: str
    max_retries: int = 1
    timeout: float = 30.0


class FallbackClient:
    """带自动回退的 OpenAI 客户端.

    主模型失败时自动切换到备用模型。
    """

    def __init__(
        self,
        primary_client: OpenAI,
        primary_model: str,
        fallback_config: FallbackConfig | None = None,
    ):
        self.primary_client = primary_client
        self.primary_model = primary_model.lower()

        # 自动构建 fallback 配置
        if fallback_config is None:
            fallback_config = self._build_fallback_config()

        self.fallback_config = fallback_config

        # 备用客户端（延迟初始化）
        self._fallback_client: OpenAI | None = None
        self._fallback_used_count = 0

    def _build_fallback_config(self) -> FallbackConfig | None:
        """根据主模型自动选择合适的备用模型."""
        primary = self.primary_model

        # MiMo 系列 -> DeepSeek（经 LiteLLM 时用 deepseek-chat 别名）
        if "mimo" in primary:
            fb_model, fb_url, fb_key = config.resolve_fallback_model(primary)
            if fb_key:
                return FallbackConfig(
                    primary_model=primary,
                    fallback_model=config.resolve_llm_model(fb_model),
                    fallback_base_url=fb_url,
                    fallback_api_key=fb_key,
                )

        # DeepSeek Chat -> DeepSeek Reasoner 或其他备用
        elif "deepseek-chat" in primary or "deepseek-v3" in primary or "deepseek-v4-flash" in primary:
            if config.AUTONOMOUS_API_KEY:
                return FallbackConfig(
                    primary_model=primary,
                    fallback_model="deepseek-v4-pro",
                    fallback_base_url=config.AUTONOMOUS_BASE_URL or "https://api.deepseek.com/v1",
                    fallback_api_key=config.AUTONOMOUS_API_KEY,
                )

        # 没有合适的备用
        return None

    @property
    def fallback_client(self) -> OpenAI | None:
        """获取或创建备用客户端."""
        if self._fallback_client is None and self.fallback_config:
            self._fallback_client = OpenAI(
                api_key=self.fallback_config.fallback_api_key,
                base_url=self.fallback_config.fallback_base_url,
            )
        return self._fallback_client

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> tuple[Any, dict[str, Any]]:
        """调用聊天完成，支持自动回退.

        Returns:
            (response, metadata) — metadata 包含是否使用了 fallback 等信息
        """
        metadata = {
            "primary_model": self.primary_model,
            "fallback_used": False,
            "fallback_model": None,
            "error": None,
        }

        circuit_key = f"llm:{self.primary_model}"
        circuit = get_circuit(
            circuit_key,
            failure_threshold=config.CIRCUIT_FAILURE_THRESHOLD,
            open_sec=config.CIRCUIT_OPEN_SEC,
        )
        if not circuit.allow():
            # 配置/模型修复后允许一次恢复（避免 Pro 名无效导致长期熔断）
            reset_circuit(circuit_key)
            alt = _alternate_model_name(self.primary_model)
            if alt:
                reset_circuit(f"llm:{alt}")
            reset_circuits_prefix("llm:")
            if not circuit.allow():
                raise CircuitOpenError(
                    f"LLM 熔断中: {self.primary_model}（可 POST /api/resilience/circuits/reset 或稍后重试）"
                )

        budget = get_request_budget()
        llm_timeout = (
            budget.slice_timeout("llm")
            if budget
            else (self.fallback_config.timeout if self.fallback_config else 60)
        )

        call_model = config.resolve_agent_model(self.primary_model)

        @_llm_retry_decorator(max_attempts=3)
        def _call_primary():
            return self.primary_client.chat.completions.create(
                model=call_model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                timeout=llm_timeout,
                **kwargs,
            )

        # 1. 尝试主模型（tenacity 指数退避重试临时性错误）
        try:
            response = _call_primary()
            circuit.record_success()
            fallback_model = self.fallback_config.fallback_model if self.fallback_config else None
            record_fallback_call(fallback_used=False, primary_model=self.primary_model, fallback_model=fallback_model)
            return response, metadata

        except (APIError, APITimeoutError, Exception) as e:
            metadata["error"] = str(e)
            error_str = str(e).lower()

            # 判断是否值得尝试 fallback（含无效模型名）
            should_fallback = (
                "timeout" in error_str
                or "429" in error_str
                or "rate limit" in error_str
                or "too many requests" in error_str
                or "server error" in error_str
                or "connection" in error_str
                or "unavailable" in error_str
                or "invalid model" in error_str
                or ("model" in error_str and "400" in error_str)
            )

            # 同端点换模型重试（如 mimo-v2.5-pro → mimo-v2.5）
            if should_fallback and "invalid model" in error_str:
                alt = _alternate_model_name(call_model) or _alternate_model_name(self.primary_model)
                if alt:
                    try:
                        response = self.primary_client.chat.completions.create(
                            model=alt,
                            messages=messages,
                            tools=tools,
                            tool_choice=tool_choice,
                            timeout=llm_timeout,
                            **kwargs,
                        )
                        circuit.record_success()
                        metadata["model_switched"] = alt
                        record_fallback_call(
                            fallback_used=False,
                            primary_model=alt,
                            fallback_model=self.fallback_config.fallback_model if self.fallback_config else None,
                        )
                        return response, metadata
                    except Exception:
                        pass

            if not should_fallback:
                circuit.record_failure(str(e))
                raise

        circuit.record_failure(str(metadata["error"]))

        # 2. 主模型失败，尝试备用模型
        if self.fallback_client and self.fallback_config:
            try:
                fb_model = config.resolve_agent_model(self.fallback_config.fallback_model)
                response = self.fallback_client.chat.completions.create(
                    model=fb_model,
                    messages=messages,
                    tools=tools if tools else None,
                    timeout=llm_timeout,
                    **{k: v for k, v in kwargs.items() if k not in ["tools", "tool_choice"]},
                )

                self._fallback_used_count += 1
                metadata["fallback_used"] = True
                metadata["fallback_model"] = self.fallback_config.fallback_model
                circuit.record_success()
                record_fallback_call(
                    fallback_used=True,
                    primary_model=self.primary_model,
                    fallback_model=self.fallback_config.fallback_model,
                )
                return response, metadata

            except Exception as e2:
                metadata["error"] = f"主模型: {metadata['error']}; 备用模型: {e2}"
                circuit.record_failure(str(e2))
                raise RuntimeError(f"主模型和备用模型均失败: {metadata['error']}") from e2

        raise RuntimeError(f"主模型失败且未配置备用模型: {metadata['error']}")

    def get_stats(self) -> dict[str, Any]:
        """获取 fallback 统计信息."""
        return {
            "primary_model": self.primary_model,
            "fallback_model": self.fallback_config.fallback_model if self.fallback_config else None,
            "fallback_used_count": self._fallback_used_count,
            "fallback_available": self.fallback_config is not None,
        }


# 全局 fallback 统计（用于 UI 显示）
_fallback_stats: dict[str, Any] = {
    "total_calls": 0,
    "fallback_triggers": 0,
    "primary_model": None,
    "fallback_model": None,
}


def get_fallback_stats() -> dict[str, Any]:
    """获取全局 fallback 统计."""
    return _fallback_stats.copy()


def reset_fallback_stats() -> None:
    """重置 fallback 统计."""
    _fallback_stats["total_calls"] = 0
    _fallback_stats["fallback_triggers"] = 0
    _fallback_stats["primary_model"] = None
    _fallback_stats["fallback_model"] = None


def record_fallback_call(fallback_used: bool, primary_model: str, fallback_model: str | None = None) -> None:
    """记录一次 fallback 调用统计."""
    _fallback_stats["total_calls"] += 1
    _fallback_stats["primary_model"] = primary_model
    if fallback_model:
        _fallback_stats["fallback_model"] = fallback_model
    if fallback_used:
        _fallback_stats["fallback_triggers"] += 1
