"""Central registry importing all application models for Alembic metadata discovery."""

from app.modules.auth.models import User  # noqa: F401
from app.modules.workspaces.models import Workspace  # noqa: F401
