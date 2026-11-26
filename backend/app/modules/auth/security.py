"""Cryptographic security utilities: Argon2id password hashing and JWT tokens."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import argon2
import jwt
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jwt.exceptions import PyJWTError

from app.core.config import JWT_ALGORITHM, JWT_AUDIENCE, JWT_ISSUER, get_settings

_hasher = argon2.PasswordHasher()
_DUMMY_HASH: str | None = None


class InvalidTokenError(Exception):
    """Raised when an access token cannot be validated or decoded."""


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2id with secure defaults."""
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash.

    Catches mismatch and corruption exceptions and returns False safely.
    """
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    """Check if the password hash needs upgrading according to current parameters."""
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except (InvalidHashError, VerificationError):
        return True


def get_dummy_hash() -> str:
    """Retrieve or lazily compute a dummy hash to prevent timing attacks on nonexistent users."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(32))
    return _DUMMY_HASH


def create_access_token(
    user_id: uuid.UUID,
    *,
    expires_delta: timedelta | None = None,
    now: datetime | None = None,
) -> tuple[str, int]:
    """Generate a signed JWT access token containing only subject and standard claims.

    ADR-021: Role, email, and workspace_id are deliberately excluded from token claims;
    all authorizations are resolved dynamically against the database on each request.

    Args:
        user_id: Subject UUID identifier for the user.
        expires_delta: Optional custom token expiration duration.
        now: Optional current timestamp (useful for deterministic testing).

    Returns:
        Tuple of (encoded_token_string, expires_in_seconds).
    """
    settings = get_settings()
    current_time = now if now is not None else datetime.now(UTC)
    if expires_delta is not None:
        duration = expires_delta
    else:
        duration = timedelta(minutes=settings.access_token_minutes)

    expires_at = current_time + duration
    expires_in_seconds = int(duration.total_seconds())

    payload = {
        "sub": str(user_id),
        "iat": int(current_time.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )
    return token, expires_in_seconds


def decode_access_token(token: str) -> uuid.UUID:
    """Decode and validate a JWT access token, returning the subject user UUID.

    Enforces mandatory exp, iat, sub, iss, aud claims, typ=='access', and HS256 algorithm.
    Any failure raises InvalidTokenError without leaking internal validation details.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={
                "require": ["exp", "iat", "sub", "iss", "aud"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except (PyJWTError, Exception) as exc:
        raise InvalidTokenError("Invalid token") from exc

    if payload.get("typ") != "access":
        raise InvalidTokenError("Invalid token type")

    sub = payload.get("sub")
    if not sub:
        raise InvalidTokenError("Token missing subject")

    try:
        return uuid.UUID(str(sub))
    except (ValueError, TypeError) as exc:
        raise InvalidTokenError("Token subject is not a valid UUID") from exc
