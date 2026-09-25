"""ShellQuest 后端入口。

职责：
1. 启动时校验课程数据（``validate_curriculum``）并幂等落库（``seed_curriculum``）；
2. 提供课程结构、作答判题、进度、技能树、打卡与认证接口。

课程内容全部来自 ``app/curriculum``，本文件不硬编码任何题目。
数据模型见 REQUIREMENTS.md §4.1.2。
"""

import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, selectinload

from .achievements import (
    ACHIEVEMENTS,
    GROUP_ORDER,
    Achievement,
    UserStats,
    collect_stats,
    progress_of,
    sync_achievements,
    unlocked_codes,
)
from .command_search import (
    PhrasingIndex,
    build_phrasing_index,
    keyword_search,
    suggest_commands,
)
from .command_seed import command_count, ensure_commands_seeded
from .curriculum import UNITS as CURRICULUM
from .database import Base, SessionLocal, engine
from .models import (
    CheckIn,
    Command,
    CommandTag,
    CourseUnit,
    Quest,
    QuestAttempt,
    QuestCommand,
    QuestCompletion,
    QuestOption,
    SkillProgress,
    User,
    UserAchievement,
    UserSession,
)
from .schemas import (
    AchievementGroup,
    AchievementItem,
    AchievementList,
    AchievementProgress,
    AchievementUnlock,
    AuthResponse,
    CheckInResponse,
    CheckInStatus,
    CommandCategoryCount,
    CommandDetail,
    CommandFacets,
    CommandLetterCount,
    CommandListItem,
    CommandPage,
    CommandSearchHit,
    CommandSearchResult,
    CommandTagCount,
    Leaderboard,
    LeaderboardEntry,
    QuestOptionPublic,
    QuestPublic,
    RegisterRequest,
    RelatedQuest,
    SkillNode,
    SkillTree,
    SkillZone,
    SubmitRequest,
    SubmitResponse,
    UnitSummary,
    UserProgress,
    UserSummary,
    compute_level,
    compute_level_title,
)
from .security import hash_password, verify_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("shellquest")

DAILY_CHECKIN_XP = 30
UNIT_COMPLETION_BONUS = 60
STREAK_LOOKBACK = 30

# 区域顺序：必须与 app/curriculum 的拼装顺序一致，否则技能树会错位。
ZONE_ORDER = ["文件工坊", "系统哨站", "网络前线", "Shell 作战室", "容器基地", "故障指挥中心"]

# 命令手册的分类取值域 = 课程 6 大区域 + 其他（见 REQUIREMENTS.md §4.4.4）
COMMAND_CATEGORY_ORDER = [*ZONE_ORDER, "其他"]

COMMAND_PAGE_SIZE_MAX = 100

# 命令手册的离线种子快照（由 scripts/import_commands.py --export 生成）。
# 运行期不联网：数据库为空时从这里灌入，详见 app/command_seed.py 的说明。
COMMAND_SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "commands_seed.json.gz"

VALID_KINDS = {"terminal", "fill", "choice", "judge"}
VALID_JUDGE_TYPES = {"contains_all", "contains_any", "regex", "equals", "option"}

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:8080",
    ).split(",")
    if origin.strip()
]

DB_STARTUP_RETRIES = int(os.getenv("DB_STARTUP_RETRIES", "30"))
DB_STARTUP_INTERVAL = float(os.getenv("DB_STARTUP_INTERVAL", "2"))


# --------------------------------------------------------------------------- #
# 判题引擎
# --------------------------------------------------------------------------- #

# 常见的提示符前缀，用户从终端复制命令时会带上。
_PROMPT_PREFIX = re.compile(r"^\s*(?:\$|#|>|PS\s*[^>]*>|\[[^\]]*\]\s*[$#>])\s*")

# 全角/弯引号与反引号统一成半角，避免「看起来一样但判错」。
_QUOTE_MAP = {
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\uff02": '"',
    "\uff07": "'",
    "`": "'",
}

_WHITESPACE = re.compile(r"\s+")


def normalize_answer(raw: str | None) -> str:
    """归一化用户输入：去提示符、统一引号、折叠空白、转小写。

    与 ``judge_payload`` 里的标准答案使用同一套归一化，保证两侧可比。
    """
    if not raw:
        return ""
    text = raw.strip()
    text = _PROMPT_PREFIX.sub("", text)
    for src, dst in _QUOTE_MAP.items():
        text = text.replace(src, dst)
    text = _WHITESPACE.sub(" ", text)
    return text.strip().lower()


def judge_answer(quest: Quest, answer: str | None, option_keys: list[str] | None) -> bool:
    """按 ``quest.judge_type`` 判定作答是否正确。"""
    judge_type = quest.judge_type
    payload = quest.judge_payload or {}

    if judge_type == "option":
        expected = {str(k).strip().upper() for k in payload.get("correct_keys", [])}
        picked = {str(k).strip().upper() for k in (option_keys or []) if str(k).strip()}
        return bool(expected) and picked == expected

    normalized = normalize_answer(answer)
    if not normalized:
        return False

    if judge_type == "contains_all":
        terms = [normalize_answer(t) for t in payload.get("terms", [])]
        terms = [t for t in terms if t]
        return bool(terms) and all(t in normalized for t in terms)

    if judge_type == "contains_any":
        terms = [normalize_answer(t) for t in payload.get("terms", [])]
        terms = [t for t in terms if t]
        return bool(terms) and any(t in normalized for t in terms)

    if judge_type == "equals":
        expected = normalize_answer(payload.get("value", ""))
        return bool(expected) and normalized == expected

    if judge_type == "regex":
        pattern = payload.get("pattern", "")
        if not pattern:
            return False
        try:
            return re.search(pattern, normalized, re.IGNORECASE) is not None
        except re.error as exc:  # pragma: no cover - 由 validate_curriculum 提前拦截
            logger.error("题目 %s 的正则无法编译：%s", quest.order, exc)
            return False

    logger.error("题目 %s 使用了未知判题器 %s", quest.order, judge_type)
    return False


def correct_option_keys(quest: Quest) -> list[str]:
    """返回该题的正确答案 key 列表（仅 option 题型非空）。"""
    payload = quest.judge_payload or {}
    return [str(k) for k in payload.get("correct_keys", [])]


# --------------------------------------------------------------------------- #
# 课程校验与落库
# --------------------------------------------------------------------------- #


def validate_curriculum() -> None:
    """启动期自检：数据写错就立刻失败，而不是等用户点进页面才发现。"""
    errors: list[str] = []

    if not CURRICULUM:
        raise RuntimeError("课程数据为空")

    expected_unit_order = 1
    expected_quest_order = 1
    seen_zones: list[str] = []

    for unit in CURRICULUM:
        if unit["order"] != expected_unit_order:
            errors.append(f"单元顺序不连续：期望 {expected_unit_order}，实际 {unit['order']}")
        expected_unit_order += 1

        zone = unit.get("zone", "")
        if zone not in ZONE_ORDER:
            errors.append(f"单元 {unit['order']} 的区域 `{zone}` 不在 ZONE_ORDER 中")
        elif zone not in seen_zones:
            seen_zones.append(zone)

        for field in ("title", "goal", "knowledge"):
            if not str(unit.get(field, "")).strip():
                errors.append(f"单元 {unit['order']} 缺少 {field}")

        quests = unit.get("quests", [])
        if not quests:
            errors.append(f"单元 {unit['order']} 没有任何题目")

        for quest in quests:
            # 题目的 order 由列表位置推导，种子数据里不显式声明。
            tag = f"单元 {unit['order']} 的第 {expected_quest_order} 题"
            expected_quest_order += 1

            kind = quest.get("kind")
            if kind not in VALID_KINDS:
                errors.append(f"{tag} 的题型 `{kind}` 非法")

            judge_type = quest.get("judge_type")
            if judge_type not in VALID_JUDGE_TYPES:
                errors.append(f"{tag} 的判题器 `{judge_type}` 非法")

            payload = quest.get("judge_payload") or {}
            options = quest.get("options", [])

            for field in ("title", "scenario", "prompt", "answer_display", "explanation"):
                if not str(quest.get(field, "")).strip():
                    errors.append(f"{tag} 缺少 {field}")

            if judge_type == "contains_all" or judge_type == "contains_any":
                if not payload.get("terms"):
                    errors.append(f"{tag} 使用 {judge_type} 但 judge_payload.terms 为空")
            elif judge_type == "equals":
                if not payload.get("value"):
                    errors.append(f"{tag} 使用 equals 但 judge_payload.value 为空")
            elif judge_type == "regex":
                pattern = payload.get("pattern")
                if not pattern:
                    errors.append(f"{tag} 使用 regex 但 judge_payload.pattern 为空")
                else:
                    try:
                        re.compile(pattern)
                    except re.error as exc:
                        errors.append(f"{tag} 的正则无法编译：{exc}")
            elif judge_type == "option":
                keys = [str(k) for k in payload.get("correct_keys", [])]
                if not keys:
                    errors.append(f"{tag} 使用 option 但 judge_payload.correct_keys 为空")
                option_keys = [str(o["key"]) for o in options]
                if len(options) < 2:
                    errors.append(f"{tag} 是选择题但选项少于 2 个")
                missing = [k for k in keys if k not in option_keys]
                if missing:
                    errors.append(f"{tag} 的 correct_keys {missing} 不在选项列表中")
                flagged = [str(o["key"]) for o in options if o.get("is_correct")]
                if sorted(flagged) != sorted(keys):
                    errors.append(
                        f"{tag} 的 correct_keys {keys} 与选项 is_correct 标记 {flagged} 不一致"
                    )

            if kind in {"choice", "judge"} and len(options) < 2:
                errors.append(f"{tag} 的题型是 {kind}，但选项少于 2 个")
            if kind in {"terminal", "fill"} and options:
                errors.append(f"{tag} 的题型是 {kind}，不应携带选项")

            if not quest.get("commands"):
                errors.append(f"{tag} 没有关联任何命令，命令查询模块无法双向跳转")

    if errors:
        detail = "\n  - ".join(errors)
        raise RuntimeError(f"课程数据校验失败，共 {len(errors)} 处问题：\n  - {detail}")

    logger.info("课程数据校验通过：%d 个单元 / %d 道题目", len(CURRICULUM), expected_quest_order - 1)


def _unit_matches(unit: CourseUnit, seed: dict) -> bool:
    return (
        unit.zone == seed["zone"]
        and unit.title == seed["title"]
        and unit.goal == seed["goal"]
        and unit.knowledge == seed["knowledge"]
    )


def _quest_matches(quest: Quest, seed: dict) -> bool:
    scalars = (
        quest.kind,
        quest.title,
        quest.scenario,
        quest.context,
        quest.prompt,
        quest.answer_display,
        quest.explanation,
        quest.pitfalls,
        quest.safer_alt,
        quest.judge_type,
        quest.difficulty,
        quest.xp_reward,
    )
    expected = (
        seed["kind"],
        seed["title"],
        seed["scenario"],
        seed.get("context", ""),
        seed["prompt"],
        seed["answer_display"],
        seed["explanation"],
        seed.get("pitfalls", ""),
        seed.get("safer_alt", ""),
        seed["judge_type"],
        seed.get("difficulty", 1),
        seed.get("xp_reward", 40),
    )
    if scalars != expected:
        return False
    if (quest.judge_payload or {}) != (seed.get("judge_payload") or {}):
        return False

    current_options = sorted((o.key, o.text, bool(o.is_correct)) for o in quest.options)
    seed_options = sorted(
        (str(o["key"]), o["text"], bool(o.get("is_correct"))) for o in seed.get("options", [])
    )
    if current_options != seed_options:
        return False

    current_commands = sorted(c.command_name for c in quest.commands)
    seed_commands = sorted(seed.get("commands", []))
    return current_commands == seed_commands


def seed_curriculum(db: Session) -> dict[str, int]:
    """幂等地把 ``curriculum`` 写入数据库。

    以 ``order`` 作为稳定主键做 UPSERT：内容没变就完全不动数据库，
    内容变了只重建变化的那道题的选项与命令关联，因此用户进度不会丢。
    """
    units_by_order = {u.order: u for u in db.scalars(select(CourseUnit))}
    quests_by_order = {q.order: q for q in db.scalars(select(Quest))}

    created_units = created_quests = updated_units = updated_quests = 0
    rebuilt: list[tuple[Quest, dict]] = []
    global_order = 0

    for unit_seed in CURRICULUM:
        unit = units_by_order.get(unit_seed["order"])
        if unit is None:
            unit = CourseUnit(order=unit_seed["order"])
            db.add(unit)
            created_units += 1
        elif not _unit_matches(unit, unit_seed):
            updated_units += 1
        unit.zone = unit_seed["zone"]
        unit.title = unit_seed["title"]
        unit.goal = unit_seed["goal"]
        unit.knowledge = unit_seed["knowledge"]
        db.flush()

        for quest_seed in unit_seed["quests"]:
            global_order += 1
            quest = quests_by_order.get(global_order)
            if quest is None:
                quest = Quest(order=global_order)
                db.add(quest)
                created_quests += 1
                needs_rebuild = True
            else:
                needs_rebuild = not _quest_matches(quest, quest_seed)
                if needs_rebuild:
                    updated_quests += 1

            quest.unit_id = unit.id
            quest.kind = quest_seed["kind"]
            quest.title = quest_seed["title"]
            quest.scenario = quest_seed["scenario"]
            quest.context = quest_seed.get("context", "")
            quest.prompt = quest_seed["prompt"]
            quest.answer_display = quest_seed["answer_display"]
            quest.explanation = quest_seed["explanation"]
            quest.pitfalls = quest_seed.get("pitfalls", "")
            quest.safer_alt = quest_seed.get("safer_alt", "")
            quest.judge_type = quest_seed["judge_type"]
            quest.judge_payload = dict(quest_seed["judge_payload"])
            quest.difficulty = quest_seed.get("difficulty", 1)
            quest.xp_reward = quest_seed.get("xp_reward", 40)

            if needs_rebuild:
                rebuilt.append((quest, quest_seed))

    db.flush()

    # 先删旧关联再插新关联，避免 (quest_id, key) 唯一约束冲突。
    for quest, _ in rebuilt:
        for option in list(quest.options):
            db.delete(option)
        for command in list(quest.commands):
            db.delete(command)
    db.flush()

    for quest, quest_seed in rebuilt:
        for option in quest_seed.get("options", []):
            db.add(
                QuestOption(
                    quest_id=quest.id,
                    key=str(option["key"]),
                    text=option["text"],
                    is_correct=bool(option.get("is_correct")),
                )
            )
        for name in quest_seed.get("commands", []):
            db.add(QuestCommand(quest_id=quest.id, command_name=name))
    db.flush()
    db.commit()

    result = {
        "created_units": created_units,
        "updated_units": updated_units,
        "created_quests": created_quests,
        "updated_quests": updated_quests,
    }
    if any(result.values()):
        logger.info(
            "课程同步完成：新增单元 %d / 更新单元 %d / 新增题目 %d / 更新题目 %d",
            created_units,
            updated_units,
            created_quests,
            updated_quests,
        )
    else:
        logger.info("课程内容与数据库一致，无需变更")
    return result


def wait_for_db_and_init() -> None:
    validate_curriculum()
    last_error: Exception | None = None
    for attempt in range(1, DB_STARTUP_RETRIES + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("数据库连接正常（第 %d 次尝试）", attempt)
            Base.metadata.create_all(bind=engine)
            with SessionLocal() as db:
                seed_curriculum(db)
                ensure_commands_seeded(db, COMMAND_SEED_PATH)
                logger.info("命令手册现有 %d 条记录", command_count(db))
                backfilled = backfill_achievements(db)
                if backfilled:
                    logger.info("为已有用户补发 %d 个成就", backfilled)
            return
        except OperationalError as exc:
            last_error = exc
            logger.warning("数据库未就绪，第 %d/%d 次尝试失败：%s", attempt, DB_STARTUP_RETRIES, exc)
            time.sleep(DB_STARTUP_INTERVAL)
    raise RuntimeError(f"数据库连接失败，已重试 {DB_STARTUP_RETRIES} 次：{last_error}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("ShellQuest API 启动中，正在初始化数据库...")
    logger.info("CORS_ORIGINS = %s", CORS_ORIGINS)
    wait_for_db_and_init()
    logger.info("初始化完成，服务就绪")
    yield


app = FastAPI(title="ShellQuest API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# 依赖
# --------------------------------------------------------------------------- #


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    x_session_token: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User:
    if not x_session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    session = db.scalar(select(UserSession).where(UserSession.token == x_session_token))
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


def get_optional_user(
    x_session_token: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User | None:
    """未登录也能浏览课程结构，因此这里不抛 401。"""
    if not x_session_token:
        return None
    session = db.scalar(select(UserSession).where(UserSession.token == x_session_token))
    if not session:
        return None
    return db.get(User, session.user_id)


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(UserSession(user_id=user.id, token=token))
    db.commit()
    return token


# --------------------------------------------------------------------------- #
# 课程装配
# --------------------------------------------------------------------------- #


def load_curriculum(db: Session) -> list[CourseUnit]:
    """一次性把单元、题目、选项、命令关联全部加载出来，避免 N+1 查询。"""
    return list(
        db.scalars(
            select(CourseUnit)
            .order_by(CourseUnit.order)
            .options(
                selectinload(CourseUnit.quests).selectinload(Quest.options),
                selectinload(CourseUnit.quests).selectinload(Quest.commands),
            )
        )
    )


def compute_unit_statuses(
    units: list[CourseUnit], completed_quest_ids: set[int]
) -> tuple[dict[int, str], int | None]:
    """单元状态：按 order 严格串行解锁。

    全部题目完成 → done；第一个未完成的单元 → current；其余 → locked。
    """
    status_map: dict[int, str] = {}
    current_unit_id: int | None = None
    for unit in units:
        if unit.quests and all(q.id in completed_quest_ids for q in unit.quests):
            status_map[unit.id] = "done"
        elif current_unit_id is None:
            status_map[unit.id] = "current"
            current_unit_id = unit.id
        else:
            status_map[unit.id] = "locked"
    return status_map, current_unit_id


def compute_quest_statuses(
    units: list[CourseUnit], completed_quest_ids: set[int], unit_status: dict[int, str]
) -> dict[int, str]:
    """题目状态：当前单元内的题都可作答，锁定单元内的题一律 locked。"""
    status_map: dict[int, str] = {}
    for unit in units:
        unlocked = unit_status.get(unit.id) == "current"
        for quest in unit.quests:
            if quest.id in completed_quest_ids:
                status_map[quest.id] = "done"
            else:
                status_map[quest.id] = "current" if unlocked else "locked"
    return status_map


def build_quest_public(
    quest: Quest, unit: CourseUnit, status_value: str | None
) -> QuestPublic:
    return QuestPublic(
        id=quest.id,
        order=quest.order,
        unit_id=unit.id,
        unit_order=unit.order,
        zone=unit.zone,
        kind=quest.kind,
        title=quest.title,
        scenario=quest.scenario,
        context=quest.context or "",
        prompt=quest.prompt or "",
        difficulty=quest.difficulty,
        xp_reward=quest.xp_reward,
        options=[QuestOptionPublic(key=o.key, text=o.text) for o in quest.options],
        commands=[c.command_name for c in quest.commands],
        status=status_value,
    )


def build_unit_summary(
    unit: CourseUnit,
    unit_status: dict[int, str] | None,
    quest_status: dict[int, str] | None,
) -> UnitSummary:
    quests = [
        build_quest_public(q, unit, (quest_status or {}).get(q.id))
        for q in sorted(unit.quests, key=lambda x: x.order)
    ]
    return UnitSummary(
        id=unit.id,
        order=unit.order,
        zone=unit.zone,
        title=unit.title,
        goal=unit.goal,
        knowledge=unit.knowledge,
        quest_count=len(quests),
        completed_quests=sum(1 for q in quests if q.status == "done"),
        xp_total=sum(q.xp_reward for q in quests),
        status=(unit_status or {}).get(unit.id),
        quests=quests,
    )


def completed_quest_ids(db: Session, user: User) -> set[int]:
    return set(
        db.scalars(select(QuestCompletion.quest_id).where(QuestCompletion.user_id == user.id))
    )


# --------------------------------------------------------------------------- #
# 技能树
# --------------------------------------------------------------------------- #


def grant_skill_if_unit_done(db: Session, user: User, unit: CourseUnit) -> bool:
    existing = db.scalar(
        select(SkillProgress).where(
            SkillProgress.user_id == user.id, SkillProgress.unit_id == unit.id
        )
    )
    if existing:
        return False
    zone_units = list(
        db.scalars(
            select(CourseUnit).where(CourseUnit.zone == unit.zone).order_by(CourseUnit.order)
        )
    )
    node_index = next((i for i, u in enumerate(zone_units) if u.id == unit.id), 0)
    db.add(
        SkillProgress(
            user_id=user.id,
            unit_id=unit.id,
            zone=unit.zone,
            node_index=node_index,
        )
    )
    return True


def build_skill_tree(db: Session, user: User) -> SkillTree:
    units = load_curriculum(db)
    unlocked = {
        s.unit_id: s
        for s in db.scalars(select(SkillProgress).where(SkillProgress.user_id == user.id))
    }

    by_zone: dict[str, list[CourseUnit]] = {}
    for unit in units:
        by_zone.setdefault(unit.zone, []).append(unit)

    # ZONE_ORDER 之外的区域（例如后续新增的「其他」）追加到末尾，避免内容凭空消失。
    ordered_zones = [z for z in ZONE_ORDER if z in by_zone]
    ordered_zones += [z for z in by_zone if z not in ZONE_ORDER]

    zones: list[SkillZone] = []
    total_nodes = total_unlocked = 0
    for zone_index, zone in enumerate(ordered_zones, start=1):
        zone_units = by_zone[zone]
        nodes: list[SkillNode] = []
        zone_unlocked = 0
        for index, unit in enumerate(zone_units):
            progress = unlocked.get(unit.id)
            if progress:
                zone_unlocked += 1
            nodes.append(
                SkillNode(
                    unit_id=unit.id,
                    index=index,
                    title=unit.title,
                    unlocked=progress is not None,
                    unlocked_at=progress.unlocked_at.isoformat()
                    if progress and progress.unlocked_at
                    else None,
                )
            )
        zones.append(
            SkillZone(
                zone=zone,
                zone_index=zone_index,
                total_nodes=len(zone_units),
                unlocked_nodes=zone_unlocked,
                unlocked_percent=round(zone_unlocked / len(zone_units) * 100, 1)
                if zone_units
                else 0.0,
                nodes=nodes,
            )
        )
        total_nodes += len(zone_units)
        total_unlocked += zone_unlocked

    return SkillTree(
        total_nodes=total_nodes,
        unlocked_nodes=total_unlocked,
        total_percent=round(total_unlocked / total_nodes * 100, 1) if total_nodes else 0.0,
        zones=zones,
    )


# --------------------------------------------------------------------------- #
# 基础接口
# --------------------------------------------------------------------------- #


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "shellquest-api"}


@app.get("/api/v1/units", response_model=list[UnitSummary])
def list_units(
    db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
) -> list[UnitSummary]:
    """课程结构。带 token 时附带每道题的作答状态。"""
    units = load_curriculum(db)
    if user is None:
        return [build_unit_summary(u, None, None) for u in units]
    done = completed_quest_ids(db, user)
    unit_status, _ = compute_unit_statuses(units, done)
    quest_status = compute_quest_statuses(units, done, unit_status)
    return [build_unit_summary(u, unit_status, quest_status) for u in units]


@app.get("/api/v1/user/progress", response_model=UserProgress)
def get_user_progress(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> UserProgress:
    units = load_curriculum(db)
    done = completed_quest_ids(db, user)
    unit_status, current_unit_id = compute_unit_statuses(units, done)
    quest_status = compute_quest_statuses(units, done, unit_status)
    summaries = [build_unit_summary(u, unit_status, quest_status) for u in units]

    total_quests = sum(s.quest_count for s in summaries)
    completed_quests = sum(s.completed_quests for s in summaries)
    completed_units = sum(1 for s in summaries if s.status == "done")
    return UserProgress(
        user=user,
        total_units=len(summaries),
        completed_units=completed_units,
        total_quests=total_quests,
        completed_quests=completed_quests,
        completion_percent=round(completed_quests / total_quests * 100, 1) if total_quests else 0.0,
        current_unit_id=current_unit_id,
        units=summaries,
    )


@app.get("/api/v1/user/skills", response_model=SkillTree)
def get_user_skills(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SkillTree:
    return build_skill_tree(db, user)


# --------------------------------------------------------------------------- #
# 认证
# --------------------------------------------------------------------------- #


@app.post("/api/v1/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已被占用")

    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(token=create_session(db, user), user=UserSummary.model_validate(user))


@app.post("/api/v1/auth/login", response_model=AuthResponse)
def login(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return AuthResponse(token=create_session(db, user), user=UserSummary.model_validate(user))


@app.get("/api/v1/auth/me", response_model=UserSummary)
def current_user(user: User = Depends(get_current_user)) -> User:
    return user


# --------------------------------------------------------------------------- #
# 打卡
# --------------------------------------------------------------------------- #


def build_checkin_status(db: Session, user: User, today: date | None = None) -> CheckInStatus:
    today = today or date.today()
    recent_dates = [today - timedelta(days=i) for i in range(STREAK_LOOKBACK)]
    rows = list(
        db.scalars(
            select(CheckIn.checkin_date).where(
                CheckIn.user_id == user.id, CheckIn.checkin_date.in_(recent_dates)
            )
        )
    )
    row_set = set(rows)
    consecutive: list[str] = []
    day = today
    while day in row_set:
        consecutive.append(day.isoformat())
        day -= timedelta(days=1)
    today_checked = today in row_set
    if not today_checked:
        yesterday = today - timedelta(days=1)
        if yesterday not in row_set and user.last_checkin_date != yesterday:
            if user.streak_days > 0:
                user.streak_days = 0
    return CheckInStatus(
        today_checked_in=today_checked,
        streak_days=user.streak_days,
        last_checkin_date=user.last_checkin_date.isoformat() if user.last_checkin_date else None,
        consecutive_dates=consecutive,
    )


def do_checkin(db: Session, user: User) -> tuple[bool, int, CheckInStatus]:
    today = date.today()
    existing = db.scalar(
        select(CheckIn).where(CheckIn.user_id == user.id, CheckIn.checkin_date == today)
    )
    if existing:
        return True, 0, build_checkin_status(db, user, today)
    yesterday = today - timedelta(days=1)
    if user.last_checkin_date == yesterday:
        user.streak_days += 1
    else:
        user.streak_days = 1
    user.last_checkin_date = today
    user.xp += DAILY_CHECKIN_XP
    db.add(CheckIn(user_id=user.id, checkin_date=today, xp_awarded=DAILY_CHECKIN_XP))
    db.commit()
    db.refresh(user)
    logger.info("用户 %s 打卡成功，连续 %d 天，+%d XP", user.username, user.streak_days, DAILY_CHECKIN_XP)
    return False, DAILY_CHECKIN_XP, build_checkin_status(db, user, today)


@app.get("/api/v1/checkin/status", response_model=CheckInStatus)
def get_checkin_status(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CheckInStatus:
    return build_checkin_status(db, user)


@app.post("/api/v1/checkin", response_model=CheckInResponse)
def perform_checkin(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CheckInResponse:
    already_checked, xp_awarded, checkin_status = do_checkin(db, user)
    # 打卡推进连续天数，可能刚好满足「连续打卡 N 天」类成就。
    unlocked = sync_achievements(db, user, load_curriculum(db))
    db.commit()
    db.refresh(user)
    return CheckInResponse(
        already_checked_in=already_checked,
        xp_awarded=xp_awarded,
        status=checkin_status,
        user=UserSummary.model_validate(user),
        achievements=[achievement_unlock(item) for item in unlocked],
    )


# --------------------------------------------------------------------------- #
# 作答
# --------------------------------------------------------------------------- #


@app.post("/api/v1/quests/{quest_id}/submit", response_model=SubmitResponse)
def submit_quest(
    quest_id: int,
    payload: SubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubmitResponse:
    quest = db.get(Quest, quest_id)
    if not quest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")

    units = load_curriculum(db)
    unit = next((u for u in units if u.id == quest.unit_id), None)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="题目未归属任何单元")

    done = completed_quest_ids(db, user)
    unit_status, _ = compute_unit_statuses(units, done)
    if unit_status.get(unit.id) == "locked":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该课程单元尚未解锁")

    correct = judge_answer(quest, payload.answer, payload.option_keys)
    already_completed = quest.id in done
    xp_awarded = 0
    unit_completed = False

    # 只在题目尚未完成时记录尝试：完成之后的重复提交属于练习，
    # 不应该追溯破坏此前的「无错通关」记录（见 models.QuestAttempt）。
    if not already_completed:
        db.add(QuestAttempt(user_id=user.id, quest_id=quest.id, correct=correct))

    if correct and not already_completed:
        xp_awarded += quest.xp_reward
        user.xp += quest.xp_reward
        db.add(QuestCompletion(user_id=user.id, quest_id=quest.id))
        db.flush()
        done.add(quest.id)

        if unit.quests and all(q.id in done for q in unit.quests):
            unit_completed = True
            xp_awarded += UNIT_COMPLETION_BONUS
            user.xp += UNIT_COMPLETION_BONUS
            grant_skill_if_unit_done(db, user, unit)
            logger.info("用户 %s 完成单元 %s，+%d XP", user.username, unit.title, UNIT_COMPLETION_BONUS)

        today = date.today()
        if not db.scalar(
            select(CheckIn).where(CheckIn.user_id == user.id, CheckIn.checkin_date == today)
        ):
            do_checkin(db, user)

    unlocked: list[Achievement] = []
    if not already_completed:
        # 成就判定放在写库之后：统计要读到本次已 flush 的完成记录、经验值与尝试记录。
        # 答错也要判一次 —— 它虽然不加经验，但可能刚好触发不了任何成就，成本很低；
        # 真正需要它的是「首次作答即正确」之外的规则（例如打卡触发的连续天数）。
        unlocked = sync_achievements(db, user, units)
        db.commit()
        db.refresh(user)

    return SubmitResponse(
        correct=correct,
        already_completed=already_completed,
        xp_awarded=xp_awarded,
        unit_completed=unit_completed,
        expected_display=quest.answer_display,
        correct_keys=correct_option_keys(quest),
        explanation=quest.explanation,
        pitfalls=quest.pitfalls or "",
        safer_alt=quest.safer_alt or "",
        user=UserSummary.model_validate(user),
        achievements=[achievement_unlock(item) for item in unlocked],
    )


# --------------------------------------------------------------------------- #
# 成就与排行榜（REQUIREMENTS.md §4.3 / §4.5）
# --------------------------------------------------------------------------- #


def achievement_unlock(item: Achievement) -> AchievementUnlock:
    return AchievementUnlock(
        code=item.code,
        title=item.title,
        description=item.description,
        icon=item.icon,
        group=item.group,
    )


def backfill_achievements(db: Session) -> int:
    """给「有进度但还没有成就记录」的老用户补一次判定。

    user_achievements 是后加的表：老用户的经验、完成记录都在，成就记录却是空的。
    只在「有用户、但一条成就记录都没有」时执行，之后启动不再付出代价。
    返回本次补发的成就总数。
    """
    if db.scalar(select(func.count()).select_from(UserAchievement)):
        return 0
    users = list(db.scalars(select(User)))
    if not users:
        return 0
    units = load_curriculum(db)
    total = 0
    for user in users:
        total += len(sync_achievements(db, user, units))
    if total:
        db.commit()
    return total


def achievement_item(
    item: Achievement, unlocked: dict[str, datetime | None], stats: UserStats
) -> AchievementItem:
    bounds = progress_of(item, stats)
    unlocked_at = unlocked.get(item.code)
    return AchievementItem(
        code=item.code,
        title=item.title,
        description=item.description,
        icon=item.icon,
        group=item.group,
        unlocked=item.code in unlocked,
        unlocked_at=unlocked_at.isoformat() if unlocked_at else None,
        progress=AchievementProgress(current=bounds[0], target=bounds[1]) if bounds else None,
    )


@app.get("/api/v1/achievements", response_model=AchievementList)
def list_achievements(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> AchievementList:
    """成就目录 + 当前用户的解锁状态与进度。

    只读，不做同步 —— 解锁发生在作答与打卡这两个写路径上（见 submit_quest / perform_checkin）。
    """
    units = load_curriculum(db)
    stats = collect_stats(db, user, units)
    unlocked = unlocked_codes(db, user)

    groups: list[AchievementGroup] = []
    total = total_unlocked = 0
    for group_name in GROUP_ORDER:
        items = [
            achievement_item(item, unlocked, stats)
            for item in ACHIEVEMENTS
            if item.group == group_name
        ]
        group_unlocked = sum(1 for item in items if item.unlocked)
        groups.append(
            AchievementGroup(
                group=group_name,
                total=len(items),
                unlocked=group_unlocked,
                items=items,
            )
        )
        total += len(items)
        total_unlocked += group_unlocked

    return AchievementList(
        total=total,
        unlocked=total_unlocked,
        unlocked_percent=round(total_unlocked / total * 100, 1) if total else 0.0,
        groups=groups,
    )


def _leaderboard_order() -> tuple:
    """排名顺序：经验降序 → 连续打卡降序 → id 升序（保证并列时结果稳定）。"""
    return (User.xp.desc(), User.streak_days.desc(), User.id.asc())


def _rank_of(db: Session, user: User) -> int:
    """在全量用户中的名次（不是「前 N 名里的位置」），与 _leaderboard_order 保持一致。"""
    ahead = db.scalar(
        select(func.count())
        .select_from(User)
        .where(
            or_(
                User.xp > user.xp,
                and_(User.xp == user.xp, User.streak_days > user.streak_days),
                and_(
                    User.xp == user.xp,
                    User.streak_days == user.streak_days,
                    User.id < user.id,
                ),
            )
        )
    )
    return int(ahead or 0) + 1


def _leaderboard_entry(user: User, rank: int, me_id: int | None) -> LeaderboardEntry:
    return LeaderboardEntry(
        rank=rank,
        username=user.username,
        level=compute_level(user.xp),
        level_title=compute_level_title(compute_level(user.xp)),
        xp=user.xp,
        streak_days=user.streak_days,
        is_me=me_id is not None and user.id == me_id,
    )


@app.get("/api/v1/leaderboard", response_model=Leaderboard)
def get_leaderboard(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> Leaderboard:
    """公开排行榜，无需登录。

    只暴露用户名 / 等级 / 经验 / 连续打卡，不含邮箱与答题详情（见 REQUIREMENTS.md §4.5）。
    登录用户额外拿到 `me`，这样即使自己排在 limit 之外也能看到名次。
    """
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    rows = list(db.scalars(select(User).order_by(*_leaderboard_order()).limit(limit)))
    me_id = user.id if user else None

    me_entry = None
    if user is not None:
        me_entry = _leaderboard_entry(user, _rank_of(db, user), me_id)

    return Leaderboard(
        total_users=total_users,
        entries=[_leaderboard_entry(row, index, me_id) for index, row in enumerate(rows, start=1)],
        me=me_entry,
    )


# --------------------------------------------------------------------------- #
# 命令查询（REQUIREMENTS.md §4.4）
# --------------------------------------------------------------------------- #

_phrasing_index: PhrasingIndex | None = None


def phrasing_index(db: Session) -> PhrasingIndex:
    """自然语言检索的倒排索引。课程内容在运行期不变，构建一次即可。"""
    global _phrasing_index
    if _phrasing_index is None:
        _phrasing_index = build_phrasing_index(db)
    return _phrasing_index


def command_list_item(row: Command) -> CommandListItem:
    return CommandListItem(
        name=row.name,
        summary=row.summary,
        category=row.category,
        tags=[tag.tag for tag in row.tags],
    )


def related_quests_map(db: Session, names: set[str]) -> dict[str, list[RelatedQuest]]:
    """批量取「命令 → 任务」关联，避免搜索结果逐条查库。"""
    result: dict[str, list[RelatedQuest]] = {name: [] for name in names}
    if not names:
        return result
    rows = db.execute(
        select(QuestCommand.command_name, CourseUnit, Quest)
        .join(Quest, Quest.id == QuestCommand.quest_id)
        .join(CourseUnit, CourseUnit.id == Quest.unit_id)
        .where(QuestCommand.command_name.in_(names))
        .order_by(CourseUnit.order, Quest.order)
    ).all()
    for command_name, unit, quest in rows:
        result.setdefault(command_name, []).append(
            RelatedQuest(
                unit_id=unit.id,
                unit_order=unit.order,
                zone=unit.zone,
                unit_title=unit.title,
                quest_id=quest.id,
                quest_order=quest.order,
                quest_title=quest.title,
                quest_kind=quest.kind,
            )
        )
    return result


def related_commands_for(db: Session, row: Command, limit: int = 8) -> list[CommandListItem]:
    """按共享标签数量推荐相关命令。"""
    tags = [tag.tag for tag in row.tags]
    if not tags:
        return []
    candidates = db.scalars(
        select(Command)
        .join(CommandTag, CommandTag.command_id == Command.id)
        .where(CommandTag.tag.in_(tags), Command.id != row.id)
        .options(selectinload(Command.tags))
    ).all()
    scored: list[tuple[int, Command]] = []
    for candidate in {item.id: item for item in candidates}.values():
        shared = len(set(tags) & {tag.tag for tag in candidate.tags})
        scored.append((shared, candidate))
    scored.sort(key=lambda item: (-item[0], item[1].name))
    return [command_list_item(item) for _, item in scored[:limit]]


def command_filters(category: str | None, tag: str | None, letter: str | None) -> list:
    conditions = []
    if category:
        conditions.append(Command.category == category)
    if tag:
        conditions.append(
            Command.id.in_(select(CommandTag.command_id).where(CommandTag.tag == tag))
        )
    if letter:
        first = func.lower(func.substr(Command.name, 1, 1))
        if letter == "#":
            conditions.append(first.notin_(list("abcdefghijklmnopqrstuvwxyz")))
        else:
            conditions.append(first == letter.lower())
    return conditions


@app.get("/api/v1/commands", response_model=CommandPage)
def list_commands(
    q: str | None = Query(default=None, description="关键词；为空时按筛选条件分页浏览"),
    category: str | None = None,
    tag: str | None = None,
    letter: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=40, ge=1, le=COMMAND_PAGE_SIZE_MAX),
    db: Session = Depends(get_db),
) -> CommandPage:
    conditions = command_filters(category, tag, letter)

    if q and q.strip():
        hits, total = keyword_search(
            db, q, limit=page_size, offset=(page - 1) * page_size, conditions=conditions
        )
        return CommandPage(
            total=total, page=page, page_size=page_size, items=[command_list_item(h.command) for h in hits]
        )

    total = db.scalar(select(func.count()).select_from(Command).where(*conditions)) or 0
    rows = db.scalars(
        select(Command)
        .where(*conditions)
        .order_by(Command.name)
        .limit(page_size)
        .offset((page - 1) * page_size)
        .options(selectinload(Command.tags))
    ).all()
    return CommandPage(total=total, page=page, page_size=page_size, items=[command_list_item(r) for r in rows])


@app.get("/api/v1/commands/facets", response_model=CommandFacets)
def command_facets(db: Session = Depends(get_db)) -> CommandFacets:
    total = db.scalar(select(func.count()).select_from(Command)) or 0

    category_rows = dict(
        db.execute(select(Command.category, func.count()).group_by(Command.category)).all()
    )
    ordered = [c for c in COMMAND_CATEGORY_ORDER if c in category_rows]
    ordered += [c for c in category_rows if c not in COMMAND_CATEGORY_ORDER]
    categories = [CommandCategoryCount(category=c, count=category_rows[c]) for c in ordered]

    tag_rows = db.execute(
        select(CommandTag.tag, func.count())
        .group_by(CommandTag.tag)
        .order_by(func.count().desc(), CommandTag.tag)
    ).all()
    tags = [CommandTagCount(tag=name, count=count) for name, count in tag_rows]

    letters: dict[str, int] = {}
    for name in db.scalars(select(Command.name)):
        head = name[0].upper()
        key = head if head.isascii() and head.isalpha() else "#"
        letters[key] = letters.get(key, 0) + 1
    letter_items = [
        CommandLetterCount(letter=key, count=letters[key])
        for key in ["#", *sorted(k for k in letters if k != "#")]
    ]

    return CommandFacets(total=total, categories=categories, tags=tags, letters=letter_items)


@app.get("/api/v1/commands/natural", response_model=CommandSearchResult)
def natural_search_commands(
    q: str = Query(..., min_length=1, description="问题描述，如「查看某个端口被谁占用」"),
    limit: int = Query(default=8, ge=1, le=30),
    db: Session = Depends(get_db),
) -> CommandSearchResult:
    """自然语言检索。

    词表从课程关卡声明派生（见 command_search.PhrasingIndex），因此结果天然带
    「关联任务」入口 —— 命中哪个关卡就说明该命令出现在哪一课。
    """
    index = phrasing_index(db)
    hits = index.search(q, limit=limit)

    ordered_names: list[str] = []
    quest_by_command: dict[str, list[RelatedQuest]] = {}
    best: dict[str, tuple[float, str]] = {}

    for hit in hits:
        phrasing = hit.phrasing
        related = RelatedQuest(
            unit_id=phrasing.unit_id,
            unit_order=phrasing.unit_order,
            zone=phrasing.zone,
            unit_title=phrasing.unit_title,
            quest_id=phrasing.quest_id,
            quest_order=phrasing.quest_order,
            quest_title=phrasing.quest_title,
            quest_kind=phrasing.quest_kind,
        )
        # hits 已按得分降序，因此每个命令第一次出现时对应的就是最相关的那个关卡。
        snippet = f"{phrasing.unit_title} · {phrasing.quest_title}：{phrasing.scenario}"
        for name in phrasing.commands:
            if name not in ordered_names:
                ordered_names.append(name)
                best[name] = (hit.score, snippet)
            quest_by_command.setdefault(name, []).append(related)

    rows = (
        {
            row.name: row
            for row in db.scalars(
                select(Command)
                .where(Command.name.in_(ordered_names))
                .options(selectinload(Command.tags))
            )
        }
        if ordered_names
        else {}
    )

    results: list[CommandSearchHit] = []
    for name in ordered_names:
        row = rows.get(name)
        if row is None:
            continue
        score, snippet = best[name]
        results.append(
            CommandSearchHit(
                command=command_list_item(row),
                score=score,
                matched_field="quest",
                snippet=snippet,
                related_quests=quest_by_command.get(name, []),
            )
        )

    # 兜底建议走关键词检索：课程只覆盖 21 个主题，像「怎么压缩目录」这类问题在课程里
    # 没有对应关卡，自然语言匹配会给出勉强的结果。此时关键词命中的命令才是用户想要的
    # （见 4.4.7「其余命令由关键词搜索兜底」）。整句问法不能直接 LIKE，故用 suggest_commands
    # 拆成词元逐个检索再合并。
    suggestions = [command.name for command in suggest_commands(db, q, limit=8)]

    return CommandSearchResult(
        mode="natural", query=q, total=len(results), hits=results, suggestions=suggestions
    )


@app.get("/api/v1/commands/{name}", response_model=CommandDetail)
def get_command(name: str, db: Session = Depends(get_db)) -> CommandDetail:
    row = db.scalar(
        select(Command).where(Command.name == name.lower()).options(selectinload(Command.tags))
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="命令不存在")

    return CommandDetail(
        name=row.name,
        summary=row.summary,
        category=row.category,
        tags=[tag.tag for tag in row.tags],
        syntax=row.syntax,
        sections=row.sections or [],
        options=row.options,
        examples=row.examples,
        body_markdown=row.body_markdown,
        source_url=row.source_url,
        license=row.license,
        source_version=row.source_version,
        related_commands=related_commands_for(db, row),
        related_quests=related_quests_map(db, {row.name}).get(row.name, []),
    )
