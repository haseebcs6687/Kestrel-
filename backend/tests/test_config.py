"""Tests for application settings and configuration."""

from pydantic import SecretStr

from app.core.config import Settings, get_settings


def test_settings_load_from_environment() -> None:
    """Verify settings correctly load database parameters from environment or root .env."""
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.postgres_user == "kestrel"
    assert settings.postgres_db == "kestrel"
    assert settings.postgres_host == "127.0.0.1"
    assert settings.postgres_port == 5432


def test_settings_secret_masking() -> None:
    """Verify password is never exposed in repr(), str(), or property representations."""
    raw_secret = "super_secret_password_123"
    settings = Settings(
        postgres_user="test_user",
        postgres_password=SecretStr(raw_secret),
        postgres_db="test_db",
    )
    assert raw_secret not in repr(settings)
    assert raw_secret not in str(settings)
    assert raw_secret not in repr(settings.postgres_password)
    assert raw_secret not in str(settings.postgres_password)


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
