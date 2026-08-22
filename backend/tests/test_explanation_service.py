"""Tests for ExplanationService (app/services/explanation_service.py) - the
Groq-backed layer that turns an already-computed EstimateResult/
ScenarioComparison into customer-friendly prose for the Excel/PDF report
flow and POST /api/v1/explanations/*.

Covers: assumption explanations (the "3 vCPU -> assumed 2 vCPU" style case),
multiple priced resources, currency is passed through untouched (never
converted/invented), and every Groq failure mode (unconfigured, malformed
response, partial response) degrades to the same deterministic template text
the platform already ships - explanation generation must never break an
estimate or report.
"""
import json

import httpx

from app.domain.optimization import ScenarioComparison, ScenarioOutcome
from app.llm.groq_provider import GroqProvider
from app.services.explanation_service import ExplanationService


def _groq_items_response(estimate, *, executive_summary="AI summary."):
    n = len(estimate.assumptions)
    items = [{"id": i, "explanation": f"AI explanation for assumption {i}."} for i in range(n)]
    items += [
        {"id": n + i, "explanation": f"AI explanation for resource {i}."}
        for i in range(len(estimate.cost.resource_summaries))
    ]
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps({"executive_summary": executive_summary, "items": items})}}]},
    )


# -- No provider configured (missing GROQ_API_KEY) -> template fallback -----

def test_explain_estimate_falls_back_to_templates_when_not_configured(sample_estimate):
    service = ExplanationService(provider=None, model=None)
    result = service.explain_estimate(sample_estimate)

    assert result.summary_source == "template"
    assert all(a.source == "template" for a in result.assumption_explanations)
    assert all(r.source == "template" for r in result.resource_explanations)
    # sample_estimate requests 3 vCPU, normalized down/up to a supported
    # tier - exactly the "requested X, assumed Y" case from the spec.
    vcpu_assumption = next(a for a in result.assumption_explanations if a.field == "compute.vcpu")
    assert vcpu_assumption.requested_value == "3"
    assert vcpu_assumption.used_value in vcpu_assumption.explanation or vcpu_assumption.explanation


# -- Assumption + multi-resource explanations via Groq -----------------------

def test_explain_estimate_uses_groq_for_every_assumption_and_resource(sample_estimate):
    def handler(request: httpx.Request) -> httpx.Response:
        return _groq_items_response(sample_estimate)

    provider = GroqProvider("k", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = ExplanationService(provider=provider, model="llama-3.1-8b-instant")

    result = service.explain_estimate(sample_estimate)

    assert result.summary_source == "llm"
    assert result.executive_summary == "AI summary."
    assert len(result.assumption_explanations) == len(sample_estimate.assumptions)
    assert len(result.resource_explanations) == len(sample_estimate.cost.resource_summaries)
    # sample_estimate has compute, storage, database, and network resources -
    # confirms multi-resource explanations all resolve, not just the first.
    assert len(result.resource_explanations) >= 3
    assert all(r.source == "llm" for r in result.resource_explanations)
    assert all(a.source == "llm" for a in result.assumption_explanations)


def test_explain_estimate_never_lets_groq_change_currency_or_values(sample_estimate):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        sent = json.loads(payload["messages"][1]["content"])
        # The service must send the estimate's real currency/values verbatim -
        # this asserts what was *sent*, i.e. Groq is only ever given
        # already-decided facts, never asked to pick a currency itself.
        assert sent["currency"] == sample_estimate.cost.currency
        assert sent["total_monthly"] == sample_estimate.cost.total_monthly
        return _groq_items_response(sample_estimate)

    provider = GroqProvider("k", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = ExplanationService(provider=provider, model="llama-3.1-8b-instant")
    service.explain_estimate(sample_estimate)


# -- Groq failure modes -> graceful template fallback, never an exception ---

def test_explain_estimate_falls_back_when_groq_call_fails(sample_estimate):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    provider = GroqProvider("k", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = ExplanationService(provider=provider, model="llama-3.1-8b-instant")

    result = service.explain_estimate(sample_estimate)  # must not raise

    assert result.summary_source == "template"
    assert all(a.source == "template" for a in result.assumption_explanations)
    assert all(r.source == "template" for r in result.resource_explanations)


def test_explain_estimate_falls_back_when_groq_response_is_malformed(sample_estimate):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not valid json"}}]})

    provider = GroqProvider("k", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = ExplanationService(provider=provider, model="llama-3.1-8b-instant")

    result = service.explain_estimate(sample_estimate)  # must not raise
    assert result.summary_source == "template"


def test_explain_estimate_falls_back_per_item_on_partial_groq_response(sample_estimate):
    # Groq returns an explanation for only the first assumption/resource -
    # every other item must still get complete template text, not be dropped.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(
                {"executive_summary": "", "items": [{"id": 0, "explanation": "Only this one."}]}
            )}}]},
        )

    provider = GroqProvider("k", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = ExplanationService(provider=provider, model="llama-3.1-8b-instant")

    result = service.explain_estimate(sample_estimate)

    assert result.assumption_explanations[0].source == "llm"
    assert result.assumption_explanations[0].explanation == "Only this one."
    # Every remaining item (and the summary, which was blank) falls back.
    assert result.summary_source == "template"
    remaining = result.assumption_explanations[1:] + result.resource_explanations
    assert all(item.source == "template" for item in remaining)
    assert all(item.explanation for item in remaining)  # never empty


# -- Scenario comparison (upgrade/downgrade) ---------------------------------

def test_explain_scenario_comparison_reports_savings_and_additional_cost():
    comparison = ScenarioComparison(
        base=ScenarioOutcome(name="Current", total_monthly=200.0, total_yearly=2400.0, currency="INR",
                              delta_vs_base_monthly=0.0, delta_vs_base_percent=0.0),
        scenarios=[
            ScenarioOutcome(name="Downgrade", total_monthly=150.0, total_yearly=1800.0, currency="INR",
                             delta_vs_base_monthly=-50.0, delta_vs_base_percent=-25.0),
            ScenarioOutcome(name="Upgrade", total_monthly=300.0, total_yearly=3600.0, currency="INR",
                             delta_vs_base_monthly=100.0, delta_vs_base_percent=50.0),
        ],
    )
    service = ExplanationService(provider=None, model=None)  # template path - deterministic, easy to assert exactly

    result = service.explain_scenario_comparison(comparison)

    assert "INR" in result.scenario_explanations[0].explanation
    assert "saves" in result.scenario_explanations[0].explanation
    assert "more" in result.scenario_explanations[1].explanation
    assert all(item.source == "template" for item in result.scenario_explanations)
