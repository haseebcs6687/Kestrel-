"""Multi-tenant isolation primitives and workspace-scoped repository base."""

import uuid
from typing import Any

from sqlalchemy import Select
from sqlalchemy.orm import Session


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
