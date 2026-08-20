"""FastAPI application entrypoint for the GCP FinOps Estimation Platform."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import assistant, auth, catalog, currency, estimate, health, intake, jobs, optimization, projects, reports, service_catalog, validate
from app.core.config import get_settings
from app.core.exceptions import (
    AssistantUnavailableError,
    CatalogUnavailableError,
    CurrencyProviderError,
    DuplicateEmailError,
    FinOpsError,
    ForbiddenError,
    InvalidCredentialsError,
    NotAuthenticatedError,
    PayloadTooLargeError,
    PricingProviderError,
    ResourceNotFoundError,
    ValidationFailedError,
)
from app.core.logging import configure_logging
from app.core.secrets import validate_production_security
from app.db.base import Base
from app.db.session import engine
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.unhandled_exceptions import UnhandledExceptionMiddleware

configure_logging()
settings = get_settings()
logger = logging.getLogger("app.unhandled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuses to start with an unsafe production configuration (default JWT
    # secret, allow-all CORS, auto-managed schema) rather than boot
    # insecurely - see app/core/secrets.py.
    validate_production_security(settings)

    # Convenience for local dev/demo only. In production, disable
    # FINOPS_AUTO_CREATE_TABLES and run `alembic upgrade head` instead so
    # schema changes go through reviewable, ordered migrations.
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-powered Google Cloud FinOps Estimation & Pricing Platform. "
        "Pricing is always sourced from a PricingProvider (mock catalog today, "
        "live Google Cloud Billing Catalog API in production) - the AI layer only "
        "validates, normalizes, recommends, and explains."
    ),
    lifespan=lifespan,
)

# UnhandledExceptionMiddleware is added first, which makes it the innermost
# user middleware (closest to the router) - see the ordering note below.
# That placement is load-bearing: a route that raises anything other than a
# FinOpsError subclass (a real bug, not an expected domain error) would
# otherwise propagate all the way to Starlette's ServerErrorMiddleware, which
# sits *outside* every middleware added here, including CORSMiddleware. That
# middleware's fallback 500 response never passes back through
# CORSMiddleware, so it carries no Access-Control-Allow-Origin header - the
# browser silently discards it and callers see a bare "Network Error"
# instead of the actual failure (this is exactly how the intake/excel
# auto-price bug this was diagnosed from presented). Catching the exception
# here, inside CORSMiddleware, turns it into a normal response that CORS
# still gets to add headers to.
app.add_middleware(UnhandledExceptionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Middleware order: the last one added is outermost (runs first on the way
# in, last on the way out), so RequestLoggingMiddleware wraps everything -
# including rate-limit rejections - and its duration measurement reflects
# true end-to-end request time.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)


# Status codes are mapped from most-specific exception to least-specific;
# FastAPI dispatches to the handler registered for the most derived type.
_STATUS_CODE_BY_EXCEPTION = {
    ResourceNotFoundError: 404,
    ForbiddenError: 403,
    NotAuthenticatedError: 401,
    InvalidCredentialsError: 401,
    DuplicateEmailError: 409,
    CatalogUnavailableError: 503,
    PricingProviderError: 502,
    CurrencyProviderError: 502,
    PayloadTooLargeError: 413,
    AssistantUnavailableError: 503,
}


@app.exception_handler(ValidationFailedError)
async def validation_failed_handler(request: Request, exc: ValidationFailedError):
    return JSONResponse(
        status_code=422,
        content={
            "error": exc.code,
            "message": exc.message,
            "results": [r.model_dump(mode="json") for r in exc.results],
        },
    )


@app.exception_handler(FinOpsError)
async def finops_error_handler(request: Request, exc: FinOpsError):
    status_code = _STATUS_CODE_BY_EXCEPTION.get(type(exc), 400)
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return JSONResponse(status_code=status_code, content={"error": exc.code, "message": exc.message}, headers=headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Any exception that isn't a FinOpsError (a genuine bug, not an expected
    # domain error) would otherwise propagate past this app to Starlette's
    # ServerErrorMiddleware, which sits *outside* CORSMiddleware and returns
    # a plain-text 500 with no CORS headers at all. Browsers then block that
    # response from ever reaching client JS, so callers see a bare "Network
    # Error" instead of the actual failure - see the intake/excel upload bug
    # this was diagnosed from. Handling it here keeps the response inside
    # the normal FastAPI exception-handler path, which CORSMiddleware does
    # process, while still logging the real traceback server-side.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred. Please try again."},
    )


app.include_router(health.router)
app.include_router(catalog.router)
app.include_router(service_catalog.router)
app.include_router(validate.router)
app.include_router(estimate.router)
app.include_router(reports.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(intake.router)
app.include_router(jobs.router)
app.include_router(optimization.router)
app.include_router(currency.router)
app.include_router(assistant.router)
