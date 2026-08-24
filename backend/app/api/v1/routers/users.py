"""Kullanıcı hesabı yönetimi router — Sprint 18.

Yetki: `kullanici:*` izni gerekir (kulup_yonetici + genel_sekreter).
Tüm mutasyonlar user_account_service üzerinden geçer.

Endpoint'ler:
  GET    /users                  — Listele (sayfalı)
  POST   /users                  — Oluştur
  GET    /users/{user_id}        — Detay
  PATCH  /users/{user_id}        — Güncelle
  DELETE /users/{user_id}        — Soft delete
  POST   /users/{user_id}/restore       — Restore
  POST   /users/{user_id}/reset-password — Parola sıfırla

Güvenlik:
  G4: Kullanıcı kendi hesabını değiştiremez (silme/pasifleştirme/reset).
  G3: Son kulup_yonetici silinemez/pasifleştirilemez (serviste).
  G8: Rol matrisi kısıtı (serviste).
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.schemas.user import (
    PasswordResetResponse,
    UserCreate,
    UserCreateResponse,
    UserListOut,
    UserOut,
    UserUpdate,
    UserListItem,
)
from app.services.user_account_service import (
    create_user,
    delete_user,
    reset_password,
    restore_user,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


# ── Yardımcı ─────────────────────────────────────────────────────────────────

async def _get_user_for_club(
    user_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
    *,
    include_deleted: bool = False,
) -> User:
    """Kulübe ait kullanıcıyı yükle; bulamazsa 404."""
    where = [User.id == user_id, User.club_id == club_id]
    if not include_deleted:
        where.append(User.is_deleted.is_(False))

    result = await db.execute(select(User).where(*where))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı.")
    return user


def _assert_not_self(current_user: TokenPayload, target_id: uuid.UUID, action: str) -> None:
    """G4: Kullanıcı kendi hesabında belirli işlemleri yapamaz."""
    if str(target_id) == current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Kendi hesabınızı {action} yapamazsınız.",
        )


# ── GET /users ────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=UserListOut,
    summary="Kullanıcı listesi (sayfalı)",
)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_deleted: Optional[bool] = Query(None, description="True=yalnızca silinmişler, False/None=yalnızca aktifler"),
    search: Optional[str] = Query(None, min_length=1),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("kullanici:read")),
) -> UserListOut:
    where = [User.club_id == club_id]
    # is_deleted=True → yalnızca silinmişler; None veya False → yalnızca silinmemişler
    if is_deleted is True:
        where.append(User.is_deleted.is_(True))
    else:
        where.append(User.is_deleted.is_(False))
    if role is not None:
        where.append(User.role == role)
    if is_active is not None:
        where.append(User.is_active.is_(is_active))
    if search:
        like = f"%{search}%"
        from sqlalchemy import or_
        where.append(or_(User.full_name.ilike(like), User.email.ilike(like)))

    total_result = await db.execute(select(func.count()).select_from(User).where(*where))
    total = total_result.scalar_one()

    users_result = await db.execute(
        select(User).where(*where).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    users = users_result.scalars().all()

    return UserListOut(
        items=[UserListItem.model_validate(u) for u in users],
        total=total,
        skip=skip,
        limit=limit,
    )


# ── POST /users ───────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni kullanıcı oluştur",
)
async def create_user_endpoint(
    body: UserCreate,
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("kullanici:write")),
) -> UserCreateResponse:
    user, temp_pw = await create_user(
        club_id=club_id,
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        person_id=body.person_id,
        assigner_role=current_user.role,
        assigner_user_id=uuid.UUID(current_user.sub),
        db=db,
    )
    await db.commit()
    await db.refresh(user)
    return UserCreateResponse(
        **UserOut.model_validate(user).model_dump(),
        temp_password=temp_pw,
    )


# ── GET /users/{user_id} ──────────────────────────────────────────────────────

@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Kullanıcı detayı",
)
async def get_user(
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("kullanici:read")),
) -> UserOut:
    # include_deleted=True: silinmiş kullanıcı detayı da görülebilsin (restore UI için)
    user = await _get_user_for_club(user_id, club_id, db, include_deleted=True)
    return UserOut.model_validate(user)


# ── PATCH /users/{user_id} ────────────────────────────────────────────────────

@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Kullanıcı güncelle (rol / aktiflik / isim)",
)
async def update_user_endpoint(
    user_id: uuid.UUID,
    body: UserUpdate,
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("kullanici:write")),
) -> UserOut:
    # G4: is_active=False veya rol değişimi için self-action yasak
    if body.is_active is False or body.role is not None:
        _assert_not_self(current_user, user_id, "güncelleyemezsiniz")

    target = await _get_user_for_club(user_id, club_id, db, include_deleted=True)
    if target.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Silinmiş kullanıcı güncellenemez. Önce geri yükleyin.",
        )
    await update_user(
        target_user=target,
        role=body.role,
        is_active=body.is_active,
        full_name=body.full_name,
        assigner_role=current_user.role,
        assigner_user_id=uuid.UUID(current_user.sub),
        db=db,
    )
    await db.commit()
    await db.refresh(target)
    return UserOut.model_validate(target)


# ── DELETE /users/{user_id} ───────────────────────────────────────────────────

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Kullanıcı soft-delete",
)
async def delete_user_endpoint(
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("kullanici:write")),
) -> None:
    _assert_not_self(current_user, user_id, "silemezsiniz")  # G4
    target = await _get_user_for_club(user_id, club_id, db)
    await delete_user(
        target_user=target,
        assigner_user_id=uuid.UUID(current_user.sub),
        db=db,
    )
    await db.commit()


# ── POST /users/{user_id}/restore ────────────────────────────────────────────

@router.post(
    "/{user_id}/restore",
    response_model=UserOut,
    summary="Silinmiş kullanıcıyı geri yükle",
)
async def restore_user_endpoint(
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("kullanici:write")),
) -> UserOut:
    target = await _get_user_for_club(user_id, club_id, db, include_deleted=True)
    await restore_user(
        target_user=target,
        assigner_user_id=uuid.UUID(current_user.sub),
        db=db,
    )
    await db.commit()
    await db.refresh(target)
    return UserOut.model_validate(target)


# ── POST /users/{user_id}/reset-password ─────────────────────────────────────

@router.post(
    "/{user_id}/reset-password",
    response_model=PasswordResetResponse,
    summary="Geçici parola üret (G5: yalnızca bu yanıtta görünür)",
)
async def reset_password_endpoint(
    user_id: uuid.UUID,
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("kullanici:write")),
) -> PasswordResetResponse:
    _assert_not_self(current_user, user_id, "parolasını sıfırlayamazsınız")  # G4
    target = await _get_user_for_club(user_id, club_id, db)
    temp_pw = await reset_password(
        target_user=target,
        assigner_user_id=uuid.UUID(current_user.sub),
        db=db,
    )
    await db.commit()
    return PasswordResetResponse(user_id=user_id, temp_password=temp_pw)
