"""Agent 对话路由"""

import time
import uuid
from fastapi import APIRouter, Depends
from security_agent.api.deps import get_current_user
from security_agent.api.chat_payload import build_chat_payload
from security_agent.api.models import ChatRequest, ChatResponse
from security_agent.auth.models import User

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user: User = Depends(get_current_user)):
    """Agent 对话"""
    session_id = req.session_id or str(uuid.uuid4())[:8]
    try:
        from security_agent.agent.brain import AgentBrain
        brain = AgentBrain(session_id=session_id)
        result = await brain.chat(req.message)
        return ChatResponse(**build_chat_payload(result, session_id))
    except Exception as e:
        return ChatResponse(
            reply=f"[降级] 无法调用 Agent 引擎: {e}",
            session_id=session_id,
        )
