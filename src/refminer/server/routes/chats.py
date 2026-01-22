"""Chat session endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from refminer.server.globals import chat_manager
from refminer.server.models import (
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatMessageAdd,
    ChatMessageUpdate,
)

router = APIRouter(prefix="/api/projects/{project_id}/chats", tags=["chats"])


@router.get("")
async def get_chat_sessions(project_id: str):
    """Get all chat sessions for a project (without messages)."""
    sessions = chat_manager.get_sessions(project_id)
    return [s.to_dict() for s in sessions]


@router.post("")
async def create_chat_session(project_id: str, req: ChatSessionCreate):
    """Create a new chat session."""
    session = chat_manager.create_session(project_id, req.title)
    return session.to_dict()


@router.get("/{session_id}")
async def get_chat_session(project_id: str, session_id: str):
    """Get a specific chat session with all messages."""
    session = chat_manager.get_session(project_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session.to_dict()


@router.put("/{session_id}")
async def update_chat_session(project_id: str, session_id: str, req: ChatSessionUpdate):
    """Update a chat session (title and/or messages)."""
    session = chat_manager.update_session(
        project_id, session_id,
        title=req.title,
        messages=req.messages
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session.to_dict()


@router.delete("/{session_id}")
async def delete_chat_session(project_id: str, session_id: str):
    """Delete a chat session."""
    success = chat_manager.delete_session(project_id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"success": True}


@router.post("/{session_id}/messages")
async def add_chat_message(project_id: str, session_id: str, req: ChatMessageAdd):
    """Add a message to a chat session."""
    session = chat_manager.add_message(project_id, session_id, req.message)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session.to_dict()


@router.patch("/{session_id}/messages")
async def update_chat_message(project_id: str, session_id: str, req: ChatMessageUpdate):
    """Update a specific message in a chat session."""
    session = chat_manager.update_message(project_id, session_id, req.message_id, req.updates)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session.to_dict()
