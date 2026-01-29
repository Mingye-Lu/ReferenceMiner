"""Chat session manager for persistent storage."""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from .models import ChatSession, ChatMessage


class ChatManager:
    """Manages chat sessions per project with file persistence."""

    def __init__(self, index_dir: Path):
        self.chats_dir = index_dir / "chats"
        self.chats_dir.mkdir(parents=True, exist_ok=True)

    def _get_project_file(self, project_id: str) -> Path:
        return self.chats_dir / f"{project_id}.json"

    def _load_project_chats(self, project_id: str) -> dict[str, ChatSession]:
        """Load all chat sessions for a project."""
        filepath = self._get_project_file(project_id)
        if not filepath.exists():
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    sid: ChatSession.from_dict(sdata)
                    for sid, sdata in data.get("sessions", {}).items()
                }
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading chats for {project_id}: {e}")
            return {}

    def _save_project_chats(
        self, project_id: str, sessions: dict[str, ChatSession]
    ) -> None:
        """Save all chat sessions for a project."""
        filepath = self._get_project_file(project_id)
        data = {
            "projectId": project_id,
            "sessions": {sid: s.to_dict() for sid, s in sessions.items()},
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_sessions(self, project_id: str) -> list[ChatSession]:
        """Get all chat sessions for a project (without messages for listing)."""
        sessions = self._load_project_chats(project_id)
        # Return sessions sorted by lastActive, newest first
        result = []
        for s in sessions.values():
            # Create a copy without messages for the list view
            result.append(
                ChatSession(
                    id=s.id,
                    title=s.title,
                    lastActive=s.lastActive,
                    messageCount=s.messageCount,
                    preview=s.preview,
                    messages=[],  # Don't include messages in list
                )
            )
        return sorted(result, key=lambda x: x.lastActive, reverse=True)

    def get_session(self, project_id: str, session_id: str) -> Optional[ChatSession]:
        """Get a specific chat session with all messages."""
        sessions = self._load_project_chats(project_id)
        return sessions.get(session_id)

    def create_session(self, project_id: str, title: str = "New Chat") -> ChatSession:
        """Create a new chat session."""
        sessions = self._load_project_chats(project_id)
        now = datetime.now().timestamp() * 1000  # epoch ms
        session_id = str(int(now))

        session = ChatSession(
            id=session_id,
            title=title,
            lastActive=now,
            messageCount=0,
            preview="Start a new conversation",
            messages=[],
        )
        sessions[session_id] = session
        self._save_project_chats(project_id, sessions)
        return session

    def update_session(
        self,
        project_id: str,
        session_id: str,
        title: Optional[str] = None,
        messages: Optional[list[dict]] = None,
    ) -> Optional[ChatSession]:
        """Update a chat session."""
        sessions = self._load_project_chats(project_id)
        session = sessions.get(session_id)
        if not session:
            return None

        if title is not None:
            session.title = title

        if messages is not None:
            session.messages = [ChatMessage.from_dict(m) for m in messages]
            session.messageCount = len(session.messages)
            if session.messages:
                last_msg = session.messages[-1]
                session.lastActive = last_msg.timestamp
                session.preview = last_msg.content[:50] if last_msg.content else ""

        self._save_project_chats(project_id, sessions)
        return session

    def delete_session(self, project_id: str, session_id: str) -> bool:
        """Delete a chat session."""
        sessions = self._load_project_chats(project_id)
        if session_id not in sessions:
            return False
        del sessions[session_id]
        self._save_project_chats(project_id, sessions)
        return True

    def add_message(
        self, project_id: str, session_id: str, message: dict
    ) -> Optional[ChatSession]:
        """Add a single message to a session."""
        sessions = self._load_project_chats(project_id)
        session = sessions.get(session_id)
        if not session:
            return None

        msg = ChatMessage.from_dict(message)
        session.messages.append(msg)
        session.messageCount = len(session.messages)
        session.lastActive = msg.timestamp
        session.preview = msg.content[:50] if msg.content else ""

        self._save_project_chats(project_id, sessions)
        return session

    def update_message(
        self, project_id: str, session_id: str, message_id: str, updates: dict
    ) -> Optional[ChatSession]:
        """Update a specific message in a session."""
        sessions = self._load_project_chats(project_id)
        session = sessions.get(session_id)
        if not session:
            return None

        for msg in session.messages:
            if msg.id == message_id:
                if "content" in updates:
                    msg.content = updates["content"]
                if "isStreaming" in updates:
                    msg.isStreaming = updates["isStreaming"]
                if "completedAt" in updates:
                    msg.completedAt = updates["completedAt"]
                if "timeline" in updates:
                    from .models import TimelineStep

                    msg.timeline = [TimelineStep(**t) for t in updates["timeline"]]
                if "sources" in updates:
                    from .models import EvidenceSource

                    msg.sources = [EvidenceSource(**s) for s in updates["sources"]]
                if "keywords" in updates:
                    msg.keywords = updates["keywords"]
                break

        # Update session metadata
        if session.messages:
            last_msg = session.messages[-1]
            session.lastActive = last_msg.timestamp
            session.preview = last_msg.content[:50] if last_msg.content else ""

        self._save_project_chats(project_id, sessions)
        return session

    def delete_all_project_chats(self, project_id: str) -> bool:
        """Delete all chats for a project."""
        filepath = self._get_project_file(project_id)
        if filepath.exists():
            filepath.unlink()
            return True
        return False
