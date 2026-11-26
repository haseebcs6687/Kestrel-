"""User data access repositories implementing workspace-scoped and unscoped lookups."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.tenancy import WorkspaceScopedRepository
from app.modules.auth.models import User


class UserRepository(WorkspaceScopedRepository):
    """Tenant-scoped user queries strictly isolated to a single workspace (ADR-022)."""

    def get(self, user_id: uuid.UUID) -> User | None:
        """Fetch a user by ID within the current repository workspace boundary."""
        stmt = self.scope(select(User).where(User.id == user_id), User)
        return self.session.scalar(stmt)

    def list_users(self, limit: int = 50, offset: int = 0) -> Sequence[User]:
        """List users belonging to the current workspace, ordered deterministically."""
        stmt = (
            self.scope(select(User), User)
            .order_by(User.created_at.asc(), User.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return self.session.scalars(stmt).all()

    def get_for_update(self, user_id: uuid.UUID) -> User | None:
        """Fetch a user by ID with an exclusive row lock within the workspace boundary."""
        stmt = self.scope(select(User).where(User.id == user_id), User).with_for_update()
        return self.session.scalar(stmt)

    def count_active_admins(self) -> int:
        """Count active admin users belonging to the scoped workspace."""
        stmt = (
            select(func.count())
            .select_from(User)
            .where(
                User.workspace_id == self.workspace_id,
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
        return self.session.scalar(stmt) or 0


# Unscoped Lookups (ADR-022 Exception)
# Justification: During initial login authentication and JWT bearer token decoding,
# the requesting client's workspace_id is not yet established. These lookups are
# strictly scoped to credential verification and token resolution.


def get_user_by_email(session: Session, email: str) -> User | None:
    """Find a user by normalized email address across all workspaces for authentication only."""
    return session.scalar(select(User).where(User.email == email))


def get_user_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    """Find a user by primary key ID for JWT bearer token validation only."""
    return session.scalar(select(User).where(User.id == user_id))
