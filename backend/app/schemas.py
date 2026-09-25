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
# `available` 只在「自由闯关」模式下出现：该单元可作答，但不是循序推荐的下一个。
UnitStatus = Literal["done", "current", "available", "locked"]
QuestKind = Literal["terminal", "fill", "choice", "judge"]
JudgeType = Literal["contains_all", "contains_any", "regex", "equals", "option"]
# 训练路径（REQUIREMENTS.md §3）：camp = 21 天训练营（串行解锁）；free = 自由闯关（任意选关）
TrainingMode = Literal["camp", "free"]


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
    training_mode: TrainingMode = "camp"

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
    achievements: list["AchievementUnlock"] = []


class UserProgress(BaseModel):
    user: UserSummary
    total_units: int
    completed_units: int
    total_quests: int
    completed_quests: int
    completion_percent: float
    current_unit_id: int | None
    units: list[UnitSummary]


class TrainingModeRequest(BaseModel):
    """切换训练路径（REQUIREMENTS.md §3）。"""

    mode: TrainingMode


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
    achievements: list["AchievementUnlock"] = []


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


# --------------------------------------------------------------------------- #
# 成就与排行榜（REQUIREMENTS.md §4.3 / §4.5）
# --------------------------------------------------------------------------- #


class AchievementUnlock(BaseModel):
    """作答 / 打卡响应里回传的**新解锁**成就，供前端弹提示。"""

    code: str
    title: str
    description: str
    icon: str
    group: str


class AchievementProgress(BaseModel):
    current: int
    target: int


class AchievementItem(BaseModel):
    code: str
    title: str
    description: str
    icon: str
    group: str
    unlocked: bool
    unlocked_at: str | None = None
    progress: AchievementProgress | None = None


class AchievementGroup(BaseModel):
    group: str
    total: int
    unlocked: int
    items: list[AchievementItem]


class AchievementList(BaseModel):
    total: int
    unlocked: int
    unlocked_percent: float
    groups: list[AchievementGroup]


class LeaderboardEntry(BaseModel):
    """排行榜条目。只暴露用户名 / 等级 / 经验 / 连续打卡，不含邮箱与答题详情（见 §4.5）。"""

    rank: int
    username: str
    level: int
    level_title: str
    xp: int
    streak_days: int
    is_me: bool = False


class Leaderboard(BaseModel):
    total_users: int
    entries: list[LeaderboardEntry]
    me: LeaderboardEntry | None = None


# --------------------------------------------------------------------------- #
# 命令查询（REQUIREMENTS.md §4.4）
# --------------------------------------------------------------------------- #


class CommandListItem(BaseModel):
    name: str
    summary: str
    category: str
    tags: list[str] = []


class CommandSection(BaseModel):
    """上游 Markdown 的一个章节。role 用于前端按 4.4.5 的顺序排版，extra 表示未识别的标题。"""

    title: str
    role: str
    level: int
    content: str

    model_config = {"extra": "ignore"}


class CommandOption(BaseModel):
    flag: str
    desc: str = ""
    group: str | None = None

    model_config = {"extra": "ignore"}


class CommandExample(BaseModel):
    description: str = ""
    code: str

    model_config = {"extra": "ignore"}


class RelatedQuest(BaseModel):
    """命令 → 任务的关联，数据来自 quest_commands（由课程关卡声明的 commands 生成）。"""

    unit_id: int
    unit_order: int
    zone: str
    unit_title: str
    quest_id: int
    quest_order: int
    quest_title: str
    quest_kind: QuestKind


class CommandDetail(CommandListItem):
    syntax: str | None = None
    sections: list[CommandSection] = []
    options: list[CommandOption] | None = None
    examples: list[CommandExample] | None = None
    body_markdown: str
    source_url: str
    license: str
    source_version: str
    related_commands: list[CommandListItem] = []
    related_quests: list[RelatedQuest] = []


class CommandPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CommandListItem]


class CommandCategoryCount(BaseModel):
    category: str
    count: int


class CommandTagCount(BaseModel):
    tag: str
    count: int


class CommandLetterCount(BaseModel):
    letter: str
    count: int


class CommandFacets(BaseModel):
    total: int
    categories: list[CommandCategoryCount]
    tags: list[CommandTagCount]
    letters: list[CommandLetterCount]


class CommandSearchHit(BaseModel):
    command: CommandListItem
    score: float
    matched_field: str
    snippet: str
    related_quests: list[RelatedQuest] = []


class CommandSearchResult(BaseModel):
    mode: Literal["keyword", "natural"]
    query: str
    total: int
    hits: list[CommandSearchHit]
    suggestions: list[str] = []


# SubmitResponse / CheckInResponse 引用了下方才定义的 AchievementUnlock（前向引用），
# 必须在文件末尾重建一次，否则 Pydantic 在首次使用时才报解析失败。
SubmitResponse.model_rebuild()
CheckInResponse.model_rebuild()
