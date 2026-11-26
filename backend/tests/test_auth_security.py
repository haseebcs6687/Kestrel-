"""Unit tests for Argon2id password hashing and JWT access token security."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import JWT_ALGORITHM, JWT_AUDIENCE, JWT_ISSUER, get_settings
from app.modules.auth.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    get_dummy_hash,
    hash_password,
    password_needs_rehash,
    verify_password,
)


def test_password_hash_and_verify_success() -> None:
    """Verify passwords can be hashed and accurately verified."""
    plain = "SuperSecurePassword123!"
    hashed = hash_password(plain)

    assert hashed.startswith("$argon2id$")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_password_verify_catches_invalid_hashes_safely() -> None:
    """Verify corrupted or invalid hashes return False without crashing."""
    assert verify_password("secret", "invalid_garbage_hash") is False
    assert verify_password("secret", "$argon2id$v=19$m=65536,t=3,p=4$corrupted") is False


def test_password_needs_rehash_behavior() -> None:
    """Verify password_needs_rehash detects hash validity and upgrades."""
    hashed = hash_password("ValidPassword123")
    assert password_needs_rehash(hashed) is False
    assert password_needs_rehash("corrupted_hash") is True


def test_dummy_hash_is_stable_and_valid() -> None:
    """Verify dummy hash is lazily computed, cached, and valid Argon2id."""
    h1 = get_dummy_hash()
    h2 = get_dummy_hash()
    assert h1 == h2
    assert h1.startswith("$argon2id$")
    assert verify_password("nonexistent_password", h1) is False


def test_create_access_token_claims_and_exclusion() -> None:
    """Verify token contains required claims and excludes role, email, and workspace."""
    user_id = uuid.uuid4()
    now = datetime.now(UTC) - timedelta(seconds=1)
    delta = timedelta(minutes=15)

    token, expires_in = create_access_token(user_id, expires_delta=delta, now=now)
    assert expires_in == 900

    settings = get_settings()
    decoded = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
    )

    assert decoded["sub"] == str(user_id)
    assert decoded["iss"] == "kestrel"
    assert decoded["aud"] == "kestrel-api"
    assert decoded["typ"] == "access"
    assert decoded["iat"] == int(now.timestamp())
    assert decoded["exp"] == int((now + delta).timestamp())

    # ADR-021: Strict claim exclusion assertions
    assert "role" not in decoded
    assert "email" not in decoded
    assert "workspace_id" not in decoded


def test_decode_access_token_success() -> None:
    """Verify valid token decodes back to user UUID."""
    user_id = uuid.uuid4()
    token, _ = create_access_token(user_id)
    decoded_id = decode_access_token(token)
    assert decoded_id == user_id


def test_decode_access_token_rejects_expired() -> None:
    """Verify expired token raises InvalidTokenError."""
    user_id = uuid.uuid4()
    past_time = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
    token, _ = create_access_token(
        user_id,
        expires_delta=timedelta(minutes=5),
        now=past_time,
    )

    with pytest.raises(InvalidTokenError, match="Invalid token"):
        decode_access_token(token)


def test_decode_access_token_rejects_wrong_secret() -> None:
    """Verify token signed with an untrusted secret is rejected."""
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }
    bogus_token = jwt.encode(
        payload, "wrong_secret_key_that_is_32_characters_long", algorithm="HS256"
    )

    with pytest.raises(InvalidTokenError, match="Invalid token"):
        decode_access_token(bogus_token)


def test_decode_access_token_rejects_invalid_typ() -> None:
    """Verify token with typ != 'access' is rejected."""
    user_id = uuid.uuid4()
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "refresh",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(InvalidTokenError, match="Invalid token type"):
        decode_access_token(token)


def test_decode_access_token_rejects_non_uuid_sub() -> None:
    """Verify token with non-UUID subject is rejected."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": "not-a-valid-uuid",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(InvalidTokenError, match="not a valid UUID"):
        decode_access_token(token)


def test_decode_access_token_rejects_algorithm_none() -> None:
    """Verify unsigned tokens with algorithm 'none' are rejected."""
    user_id = uuid.uuid4()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }
    # Create unsigned token header + payload with alg none
    token_none = jwt.encode(payload, key="", algorithm="none")

    with pytest.raises(InvalidTokenError, match="Invalid token"):
        decode_access_token(token_none)


def test_decode_access_token_rejects_wrong_issuer() -> None:
    """Verify tokens with unexpected issuer claim are rejected."""
    user_id = uuid.uuid4()
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "iss": "untrusted-issuer",
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(InvalidTokenError, match="Invalid token"):
        decode_access_token(token)


def test_decode_access_token_rejects_wrong_audience() -> None:
    """Verify tokens with unexpected audience claim are rejected."""
    user_id = uuid.uuid4()
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "iss": JWT_ISSUER,
        "aud": "wrong-audience",
        "typ": "access",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(InvalidTokenError, match="Invalid token"):
        decode_access_token(token)


def test_decode_access_token_rejects_missing_exp() -> None:
    """Verify tokens missing required exp claim are rejected."""
    user_id = uuid.uuid4()
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(InvalidTokenError, match="Invalid token"):
        decode_access_token(token)
