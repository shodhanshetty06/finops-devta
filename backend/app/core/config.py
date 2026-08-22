"""
Application configuration.

Settings are loaded from environment variables (12-factor style) with sane
defaults for local development. In production, override via env vars or a
mounted .env file - never hardcode secrets.
"""
import os
from enum import Enum
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class NormalizationStrategy(str, Enum):
    """How the normalization engine resolves unsupported requested values."""

    CONSERVATIVE = "conservative"  # nearest lower supported value
    BALANCED = "balanced"          # mathematically closest supported value
    PERFORMANCE = "performance"    # nearest higher supported value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINOPS_", extra="ignore")

    app_name: str = "GCP FinOps Estimation Platform"
    app_version: str = "0.1.0"
    environment: str = "development"

    # Default normalization strategy; can be overridden per-request.
    default_normalization_strategy: NormalizationStrategy = NormalizationStrategy.BALANCED

    # Pricing provider: "mock" uses deterministic mock catalog data that mirrors
    # the shape of the real Google Cloud Billing Catalog API. "gcp" calls the
    # live Cloud Billing Catalog API using a service account (Phase 5). Only
    # meaningful when cloud_provider="gcp" - AWS/Azure always use their mock
    # providers this phase (see cloud_provider below).
    pricing_provider: str = "mock"

    # -- Multi-cloud (Phase 9) -------------------------------------------------
    # Which cloud's CatalogProvider/PricingProvider backs the estimation
    # pipeline. "gcp" (default) preserves all prior-phase behavior exactly,
    # including the pricing_provider mock/live toggle above. "aws"/"azure"
    # route to AwsCatalogProvider/AwsPricingProvider or
    # AzureCatalogProvider/AzurePricingProvider - both mock-only this phase,
    # same status GCP's mock provider had before Phase 5. `CustomerRequirement`
    # is unchanged either way: `region`/`compute.machine_family` values are
    # treated as a cloud-agnostic canonical vocabulary that each provider maps
    # onto its own real regions/instance families - see
    # app/catalog/aws_provider.py for the mapping rationale.
    cloud_provider: str = "gcp"

    # Default currency and tax rate applied to generated estimates.
    default_currency: str = "USD"
    default_tax_rate_percent: float = Field(default=0.0, ge=0, le=100)

    # Support plan uplift applied on top of infrastructure cost (configurable).
    support_plan_percent: float = Field(default=0.0, ge=0, le=100)

    # Google Cloud credentials (only used when pricing_provider="gcp"). Either
    # is sufficient for the Cloud Billing Catalog API - it serves public list
    # pricing, so a plain restricted API key works; a service account is
    # supported too since many orgs disable API key creation via org policy.
    gcp_service_account_json: str | None = None  # path to a service account key file
    gcp_api_key: str | None = None
    gcp_billing_account_id: str | None = None  # not required by the Catalog API; reserved for future account-scoped features

    # -- Live pricing SKU cache (Phase 5) ------------------------------------
    # The Cloud Billing Catalog API returns the full SKU list per service
    # (thousands of rows) and is rate-limited, so results are cached. Redis
    # is used when reachable (see docker-compose.yml); falls back to an
    # in-memory cache automatically otherwise, so this never blocks local dev.
    redis_url: str = "redis://localhost:6379/0"
    sku_cache_ttl_seconds: int = 24 * 60 * 60  # Google typically updates list pricing at most daily

    # -- Currency display conversion --------------------------------------------
    # Every estimate is priced in a single native currency (default_currency
    # above, USD for the mock provider). This is a *separate* concern: letting
    # a user view those same figures converted into their own currency for
    # display (e.g. a customer in India viewing USD-priced estimates in INR)
    # without re-pricing anything. Rates come from a free, no-API-key
    # currency API (Frankfurter - European Central Bank reference rates,
    # https://www.frankfurter.dev) so displayed conversions are always real
    # fetched rates, never a hardcoded/guessed number - consistent with this
    # platform's "never fabricate a price" rule for the pricing engine
    # itself. See app/pricing/currency_converter.py.
    currency_exchange_api_url: str = "https://api.frankfurter.dev/v1/latest"
    currency_exchange_cache_ttl_seconds: int = 6 * 60 * 60  # rates don't need to be fresher than this
    supported_display_currencies: list[str] = [
        "USD", "INR", "EUR", "GBP", "JPY", "AUD", "CAD", "SGD", "AED", "CNY",
    ]

    cors_allow_origins: list[str] = ["*"]

    log_level: str = "INFO"

    # -- Uploads (Phase 10 security review) ------------------------------------
    # Excel questionnaire uploads (POST /api/v1/intake/excel - which has no
    # auth requirement at all - and the per-project authenticated shortcut)
    # used to call `await file.read()` with no size limit: an *unauthenticated*
    # memory-exhaustion DoS vector on the stateless intake endpoint. Bounded
    # via app/core/uploads.py; 10 MB is generous for a questionnaire workbook.
    max_upload_size_bytes: int = 10 * 1024 * 1024

    # -- Persistence (Phase 3) ------------------------------------------------
    # SQLite by default for zero-setup local development; point at Postgres in
    # production (see docker-compose.yml). Repositories/services are written
    # against the SQLAlchemy ORM only, so either backend works unmodified.
    database_url: str = "sqlite:///./finops.db"
    # Auto-create tables on startup - convenient for local dev/demo. In
    # production, disable this and run `alembic upgrade head` instead so
    # schema changes go through reviewable migrations.
    auto_create_tables: bool = True

    # -- Auth (Phase 3) ------------------------------------------------
    # MUST be overridden via FINOPS_JWT_SECRET_KEY in any non-development
    # environment. The default is intentionally obviously insecure so it can
    # never be mistaken for a real production secret.
    jwt_secret_key: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 1 day

    # bcrypt work factor. 12 is a secure default for production. Tests lower
    # this via FINOPS_BCRYPT_ROUNDS to keep the suite fast - hashing is
    # deliberately CPU-expensive, and that cost multiplies across the many
    # register/login calls a full test run makes.
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)

    # -- Async jobs (Phase 7) -------------------------------------------------
    # Celery broker/result backend. Both default to the same Redis instance
    # the Phase 5 SKU cache uses - one Redis for both purposes is a
    # reasonable default for this platform's scale; split them via env vars
    # if broker and result traffic ever need to be isolated.
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    # Runs tasks synchronously in-process instead of dispatching to a worker.
    # Tests set this to True (see tests/conftest.py) so the suite never
    # depends on a running Celery worker or broker. Never enable in
    # production - it defeats the entire purpose of the queue.
    celery_task_always_eager: bool = False
    # How long a completed job's result stays in the result backend before
    # Celery expires it. Report bytes are base64-encoded in the result, so
    # this bounds how long generated files remain downloadable.
    celery_result_expires_seconds: int = 60 * 60  # 1 hour

    def resolved_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    # -- Rate limiting (Phase 7) -----------------------------------------------
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = Field(default=120, gt=0)
    # Endpoints under this prefix get a stricter limit - report/estimate
    # generation is far more CPU/IO-expensive per request than e.g. /health.
    # /api/v1/auth/login is included for a different reason (Phase 10
    # security review): the standard limit (120/min default) is too
    # permissive for a login endpoint specifically - the heavy limit throttles
    # credential-stuffing/brute-force attempts without blocking normal use.
    rate_limit_heavy_requests_per_minute: int = Field(default=20, gt=0)
    rate_limit_heavy_path_prefixes: list[str] = [
        "/api/v1/estimate", "/api/v1/reports", "/api/v1/jobs", "/api/v1/intake", "/api/v1/auth/login",
        "/api/v1/assistant", "/api/v1/explanations",
    ]

    # -- Request logging (Phase 7) ---------------------------------------------
    request_logging_enabled: bool = True

    # -- Secrets management (Phase 7) ------------------------------------------
    # Any FINOPS_<NAME>_FILE env var (see app/core/secrets.py) is read as a
    # mounted-secret-file path and takes precedence over FINOPS_<NAME> - the
    # standard Docker/Kubernetes secrets-as-files pattern, so a real
    # deployment never needs to put a raw secret value directly in an env var.
    jwt_secret_key_file: str | None = None

    # -- AI Assistant (Phase 11) -------------------------------------------
    # Backs the floating chat widget (frontend/src/components/ai-assistant.tsx)
    # with a real Claude call instead of the local keyword-matched FAQ it
    # previously used. Unset by default - the endpoint returns 503 rather
    # than silently falling back to a canned answer, so the frontend can
    # tell "not configured" apart from "the model call failed" and show the
    # user something honest either way.
    anthropic_api_key: str | None = None
    assistant_model: str = "claude-opus-5"

    # -- LLM-assisted explanations (Groq) ---------------------------------------
    # Generates customer-friendly, plain-English explanations of normalization
    # assumptions, priced resources, and upgrade/downgrade cost comparisons for
    # the estimate/report flow (app/services/explanation_service.py). Purely
    # explanatory: Groq never calculates a price, selects a SKU, chooses a
    # currency, or validates anything - the deterministic pricing/normalization/
    # validation engines remain the single source of truth for every number and
    # configuration value it is given to explain. Unset by default; every
    # endpoint that uses this falls back to deterministic template text (never
    # an error) when it's unset, times out, or the call fails, exactly like the
    # currency converter's stale-cache fallback above.
    #
    # Deliberately named without the FINOPS_ prefix (validation_alias below) so
    # the required env var names match GROQ_API_KEY / GROQ_MODEL exactly, e.g.
    # for parity with how the Groq docs/dashboard refer to them.
    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    groq_model: str | None = Field(default=None, validation_alias="GROQ_MODEL")

    # -- Audit log retention ---------------------------------------------------
    # Per-estimate audit trail rows (app/db/models.py::AuditLogRowModel) are
    # only ever shown to admins (see EstimateResultView / projects.py
    # _to_detail) - regular users never see them, so there's no reason to
    # retain them beyond a short compliance/debugging window. A daily Celery
    # beat task (app/tasks/audit_tasks.py) purges rows older than this.
    audit_log_retention_days: int = Field(default=2, ge=1)

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        # Some managed Postgres providers (notably Heroku-style connection
        # strings) still hand out the legacy "postgres://" scheme, which
        # SQLAlchemy 2.x no longer recognizes ("Could not parse SQLAlchemy
        # URL"). Neon's own connection strings already use "postgresql://",
        # so this is purely a defensive fallback, not something Neon itself
        # requires.
        if self.database_url.startswith("postgres://"):
            self.database_url = "postgresql://" + self.database_url[len("postgres://"):]
        return self

    @model_validator(mode="after")
    def _validate_cloud_provider(self) -> "Settings":
        valid = {"gcp", "aws", "azure"}
        if self.cloud_provider not in valid:
            raise ValueError(f"FINOPS_CLOUD_PROVIDER must be one of {sorted(valid)}, got '{self.cloud_provider}'.")
        return self

    @model_validator(mode="after")
    def _load_secret_files(self) -> "Settings":
        """If FINOPS_JWT_SECRET_KEY_FILE is set, its file content overrides
        FINOPS_JWT_SECRET_KEY - the standard Docker/Kubernetes
        secrets-as-a-mounted-file pattern. Runs once at Settings
        construction (this is cached via `get_settings()`), not per-request."""
        if self.jwt_secret_key_file:
            path = self.jwt_secret_key_file
            if not os.path.isfile(path):
                raise ValueError(f"FINOPS_JWT_SECRET_KEY_FILE points at a nonexistent file: {path}")
            with open(path, encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                raise ValueError(f"FINOPS_JWT_SECRET_KEY_FILE ({path}) is empty.")
            self.jwt_secret_key = content
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
