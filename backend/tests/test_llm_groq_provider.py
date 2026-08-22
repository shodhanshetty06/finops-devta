"""Tests for the Groq HTTP client (app/llm/groq_provider.py) and the
provider factory (app/llm/factory.py). No real network calls are made -
httpx.MockTransport intercepts every request, same pattern as
tests/test_currency.py's CurrencyExchangeClient tests."""
import httpx
import pytest

from app.llm.base import LLMProviderError
from app.llm.factory import build_llm_provider
from app.llm.groq_provider import GroqProvider


def _groq_response(content: str = '{"items": [], "executive_summary": ""}'):
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
        },
    )


def test_complete_json_parses_a_successful_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert b"system prompt" in request.content
        return _groq_response('{"items": [{"id": 0, "explanation": "hello"}], "executive_summary": "hi"}')

    provider = GroqProvider("test-key", "llama-3.3-70b-versatile", transport=httpx.MockTransport(handler))
    text = provider.complete_json(system_prompt="system prompt", user_prompt="{}")
    assert text == '{"items": [{"id": 0, "explanation": "hello"}], "executive_summary": "hi"}'


def test_complete_json_retries_transient_5xx_then_succeeds():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 2:
            return httpx.Response(503, text="temporarily unavailable")
        return _groq_response()

    provider = GroqProvider("test-key", "llama-3.3-70b-versatile", transport=httpx.MockTransport(handler))
    text = provider.complete_json(system_prompt="s", user_prompt="{}")
    assert text
    assert calls["count"] == 2


def test_complete_json_gives_up_after_max_retries_and_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    provider = GroqProvider("test-key", "llama-3.3-70b-versatile", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMProviderError):
        provider.complete_json(system_prompt="s", user_prompt="{}")


def test_complete_json_raises_immediately_on_401_without_retrying():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401, json={"error": "invalid api key"})

    provider = GroqProvider("bad-key", "llama-3.3-70b-versatile", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMProviderError):
        provider.complete_json(system_prompt="s", user_prompt="{}")
    assert calls["count"] == 1


def test_complete_json_raises_on_malformed_response_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = GroqProvider("test-key", "llama-3.3-70b-versatile", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMProviderError):
        provider.complete_json(system_prompt="s", user_prompt="{}")


def test_complete_json_raises_on_empty_completion():
    def handler(request: httpx.Request) -> httpx.Response:
        return _groq_response(content="")

    provider = GroqProvider("test-key", "llama-3.3-70b-versatile", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMProviderError):
        provider.complete_json(system_prompt="s", user_prompt="{}")


def test_complete_json_raises_on_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    provider = GroqProvider("test-key", "llama-3.3-70b-versatile", transport=httpx.MockTransport(handler))
    with pytest.raises(LLMProviderError):
        provider.complete_json(system_prompt="s", user_prompt="{}")


# -- factory: missing GROQ_API_KEY / GROQ_MODEL must degrade to "no provider",
#    never raise - this is the "Groq unavailable / missing API key" fallback
#    contract that ExplanationService relies on. --

def test_build_llm_provider_returns_none_when_api_key_missing():
    assert build_llm_provider(None, "llama-3.3-70b-versatile") is None


def test_build_llm_provider_returns_none_when_model_missing():
    assert build_llm_provider("gsk_something", None) is None


def test_build_llm_provider_returns_none_when_both_missing():
    assert build_llm_provider(None, None) is None


def test_build_llm_provider_returns_groq_provider_when_both_configured():
    provider = build_llm_provider("gsk_something", "llama-3.3-70b-versatile")
    assert isinstance(provider, GroqProvider)


def test_settings_read_groq_env_vars_without_finops_prefix():
    # GROQ_API_KEY / GROQ_MODEL are deliberately NOT prefixed with FINOPS_
    # (unlike every other setting) - see app/core/config.py's validation_alias
    # on these two fields. This confirms that alias actually wins over the
    # global env_prefix="FINOPS_" pydantic-settings applies to every other field.
    import os

    from app.core.config import Settings

    os.environ["GROQ_API_KEY"] = "gsk_from_env_test"
    os.environ["GROQ_MODEL"] = "llama-3.1-from-env-test"
    try:
        settings = Settings(_env_file=None)
        assert settings.groq_api_key == "gsk_from_env_test"
        assert settings.groq_model == "llama-3.1-from-env-test"
    finally:
        del os.environ["GROQ_API_KEY"]
        del os.environ["GROQ_MODEL"]
