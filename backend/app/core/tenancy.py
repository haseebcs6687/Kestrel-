"""Multi-tenant isolation primitives and workspace-scoped repository base."""

import uuid
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace


class WorkspaceScopedRepository:
    """Central tenant-isolation mechanism enforcing workspace boundaries on all queries.

    ADR-022: Multi-tenant operations must be executed through repositories inheriting
    from this base class to ensure all queries are automatically and strictly scoped
    to the active workspace_id, preventing cross-tenant data leakage.
    """

    def __init__(self, session: Session, workspace_id: uuid.UUID) -> None:
        """Initialize the repository bound to a specific session and workspace.

        Args:
            session: Active SQLAlchemy database session.
            workspace_id: UUID of the workspace isolating all operations.
        """
        self.session = session
        self.workspace_id = workspace_id

    def scope(self, statement: Select[Any], model: Any) -> Select[Any]:
        """Apply workspace_id filter to a SQLAlchemy Select statement.

        Args:
            statement: SQLAlchemy Select query.
            model: ORM model class possessing a workspace_id attribute.

        Returns:
            Select query scoped strictly to self.workspace_id.
        """
        return statement.where(model.workspace_id == self.workspace_id)


def lock_workspace(db: Session, workspace_id: uuid.UUID) -> Workspace | None:
    """Acquire an exclusive row-level lock on the specified workspace (ADR-030).

    Args:
        db: Active database session.
        workspace_id: UUID of workspace row to lock with SELECT ... FOR UPDATE.

    Returns:
        Workspace | None: The locked workspace instance if found.
    """
    stmt = select(Workspace).where(Workspace.id == workspace_id).with_for_update()
    return db.scalar(stmt)
