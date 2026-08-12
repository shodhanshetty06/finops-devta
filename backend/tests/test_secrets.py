"""Tests for Phase 7 secrets management: reading a secret from a mounted
file (app/core/config.py's Settings._load_secret_files) and refusing to
start with an unsafe production configuration (app/core/secrets.py)."""
import pytest

from app.core.config import Settings
from app.core.secrets import InsecureConfigurationError, validate_production_security


def test_jwt_secret_file_overrides_inline_value(tmp_path):
    secret_file = tmp_path / "jwt-secret.txt"
    secret_file.write_text("a-real-secret-from-a-mounted-file\n")

    settings = Settings(jwt_secret_key="insecure-dev-secret-change-me", jwt_secret_key_file=str(secret_file))
    assert settings.jwt_secret_key == "a-real-secret-from-a-mounted-file"


def test_jwt_secret_file_missing_raises():
    with pytest.raises(ValueError, match="nonexistent file"):
        Settings(jwt_secret_key_file="/nonexistent/path/to/secret")


def test_jwt_secret_file_empty_raises(tmp_path):
    secret_file = tmp_path / "empty.txt"
    secret_file.write_text("   \n")
    with pytest.raises(ValueError, match="empty"):
        Settings(jwt_secret_key_file=str(secret_file))


def test_no_secret_file_leaves_inline_value_untouched():
    settings = Settings(jwt_secret_key="whatever-value")
    assert settings.jwt_secret_key == "whatever-value"


def test_production_with_default_jwt_secret_refuses_to_start():
    settings = Settings(environment="production", jwt_secret_key="insecure-dev-secret-change-me",
                         cors_allow_origins=["https://app.example.com"], auto_create_tables=False)
    with pytest.raises(InsecureConfigurationError, match="FINOPS_JWT_SECRET_KEY"):
        validate_production_security(settings)


def test_production_with_allow_all_cors_refuses_to_start():
    settings = Settings(environment="production", jwt_secret_key="a-real-random-secret-value-that-is-at-least-32-chars-long",
                         cors_allow_origins=["*"], auto_create_tables=False)
    with pytest.raises(InsecureConfigurationError, match="CORS"):
        validate_production_security(settings)


def test_production_with_auto_create_tables_refuses_to_start():
    settings = Settings(environment="production", jwt_secret_key="a-real-random-secret-value-that-is-at-least-32-chars-long",
                         cors_allow_origins=["https://app.example.com"], auto_create_tables=True)
    with pytest.raises(InsecureConfigurationError, match="AUTO_CREATE_TABLES"):
        validate_production_security(settings)


def test_production_with_safe_configuration_starts_cleanly():
    # bcrypt_rounds explicitly overridden here: the suite-wide test default
    # (FINOPS_BCRYPT_ROUNDS=4, see conftest.py) is itself below the
    # production-safe minimum, which would otherwise make this "everything
    # is fine" test fail for an unrelated reason.
    settings = Settings(environment="production", jwt_secret_key="a-real-random-secret-value-that-is-at-least-32-chars-long",
                         cors_allow_origins=["https://app.example.com"], auto_create_tables=False, bcrypt_rounds=12)
    validate_production_security(settings)  # should not raise


def test_production_with_short_jwt_secret_refuses_to_start():
    """Phase 10 security review: a secret that isn't the literal known-default
    string can still be too short to be a real HMAC-SHA256 key."""
    settings = Settings(environment="production", jwt_secret_key="short-secret",
                         cors_allow_origins=["https://app.example.com"], auto_create_tables=False)
    with pytest.raises(InsecureConfigurationError, match="FINOPS_JWT_SECRET_KEY"):
        validate_production_security(settings)


def test_production_with_placeholder_looking_jwt_secret_refuses_to_start():
    """Regression test (live QA pass): docker-compose.yml's own example JWT
    secret ("change-me-to-a-random-secret-in-any-shared-environment") is 54
    characters long - long enough to sail past the length check even
    though it's obviously still a placeholder. A deployment that only
    flipped FINOPS_ENVIRONMENT to "production" without also replacing that
    value must still be refused at boot."""
    settings = Settings(environment="production",
                         jwt_secret_key="change-me-to-a-random-secret-in-any-shared-environment",
                         cors_allow_origins=["https://app.example.com"], auto_create_tables=False, bcrypt_rounds=12)
    with pytest.raises(InsecureConfigurationError, match="FINOPS_JWT_SECRET_KEY"):
        validate_production_security(settings)


def test_production_with_low_bcrypt_rounds_refuses_to_start():
    """Phase 10 security review: FINOPS_BCRYPT_ROUNDS exists so tests can hash
    fast (see conftest.py, rounds=4) - a production deployment must not
    inherit that value."""
    settings = Settings(environment="production", jwt_secret_key="a-real-random-secret-value-that-is-at-least-32-chars-long",
                         cors_allow_origins=["https://app.example.com"], auto_create_tables=False, bcrypt_rounds=4)
    with pytest.raises(InsecureConfigurationError, match="FINOPS_BCRYPT_ROUNDS"):
        validate_production_security(settings)


def test_development_environment_is_never_blocked():
    settings = Settings(environment="development", jwt_secret_key="insecure-dev-secret-change-me",
                         cors_allow_origins=["*"], auto_create_tables=True)
    validate_production_security(settings)  # should not raise - dev is allowed to be insecure


def test_all_problems_are_listed_together():
    settings = Settings(environment="production", jwt_secret_key="insecure-dev-secret-change-me",
                         cors_allow_origins=["*"], auto_create_tables=True)
    with pytest.raises(InsecureConfigurationError) as exc_info:
        validate_production_security(settings)
    message = str(exc_info.value)
    assert "JWT_SECRET_KEY" in message
    assert "CORS" in message
    assert "AUTO_CREATE_TABLES" in message
