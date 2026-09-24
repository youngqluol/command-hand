"""Pydantic 出入参模型。字段与 REQUIREMENTS.md §4.1.2 的数据模型保持一致。"""

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
UnitStatus = Literal["done", "current", "locked"]
QuestKind = Literal["terminal", "fill", "choice", "judge"]
JudgeType = Literal["contains_all", "contains_any", "regex", "equals", "option"]


# --------------------------------------------------------------------------- #
# 认证与用户
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# 课程内容
# --------------------------------------------------------------------------- #


class QuestOptionPublic(BaseModel):
    """选项只暴露 key 与文本，正确答案由提交接口返回。"""

    key: str
    text: str


class QuestPublic(BaseModel):
    id: int
    order: int
    unit_id: int
    unit_order: int
    zone: str
    kind: QuestKind
    title: str
    scenario: str
    context: str
    prompt: str
    difficulty: int
    xp_reward: int
    options: list[QuestOptionPublic] = []
    commands: list[str] = []
    status: QuestStatus | None = None


class UnitSummary(BaseModel):
    id: int
    order: int
    zone: str
    title: str
    goal: str
    knowledge: str
    quest_count: int
    completed_quests: int
    xp_total: int
    status: UnitStatus | None = None
    quests: list[QuestPublic] = []


# --------------------------------------------------------------------------- #
# 作答与进度
# --------------------------------------------------------------------------- #


class SubmitRequest(BaseModel):
    """terminal / fill 题提交 answer；choice / judge 题提交 option_keys。"""

    answer: str | None = Field(default=None, max_length=2000)
    option_keys: list[str] | None = None


class SubmitResponse(BaseModel):
    correct: bool
    already_completed: bool
    xp_awarded: int
    unit_completed: bool
    expected_display: str
    correct_keys: list[str] = []
    explanation: str
    pitfalls: str
    safer_alt: str
    user: UserSummary


class UserProgress(BaseModel):
    user: UserSummary
    total_units: int
    completed_units: int
    total_quests: int
    completed_quests: int
    completion_percent: float
    current_unit_id: int | None
    units: list[UnitSummary]


# --------------------------------------------------------------------------- #
# 打卡
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# 技能树
# --------------------------------------------------------------------------- #


class SkillNode(BaseModel):
    unit_id: int
    index: int
    title: str
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
