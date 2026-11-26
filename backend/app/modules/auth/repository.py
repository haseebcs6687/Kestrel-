"""User data access repositories implementing workspace-scoped and unscoped lookups."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
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
