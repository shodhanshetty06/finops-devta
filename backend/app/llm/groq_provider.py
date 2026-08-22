"""
Groq LLM provider (OpenAI-compatible Chat Completions API).

Used only to turn already-computed structured data (assumptions, resource
costs, scenario deltas) into customer-friendly prose - see
app/services/explanation_service.py, which is the only caller and is the
component responsible for what gets asked and how the response is
validated. This module's job ends at "send a chat completion request, get
text back, or raise".

Talks to the Groq API directly over httpx (same raw-HTTP-with-retry
pattern as app/pricing/currency_converter.py's CurrencyExchangeClient)
rather than pulling in the `groq` SDK, so this stays a thin, easily
swappable adapter behind app/llm/base.py::LLMProvider - and `transport` can
be swapped for `httpx.MockTransport` in tests exactly like
CurrencyExchangeClient, with no real network call.
"""
from __future__ import annotations

import logging
import time

import httpx

from app.llm.base import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)

_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_REQUEST_TIMEOUT_SECONDS = 12.0
_MAX_RETRIES = 2
_BACKOFF_BASE_SECONDS = 0.5
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_TOKENS = 1536
_TEMPERATURE = 0.3  # low but nonzero - fluent prose, not creative embellishment


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._transport = transport

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": _TEMPERATURE,
            "max_tokens": _MAX_TOKENS,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                with httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS, transport=self._transport) as client:
                    response = client.post(_API_URL, json=payload, headers=headers)
                if response.status_code in _RETRYABLE_STATUS_CODES:
                    raise httpx.HTTPStatusError(
                        f"Groq API returned {response.status_code}", request=response.request, response=response,
                    )
                if response.status_code == 401:
                    raise LLMProviderError("Groq API rejected the configured GROQ_API_KEY (401 Unauthorized).")
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                if not content:
                    raise LLMProviderError("Groq API returned an empty completion.")
                return content
            except LLMProviderError:
                raise
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    time.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))

        raise LLMProviderError(f"Groq API call failed after {_MAX_RETRIES + 1} attempt(s): {last_exc}")
