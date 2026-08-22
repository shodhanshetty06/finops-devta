"""
AI assistant chat (Phase 11, migrated to Groq).

Backs the floating "FinOps Assistant" widget. Originally a direct Claude
integration; now routed through the same provider-agnostic LLMProvider
abstraction ExplanationService uses (app/llm/base.py, app/llm/factory.py),
so it runs on Groq like every other AI feature on this platform and shares
one GROQ_API_KEY / GROQ_MODEL configuration. See app/llm/groq_provider.py
for the actual HTTP call.

The system prompt grounds the model in this platform's actual, documented
behavior (pricing sources, validation severities, normalization strategies,
the recommendation/optimization engines, multi-cloud support) and, when the
caller supplies an already-computed EstimateResult and/or ScenarioComparison
(see app/domain/assistant.py), in the exact figures those objects contain -
never a number the model invents itself. This is the same hard invariant
ExplanationService enforces: the deterministic pricing/normalization/
validation engines are the only source of truth for any number, SKU,
currency, or configuration value; the AI layer only explains what's already
been decided. If the user asks about something not present in the supplied
context (or no context was supplied at all), the assistant must say plainly
that it isn't available rather than guess.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache

from app.core.exceptions import AssistantUnavailableError
from app.domain.assistant import AssistantMessage
from app.domain.estimate import EstimateResult
from app.domain.optimization import ScenarioComparison
from app.llm.base import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are the FinOps Assistant, a support chat widget embedded in the GCP FinOps \
Estimation Platform - a tool that turns customer requirements into priced GCP \
(and mock AWS/Azure) infrastructure estimates. Keep answers short (2-4 \
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

Answer general questions about how the platform works (anything covered by \
the facts above - pricing sources, validation, normalization, architecture, \
optimization, multi-cloud, intake) directly and confidently; that's not a \
number you're inventing, it's documented platform behavior you already know.

Separately, you may be given a JSON "context" object containing an "estimate" \
and/or a "comparison" - an already-computed cost estimate and/or \
upgrade/downgrade scenario comparison that the deterministic pricing, \
normalization, and validation engines produced for the user's current \
session. Every number, currency code, resource name, and assumption reason in \
"context" is final and correct - you must NEVER calculate, estimate, convert, \
or invent a number, price, currency, SKU, or resource that isn't literally \
present in it, and NEVER state a figure that doesn't appear there. This rule \
applies ONLY to specific costs, assumptions, resources, totals, or a \
savings/additional-cost comparison for the user's own session - never to the \
general platform facts above. If "context" is missing, empty, or simply \
doesn't contain the specific figure being asked about, say plainly that you \
don't have that information in the current session and point them at the \
relevant page (Pricing, Assumptions, Optimization) instead of guessing.

Never invent a specific dollar amount, SKU price, or discount percentage that \
isn't already given to you. If a question is outside both the facts above and \
the given context, say you don't have a canned answer for that and suggest \
what you can help with instead of guessing.

Respond with ONLY a single JSON object, no markdown formatting, no code \
fences, matching exactly this shape: {"answer": "<your reply text>"}
"""

_MAX_CONTEXT_RESOURCES = 40
_MAX_CONTEXT_ASSUMPTIONS = 40


class AssistantService:
    def __init__(self, provider: LLMProvider | None, model: str):
        self._provider = provider
        self.model = model

    def chat(
        self,
        message: str,
        history: list[AssistantMessage],
        *,
        estimate: EstimateResult | None = None,
        comparison: ScenarioComparison | None = None,
    ) -> str:
        if self._provider is None:
            raise AssistantUnavailableError(
                "The AI assistant isn't configured on this deployment (no GROQ_API_KEY set)."
            )

        payload = {
            "message": message,
            "history": [{"role": h.role, "text": h.text} for h in history],
            "context": self._build_context_payload(estimate, comparison),
        }

        try:
            raw = self._provider.complete_json(
                system_prompt=_SYSTEM_PROMPT, user_prompt=json.dumps(payload),
            )
        except LLMProviderError as exc:
            logger.warning("AssistantService: Groq call failed: %s", exc)
            raise AssistantUnavailableError(
                "The AI assistant is temporarily unavailable. Try again shortly."
            ) from exc

        try:
            parsed = json.loads(raw)
            text = str(parsed["answer"]).strip()
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("AssistantService: could not parse Groq response: %s", exc)
            raise AssistantUnavailableError("The AI assistant returned an unexpected response.") from exc

        if not text:
            raise AssistantUnavailableError("The AI assistant returned an empty response.")
        return text

    # -- Context payload: only ever fields the deterministic engines already
    #    computed, copied verbatim - never recomputed, converted, or guessed. --

    def _build_context_payload(
        self, estimate: EstimateResult | None, comparison: ScenarioComparison | None,
    ) -> dict:
        context: dict = {}
        if estimate is not None:
            context["estimate"] = {
                "project_name": estimate.project_name,
                "region": estimate.normalized_spec.region,
                "currency": estimate.cost.currency,
                "total_monthly": estimate.cost.total_monthly,
                "total_yearly": estimate.cost.total_yearly,
                "discount_total_monthly": estimate.cost.discount_total_monthly,
                "assumptions": [
                    {
                        "field": a.field,
                        "requested_value": a.requested_value,
                        "used_value": a.used_value,
                        "reason": a.reason,
                        "strategy_applied": a.strategy_applied,
                    }
                    for a in estimate.assumptions[:_MAX_CONTEXT_ASSUMPTIONS]
                ],
                "resources": [
                    {
                        "resource_name": r.resource_name,
                        "category": r.category,
                        "quantity": r.quantity,
                        "configuration": r.normalized_configuration or r.configuration,
                        "status": r.status,
                        "currency": r.currency,
                        "unit_cost_monthly": r.unit_cost,
                        "subtotal_monthly": r.subtotal,
                    }
                    for r in estimate.cost.resource_summaries[:_MAX_CONTEXT_RESOURCES]
                ],
                "validation": {
                    "warning_count": estimate.validation.warning_count,
                    "blocker_count": estimate.validation.blocker_count,
                    "results": [
                        {
                            "field": v.field,
                            "severity": v.severity,
                            "reason": v.reason,
                            "recommendation": v.recommendation,
                        }
                        for v in estimate.validation.results
                    ],
                },
            }
        if comparison is not None:
            context["comparison"] = {
                "base": {
                    "name": comparison.base.name,
                    "total_monthly": comparison.base.total_monthly,
                    "total_yearly": comparison.base.total_yearly,
                    "currency": comparison.base.currency,
                },
                "scenarios": [
                    {
                        "name": s.name,
                        "total_monthly": s.total_monthly,
                        "total_yearly": s.total_yearly,
                        "currency": s.currency,
                        "delta_vs_base_monthly": s.delta_vs_base_monthly,
                        "delta_vs_base_percent": s.delta_vs_base_percent,
                        "direction": (
                            "savings" if s.delta_vs_base_monthly < 0
                            else "additional_cost" if s.delta_vs_base_monthly > 0
                            else "no_change"
                        ),
                    }
                    for s in comparison.scenarios
                ],
            }
        return context


@lru_cache
def get_assistant_service() -> AssistantService:
    from app.core.config import get_settings
    from app.llm.factory import get_llm_provider

    settings = get_settings()
    return AssistantService(provider=get_llm_provider(), model=settings.groq_model or "")
