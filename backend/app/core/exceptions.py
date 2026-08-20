"""Domain-level exceptions. Each maps to a specific HTTP status in the API layer."""


class FinOpsError(Exception):
    """Base class for all application errors."""

    def __init__(self, message: str, *, code: str = "finops_error"):
        super().__init__(message)
        self.message = message
        self.code = code


class ResourceNotFoundError(FinOpsError):
    def __init__(self, message: str):
        super().__init__(message, code="resource_not_found")


class ValidationFailedError(FinOpsError):
    """Raised when one or more validation results are BLOCKER severity."""

    def __init__(self, message: str, results: list | None = None):
        super().__init__(message, code="validation_failed")
        self.results = results or []


class CatalogUnavailableError(FinOpsError):
    def __init__(self, message: str):
        super().__init__(message, code="catalog_unavailable")


class PricingProviderError(FinOpsError):
    def __init__(self, message: str):
        super().__init__(message, code="pricing_provider_error")


class DuplicateEmailError(FinOpsError):
    def __init__(self, message: str = "An account with this email already exists."):
        super().__init__(message, code="duplicate_email")


class InvalidCredentialsError(FinOpsError):
    def __init__(self, message: str = "Incorrect email or password."):
        super().__init__(message, code="invalid_credentials")


class NotAuthenticatedError(FinOpsError):
    def __init__(self, message: str = "Authentication required."):
        super().__init__(message, code="not_authenticated")


class ForbiddenError(FinOpsError):
    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(message, code="forbidden")


class PayloadTooLargeError(FinOpsError):
    """Raised when an uploaded file exceeds `Settings.max_upload_size_bytes`
    (Phase 10 security review) - see app/core/uploads.py."""

    def __init__(self, message: str):
        super().__init__(message, code="payload_too_large")


class CurrencyProviderError(FinOpsError):
    """Raised when live exchange rates can't be obtained at all - i.e. the
    live fetch failed AND there is no still-usable cached rate to fall back
    to (see app/pricing/currency_converter.py). Never raised just because
    the live fetch failed while a cached rate exists; that case degrades
    silently to the cached value instead, same philosophy as SkuCache."""

    def __init__(self, message: str):
        super().__init__(message, code="currency_provider_error")


class IntakeParseError(FinOpsError):
    """Raised when an uploaded file can't be read at all (not a valid
    workbook) - distinct from a readable file with some invalid field
    values, which is reported as a list of ParseIssue instead of an error."""

    def __init__(self, message: str = "The uploaded file could not be read."):
        super().__init__(message, code="intake_parse_error")


class AssistantUnavailableError(FinOpsError):
    """Raised when the AI assistant can't answer - no API key configured,
    or the Claude API call itself failed (auth, rate limit, network,
    server error). Never raised for "the model didn't know the answer" -
    that's a normal 200 response with an honest answer."""

    def __init__(self, message: str = "The AI assistant is temporarily unavailable."):
        super().__init__(message, code="assistant_unavailable")
