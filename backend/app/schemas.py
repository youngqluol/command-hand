from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

XP_PER_LEVEL = 1000

LEVEL_TITLES = [
    (1, 3, "初级探索者"),
    (4, 6, "中级执令者"),
    (7, 9, "高级指挥官"),
    (10, 9999, "传奇 ShellMaster"),
]


def compute_level(xp: int) -> int:
    return max(1, xp // XP_PER_LEVEL + 1)


def compute_level_title(level: int) -> str:
    for start, end, title in LEVEL_TITLES:
        if start <= level <= end:
            return title
    return LEVEL_TITLES[-1][2]


def compute_level_progress(xp: int) -> tuple[int, int]:
    level = compute_level(xp)
    base = (level - 1) * XP_PER_LEVEL
    earned = xp - base
    return earned, XP_PER_LEVEL


QuestStatus = Literal["done", "current", "locked"]


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

    @computed_field
    @property
    def level(self) -> int:
        return compute_level(self.xp)

    @computed_field
    @property
    def level_title(self) -> str:
        return compute_level_title(self.level)

    @computed_field
    @property
    def level_xp_earned(self) -> int:
        return compute_level_progress(self.xp)[0]

    @computed_field
    @property
    def level_xp_total(self) -> int:
        return compute_level_progress(self.xp)[1]


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


class QuestStatusItem(BaseModel):
    id: int
    order: int
    zone: str
    title: str
    command_hint: str
    description: str
    scenario: str
    answer_hint: str
    status: QuestStatus
    xp_reward: int = 120


class UserProgress(BaseModel):
    user: UserSummary
    total_quests: int
    completed_quests: int
    completion_percent: float
    current_quest_id: int | None
    quests: list[QuestStatusItem]


class CheckInStatus(BaseModel):
    today_checked_in: bool
    streak_days: int
    last_checkin_date: str | None
    consecutive_dates: list[str]


class CheckInResponse(BaseModel):
    already_checked_in: bool
    xp_awarded: int
    status: CheckInStatus
    user: UserSummary


class SkillNode(BaseModel):
    zone: str
    index: int
    title: str
    quest_id: int
    unlocked: bool
    unlocked_at: str | None


class SkillZone(BaseModel):
    zone: str
    zone_index: int
    total_nodes: int
    unlocked_nodes: int
    unlocked_percent: float
    nodes: list[SkillNode]


class SkillTree(BaseModel):
    total_nodes: int
    unlocked_nodes: int
    total_percent: float
    zones: list[SkillZone]
