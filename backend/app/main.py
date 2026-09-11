from contextlib import asynccontextmanager

import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import Quest, QuestCompletion, User, UserSession
from .schemas import AuthResponse, CompletionResponse, QuestSummary, RegisterRequest, UserSummary
from .security import hash_password, verify_password
from .seed_data import QUEST_SEEDS

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


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_quests(db)
    yield


app = FastAPI(title="ShellQuest API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "shellquest-api"}


@app.get("/api/v1/quests", response_model=list[QuestSummary])
def list_quests(db: Session = Depends(get_db)) -> list[Quest]:
    return list(db.scalars(select(Quest).order_by(Quest.order)))


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


@app.get("/api/v1/auth/me", response_model=UserSummary)
def current_user(user: User = Depends(get_current_user)) -> User:
    return user


@app.post("/api/v1/quests/{quest_id}/complete", response_model=CompletionResponse)
def complete_quest(quest_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CompletionResponse:
    if not db.get(Quest, quest_id):
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
    db.commit()
    db.refresh(user)
    return CompletionResponse(already_completed=False, xp_awarded=120, user=user)
