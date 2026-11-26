"""Domain services and exceptions for workspace user management."""

import uuid

import structlog
from sqlalchemy.orm import Session

from app.core.tenancy import lock_workspace
from app.modules.audit import service as audit_service
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository, get_user_by_email
from app.modules.auth.security import hash_password
from app.modules.auth.service import EmailAlreadyRegistered
from app.modules.auth.sessions import revoke_all_user_tokens

logger = structlog.get_logger()


class UserManagementError(Exception):
    """Base exception for user management domain operations."""


class UserNotFound(UserManagementError):  # noqa: N818
    """Raised when a user is not found within the tenant boundary."""


class LastAdminError(UserManagementError):
    """Raised when an operation would eliminate the last active administrator."""


def create_user(
    db: Session,
    *,
    actor_user: User,
    email: str,
    password: str,
    role: str,
) -> User:
    """Create a new user within the actor's workspace boundary.

    Normalizes email, verifies global uniqueness, hashes the password, records an audit
    event, and commits the transaction.
    """
    normalized_email = email.strip().lower()
    existing = get_user_by_email(db, normalized_email)
    if existing is not None:
        raise EmailAlreadyRegistered("Email already registered")

    pwd_hash = hash_password(password)
    new_user = User(
        workspace_id=actor_user.workspace_id,
        email=normalized_email,
        password_hash=pwd_hash,
        role=role,
        is_active=True,
    )
    db.add(new_user)
    db.flush()

    audit_service.record(
        db,
        workspace_id=actor_user.workspace_id,
        action="user.create",
        actor_type="user",
        actor_user_id=actor_user.id,
        target_type="user",
        target_id=str(new_user.id),
        details={"role": role},
    )
    logger.info(
        "user_created",
        user_id=str(new_user.id),
        workspace_id=str(actor_user.workspace_id),
    )
    db.commit()
    return new_user


def get_user(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> User:
    """Retrieve a single user within the caller's workspace boundary."""
    repo = UserRepository(db, workspace_id)
    user = repo.get(user_id)
    if user is None:
        raise UserNotFound("User not found")
    return user


def update_user(
    db: Session,
    *,
    actor_user: User,
    target_user_id: uuid.UUID,
    role: str | None = None,
    is_active: bool | None = None,
) -> User:
    """Update user role and active state under a workspace lock with last-admin protection.

    Executes in a single transaction:
    1. Locks caller's workspace row with SELECT ... FOR UPDATE.
    2. Loads target user via scoped repository with row lock (404 if absent).
    3. Applies requested changes and calculates diff.
    4. Flushes changes.
    5. Verifies at least one active admin remains in the workspace (409 if 0).
    6. Writes an audit log if changes occurred.
    7. Revokes all active refresh tokens if user was deactivated.
    8. Commits the transaction and returns updated user.
    """
    lock_workspace(db, actor_user.workspace_id)

    repo = UserRepository(db, actor_user.workspace_id)
    target = repo.get_for_update(target_user_id)
    if target is None:
        raise UserNotFound("User not found")

    changes: dict[str, dict[str, object]] = {}
    if role is not None and role != target.role:
        changes["role"] = {"from": target.role, "to": role}
        target.role = role

    if is_active is not None and is_active != target.is_active:
        changes["is_active"] = {"from": target.is_active, "to": is_active}
        target.is_active = is_active

    db.flush()

    active_admins = repo.count_active_admins()
    if active_admins == 0:
        db.rollback()
        raise LastAdminError("Cannot remove the last active admin")

    if changes:
        audit_service.record(
            db,
            workspace_id=actor_user.workspace_id,
            action="user.update",
            actor_type="user",
            actor_user_id=actor_user.id,
            target_type="user",
            target_id=str(target.id),
            details={"changes": changes},
        )
        if "is_active" in changes and target.is_active is False:
            logger.info(
                "user_deactivated",
                user_id=str(target.id),
                workspace_id=str(actor_user.workspace_id),
            )
        logger.info(
            "user_updated",
            user_id=str(target.id),
            workspace_id=str(actor_user.workspace_id),
        )

    if changes.get("is_active", {}).get("to") is False:
        revoke_all_user_tokens(db, target.id)

    db.commit()
    return target


def admin_reset_password(
    db: Session,
    *,
    actor_user: User,
    target_user_id: uuid.UUID,
    new_password: str,
) -> int:
    """Administratively reset a workspace user's password and revoke active sessions (ADR-031)."""
    repo = UserRepository(db, actor_user.workspace_id)
    target = repo.get_for_update(target_user_id)
    if target is None:
        raise UserNotFound("User not found")

    target.password_hash = hash_password(new_password)
    sessions_revoked = revoke_all_user_tokens(db, target.id)

    audit_service.record(
        db,
        workspace_id=actor_user.workspace_id,
        action="user.password_reset",
        actor_type="user",
        actor_user_id=actor_user.id,
        target_type="user",
        target_id=str(target.id),
        details={"sessions_revoked": sessions_revoked},
    )
    logger.info(
        "user_password_reset",
        user_id=str(target.id),
        workspace_id=str(actor_user.workspace_id),
    )
    db.commit()
    return sessions_revoked
