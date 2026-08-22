"""Provider-agnostic LLM interface.

`ExplanationService` (app/services/explanation_service.py) depends only on
this interface, never on a specific vendor's SDK or request/response shape.
Swapping Groq for Gemini/Claude later means adding one new class here that
implements `LLMProvider` and pointing `app/llm/factory.py` at it - nothing
in the pricing/normalization/validation engines, or in ExplanationService's
own logic, needs to change.
"""
from abc import ABC, abstractmethod


class LLMProviderError(Exception):
    """Raised when an LLM provider call fails for any reason - missing
    configuration, auth failure, rate limit, timeout, network error, or a
    response that can't be parsed. Always caught inside ExplanationService
    and turned into deterministic template text; never allowed to propagate
    and break estimate or report generation."""


class LLMProvider(ABC):
    """Minimal interface every LLM backend must implement."""

    @abstractmethod
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        """Runs one completion and returns the raw text of a JSON-object
        response. Raises LLMProviderError on any failure - never returns
        None or a partial/garbage string silently."""
        ...
