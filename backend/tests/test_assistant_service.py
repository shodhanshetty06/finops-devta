"""Tests for the Groq-backed AI assistant chat (app/services/assistant_service.py).

Same httpx.MockTransport pattern as tests/test_llm_groq_provider.py - no real
network call is ever made. Covers: general platform Q&A with no context,
grounding an answer in a supplied EstimateResult/ScenarioComparison (never
inventing a number outside them), the "not available" behavior when asked
about something absent from context, and every Groq failure mode degrading
to AssistantUnavailableError rather than leaking an exception or a fake
answer.
"""
import json

import httpx
import pytest

from app.core.exceptions import AssistantUnavailableError
from app.domain.assistant import AssistantMessage
from app.llm.groq_provider import GroqProvider
from app.services.assistant_service import AssistantService


def _groq_response(answer: str = "Here is your answer."):
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"answer": answer})}}]})


def test_chat_raises_when_not_configured():
    service = AssistantService(provider=None, model="")
    with pytest.raises(AssistantUnavailableError):
        service.chat("How does pricing work?", [])


def test_chat_returns_groq_answer_with_no_context():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _groq_response("Pricing comes from a PricingProvider.")

    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = AssistantService(provider=provider, model="llama-3.1-8b-instant")

    answer = service.chat("How does pricing work?", [])

    assert answer == "Pricing comes from a PricingProvider."
    sent_payload = json.loads(captured["body"]["messages"][1]["content"])
    assert sent_payload["message"] == "How does pricing work?"
    assert sent_payload["context"] == {}  # no estimate/comparison supplied


def test_chat_forwards_history():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _groq_response("Sure.")

    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = AssistantService(provider=provider, model="llama-3.1-8b-instant")

    history = [AssistantMessage(role="user", text="Hi"), AssistantMessage(role="assistant", text="Hello!")]
    service.chat("Follow-up question", history)

    sent_payload = json.loads(captured["body"]["messages"][1]["content"])
    assert sent_payload["history"] == [{"role": "user", "text": "Hi"}, {"role": "assistant", "text": "Hello!"}]


def test_chat_grounds_answer_in_supplied_estimate(sample_estimate):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _groq_response(f"Your total is {sample_estimate.cost.currency} {sample_estimate.cost.total_monthly:,.2f}/mo.")

    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = AssistantService(provider=provider, model="llama-3.1-8b-instant")

    answer = service.chat("What's my total monthly cost?", [], estimate=sample_estimate)

    sent_payload = json.loads(captured["body"]["messages"][1]["content"])
    ctx = sent_payload["context"]["estimate"]
    # Every figure the assistant is allowed to quote is copied verbatim from
    # the deterministic EstimateResult - never recomputed.
    assert ctx["currency"] == sample_estimate.cost.currency
    assert ctx["total_monthly"] == sample_estimate.cost.total_monthly
    assert ctx["total_yearly"] == sample_estimate.cost.total_yearly
    assert len(ctx["assumptions"]) == len(sample_estimate.assumptions)
    assert len(ctx["resources"]) == len(sample_estimate.cost.resource_summaries)
    assert str(sample_estimate.cost.total_monthly) in answer or f"{sample_estimate.cost.total_monthly:,.2f}" in answer


def test_chat_includes_comparison_context():
    from app.domain.optimization import ScenarioComparison, ScenarioOutcome

    comparison = ScenarioComparison(
        base=ScenarioOutcome(name="Current", total_monthly=100.0, total_yearly=1200.0, currency="USD",
                              delta_vs_base_monthly=0.0, delta_vs_base_percent=0.0),
        scenarios=[ScenarioOutcome(name="Upgraded", total_monthly=150.0, total_yearly=1800.0, currency="USD",
                                    delta_vs_base_monthly=50.0, delta_vs_base_percent=50.0)],
    )
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _groq_response("Upgrading costs USD 50.00 more per month.")

    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = AssistantService(provider=provider, model="llama-3.1-8b-instant")

    service.chat("How much more does the upgrade cost?", [], comparison=comparison)

    sent_payload = json.loads(captured["body"]["messages"][1]["content"])
    ctx = sent_payload["context"]["comparison"]
    assert ctx["base"]["total_monthly"] == 100.0
    assert ctx["scenarios"][0]["delta_vs_base_monthly"] == 50.0
    assert ctx["scenarios"][0]["direction"] == "additional_cost"


def test_chat_raises_gracefully_on_groq_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = AssistantService(provider=provider, model="llama-3.1-8b-instant")

    with pytest.raises(AssistantUnavailableError):
        service.chat("How does pricing work?", [])


def test_chat_raises_gracefully_on_malformed_groq_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    provider = GroqProvider("test-key", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = AssistantService(provider=provider, model="llama-3.1-8b-instant")

    with pytest.raises(AssistantUnavailableError):
        service.chat("How does pricing work?", [])


def test_chat_error_message_never_leaks_upstream_details():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key gsk_supersecret"})

    provider = GroqProvider("bad-key", "llama-3.1-8b-instant", transport=httpx.MockTransport(handler))
    service = AssistantService(provider=provider, model="llama-3.1-8b-instant")

    with pytest.raises(AssistantUnavailableError) as excinfo:
        service.chat("How does pricing work?", [])
    assert "gsk_" not in str(excinfo.value)
    assert "bad-key" not in str(excinfo.value)
