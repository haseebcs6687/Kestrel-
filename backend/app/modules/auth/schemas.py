"""Pydantic schemas for authentication, registration, tokens, and user profiles."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload for user registration and workspace creation.

    Enforces mass-assignment protection with extra='forbid' to prevent unauthorized
    injection of roles, workspace IDs, or activation flags.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=12, max_length=128)
    workspace_name: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    """Payload for user authentication with email and password."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=320)
    password: str = Field(max_length=128)


class TokenResponse(BaseModel):
    """Bearer access token response format."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class UserRead(BaseModel):
    """Public read model for user accounts. Password hashes are never exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    workspace_id: uuid.UUID
    created_at: datetime
    last_login_at: datetime | None = None


class WorkspaceRead(BaseModel):
    """Public read model for workspace metadata associated with a user."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class MeResponse(BaseModel):
    """Detailed user profile response with associated workspace information."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    workspace_id: uuid.UUID
    created_at: datetime
    last_login_at: datetime | None = None
    workspace: WorkspaceRead
