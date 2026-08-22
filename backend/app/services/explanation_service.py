"""
ExplanationService: turns already-computed estimate/comparison data into
customer-friendly prose via an LLMProvider (Groq today - see
app/llm/groq_provider.py), with automatic fallback to deterministic
template text.

Hard invariant, enforced by construction rather than just by prompt
wording: this service only ever receives values the deterministic
pricing/normalization engines already computed (see
app/normalization/engine.py, app/pricing/engine.py, app/domain/pricing.py).
It never asks the LLM to calculate a price, select a SKU, choose a
currency, or validate anything - only to phrase already-decided facts for
a customer audience. Every currency figure is passed through in whatever
currency the estimate/comparison already carries; this service never
converts currency itself.

If the LLM is unavailable (no API key), times out, is rate-limited, or
returns something that can't be parsed, every explanation silently falls
back to a template built from the same structured data - callers always
get a complete result, and estimate/report generation never breaks because
of this feature. See `_complete` / `_resolve_item`.
"""
from __future__ import annotations

import json
import logging

from app.domain.assumption import Assumption
from app.domain.estimate import EstimateResult
from app.domain.explanation import (
    AssumptionExplanation,
    EstimateExplanation,
    ResourceExplanation,
    ScenarioComparisonExplanation,
    ScenarioExplanationItem,
)
from app.domain.optimization import ScenarioComparison, ScenarioOutcome
from app.domain.pricing import ResourceCostSummary
from app.llm.base import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You write short, professional, customer-facing explanations for a Google \
Cloud cost estimation platform. You are given a JSON object describing \
configuration assumptions, priced resources, and/or cost comparisons that \
a deterministic pricing, normalization, and validation engine has already \
computed - every number, currency code, SKU, and configuration value in it \
is final and correct.

Your only job is to phrase these already-decided facts in clear, \
reassuring, plain English for a non-technical customer. You must NEVER: \
calculate, estimate, convert, or invent any number, price, or currency \
value; change or second-guess a configuration, price, or currency; state a \
number that does not appear in the input; add caveats implying the \
figures might be wrong. Only use the exact values given to you.

For an item that explains a configuration assumption, follow this \
structure in your explanation: (1) what the customer requested, (2) why it \
is not available/valid as requested, (3) what configuration was assumed \
instead, (4) why that specific substitution was chosen. For an item that \
explains a priced resource or a cost comparison/scenario, state the \
resource or scenario name, its cost (with the currency code given), and - \
if a comparison - whether it is a saving or an additional cost versus the \
base, using the exact delta given. Keep each explanation to 1-3 sentences.

Respond with ONLY a single JSON object, no markdown formatting, no code \
fences, matching exactly this shape:
{"executive_summary": "<2-4 sentence overview if requested, else empty string>",
 "items": [{"id": <integer id copied from the input item>, "explanation": "<text>"}, ...]}
"""


class ExplanationService:
    def __init__(self, provider: LLMProvider | None, model: str | None):
        self._provider = provider
        self.model = model

    # -- Estimate (assumptions + resources) -----------------------------------

    def explain_estimate(self, estimate: EstimateResult) -> EstimateExplanation:
        assumption_items = [
            {
                "id": i,
                "kind": "assumption",
                "field": a.field,
                "requested_value": a.requested_value,
                "used_value": a.used_value,
                "reason": a.reason,
                "strategy_applied": a.strategy_applied,
            }
            for i, a in enumerate(estimate.assumptions)
        ]
        n_assumptions = len(assumption_items)
        resource_items = [
            {
                "id": n_assumptions + i,
                "kind": "resource",
                "resource_name": r.resource_name,
                "category": r.category,
                "quantity": r.quantity,
                "requested_configuration": r.requested_configuration or r.configuration,
                "actual_configuration": r.normalized_configuration or r.configuration,
                "assumption_reason": r.assumption_reason,
                "status": r.status,
                "currency": r.currency,
                "unit_cost_monthly": r.unit_cost,
                "subtotal_monthly": r.subtotal,
                "subtotal_yearly": round(r.subtotal * 12, 2),
            }
            for i, r in enumerate(estimate.cost.resource_summaries)
        ]

        payload = {
            "project_name": estimate.project_name,
            "region": estimate.normalized_spec.region,
            "currency": estimate.cost.currency,
            "total_monthly": estimate.cost.total_monthly,
            "total_yearly": estimate.cost.total_yearly,
            "discount_total_monthly": estimate.cost.discount_total_monthly,
            "assumptions": assumption_items,
            "resources": resource_items,
            "request_executive_summary": True,
        }

        parsed = self._complete(payload)

        assumption_explanations = [
            AssumptionExplanation(
                field=a.field,
                requested_value=a.requested_value,
                used_value=a.used_value,
                **dict(zip(("explanation", "source"), self._resolve_item(parsed, i, self._fallback_assumption_text(a)))),
            )
            for i, a in enumerate(estimate.assumptions)
        ]

        resource_explanations = [
            ResourceExplanation(
                resource_name=r.resource_name,
                **dict(zip(
                    ("explanation", "source"),
                    self._resolve_item(parsed, n_assumptions + i, self._fallback_resource_text(r)),
                )),
            )
            for i, r in enumerate(estimate.cost.resource_summaries)
        ]

        summary_text = self._resolve_summary(parsed)
        if summary_text is None:
            summary_text, summary_source = self._fallback_executive_summary(estimate), "template"
        else:
            summary_source = "llm"

        return EstimateExplanation(
            executive_summary=summary_text,
            summary_source=summary_source,
            assumption_explanations=assumption_explanations,
            resource_explanations=resource_explanations,
        )

    # -- Scenario comparison (upgrade/downgrade) -------------------------------

    def explain_scenario_comparison(self, comparison: ScenarioComparison) -> ScenarioComparisonExplanation:
        items = [
            {
                "id": i,
                "kind": "scenario",
                "name": s.name,
                "currency": s.currency,
                "total_monthly": s.total_monthly,
                "total_yearly": s.total_yearly,
                "delta_vs_base_monthly": s.delta_vs_base_monthly,
                "delta_vs_base_annual": round(s.delta_vs_base_monthly * 12, 2),
                "delta_vs_base_percent": s.delta_vs_base_percent,
                "direction": (
                    "savings" if s.delta_vs_base_monthly < 0
                    else "additional_cost" if s.delta_vs_base_monthly > 0
                    else "no_change"
                ),
            }
            for i, s in enumerate(comparison.scenarios)
        ]
        payload = {
            "base": {
                "name": comparison.base.name,
                "total_monthly": comparison.base.total_monthly,
                "total_yearly": comparison.base.total_yearly,
                "currency": comparison.base.currency,
            },
            "scenarios": items,
            "request_executive_summary": True,
        }

        parsed = self._complete(payload)

        base_text = self._resolve_summary(parsed)
        base_source = "llm" if base_text is not None else "template"
        if base_text is None:
            base_text = self._fallback_scenario_base_text(comparison)

        scenario_explanations = [
            ScenarioExplanationItem(
                name=s.name,
                **dict(zip(("explanation", "source"), self._resolve_item(parsed, i, self._fallback_scenario_text(s)))),
            )
            for i, s in enumerate(comparison.scenarios)
        ]

        return ScenarioComparisonExplanation(
            base_explanation=base_text, source=base_source, scenario_explanations=scenario_explanations,
        )

    # -- LLM call + parsing -----------------------------------------------------

    def _complete(self, payload: dict) -> dict | None:
        """Returns the parsed JSON object, or None if the LLM isn't
        configured or the call/parse failed in any way. Never raises -
        every failure mode degrades to None, and every caller above treats
        None exactly like "use template text for everything"."""
        if self._provider is None:
            return None
        try:
            raw = self._provider.complete_json(system_prompt=_SYSTEM_PROMPT, user_prompt=json.dumps(payload))
            parsed = json.loads(raw)
            if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list):
                raise ValueError("Groq response did not contain the expected 'items' list.")
            return parsed
        except LLMProviderError as exc:
            logger.warning("ExplanationService: Groq call failed, falling back to template text: %s", exc)
            return None
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("ExplanationService: could not parse Groq response, falling back to template text: %s", exc)
            return None

    def _resolve_item(self, parsed: dict | None, item_id: int, default: str) -> tuple[str, str]:
        """Looks up one item's explanation by id in an already-parsed
        response. Falls back to `default` (template text) for just this
        item if the id is missing or its explanation is empty - a partial
        LLM response still gets every other item's real explanation."""
        if parsed is not None:
            for item in parsed.get("items", []):
                if isinstance(item, dict) and item.get("id") == item_id:
                    text = str(item.get("explanation") or "").strip()
                    if text:
                        return text, "llm"
                    break
        return default, "template"

    def _resolve_summary(self, parsed: dict | None) -> str | None:
        if parsed is None:
            return None
        text = str(parsed.get("executive_summary") or "").strip()
        return text or None

    # -- Deterministic fallback templates ----------------------------------------
    # Mirrors the plain-English style already used for Assumption.reason
    # (app/normalization/engine.py) and the PDF executive summary
    # (app/reports/pdf_generator.py) - this is the same wording quality the
    # platform already ships, just also used when Groq isn't available.

    def _fallback_assumption_text(self, a: Assumption) -> str:
        return (
            f'The requested {a.field} value of "{a.requested_value}" is not available in the supported '
            f'pricing catalog. We have used "{a.used_value}" instead. {a.reason}'
        )

    def _fallback_resource_text(self, r: ResourceCostSummary) -> str:
        config = r.normalized_configuration or r.configuration
        text = f"{r.resource_name}: {r.quantity} x {config}, costing {r.currency} {r.subtotal:,.2f} per month."
        if r.status != "valid" and r.assumption_reason:
            text += f" {r.assumption_reason}"
        return text

    def _fallback_executive_summary(self, estimate: EstimateResult) -> str:
        return (
            f"This estimate for {estimate.project_name} totals {estimate.cost.currency} "
            f"{estimate.cost.total_monthly:,.2f} per month ({estimate.cost.currency} "
            f"{estimate.cost.total_yearly:,.2f} per year), based on {len(estimate.cost.resource_summaries)} "
            f"priced resource(s) and {len(estimate.assumptions)} configuration assumption(s)."
        )

    def _fallback_scenario_base_text(self, comparison: ScenarioComparison) -> str:
        return (
            f"The base configuration ({comparison.base.name}) costs {comparison.base.currency} "
            f"{comparison.base.total_monthly:,.2f} per month ({comparison.base.currency} "
            f"{comparison.base.total_yearly:,.2f} per year)."
        )

    def _fallback_scenario_text(self, s: ScenarioOutcome) -> str:
        delta = s.delta_vs_base_monthly
        if delta > 0:
            return (
                f'"{s.name}" costs {s.currency} {delta:,.2f} more per month ({s.delta_vs_base_percent:.1f}% higher) '
                f"than the base configuration, for a total of {s.currency} {s.total_monthly:,.2f} per month."
            )
        if delta < 0:
            return (
                f'"{s.name}" saves {s.currency} {abs(delta):,.2f} per month ({abs(s.delta_vs_base_percent):.1f}% lower) '
                f"compared to the base configuration, for a total of {s.currency} {s.total_monthly:,.2f} per month."
            )
        return f'"{s.name}" costs the same as the base configuration: {s.currency} {s.total_monthly:,.2f} per month.'


def get_explanation_service() -> ExplanationService:
    from app.core.config import get_settings
    from app.llm.factory import get_llm_provider

    settings = get_settings()
    return ExplanationService(provider=get_llm_provider(), model=settings.groq_model)
