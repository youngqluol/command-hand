from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)


class UserSummary(BaseModel):
    id: int
    username: str
    xp: int
    streak_days: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    token: str
    user: UserSummary


class CompletionResponse(BaseModel):
    already_completed: bool
    xp_awarded: int
    user: UserSummary


class QuestSummary(BaseModel):
    id: int
    zone: str
    order: int
    title: str
    command_hint: str
    description: str

    model_config = {"from_attributes": True}
