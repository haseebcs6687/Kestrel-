"""Tests for application settings and configuration."""

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import (
    CSRF_HEADER_NAME,
    CSRF_HEADER_VALUE,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    Settings,
    get_settings,
)


def test_settings_load_from_environment() -> None:
    """Verify settings correctly load database parameters from environment or root .env."""
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.postgres_user == "kestrel"
    assert settings.postgres_db == "kestrel"
    assert settings.postgres_host == "127.0.0.1"
    assert settings.postgres_port == 5432
    assert settings.access_token_minutes == 15
    assert settings.registration_enabled is True
    assert len(settings.jwt_secret_key.get_secret_value()) >= 32


def test_settings_secret_masking() -> None:
    """Verify passwords and JWT secrets are never exposed in repr() or str()."""
    raw_secret = "super_secret_password_123"
    raw_jwt = "super_secure_random_jwt_secret_key_64_chars_length_here_now"
    settings = Settings(
        postgres_user="test_user",
        postgres_password=SecretStr(raw_secret),
        postgres_db="test_db",
        jwt_secret_key=SecretStr(raw_jwt),
    )
    assert raw_secret not in repr(settings)
    assert raw_secret not in str(settings)
    assert raw_secret not in repr(settings.postgres_password)
    assert raw_secret not in str(settings.postgres_password)

    assert raw_jwt not in repr(settings)
    assert raw_jwt not in str(settings)
    assert raw_jwt not in repr(settings.jwt_secret_key)
    assert raw_jwt not in str(settings.jwt_secret_key)


def test_jwt_secret_validation_rejects_weak_keys() -> None:
    """Verify JWT_SECRET_KEY fails fast when too short or using change_me prefix."""
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            postgres_user="test",
            postgres_password=SecretStr("pass"),
            postgres_db="db",
            jwt_secret_key=SecretStr("short_secret_under_32"),
        )

    with pytest.raises(ValidationError, match="change_me"):
        Settings(
            postgres_user="test",
            postgres_password=SecretStr("pass"),
            postgres_db="db",
            jwt_secret_key=SecretStr("change_me_this_is_long_enough_to_pass_length_check"),
        )


def test_access_token_minutes_bounds() -> None:
    """Verify ACCESS_TOKEN_MINUTES accepts 1..60 and rejects out-of-range values."""
    valid_key = SecretStr("a" * 32)
    s1 = Settings(
        postgres_user="u",
        postgres_password=SecretStr("p"),
        postgres_db="d",
        jwt_secret_key=valid_key,
        access_token_minutes=1,
    )
    assert s1.access_token_minutes == 1

    s60 = Settings(
        postgres_user="u",
        postgres_password=SecretStr("p"),
        postgres_db="d",
        jwt_secret_key=valid_key,
        access_token_minutes=60,
    )
    assert s60.access_token_minutes == 60

    with pytest.raises(ValidationError):
        Settings(
            postgres_user="u",
            postgres_password=SecretStr("p"),
            postgres_db="d",
            jwt_secret_key=valid_key,
            access_token_minutes=0,
        )

    with pytest.raises(ValidationError):
        Settings(
            postgres_user="u",
            postgres_password=SecretStr("p"),
            postgres_db="d",
            jwt_secret_key=valid_key,
            access_token_minutes=61,
        )


def test_jwt_constants() -> None:
    """Verify JWT security constants are immutable code constants."""
    assert JWT_ALGORITHM == "HS256"
    assert JWT_ISSUER == "kestrel"
    assert JWT_AUDIENCE == "kestrel-api"


def test_session_constants() -> None:
    """Verify session cookie and CSRF header constants are immutable code constants."""
    assert REFRESH_COOKIE_NAME == "kestrel_refresh"
    assert REFRESH_COOKIE_PATH == "/api/v1/auth"
    assert CSRF_HEADER_NAME == "X-Kestrel-Client"
    assert CSRF_HEADER_VALUE == "web"


def test_refresh_token_days_bounds() -> None:
    """Verify refresh_token_days bounds (1..30) and default value (7)."""
    valid_key = SecretStr("a" * 32)
    s = Settings(
        postgres_user="u",
        postgres_password=SecretStr("p"),
        postgres_db="d",
        jwt_secret_key=valid_key,
    )
    assert s.refresh_token_days == 7

    s1 = Settings(
        postgres_user="u",
        postgres_password=SecretStr("p"),
        postgres_db="d",
        jwt_secret_key=valid_key,
        refresh_token_days=1,
    )
    assert s1.refresh_token_days == 1

    s30 = Settings(
        postgres_user="u",
        postgres_password=SecretStr("p"),
        postgres_db="d",
        jwt_secret_key=valid_key,
        refresh_token_days=30,
    )
    assert s30.refresh_token_days == 30

    with pytest.raises(ValidationError):
        Settings(
            postgres_user="u",
            postgres_password=SecretStr("p"),
            postgres_db="d",
            jwt_secret_key=valid_key,
            refresh_token_days=0,
        )

    with pytest.raises(ValidationError):
        Settings(
            postgres_user="u",
            postgres_password=SecretStr("p"),
            postgres_db="d",
            jwt_secret_key=valid_key,
            refresh_token_days=31,
        )


def test_cookie_secure_resolution() -> None:
    """Verify is_cookie_secure resolves based on app_env and explicit override."""
    valid_key = SecretStr("a" * 32)
    # Dev default -> False
    s_dev = Settings(
        postgres_user="u",
        postgres_password=SecretStr("p"),
        postgres_db="d",
        jwt_secret_key=valid_key,
        app_env="dev",
    )
    assert s_dev.is_cookie_secure is False

    # Prod default -> True
    s_prod = Settings(
        postgres_user="u",
        postgres_password=SecretStr("p"),
        postgres_db="d",
        jwt_secret_key=valid_key,
        app_env="prod",
    )
    assert s_prod.is_cookie_secure is True

    # Explicit override True in dev
    s_override_true = Settings(
        postgres_user="u",
        postgres_password=SecretStr("p"),
        postgres_db="d",
        jwt_secret_key=valid_key,
        app_env="dev",
        cookie_secure=True,
    )
    assert s_override_true.is_cookie_secure is True

    # Explicit override False in prod
    s_override_false = Settings(
        postgres_user="u",
        postgres_password=SecretStr("p"),
        postgres_db="d",
        jwt_secret_key=valid_key,
        app_env="prod",
        cookie_secure=False,
    )
    assert s_override_false.is_cookie_secure is False


def test_sqlalchemy_url_driver_and_database() -> None:
    """Verify SQLAlchemy URL is constructed with psycopg driver and correct parameters."""
    settings = Settings(
        postgres_user="test_user",
        postgres_password=SecretStr("my_test_password"),
        postgres_db="test_db",
        postgres_host="localhost",
        postgres_port=5432,
    )
    url = settings.get_database_url()
    assert url.drivername == "postgresql+psycopg"
    assert url.database == "test_db"
    assert url.username == "test_user"
    assert url.host == "localhost"
    assert url.port == 5432
