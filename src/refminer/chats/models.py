"""Chat session models for persistent storage."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class TimelineStep:
    phase: str
    message: str
    startTime: float  # epoch ms
    details: Optional[str] = None
    endTime: Optional[float] = None


@dataclass
class EvidenceSource:
    chunkId: str
    path: str
    page: Optional[int] = None
    section: Optional[str] = None
    text: str = ""
    score: float = 0.0
    bbox: Optional[list[dict]] = None


@dataclass
class ChatMessage:
    id: str
    role: str  # "user" or "ai"
    content: str
    timestamp: float  # epoch ms
    timeline: list[TimelineStep] = field(default_factory=list)
    sources: list[EvidenceSource] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    isStreaming: bool = False
    completedAt: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "timeline": [asdict(t) for t in self.timeline],
            "sources": [asdict(s) for s in self.sources],
            "keywords": self.keywords,
            "isStreaming": self.isStreaming,
            "completedAt": self.completedAt,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        return cls(
            id=data["id"],
            role=data["role"],
            content=data["content"],
            timestamp=data["timestamp"],
            timeline=[TimelineStep(**t) for t in data.get("timeline", [])],
            sources=[EvidenceSource(**s) for s in data.get("sources", [])],
            keywords=data.get("keywords", []),
            isStreaming=data.get("isStreaming", False),
            completedAt=data.get("completedAt"),
        )


@dataclass
class ChatSession:
    id: str
    title: str
    lastActive: float  # epoch ms
    messageCount: int = 0
    preview: str = ""
    messages: list[ChatMessage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "lastActive": self.lastActive,
            "messageCount": self.messageCount,
            "preview": self.preview,
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatSession":
        return cls(
            id=data["id"],
            title=data["title"],
            lastActive=data["lastActive"],
            messageCount=data.get("messageCount", 0),
            preview=data.get("preview", ""),
            messages=[ChatMessage.from_dict(m) for m in data.get("messages", [])],
        )
