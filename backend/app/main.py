import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import date, timedelta

import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import CheckIn, Quest, QuestCompletion, SkillProgress, User, UserSession
from .schemas import (
    AuthResponse,
    CheckInResponse,
    CheckInStatus,
    CompletionResponse,
    QuestStatusItem,
    QuestSummary,
    RegisterRequest,
    SkillNode,
    SkillTree,
    SkillZone,
    UserProgress,
    UserSummary,
)
from .security import hash_password, verify_password
from .seed_data import QUEST_SEEDS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("shellquest")

DAILY_CHECKIN_XP = 30
STREAK_LOOKBACK = 30

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


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(UserSession(user_id=user.id, token=token))
    db.commit()
    return token


def seed_quests(db: Session) -> None:
    existing_orders = set(db.scalars(select(Quest.order)))
    additions = [
        Quest(
            order=order,
            zone=zone,
            title=title,
            command_hint=command_hint,
            description=description,
            scenario=scenario,
            answer_hint=answer_hint,
        )
        for order, (zone, title, command_hint, description, scenario, answer_hint) in enumerate(QUEST_SEEDS, start=1)
        if order not in existing_orders
    ]
    if additions:
        db.add_all(additions)
        db.commit()
        logger.info("已插入 %d 条初始任务", len(additions))


def wait_for_db_and_init() -> None:
    last_error: Exception | None = None
    for attempt in range(1, DB_STARTUP_RETRIES + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("数据库连接正常（第 %d 次尝试）", attempt)
            Base.metadata.create_all(bind=engine)
            with SessionLocal() as db:
                seed_quests(db)
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


app = FastAPI(title="ShellQuest API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "shellquest-api"}


def list_all_quests(db: Session) -> list[Quest]:
    return list(db.scalars(select(Quest).order_by(Quest.order)))


def compute_zone_order(quests: list[Quest]) -> dict[str, list[int]]:
    zone_orders: dict[str, list[int]] = {}
    for q in quests:
        zone_orders.setdefault(q.zone, []).append(q.order)
    for orders in zone_orders.values():
        orders.sort()
    return zone_orders


def compute_quest_statuses(
    quests: list[Quest], completed_ids: set[int]
) -> tuple[dict[int, str], int | None]:
    zone_orders = compute_zone_order(quests)
    zone_completed_all: dict[str, bool] = {}
    for zone, orders in zone_orders.items():
        zone_completed_all[zone] = all(q.id in completed_ids for q in quests if q.zone == zone)

    ordered = sorted(quests, key=lambda q: q.order)
    prev_zone: str | None = None
    first_unset_done = False
    status_map: dict[int, str] = {}
    current_id: int | None = None

    for q in ordered:
        if q.id in completed_ids:
            status_map[q.id] = "done"
            prev_zone = q.zone
            continue
        zone_first = zone_orders[q.zone][0] == q.order
        if zone_first and prev_zone is not None and q.zone != prev_zone:
            if not zone_completed_all.get(prev_zone, False):
                status_map[q.id] = "locked"
                continue
        prev_order = q.order - 1
        prev_quest = next((x for x in ordered if x.order == prev_order), None)
        order_locked = prev_quest is not None and prev_quest.id not in completed_ids
        if order_locked:
            status_map[q.id] = "locked"
            continue
        if not first_unset_done:
            status_map[q.id] = "current"
            current_id = q.id
            first_unset_done = True
        else:
            status_map[q.id] = "locked"
        prev_zone = q.zone
    return status_map, current_id


def build_zone_skill_catalog(quests: list[Quest]) -> dict[str, list[Quest]]:
    catalog: dict[str, list[Quest]] = {}
    for q in sorted(quests, key=lambda x: x.order):
        catalog.setdefault(q.zone, []).append(q)
    return catalog


ZONE_ORDER = ["文件工坊", "系统哨站", "网络前线", "Shell 作战室", "容器基地", "故障指挥中心"]


def grant_skill(db: Session, user: User, quest: Quest) -> bool:
    quests = list_all_quests(db)
    catalog = build_zone_skill_catalog(quests)
    zone_quests = catalog.get(quest.zone, [])
    try:
        node_index = zone_quests.index(quest)
    except ValueError:
        return False
    existing = db.scalar(
        select(SkillProgress).where(
            SkillProgress.user_id == user.id,
            SkillProgress.zone == quest.zone,
            SkillProgress.node_index == node_index,
        )
    )
    if existing:
        return False
    db.add(
        SkillProgress(
            user_id=user.id,
            zone=quest.zone,
            node_index=node_index,
            quest_id=quest.id,
        )
    )
    return True


def build_skill_tree(db: Session, user: User) -> SkillTree:
    quests = list_all_quests(db)
    catalog = build_zone_skill_catalog(quests)
    unlocked = list(
        db.scalars(select(SkillProgress).where(SkillProgress.user_id == user.id))
    )
    unlocked_key = {(s.zone, s.node_index): s for s in unlocked}
    zones: list[SkillZone] = []
    total_nodes = 0
    total_unlocked = 0
    for z_idx, zone in enumerate(ZONE_ORDER, start=1):
        zone_quests = catalog.get(zone, [])
        nodes: list[SkillNode] = []
        zone_unlocked = 0
        for idx, q in enumerate(zone_quests):
            sp = unlocked_key.get((zone, idx))
            if sp:
                zone_unlocked += 1
            nodes.append(
                SkillNode(
                    zone=zone,
                    index=idx,
                    title=q.title,
                    quest_id=q.id,
                    unlocked=sp is not None,
                    unlocked_at=sp.unlocked_at.isoformat() if sp and sp.unlocked_at else None,
                )
            )
        zones.append(
            SkillZone(
                zone=zone,
                zone_index=z_idx,
                total_nodes=len(zone_quests),
                unlocked_nodes=zone_unlocked,
                unlocked_percent=round((zone_unlocked / len(zone_quests)) * 100, 1) if zone_quests else 0.0,
                nodes=nodes,
            )
        )
        total_nodes += len(zone_quests)
        total_unlocked += zone_unlocked
    return SkillTree(
        total_nodes=total_nodes,
        unlocked_nodes=total_unlocked,
        total_percent=round((total_unlocked / total_nodes) * 100, 1) if total_nodes else 0.0,
        zones=zones,
    )


@app.get("/api/v1/quests", response_model=list[QuestSummary])
def list_quests(db: Session = Depends(get_db)) -> list[Quest]:
    return list_all_quests(db)


@app.get("/api/v1/user/progress", response_model=UserProgress)
def get_user_progress(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserProgress:
    quests = list_all_quests(db)
    completed_ids = set(
        db.scalars(
            select(QuestCompletion.quest_id).where(QuestCompletion.user_id == user.id)
        )
    )
    status_map, current_id = compute_quest_statuses(quests, completed_ids)
    items: list[QuestStatusItem] = []
    for q in quests:
        items.append(
            QuestStatusItem(
                id=q.id,
                order=q.order,
                zone=q.zone,
                title=q.title,
                command_hint=q.command_hint,
                description=q.description,
                scenario=q.scenario,
                answer_hint=q.answer_hint,
                status=status_map.get(q.id, "locked"),
            )
        )
    completed = len(completed_ids)
    total = len(quests)
    return UserProgress(
        user=user,
        total_quests=total,
        completed_quests=completed,
        completion_percent=round((completed / total) * 100, 1) if total else 0.0,
        current_quest_id=current_id,
        quests=items,
    )


@app.post("/api/v1/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已被占用")

    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(token=create_session(db, user), user=user)


@app.post("/api/v1/auth/login", response_model=AuthResponse)
def login(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return AuthResponse(token=create_session(db, user), user=user)


def build_checkin_status(db: Session, user: User, today: date | None = None) -> CheckInStatus:
    today = today or date.today()
    recent_dates = [today - timedelta(days=i) for i in range(STREAK_LOOKBACK)]
    rows = list(
        db.scalars(
            select(CheckIn.checkin_date)
            .where(CheckIn.user_id == user.id, CheckIn.checkin_date.in_(recent_dates))
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
    status = build_checkin_status(db, user, today)
    if existing:
        return True, 0, status
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
    status = build_checkin_status(db, user, today)
    logger.info("用户 %s 打卡成功，连续 %d 天，+%d XP", user.username, user.streak_days, DAILY_CHECKIN_XP)
    return False, DAILY_CHECKIN_XP, status


@app.get("/api/v1/auth/me", response_model=UserSummary)
def current_user(user: User = Depends(get_current_user)) -> User:
    return user


@app.get("/api/v1/checkin/status", response_model=CheckInStatus)
def get_checkin_status(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CheckInStatus:
    return build_checkin_status(db, user)


@app.post("/api/v1/checkin", response_model=CheckInResponse)
def perform_checkin(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CheckInResponse:
    already_checked, xp_awarded, status = do_checkin(db, user)
    return CheckInResponse(
        already_checked_in=already_checked,
        xp_awarded=xp_awarded,
        status=status,
        user=user,
    )


@app.get("/api/v1/user/skills", response_model=SkillTree)
def get_user_skills(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SkillTree:
    return build_skill_tree(db, user)


@app.post("/api/v1/quests/{quest_id}/complete", response_model=CompletionResponse)
def complete_quest(quest_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CompletionResponse:
    quest = db.get(Quest, quest_id)
    if not quest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    completion = db.scalar(
        select(QuestCompletion).where(
            QuestCompletion.user_id == user.id, QuestCompletion.quest_id == quest_id
        )
    )
    if completion:
        return CompletionResponse(already_completed=True, xp_awarded=0, user=user)

    user.xp += 120
    db.add(QuestCompletion(user_id=user.id, quest_id=quest_id))
    grant_skill(db, user, quest)
    today = date.today()
    if not db.scalar(select(CheckIn).where(CheckIn.user_id == user.id, CheckIn.checkin_date == today)):
        do_checkin(db, user)
    db.commit()
    db.refresh(user)
    return CompletionResponse(already_completed=False, xp_awarded=120, user=user)
