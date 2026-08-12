"""API response shape for display-currency conversion (see
app/pricing/currency_converter.py). Deliberately separate from
app/domain/pricing.py - this has nothing to do with how an estimate was
priced, only with converting an already-priced figure for display."""
from pydantic import BaseModel


class ExchangeRatesResponse(BaseModel):
    base: str
    rates: dict[str, float]
    as_of: str
    source: str
    fetched_at: str
    stale: bool
    supported_currencies: list[str]
