"""WebSocket 实时 Agent 对话 — JWT 认证 + 心跳."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from security_agent.api.chat_payload import build_chat_payload
from security_agent.auth.jwt_utils import decode_access_token

router = APIRouter()

HEARTBEAT_INTERVAL = 30

active_connections: dict[str, dict[str, Any]] = {}


def _authenticate_ws(data: dict) -> tuple[bool, str, str]:
    token = data.get("token", "")
    if not token:
        return False, "anonymous", "viewer"
    payload = decode_access_token(token)
    if payload is None:
        return False, "anonymous", "viewer"
    return True, payload.get("sub", "anonymous"), payload.get("role", "viewer")


async def _heartbeat_sender(websocket: WebSocket, session_id: str) -> None:
    while session_id in active_connections:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        if session_id not in active_connections:
            return
        try:
            await websocket.send_json({"type": "ping"})
        except Exception:
            return


@router.websocket("/ws/chat")
async def agent_chat_ws(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())[:8]
    username = "anonymous"
    role = "viewer"
    authenticated = False

    active_connections[session_id] = {
        "username": username,
        "role": role,
        "authenticated": False,
        "last_pong": time.time(),
    }
    heartbeat_task = asyncio.create_task(_heartbeat_sender(websocket, session_id))

    try:
        await websocket.send_json({
            "type": "system",
            "content": f"安全运维 Agent 已就绪 [session: {session_id}]",
            "session_id": session_id,
            "auth_required": True,
        })

        while True:
            data = await asyncio.wait_for(websocket.receive_json(), timeout=120.0)
            msg_type = data.get("type", "chat")
            message = data.get("message", "")

            if msg_type in ("ping", "pong"):
                active_connections[session_id]["last_pong"] = time.time()
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "auth":
                ok, auth_user, auth_role = _authenticate_ws(data)
                if ok:
                    username, role, authenticated = auth_user, auth_role, True
                    active_connections[session_id].update(
                        username=username, role=role, authenticated=True,
                    )
                    await websocket.send_json({
                        "type": "auth_ok",
                        "username": username,
                        "role": role,
                        "session_id": session_id,
                    })
                else:
                    await websocket.send_json({
                        "type": "auth_error",
                        "content": "认证失败: 无效的 token",
                        "session_id": session_id,
                    })

            elif msg_type == "chat":
                if not authenticated:
                    await websocket.send_json({
                        "type": "error",
                        "content": "请先发送 {type: 'auth', token: '<jwt>'}",
                        "session_id": session_id,
                    })
                    continue

                await websocket.send_json({"type": "typing", "session_id": session_id})
                try:
                    reply = await process_agent_message(session_id, message)
                    await websocket.send_json({
                        "type": "response",
                        "content": reply.get("reply", ""),
                        "session_id": session_id,
                        "tools_used": reply.get("tools_used", []),
                        "risk_level": reply.get("risk_level", "low"),
                        "trace_id": reply.get("trace_id", session_id),
                        "degradation_level": reply.get("degradation_level", "S0"),
                        "fallback_used": bool(reply.get("fallback_used")),
                        "token_usage": reply.get("token_usage") or {},
                        "cost_tokens": reply.get("cost_tokens", 0),
                        "cost_estimate": reply.get("cost_estimate") or {},
                        "context_usage": reply.get("context_usage") or {},
                        "execution_meta": reply.get("execution_meta") or {},
                        "plan_summary": reply.get("plan_summary") or {},
                        "model_used": reply.get("model_used", ""),
                        "skill_flow": reply.get("skill_flow", ""),
                        "reasoning": reply.get("reasoning", ""),
                    })
                except Exception as exc:
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Agent 处理异常: {exc}",
                        "session_id": session_id,
                    })

            elif msg_type == "status" and authenticated:
                await websocket.send_json({
                    "type": "status_response",
                    "active_sessions": len(active_connections),
                    "session_id": session_id,
                })

    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        try:
            await websocket.close(code=4000, reason="idle timeout")
        except Exception:
            pass
    finally:
        heartbeat_task.cancel()
        active_connections.pop(session_id, None)


async def process_agent_message(session_id: str, message: str) -> dict[str, Any]:
    from security_agent.agent.brain import AgentBrain

    brain = AgentBrain(session_id=session_id)
    result = await brain.chat(message)
    payload = build_chat_payload(result, session_id)
    payload["reasoning"] = (result.get("plan") or {}).get("intent", "general")
    return payload
