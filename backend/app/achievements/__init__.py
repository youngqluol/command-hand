"""成就判定引擎。

设计取舍：**每次作答 / 打卡后全量重算**用户的统计，再把新满足的成就写进 ``user_achievements``。

为什么不做增量打点（「这次提交是否刚好触发了某条规则」）：成就只有二十几条，统计量
（经验、已完成单元数、无错单元数）都能用几条聚合查询一次拿到。全量重算的代码路径只有一条，
不会出现「某个入口忘了上报导致成就永远不亮」这类问题。规模变大后再说缓存。

幂等性：判定只依赖 ``user_achievements`` 里已有的 code，重复调用不会重复解锁
（表上还有 ``(user_id, code)`` 唯一约束兜底）。成就**只增不减** —— 连续打卡断掉后
``streak_days`` 会归零，但已经拿到的徽章不会收回。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CourseUnit, QuestAttempt, QuestCompletion, User, UserAchievement
from ..schemas import compute_level
from .catalog import ACHIEVEMENTS, GROUP_ORDER, Achievement

__all__ = [
    "ACHIEVEMENTS",
    "GROUP_ORDER",
    "Achievement",
    "UserStats",
    "collect_stats",
    "is_satisfied",
    "progress_of",
    "unlocked_codes",
    "sync_achievements",
]


@dataclass(frozen=True)
class UserStats:
    """判定所需的全部用户统计量。一次算好，供所有规则复用。"""

    xp: int
    level: int
    streak_days: int
    units_cleared: int
    perfect_units: int
    zone_totals: dict[str, int] = field(default_factory=dict)
    zone_cleared: dict[str, int] = field(default_factory=dict)

    @property
    def zones_cleared(self) -> int:
        """完全通关的区域数（区域内全部单元都已完成）。"""
        return sum(1 for zone, total in self.zone_totals.items() if total and self.zone_cleared.get(zone, 0) >= total)


def collect_stats(db: Session, user: User, units: list[CourseUnit]) -> UserStats:
    """汇总判定所需的统计量。``units`` 需已预加载 ``quests``（见 ``load_curriculum``）。"""
    done = set(
        db.scalars(select(QuestCompletion.quest_id).where(QuestCompletion.user_id == user.id))
    )
    # 「答错过」= 该题存在 correct=False 的记录。quest_attempts 只在题目未完成时写入，
    # 所以完成后的练习提交不会污染这个集合。
    wrong = set(
        db.scalars(
            select(QuestAttempt.quest_id).where(
                QuestAttempt.user_id == user.id, QuestAttempt.correct.is_(False)
            )
        )
    )

    zone_totals: dict[str, int] = {}
    zone_cleared: dict[str, int] = {}
    units_cleared = 0
    perfect_units = 0

    for unit in units:
        if not unit.quests:
            continue
        zone_totals[unit.zone] = zone_totals.get(unit.zone, 0) + 1
        finished = all(quest.id in done for quest in unit.quests)
        if not finished:
            continue
        units_cleared += 1
        zone_cleared[unit.zone] = zone_cleared.get(unit.zone, 0) + 1
        if not any(quest.id in wrong for quest in unit.quests):
            perfect_units += 1

    return UserStats(
        xp=user.xp,
        level=compute_level(user.xp),
        streak_days=user.streak_days,
        units_cleared=units_cleared,
        perfect_units=perfect_units,
        zone_totals=zone_totals,
        zone_cleared=zone_cleared,
    )


def is_satisfied(achievement: Achievement, stats: UserStats) -> bool:
    rule, value = achievement.rule, achievement.value
    if rule == "streak":
        return stats.streak_days >= int(value)
    if rule == "units_cleared":
        return stats.units_cleared >= int(value)
    if rule == "zones_cleared":
        return stats.zones_cleared >= int(value)
    if rule == "perfect_units":
        return stats.perfect_units >= int(value)
    if rule == "xp":
        return stats.xp >= int(value)
    if rule == "level":
        return stats.level >= int(value)
    if rule == "zone_clear":
        zone = str(value)
        total = stats.zone_totals.get(zone, 0)
        return total > 0 and stats.zone_cleared.get(zone, 0) >= total
    return False


def progress_of(achievement: Achievement, stats: UserStats) -> tuple[int, int] | None:
    """给前端画进度条用的 (当前值, 目标值)；无法量化的规则返回 None。"""
    rule, value = achievement.rule, achievement.value
    if rule == "zone_clear":
        zone = str(value)
        total = stats.zone_totals.get(zone, 0)
        if not total:
            return None
        return min(stats.zone_cleared.get(zone, 0), total), total
    if rule == "streak":
        target = int(value)
        return min(stats.streak_days, target), target
    if rule == "units_cleared":
        target = int(value)
        return min(stats.units_cleared, target), target
    if rule == "zones_cleared":
        target = int(value)
        return min(stats.zones_cleared, target), target
    if rule == "perfect_units":
        target = int(value)
        return min(stats.perfect_units, target), target
    if rule == "xp":
        target = int(value)
        return min(stats.xp, target), target
    if rule == "level":
        target = int(value)
        return min(stats.level, target), target
    return None


def unlocked_codes(db: Session, user: User) -> dict[str, datetime | None]:
    return {
        row.code: row.unlocked_at
        for row in db.scalars(
            select(UserAchievement).where(UserAchievement.user_id == user.id)
        )
    }


def sync_achievements(db: Session, user: User, units: list[CourseUnit]) -> list[Achievement]:
    """解锁所有已满足但尚未记录的成就，按目录顺序返回**本次新解锁**的那些。

    调用方负责 commit —— 这里只 ``flush``，好让新成就与本次作答处在同一个事务里。
    """
    already = unlocked_codes(db, user)
    stats = collect_stats(db, user, units)
    newly: list[Achievement] = []
    for achievement in ACHIEVEMENTS:
        if achievement.code in already or not is_satisfied(achievement, stats):
            continue
        db.add(UserAchievement(user_id=user.id, code=achievement.code))
        newly.append(achievement)
    if newly:
        db.flush()
    return newly
