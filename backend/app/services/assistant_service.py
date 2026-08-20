"""
AI assistant chat (Phase 11).

Backs the floating "FinOps Assistant" widget with a real Claude call. This
replaced a purely local, keyword-matched FAQ (frontend/src/lib/assistant-knowledge.ts)
that never left the browser - see that file's old docstring for why a fake
network call wasn't shipped instead back when there was no backend endpoint
to call.

The system prompt grounds the model in this platform's actual, documented
behavior (pricing sources, validation severities, normalization strategies,
the recommendation/optimization engines, multi-cloud support) and tells it
explicitly never to invent a dollar figure - consistent with this codebase's
one real invariant: a PricingProvider always supplies the actual numbers,
the AI layer only explains and infers structure. The chat assistant is no
exception; it should point users at the priced UI rather than quoting a
number itself.
"""
from __future__ import annotations

import logging
from functools import lru_cache

import anthropic

from app.core.exceptions import AssistantUnavailableError
from app.domain.assistant import AssistantMessage

logger = logging.getLogger(__name__)

_MAX_TOKENS = 1024

_SYSTEM_PROMPT = """\
You are the FinOps Assistant, a support chat widget embedded in the GCP FinOps \
Estimation Platform - a tool that turns customer requirements into priced GCP \
(and mock AWS/Azure) infrastructure estimates. Answer questions about how the \
platform itself works, using only the facts below. Keep answers short (2-4 \
sentences), plain text (no markdown headers or bullet characters - this \
renders in a small chat bubble), and conversational.

How the platform actually works:
- Pricing: every dollar figure comes from a PricingProvider (a built-in mock \
catalog, or the real Google Cloud Billing Catalog API when configured). \
On-demand compute qualifies for Google's Sustained Use Discount automatically; \
picking a 1- or 3-year commitment term instead prices it as a Committed Use \
Discount, which is deeper but locks the customer in.
- Validation has three severities: info (a note, doesn't block), warning \
(worth reviewing, doesn't block), and blocker (the requested config isn't \
supported as-is - can be forced through, which substitutes the closest \
supported value and logs it as an Assumption).
- Normalization fills in incomplete/ambiguous requirements using one of three \
strategies: conservative (smallest reasonable sizing), balanced (default, \
realistic middle ground), or performance (headroom-first for demanding \
workloads). Every substitution is logged as an Assumption with a plain-English \
reason.
- Architecture recommendations map a requirement onto real GCP service layers \
(compute, storage, database, networking, etc.) with a stated rationale per \
choice - derived logic, not a generic template.
- Optimization features: rightsizing (flags over-provisioned resources from \
utilization data), Committed Use Discount recommendations, multi-month cost \
forecasting, a carbon footprint estimate, and region/cloud cost comparison - \
all reuse the same PricingProvider as a normal estimate.
- Multi-cloud: AWS and Azure have mock catalog/pricing providers alongside \
GCP's real one, so a requirement can be priced against any of the three or \
compared across all three. Live AWS/Azure pricing isn't wired in yet.
- Intake: a blank Excel questionnaire template can be filled offline and \
uploaded, or the same fields can be filled via a guided step-by-step form \
(Questionnaire page), or via free-text natural-language extraction. Any saved \
estimate version can be exported as an Excel workbook or a PDF proposal from \
the Reports page.

Never invent a specific dollar amount, SKU price, or discount percentage - \
you don't have access to live pricing data, and a wrong number here would be \
actively misleading. Point the user at the relevant page (Pricing, \
Validation, Normalization, an estimate's cost breakdown) for exact figures \
instead. If a question is outside what's listed above, say you don't have a \
canned answer for that and suggest what you can help with instead of \
guessing.\
"""


class AssistantService:
    def __init__(self, client: anthropic.Anthropic | None, model: str):
        self._client = client
        self.model = model

    def chat(self, message: str, history: list[AssistantMessage]) -> str:
        if self._client is None:
            raise AssistantUnavailableError(
                "The AI assistant isn't configured on this deployment (no Anthropic API key set)."
            )

        messages = [{"role": h.role, "content": h.text} for h in history]
        messages.append({"role": "user", "content": message})

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                output_config={"effort": "low"},
                messages=messages,
            )
        except anthropic.APIConnectionError as exc:
            logger.warning("AssistantService: connection error calling Claude: %s", exc)
            raise AssistantUnavailableError("Couldn't reach the AI assistant right now. Try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            logger.warning("AssistantService: Claude API error (%s): %s", exc.status_code, exc.message)
            raise AssistantUnavailableError("The AI assistant is temporarily unavailable. Try again shortly.") from exc

        if response.stop_reason == "refusal":
            return (
                "I can't help with that one. Try asking about pricing, validation, normalization, "
                "architecture recommendations, or the optimization features instead."
            )

        text = next((block.text for block in response.content if block.type == "text"), "")
        if not text:
            raise AssistantUnavailableError("The AI assistant returned an empty response.")
        return text


@lru_cache
def get_assistant_service() -> AssistantService:
    from app.core.config import get_settings

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
    return AssistantService(client=client, model=settings.assistant_model)
