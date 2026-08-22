"""API request/response shapes for the AI assistant chat endpoint (see
app/services/assistant_service.py). Deliberately minimal - the assistant is
stateless from the backend's point of view; the frontend resends whatever
prior turns it wants considered on every call, plus - optionally - whatever
already-computed estimate/comparison it currently has on screen."""
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.estimate import EstimateResult
from app.domain.optimization import ScenarioComparison


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
    # Optional - whatever already-computed EstimateResult/ScenarioComparison
    # the frontend currently has loaded (see frontend/src/contexts/
    # assistant-context.tsx). Never recomputed or second-guessed here; the
    # assistant is only ever allowed to quote figures that appear in these
    # objects, exactly like ExplanationService - see
    # app/services/assistant_service.py::_build_context_payload. Omitted (or
    # null) means the user hasn't got a priced estimate/comparison open in
    # this session, and the assistant must say so rather than guess.
    estimate: EstimateResult | None = None
    comparison: ScenarioComparison | None = None


class AssistantChatResponse(BaseModel):
    text: str
    model: str
