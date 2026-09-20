from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_checkin_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone: Mapped[str] = mapped_column(String(64))
    order: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(128))
    command_hint: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    scenario: Mapped[str] = mapped_column(Text)
    answer_hint: Mapped[str] = mapped_column(String(256))


class QuestCompletion(Base):
    __tablename__ = "quest_completions"
    __table_args__ = (UniqueConstraint("user_id", "quest_id", name="uq_user_quest_completion"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


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
    __tablename__ = "skill_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "zone", "node_index", name="uq_user_skill_zone_node"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    zone: Mapped[str] = mapped_column(String(64), index=True)
    node_index: Mapped[int] = mapped_column(Integer)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"))
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
