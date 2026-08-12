"""
Startup secrets/security validation (Phase 7).

`app/core/config.py`'s `Settings._load_secret_files` handles *reading*
secrets from mounted files. This module handles *refusing to start* when a
production-unsafe default is still in place - the "forgot to override
FINOPS_JWT_SECRET_KEY before deploying" class of mistake, caught at boot
rather than discovered later as a security incident.

Deliberately does nothing in non-production environments (`development`,
`test`, anything else) - the whole point of `insecure-dev-secret-change-me`
being obviously-named is that local dev never needs to set a real secret.
"""
from app.core.config import Settings

_KNOWN_INSECURE_JWT_SECRET = "insecure-dev-secret-change-me"  # nosec B105 - sentinel value this guard detects, not a real credential
_PRODUCTION_ENVIRONMENT_NAMES = {"production", "prod"}
# Substrings that show up in obviously-a-placeholder secrets - catches
# values that are neither the exact dev sentinel above nor short enough to
# trip the length check, but are still clearly not a real random secret.
# Found via a live QA pass: docker-compose.yml's own example JWT secret
# ("change-me-to-a-random-secret-in-any-shared-environment") is 54
# characters long, well past _MIN_JWT_SECRET_LENGTH, so it sailed straight
# through this guard - a deployment that only flipped
# FINOPS_ENVIRONMENT to "production" without also replacing that value
# would have booted with a secret sitting in plaintext in version control.
_PLACEHOLDER_SECRET_MARKERS = (
    "change-me", "changeme", "change_me", "your-secret", "your_secret",
    "example", "placeholder", "insecure", "todo", "xxxx", "replace-me", "replace_me",
)  # nosec B105 - detection markers, not credentials
# RFC 7518 ยง3.2's minimum recommended key length for an HMAC-SHA256 JWT
# signing key (PyJWT itself warns below this - see test suite's
# InsecureKeyLengthWarning). A short-but-not-literally-the-default secret
# would otherwise sail past the check above undetected.
_MIN_JWT_SECRET_LENGTH = 32
# Phase 10 security review (found via `pip-audit`/dependency review, not an
# exploit): FINOPS_BCRYPT_ROUNDS exists purely so the test suite can hash
# passwords fast (see tests/conftest.py, rounds=4) - a production deployment
# that copies that value would meaningfully weaken password hashing.
_MIN_PRODUCTION_BCRYPT_ROUNDS = 10


class InsecureConfigurationError(RuntimeError):
    """Raised at startup when a production-unsafe default is detected."""


def validate_production_security(settings: Settings) -> None:
    if settings.environment.lower() not in _PRODUCTION_ENVIRONMENT_NAMES:
        return

    problems: list[str] = []
    if settings.jwt_secret_key == _KNOWN_INSECURE_JWT_SECRET:
        problems.append(
            "FINOPS_JWT_SECRET_KEY is still the insecure default - set FINOPS_JWT_SECRET_KEY "
            "(or FINOPS_JWT_SECRET_KEY_FILE) to a real random value."
        )
    elif len(settings.jwt_secret_key) < _MIN_JWT_SECRET_LENGTH:
        problems.append(
            f"FINOPS_JWT_SECRET_KEY is only {len(settings.jwt_secret_key)} characters long - use at least "
            f"{_MIN_JWT_SECRET_LENGTH} random characters (e.g. "
            f'`python -c "import secrets; print(secrets.token_urlsafe(48))"`).'
        )
    elif any(marker in settings.jwt_secret_key.lower() for marker in _PLACEHOLDER_SECRET_MARKERS):
        problems.append(
            f"FINOPS_JWT_SECRET_KEY looks like a placeholder value (contains a word like "
            f"'change-me' / 'example' / 'insecure'), not a real random secret - generate one with "
            f'`python -c "import secrets; print(secrets.token_urlsafe(48))"`.'
        )
    if settings.bcrypt_rounds < _MIN_PRODUCTION_BCRYPT_ROUNDS:
        problems.append(
            f"FINOPS_BCRYPT_ROUNDS is {settings.bcrypt_rounds}, below the minimum safe production value of "
            f"{_MIN_PRODUCTION_BCRYPT_ROUNDS} - this low a value only exists to keep the test suite fast "
            "(see tests/conftest.py); never use it outside tests."
        )
    if settings.cors_allow_origins == ["*"]:
        problems.append(
            "FINOPS_CORS_ALLOW_ORIGINS is '*' (allow-all) - restrict it to the actual "
            "frontend origin(s) in production."
        )
    if settings.auto_create_tables:
        problems.append(
            "FINOPS_AUTO_CREATE_TABLES is true - disable it in production and manage "
            "schema changes via `alembic upgrade head` instead."
        )

    if problems:
        raise InsecureConfigurationError(
            "Refusing to start with FINOPS_ENVIRONMENT=production and unsafe configuration:\n- "
            + "\n- ".join(problems)
        )
