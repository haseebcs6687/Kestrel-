"""Audit log Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    """Schema representing an immutable operational and security audit entry."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_type: str
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    details: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
