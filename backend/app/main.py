"""MYK Platform V2 — FastAPI uygulama giriş noktası."""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routers import health, auth, persons, dashboard, avatar, memberships, public
from app.api.v1.routers.academy import router as academy_router
from app.api.v1.routers.training import router as training_router
from app.api.v1.routers.payments import router as payments_router
from app.api.v1.routers.equipment import router as equipment_router
from app.api.v1.routers.athletes import router as athletes_router
from app.api.v1.routers.settings import router as settings_router
from app.api.v1.routers.notifications import router as notifications_router
from app.config import get_settings
from app.core.scheduler import setup_scheduler
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.schemas.auth import TokenPayload, UserResponse

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("MYK Platform V2 başlatılıyor (env=%s)", settings.myk_env)
    sched = setup_scheduler()
    sched.start()
    logger.info("APScheduler başlatıldı")
    yield
    sched.shutdown(wait=False)
    logger.info("MYK Platform V2 kapatılıyor")


app = FastAPI(
    title="MYK Platform V2",
    version="2.0.0",
    description="Mersin Yelken Kulübü Dijital Yönetim Sistemi",
    docs_url="/api/docs" if settings.myk_env != "production" else None,
    redoc_url="/api/redoc" if settings.myk_env != "production" else None,
    openapi_url="/api/openapi.json" if settings.myk_env != "production" else None,
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
_origins = (
    ["*"]
    if settings.myk_env == "development"
    else [f"https://{settings.allowed_host}"] if hasattr(settings, "allowed_host") else []
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("İşlenmemiş hata: %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Sunucu hatası. Lütfen tekrar deneyin."},
    )


# ─── Routers ──────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(persons.router, prefix=API_PREFIX)
app.include_router(avatar.router, prefix=API_PREFIX)
app.include_router(memberships.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(public.router, prefix=API_PREFIX)
app.include_router(academy_router, prefix=f"{API_PREFIX}/academy", tags=["academy"])
app.include_router(training_router, prefix=API_PREFIX)
app.include_router(payments_router, prefix=API_PREFIX)
app.include_router(equipment_router, prefix=API_PREFIX)
app.include_router(athletes_router, prefix=API_PREFIX)
app.include_router(settings_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=API_PREFIX)


# ─── /me endpoint — inject correct dependency ─────────────────────────────────
@app.get(f"{API_PREFIX}/auth/me", response_model=UserResponse, tags=["auth"])
async def get_me(
    current_user: TokenPayload = Depends(get_current_user),
    db=Depends(get_db),
) -> UserResponse:
    from sqlalchemy import select
    from app.core.tenant import assert_same_club
    from app.models.person import Person
    from app.models.user import User
    import uuid

    result = await db.execute(
        select(User).where(
            User.id == uuid.UUID(current_user.sub),
            User.is_deleted.is_(False),
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı.")
    assert_same_club(user.club_id, uuid.UUID(current_user.club_id))

    # must_change_password: User modelinde değil, bağlı Person'da tutulur.
    must_change_password = False
    if user.person_id is not None:
        person_result = await db.execute(
            select(Person).where(Person.id == user.person_id)
        )
        person = person_result.scalar_one_or_none()
        if person is not None:
            must_change_password = person.must_change_password

    base = UserResponse.model_validate(user)
    return base.model_copy(update={"must_change_password": must_change_password})


# ─── Root ─────────────────────────────────────────────────────────────────────
@app.get("/")
async def root() -> dict:
    return {"service": "myk-platform-v2", "status": "running"}
