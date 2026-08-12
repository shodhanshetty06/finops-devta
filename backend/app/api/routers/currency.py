"""Display-currency conversion endpoint - separate from pricing itself (see
app/pricing/currency_converter.py). Public/unauthenticated like /catalog and
/validate: it returns no user- or account-specific data."""
from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.domain.currency import ExchangeRatesResponse
from app.pricing.currency_converter import CurrencyConverter, get_currency_converter

router = APIRouter(prefix="/api/v1/currency", tags=["Currency"])


@router.get(
    "/rates",
    response_model=ExchangeRatesResponse,
    summary="Get live exchange rates for converting priced estimates into another currency for display",
    description=(
        "Rates come from a free, no-key currency API (Frankfurter - ECB reference rates), cached for a few "
        "hours. This does not change how anything is priced - `default_currency` and each estimate's own "
        "`cost.currency` are unaffected. It only supplies the numbers a frontend needs to *display* an "
        "already-priced estimate in the user's preferred currency. `stale=true` means the live refresh just "
        "failed and this is the last known-good cached rate, still labeled with when it was actually fetched."
    ),
)
def get_rates(
    base: str = Query(default="USD", description="Currency the source amounts are priced in"),
    converter: CurrencyConverter = Depends(get_currency_converter),
    settings: Settings = Depends(get_settings),
) -> ExchangeRatesResponse:
    snapshot = converter.get_rates(base)
    return ExchangeRatesResponse(
        **snapshot.to_dict(),
        supported_currencies=settings.supported_display_currencies,
    )
