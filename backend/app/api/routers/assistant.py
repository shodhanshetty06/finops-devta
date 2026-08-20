"""AI assistant chat endpoint - backs the floating widget
(frontend/src/components/ai-assistant.tsx). Public/unauthenticated like
/catalog and /validate: it returns no user- or account-specific data. Listed
under FINOPS_RATE_LIMIT_HEAVY_PATH_PREFIXES since, unlike every other
endpoint on this platform, each call has a real per-request dollar cost."""
from fastapi import APIRouter, Depends

from app.domain.assistant import AssistantChatRequest, AssistantChatResponse
from app.services.assistant_service import AssistantService, get_assistant_service

router = APIRouter(prefix="/api/v1/assistant", tags=["Assistant"])


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    summary="Ask the AI assistant a question about how this platform works",
    description=(
        "Answers from the platform's own documented behavior (pricing sources, validation severities, "
        "normalization strategies, architecture recommendations, optimization features) via a Claude call - "
        "never invents a specific price or SKU, since those always come from a PricingProvider. Returns 503 "
        "if no Anthropic API key is configured or the upstream call fails."
    ),
)
def chat(
    body: AssistantChatRequest,
    service: AssistantService = Depends(get_assistant_service),
) -> AssistantChatResponse:
    text = service.chat(body.message, body.history)
    return AssistantChatResponse(text=text, model=service.model)
