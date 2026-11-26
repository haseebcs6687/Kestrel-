"""Pydantic schemas for workspace user management operations."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

RoleLiteral = Literal["admin", "viewer"]


class CreateUserRequest(BaseModel):
    """Payload for creating a new user within the caller's workspace."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=12, max_length=128)
    role: RoleLiteral


class UpdateUserRequest(BaseModel):
    """Payload for modifying user role and activation status."""

    model_config = ConfigDict(extra="forbid")

    role: RoleLiteral | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> Self:
        """Ensure that at least one update attribute is provided."""
        if self.role is None and self.is_active is None:
            raise ValueError("At least one field ('role' or 'is_active') must be provided")
        return self
