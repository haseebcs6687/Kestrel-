"""Refresh token session management, rotation, reuse detection, and revocation."""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.audit import service as audit_service
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)

logger = structlog.get_logger()


class SessionError(Exception):
    """Base exception for session and refresh token operations."""


class InvalidRefreshToken(SessionError):  # noqa: N818
    """Raised when a refresh token is unknown, expired, or belongs to an inactive user."""


class RefreshTokenReused(SessionError):  # noqa: N818
    """Raised when an already revoked refresh token is presented, indicating potential theft."""


def issue_refresh_token(
    db: Session,
    *,
    user: User,
    workspace_id: uuid.UUID,
    family_id: uuid.UUID | None = None,
) -> tuple[str, RefreshToken]:
    """Generate and persist a new refresh token within a token rotation family.

    Args:
        db: Active database session.
        user: Owner user model.
        workspace_id: UUID of workspace boundary.
        family_id: Existing family UUID or None to start a new rotation family.

    Returns:
        tuple[str, RefreshToken]: The plaintext raw token and the persisted model record.
    """
    settings = get_settings()
    raw = generate_refresh_token()
    token_hash = hash_refresh_token(raw)
    family_uuid = family_id or uuid.uuid4()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_days)

    token_record = RefreshToken(
        workspace_id=workspace_id,
        user_id=user.id,
        token_hash=token_hash,
        family_id=family_uuid,
        expires_at=expires_at,
    )
    db.add(token_record)
    db.flush()
    return raw, token_record


def rotate_refresh_token(
    db: Session,
    *,
    raw_token: str,
) -> tuple[str, str, User]:
    """Rotate a valid refresh token and detect reuse attacks (ADR-024).

    Args:
        db: Active database session.
        raw_token: Plaintext refresh token presented by client cookie.

    Returns:
        tuple[str, str, User]: (access_token, new_raw_token, user)

    Raises:
        InvalidRefreshToken: If token not found, expired, or user is inactive.
        RefreshTokenReused: If a revoked token is presented, triggering family invalidation.
    """
    token_hash = hash_refresh_token(raw_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    token = db.scalar(stmt)

    if token is None:
        raise InvalidRefreshToken("Token not found")

    if token.is_revoked:
        # REUSE DETECTED: Immediately invalidate entire family
        now = datetime.now(UTC)
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        audit_service.record(
            db,
            workspace_id=token.workspace_id,
            action="auth.refresh_reuse_detected",
            actor_type="user",
            actor_user_id=token.user_id,
            target_type="session",
            target_id=str(token.id),
            details={"family_id": str(token.family_id), "reason": "revoked_token_presented"},
        )
        db.commit()  # CRITICAL: Persist revocation even though request fails
        logger.warning(
            "security.refresh_token_reuse_detected",
            family_id=str(token.family_id),
            user_id=str(token.user_id),
            token_id=str(token.id),
        )
        raise RefreshTokenReused("Token reuse detected; session family invalidated")

    if token.is_expired:
        token.revoked_at = datetime.now(UTC)
        db.commit()
        raise InvalidRefreshToken("Token expired")

    user = db.scalar(select(User).where(User.id == token.user_id))
    if user is None or not user.is_active:
        now = datetime.now(UTC)
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.commit()
        raise InvalidRefreshToken("User inactive")

    new_raw, new_token = issue_refresh_token(
        db,
        user=user,
        workspace_id=token.workspace_id,
        family_id=token.family_id,
    )

    now = datetime.now(UTC)
    token.revoked_at = now
    token.replaced_by_id = new_token.id

    access_token, _ = create_access_token(user.id)

    audit_service.record(
        db,
        workspace_id=user.workspace_id,
        action="auth.refresh",
        actor_type="user",
        actor_user_id=user.id,
        target_type="session",
        target_id=str(new_token.id),
        details={"family_id": str(token.family_id)},
    )
    db.commit()
    return access_token, new_raw, user


def revoke_family_by_token(
    db: Session,
    *,
    raw_token: str,
) -> bool:
    """Revoke all active tokens in the family associated with the presented token.

    Args:
        db: Active database session.
        raw_token: Plaintext refresh token presented during logout.

    Returns:
        bool: True if tokens were revoked or already revoked; False if token was unknown.
    """
    token_hash = hash_refresh_token(raw_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    token = db.scalar(stmt)

    if token is None:
        return False

    if token.is_revoked:
        return True

    now = datetime.now(UTC)
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == token.family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    audit_service.record(
        db,
        workspace_id=token.workspace_id,
        action="auth.logout",
        actor_type="user",
        actor_user_id=token.user_id,
        target_type="session",
        target_id=str(token.id),
        details={"family_id": str(token.family_id)},
    )
    db.commit()
    return True
