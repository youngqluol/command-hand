from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_checkin_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 训练路径：`camp` = 21 天训练营（单元严格串行解锁）；`free` = 自由闯关（任意选关）。
    # 取值域见 schemas.TrainingMode，判定见 main.compute_unit_statuses()。
    training_mode: Mapped[str] = mapped_column(String(16), default="camp")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CourseUnit(Base):
    """课程单元：21 天课程中的一天，是技能节点与解锁的基本单位。"""

    __tablename__ = "course_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order: Mapped[int] = mapped_column(Integer, unique=True)
    zone: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(128))
    goal: Mapped[str] = mapped_column(String(256))
    knowledge: Mapped[str] = mapped_column(Text)

    quests: Mapped[list["Quest"]] = relationship(
        back_populates="unit",
        order_by="Quest.order",
        cascade="all, delete-orphan",
    )


class Quest(Base):
    """一道练习题。kind 决定交互形式，judge_type + judge_payload 决定判题。"""

    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("course_units.id"), index=True)
    order: Mapped[int] = mapped_column(Integer, unique=True)
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(128))
    scenario: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text, default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    answer_display: Mapped[str] = mapped_column(String(512))
    explanation: Mapped[str] = mapped_column(Text)
    pitfalls: Mapped[str] = mapped_column(Text, default="")
    safer_alt: Mapped[str] = mapped_column(Text, default="")
    judge_type: Mapped[str] = mapped_column(String(32))
    judge_payload: Mapped[dict] = mapped_column(JSON)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    xp_reward: Mapped[int] = mapped_column(Integer, default=40)

    unit: Mapped[CourseUnit] = relationship(back_populates="quests")
    options: Mapped[list["QuestOption"]] = relationship(
        back_populates="quest",
        order_by="QuestOption.key",
        cascade="all, delete-orphan",
    )
    commands: Mapped[list["QuestCommand"]] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
    )


class QuestOption(Base):
    """choice / judge 题型的选项。"""

    __tablename__ = "quest_options"
    __table_args__ = (UniqueConstraint("quest_id", "key", name="uq_quest_option_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"), index=True)
    key: Mapped[str] = mapped_column(String(4))
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    quest: Mapped[Quest] = relationship(back_populates="options")


class QuestCommand(Base):
    """题目与命令的关联，供命令查询模块双向跳转使用。"""

    __tablename__ = "quest_commands"
    __table_args__ = (UniqueConstraint("quest_id", "command_name", name="uq_quest_command"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"), index=True)
    command_name: Mapped[str] = mapped_column(String(64), index=True)

    quest: Mapped[Quest] = relationship(back_populates="commands")


class QuestCompletion(Base):
    __tablename__ = "quest_completions"
    __table_args__ = (UniqueConstraint("user_id", "quest_id", name="uq_user_quest_completion"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class QuestAttempt(Base):
    """每次作答的对错记录，供「无错通关」类成就判定使用。

    只在题目**尚未完成**时写入：完成之后的重复提交属于练习，不应追溯破坏此前的无错记录。
    因此「这道题有没有答错过」= 该用户在该题上是否存在 correct=False 的记录。
    """

    __tablename__ = "quest_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"), index=True)
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CheckIn(Base):
    __tablename__ = "check_ins"
    __table_args__ = (UniqueConstraint("user_id", "checkin_date", name="uq_user_checkin_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    checkin_date: Mapped[date] = mapped_column(Date, index=True)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SkillProgress(Base):
    """技能节点点亮记录，绑定课程单元。

    node_index 是单元在其所属区域内的下标（对齐 COURSE_DESIGN.md 的主题地图）。
    """

    __tablename__ = "skill_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "unit_id", name="uq_user_skill_unit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("course_units.id"), index=True)
    zone: Mapped[str] = mapped_column(String(64), index=True)
    node_index: Mapped[int] = mapped_column(Integer)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserAchievement(Base):
    """已解锁的成就。

    code 对应 app/achievements/catalog.py 里的定义，**一旦发布就不要改**：它是持久化标识，
    改名会让用户的历史解锁记录失联（见 AGENTS.md §4.9）。

    成就只增不减，所以没有「撤销」路径；重复触发由 (user_id, code) 唯一约束挡住。
    """

    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_user_achievement"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(48), index=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Command(Base):
    """命令手册条目。

    内容由 scripts/import_commands.py 从 jaywcjlove/linux-command（MIT）导入。
    body_markdown 是原文全文，永远保留；syntax / options / examples 是尽力提取的结构化字段，
    提取失败时为 NULL，前端降级为渲染 sections 中的原文段落。
    """

    __tablename__ = "commands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    summary: Mapped[str] = mapped_column(String(512))
    body_markdown: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), index=True)
    syntax: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections: Mapped[list] = mapped_column(JSON, default=list)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    examples: Mapped[list | None] = mapped_column(JSON, nullable=True)
    search_text: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(512))
    license: Mapped[str] = mapped_column(String(16), default="MIT")
    source_version: Mapped[str] = mapped_column(String(32), default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    tags: Mapped[list["CommandTag"]] = relationship(
        back_populates="command",
        order_by="CommandTag.tag",
        cascade="all, delete-orphan",
    )


class CommandTag(Base):
    """命令的功能标签，用于多标签组合筛选。"""

    __tablename__ = "command_tags"
    __table_args__ = (UniqueConstraint("command_id", "tag", name="uq_command_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    command_id: Mapped[int] = mapped_column(ForeignKey("commands.id"), index=True)
    tag: Mapped[str] = mapped_column(String(64), index=True)

    command: Mapped[Command] = relationship(back_populates="tags")
