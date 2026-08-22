"""Builds the configured LLMProvider (or None) from Settings.

Kept separate from GroqProvider itself so ExplanationService's dependents
(app/api/routers/explanation.py, app/api/routers/reports.py) never import a
vendor-specific class - only this factory and the LLMProvider interface.
Swapping providers later (Gemini/Claude) means changing the body of
`build_llm_provider`, nothing else.
"""
from functools import lru_cache

from app.llm.base import LLMProvider
from app.llm.groq_provider import GroqProvider


def build_llm_provider(api_key: str | None, model: str | None) -> LLMProvider | None:
    """None means "not configured" - ExplanationService treats a missing
    provider exactly like any other provider failure and falls back to
    deterministic template text, per this feature's fallback guarantee."""
    if not api_key or not model:
        return None
    return GroqProvider(api_key=api_key, model=model)


@lru_cache
def get_llm_provider() -> LLMProvider | None:
    from app.core.config import get_settings

    settings = get_settings()
    return build_llm_provider(settings.groq_api_key, settings.groq_model)
