"""Pydantic request models for the server API."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


# Project models
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


# Settings models
class ApiKeyRequest(BaseModel):
    api_key: str
    provider: Optional[str] = None


class ApiKeyValidateRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None


class LlmSettingsRequest(BaseModel):
    base_url: str
    model: str
    provider: Optional[str] = None


class ModelsListRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    provider: Optional[str] = None


# Chat models
class ChatSessionCreate(BaseModel):
    title: str = "New Chat"


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    messages: Optional[list[dict]] = None


class ChatMessageAdd(BaseModel):
    message: dict


class ChatMessageUpdate(BaseModel):
    message_id: str
    updates: dict


# Ask models
class AskRequest(BaseModel):
    question: str
    context: Optional[list[str]] = None
    use_notes: bool = False
    notes: Optional[list[dict]] = None
    history: Optional[list[dict]] = None


class SummarizeRequest(BaseModel):
    messages: list[dict]


# File models
class FileSelectionRequest(BaseModel):
    rel_paths: list[str]


class BatchDeleteRequest(BaseModel):
    rel_paths: list[str]


class FileMetadataUpdateRequest(BaseModel):
    bibliography: Optional[dict] = None
