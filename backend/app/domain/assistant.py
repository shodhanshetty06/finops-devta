"""API request/response shapes for the AI assistant chat endpoint (see
app/services/assistant_service.py). Deliberately minimal - the assistant is
stateless from the backend's point of view; the frontend resends whatever
prior turns it wants considered on every call."""
from typing import Literal

from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=4000)


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    # Prior turns, oldest first, NOT including `message` itself. Capped
    # client-side to a handful of turns - this is a support widget, not a
    # long-running conversation, and every turn resent is billed input
    # tokens on every subsequent call.
    history: list[AssistantMessage] = Field(default_factory=list, max_length=20)


class AssistantChatResponse(BaseModel):
    text: str
    model: str
