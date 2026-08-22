"""LLM-assisted explanation domain models (see app/services/explanation_service.py).

Every value referenced in these explanations - requested/used
configuration, cost, currency, delta - is copied verbatim from an
already-computed EstimateResult or ScenarioComparison. This module and its
consumers never compute a price, pick a SKU, choose a currency, or
normalize/validate a configuration; the deterministic engines
(app/normalization, app/validation, app/pricing) remain the single source
of truth for every number that appears here.

`source` on each item is "llm" when Groq (or whichever provider is
configured) produced the text, or "template" when it fell back to
deterministic, f-string-built text - because Groq wasn't configured, timed
out, was rate-limited, or returned something that couldn't be parsed. This
lets a caller/UI show a subtle "AI-generated" badge without ever depending
on the LLM being available.
"""
from pydantic import BaseModel

from app.domain.estimate import EstimateResult
from app.domain.optimization import ScenarioComparison


class AssumptionExplanation(BaseModel):
    field: str
    requested_value: str
    used_value: str
    explanation: str
    source: str  # "llm" | "template"


class ResourceExplanation(BaseModel):
    resource_name: str
    explanation: str
    source: str  # "llm" | "template"


class EstimateExplanation(BaseModel):
    executive_summary: str
    summary_source: str  # "llm" | "template"
    assumption_explanations: list[AssumptionExplanation]
    resource_explanations: list[ResourceExplanation]


class EstimateExplanationRequest(BaseModel):
    estimate: EstimateResult


class ScenarioExplanationItem(BaseModel):
    name: str
    explanation: str
    source: str  # "llm" | "template"


class ScenarioComparisonExplanation(BaseModel):
    base_explanation: str
    source: str  # "llm" | "template"
    scenario_explanations: list[ScenarioExplanationItem]


class ScenarioComparisonExplanationRequest(BaseModel):
    comparison: ScenarioComparison
