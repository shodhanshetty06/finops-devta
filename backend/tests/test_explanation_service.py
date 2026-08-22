"""
Tests for ExplanationService (app/services/explanation_service.py).

Covers the platform's required scenarios end to end at the service layer:
normal estimate, assumption/normalization explanation, upgrade/downgrade
scenario comparison, multiple resources, different currencies, and Groq
failure / missing API key fallback. Uses a FakeLLMProvider so no real
network call is ever made and responses are fully deterministic.
"""
import json

import pytest

from app.domain.optimization import ScenarioComparison, ScenarioOutcome
from app.llm.base import LLMProvider, LLMProviderError
from app.services.explanation_service import ExplanationService


class FakeLLMProvider(LLMProvider):
    """Returns a canned JSON response, or raises, per test."""

    def __init__(self, response: str | None = None, error: Exception | None = None):
        self._response = response
        self._error = error
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if self._error is not None:
            raise self._error
        return self._response


# -- Normal estimate + assumption/normalization explanation -------------------

def test_explain_estimate_with_no_llm_configured_falls_back_to_template_text(sample_estimate):
    service = ExplanationService(provider=None, model=None)
    result = service.explain_estimate(sample_estimate)

    assert result.summary_source == "template"
    assert sample_estimate.project_name in result.executive_summary
    assert sample_estimate.cost.currency in result.executive_summary

    assert len(result.assumption_explanations) == len(sample_estimate.assumptions)
    for a, exp in zip(sample_estimate.assumptions, result.assumption_explanations):
        assert exp.source == "template"
        # The fallback must state exactly what was requested and what was
        # used - never inventing a different value.
        assert a.requested_value in exp.explanation
        assert a.used_value in exp.explanation
        assert exp.field == a.field


def test_explain_estimate_assumption_explanation_follows_the_required_structure(sample_estimate):
    # Compute vcpu=3 is not a valid E2 config in the mock catalog (see
    # conftest.py's sample_estimate) - the normalization engine substitutes
    # a supported value and records why. The template fallback must still
    # communicate: what was requested, that it's unavailable, what was used
    # instead, and why - matching the example in the feature spec.
    service = ExplanationService(provider=None, model=None)
    result = service.explain_estimate(sample_estimate)

    vcpu_assumption = next(a for a in sample_estimate.assumptions if a.field == "compute.vcpu")
    exp = next(e for e in result.assumption_explanations if e.field == "compute.vcpu")

    assert "not available" in exp.explanation.lower()
    assert vcpu_assumption.requested_value in exp.explanation
    assert vcpu_assumption.used_value in exp.explanation


def test_explain_estimate_multiple_resources_all_get_an_explanation(sample_estimate):
    # sample_estimate has compute, storage, database, and network resources
    # populated (see conftest.py) - confirms every resource line gets its
    # own explanation, not just the first.
    assert len(sample_estimate.cost.resource_summaries) > 1

    service = ExplanationService(provider=None, model=None)
    result = service.explain_estimate(sample_estimate)

    assert len(result.resource_explanations) == len(sample_estimate.cost.resource_summaries)
    resource_names = {r.resource_name for r in sample_estimate.cost.resource_summaries}
    explained_names = {e.resource_name for e in result.resource_explanations}
    assert resource_names == explained_names
    for r, exp in zip(sample_estimate.cost.resource_summaries, result.resource_explanations):
        assert exp.source == "template"
        assert r.currency in exp.explanation
        assert f"{r.subtotal:,.2f}" in exp.explanation


def test_explain_estimate_never_invents_a_number_llm_success_path(sample_estimate):
    n_assumptions = len(sample_estimate.assumptions)
    n_resources = len(sample_estimate.cost.resource_summaries)
    items = [{"id": i, "explanation": f"LLM explanation for item {i}"} for i in range(n_assumptions + n_resources)]
    response = json.dumps({"executive_summary": "A concise AI summary.", "items": items})

    provider = FakeLLMProvider(response=response)
    service = ExplanationService(provider=provider, model="llama-3.3-70b-versatile")
    result = service.explain_estimate(sample_estimate)

    assert result.summary_source == "llm"
    assert result.executive_summary == "A concise AI summary."
    assert all(e.source == "llm" for e in result.assumption_explanations)
    assert all(e.source == "llm" for e in result.resource_explanations)
    assert len(provider.calls) == 1

    # The structured payload sent to the LLM carries the deterministic
    # engine's own values verbatim - proving the service passes through,
    # rather than recomputes, every figure.
    _, user_prompt = provider.calls[0]
    payload = json.loads(user_prompt)
    assert payload["currency"] == sample_estimate.cost.currency
    assert payload["total_monthly"] == sample_estimate.cost.total_monthly
    assert len(payload["assumptions"]) == n_assumptions
    assert len(payload["resources"]) == n_resources


def test_explain_estimate_partial_llm_response_falls_back_per_missing_item(sample_estimate):
    # Only the first assumption gets a real LLM explanation; every other
    # item is missing from the response. Each missing item must still get
    # a complete, template-based explanation, not be silently dropped.
    if not sample_estimate.assumptions:
        pytest.skip("sample_estimate has no assumptions to exercise partial fallback")

    response = json.dumps({"executive_summary": "", "items": [{"id": 0, "explanation": "Only this one from Groq."}]})
    provider = FakeLLMProvider(response=response)
    service = ExplanationService(provider=provider, model="llama-3.3-70b-versatile")
    result = service.explain_estimate(sample_estimate)

    assert result.assumption_explanations[0].source == "llm"
    assert result.assumption_explanations[0].explanation == "Only this one from Groq."
    if len(result.assumption_explanations) > 1:
        assert result.assumption_explanations[1].source == "template"
    # Executive summary was blank in the response -> template fallback.
    assert result.summary_source == "template"


# -- Groq failure / missing API key fallback -----------------------------------

def test_explain_estimate_falls_back_when_provider_raises_llm_provider_error(sample_estimate):
    provider = FakeLLMProvider(error=LLMProviderError("Groq API timed out"))
    service = ExplanationService(provider=provider, model="llama-3.3-70b-versatile")
    result = service.explain_estimate(sample_estimate)

    assert result.summary_source == "template"
    assert all(e.source == "template" for e in result.assumption_explanations)
    assert all(e.source == "template" for e in result.resource_explanations)
    # Every explanation is still fully populated - the feature must never
    # break estimate/report generation just because Groq is unavailable.
    assert result.executive_summary
    assert all(e.explanation for e in result.assumption_explanations)


def test_explain_estimate_falls_back_on_malformed_json_from_provider(sample_estimate):
    provider = FakeLLMProvider(response="not valid json { at all")
    service = ExplanationService(provider=provider, model="llama-3.3-70b-versatile")
    result = service.explain_estimate(sample_estimate)
    assert result.summary_source == "template"


def test_explain_estimate_falls_back_on_response_missing_items_key(sample_estimate):
    provider = FakeLLMProvider(response=json.dumps({"executive_summary": "hi"}))
    service = ExplanationService(provider=provider, model="llama-3.3-70b-versatile")
    result = service.explain_estimate(sample_estimate)
    assert result.summary_source == "template"


# -- Different currencies -------------------------------------------------------

def test_explain_estimate_uses_the_estimates_own_currency_never_converts(sample_estimate):
    eur_cost = sample_estimate.cost.model_copy(update={
        "currency": "EUR",
        "resource_summaries": [r.model_copy(update={"currency": "EUR"}) for r in sample_estimate.cost.resource_summaries],
    })
    eur_estimate = sample_estimate.model_copy(update={"cost": eur_cost})

    service = ExplanationService(provider=None, model=None)
    result = service.explain_estimate(eur_estimate)

    assert "EUR" in result.executive_summary
    assert "USD" not in result.executive_summary
    for exp in result.resource_explanations:
        assert "EUR" in exp.explanation


# -- Upgrade/downgrade scenario comparison ---------------------------------------

def _scenario_comparison() -> ScenarioComparison:
    base = ScenarioOutcome(name="Base", total_monthly=1000.0, total_yearly=12000.0, currency="USD",
                            delta_vs_base_monthly=0.0, delta_vs_base_percent=0.0)
    upgrade = ScenarioOutcome(name="Upgrade to n2-standard-8", total_monthly=1500.0, total_yearly=18000.0,
                               currency="USD", delta_vs_base_monthly=500.0, delta_vs_base_percent=50.0)
    downgrade = ScenarioOutcome(name="Downgrade to e2-standard-2", total_monthly=700.0, total_yearly=8400.0,
                                 currency="USD", delta_vs_base_monthly=-300.0, delta_vs_base_percent=-30.0)
    return ScenarioComparison(base=base, scenarios=[upgrade, downgrade])


def test_explain_scenario_comparison_template_fallback_labels_savings_and_additional_cost():
    comparison = _scenario_comparison()
    service = ExplanationService(provider=None, model=None)
    result = service.explain_scenario_comparison(comparison)

    assert result.source == "template"
    upgrade_text = result.scenario_explanations[0].explanation
    downgrade_text = result.scenario_explanations[1].explanation

    assert "500.00" in upgrade_text and "more" in upgrade_text
    assert "300.00" in downgrade_text and "saves" in downgrade_text
    # Never invents a currency different from the one supplied.
    assert "USD" in upgrade_text and "USD" in downgrade_text


def test_explain_scenario_comparison_llm_success_path():
    comparison = _scenario_comparison()
    response = json.dumps({
        "executive_summary": "Base plan runs $1000/month.",
        "items": [
            {"id": 0, "explanation": "Upgrading adds $500/month for more headroom."},
            {"id": 1, "explanation": "Downgrading saves $300/month."},
        ],
    })
    provider = FakeLLMProvider(response=response)
    service = ExplanationService(provider=provider, model="llama-3.3-70b-versatile")
    result = service.explain_scenario_comparison(comparison)

    assert result.source == "llm"
    assert result.base_explanation == "Base plan runs $1000/month."
    assert result.scenario_explanations[0].source == "llm"
    assert result.scenario_explanations[1].explanation == "Downgrading saves $300/month."


def test_explain_scenario_comparison_falls_back_when_groq_unavailable():
    comparison = _scenario_comparison()
    provider = FakeLLMProvider(error=LLMProviderError("rate limited"))
    service = ExplanationService(provider=provider, model="llama-3.3-70b-versatile")
    result = service.explain_scenario_comparison(comparison)

    assert result.source == "template"
    assert all(e.source == "template" for e in result.scenario_explanations)
    assert result.base_explanation
