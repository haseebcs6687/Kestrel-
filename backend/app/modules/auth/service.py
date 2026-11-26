"""Authentication and registration business logic and service workflows."""

import re
import secrets
from datetime import UTC, datetime

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.audit import service as audit_service
from app.modules.auth.models import Role, User
from app.modules.auth.repository import get_user_by_email
from app.modules.auth.security import (
    get_dummy_hash,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.modules.workspaces.models import Workspace

logger = structlog.get_logger()


class RegistrationDisabled(Exception):  # noqa: N818
    """Raised when an account registration attempt occurs while registration is disabled."""


class EmailAlreadyRegistered(Exception):  # noqa: N818
    """Raised when attempting to register an email address that already exists."""


class InvalidCredentials(Exception):  # noqa: N818
    """Raised when authentication fails due to incorrect credentials or inactive status."""


def generate_workspace_slug(name: str) -> str:
    """Generate a URL-safe workspace slug from a human-readable name with a random suffix."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    truncated = cleaned[:50].rstrip("-")
    base = truncated if truncated else "workspace"
    suffix = secrets.token_hex(3)
    return f"{base}-{suffix}"


def register(
    db: Session,
    email: str,
    password: str,
    workspace_name: str,
    settings: Settings,
) -> User:
    """Register a new user and initialize their administrative workspace.

    Args:
        db: Active database session.
        email: Plaintext email address to be normalized and stored.
        password: Plaintext password to be securely hashed via Argon2id.
        workspace_name: Human-readable name for the new organization workspace.
        settings: Application settings instance.

    Returns:
        Persisted User model instance with administrative privileges.

    Raises:
        RegistrationDisabled: If settings.registration_enabled is False.
        EmailAlreadyRegistered: If the normalized email is already in use.
    """
    if not settings.registration_enabled:
        raise RegistrationDisabled("Registration is currently disabled.")

    normalized_email = email.strip().lower()
    clean_workspace_name = workspace_name.strip()
    hashed_password = hash_password(password)
    slug = generate_workspace_slug(clean_workspace_name)

    workspace = Workspace(name=clean_workspace_name, slug=slug)
    db.add(workspace)

    try:
        db.flush()
        user = User(
            workspace_id=workspace.id,
            email=normalized_email,
            password_hash=hashed_password,
            role=Role.ADMIN.value,
        )
        db.add(user)
        db.flush()
        audit_service.record(
            db,
            workspace_id=workspace.id,
            action="auth.register",
            actor_type="user",
            actor_user_id=user.id,
            target_type="user",
            target_id=str(user.id),
            details={"workspace_slug": workspace.slug, "role": user.role},
        )
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyRegistered("Email is already registered.") from exc

    logger.info(
        "auth_register_success",
        user_id=str(user.id),
        workspace_id=str(workspace.id),
    )
    return user


def authenticate(
    db: Session,
    email: str,
    password: str,
) -> User:
    """Authenticate user credentials and update their last login timestamp.

    Args:
        db: Active database session.
        email: Raw email input.
        password: Raw password input.

    Returns:
        Authenticated User model instance.

    Raises:
        InvalidCredentials: For nonexistent user, wrong password, or inactive account.
    """
    normalized_email = email.strip().lower()
    user = get_user_by_email(db, normalized_email)

    if user is None:
        # Equalize execution timing against nonexistent accounts to prevent user enumeration
        verify_password(password, get_dummy_hash())
        logger.warning("auth_login_failed", reason="invalid_credentials")
        raise InvalidCredentials("Invalid email or password.")

    if not verify_password(password, user.password_hash):
        logger.warning(
            "auth_login_failed",
            reason="invalid_credentials",
            user_id=str(user.id),
        )
        raise InvalidCredentials("Invalid email or password.")

    if not user.is_active:
        logger.warning(
            "auth_login_failed",
            reason="inactive_account",
            user_id=str(user.id),
        )
        raise InvalidCredentials("Invalid email or password.")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.last_login_at = datetime.now(UTC)
    audit_service.record(
        db,
        workspace_id=user.workspace_id,
        action="auth.login",
        actor_type="user",
        actor_user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        details={"email": user.email},
    )
    db.flush()

    logger.info(
        "auth_login_success",
        user_id=str(user.id),
        workspace_id=str(user.workspace_id),
    )
    return user
