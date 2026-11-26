"""Audit log Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    """Schema representing an immutable operational and security audit entry."""

    id: int
    workspace_id: uuid.UUID
    actor_type: str
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str | None
    target_id: str | None
    request_id: str | None
    details: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
