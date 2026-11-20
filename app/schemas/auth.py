import uuid
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.core.security import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.schemas.base import CamelModel


class LoginIn(CamelModel):
    email: str = Field(min_length=3, max_length=254)
    # No min length on login: a short password is simply wrong, not a validation error
    # (keeps the response generic). Max length caps the Argon2 work per request.
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class RefreshIn(CamelModel):
    refresh_token: str = Field(min_length=1, max_length=256)


class LogoutIn(CamelModel):
    refresh_token: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(CamelModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class TokenPairOut(CamelModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds.")


class UserOut(CamelModel):
    model_config = ConfigDict(from_attributes=True)  # build directly from the ORM object

    id: uuid.UUID
    email: str
    created_at: datetime
    last_login_at: datetime | None
