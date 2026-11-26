"""Application settings and configuration management via pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE_PATH = REPO_ROOT / ".env"

# JWT token constants - Hard-coded in code, never read from env or token header
JWT_ALGORITHM: str = "HS256"
JWT_ISSUER: str = "kestrel"
JWT_AUDIENCE: str = "kestrel-api"

# Session & Cookie constants - Hard-coded in code, never read from env
REFRESH_COOKIE_NAME: str = "kestrel_refresh"
REFRESH_COOKIE_PATH: str = "/api/v1/auth"
CSRF_HEADER_NAME: str = "X-Kestrel-Client"
CSRF_HEADER_VALUE: str = "web"


class Settings(BaseSettings):
    """Central application settings loaded from environment and root .env."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    jwt_secret_key: SecretStr
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    registration_enabled: bool = True
    refresh_token_days: int = Field(default=7, ge=1, le=30)
    cookie_secure: bool | None = None

    @property
    def is_cookie_secure(self) -> bool:
        """Resolve whether auth cookies should enforce the Secure attribute."""
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env == "prod"

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, v: SecretStr) -> SecretStr:
        secret_val = v.get_secret_value()
        if len(secret_val) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long.")
        if secret_val.startswith("change_me"):
            raise ValueError("JWT_SECRET_KEY cannot use placeholder prefix 'change_me'.")
        return v

    def get_database_url(self) -> URL:
        """Construct a SQLAlchemy connection URL using psycopg without string concatenation."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
