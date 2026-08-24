"""Kullanıcı hesabı yönetimi servisi — Sprint 18.

Tüm kullanıcı oluşturma/güncelleme/silme işlemleri buradan geçer.
Hem `users` router hem de `membership_approval` bu servisi kullanır.

Güvenlik kuralları:
  G1: Rol/pasiflik/reset/silme → tüm aktif refresh token'lar revoke edilir.
  G3: Son aktif kulup_yonetici silinemez/pasifleştirilemez.
  G4: Kullanıcı kendi hesabını pasifleştiremez/silemez.
  G5: Geçici parola yalnızca oluşturma/reset yanıtında bir kez döner; loglanmaz.
  G7: Her mutasyon audit_logs'a yazılır.
  G8: Rol yükseltme ASSIGNABLE_ROLES_BY_ROLE matrisine göre kısıtlanır.
  G9: Soft-delete sonrası aynı e-posta ile yeni hesap açılmaz; restore kullanılır.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.security import hash_password
from app.models.person import Person, PersonRole
from app.models.user import RefreshToken, User
from app.schemas.user import ASSIGNABLE_ROLES_BY_ROLE, ROLES_REQUIRING_PERSON

logger = logging.getLogger(__name__)

_TEMP_PASSWORD_BYTES = 16


# ── Yardımcı: refresh token revoke ────────────────────────────────────────────

async def _revoke_all_refresh_tokens(user_id: uuid.UUID, db: AsyncSession) -> int:
    """Kullanıcının tüm aktif refresh token'larını revoke eder. Etkilenen sayıyı döner."""
    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    return result.rowcount  # type: ignore[return-value]


# ── Yardımcı: son yönetici koruması ────────────────────────────────────────────

async def _assert_not_last_admin(
    target_user: User, db: AsyncSession, action: str
) -> None:
    """target_user son aktif kulup_yonetici ise G3 ihlali — HTTPException fırlatır."""
    if target_user.role != "kulup_yonetici":
        return
    result = await db.execute(
        select(User).where(
            User.club_id == target_user.club_id,
            User.role == "kulup_yonetici",
            User.is_active.is_(True),
            User.is_deleted.is_(False),
            User.id != target_user.id,
        )
    )
    other_admin = result.scalar_one_or_none()
    if other_admin is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Son aktif yönetici {action} edilemez. "
                   "Önce başka bir kulup_yonetici hesabı oluşturun.",
        )


# ── Yardımcı: Person bağlantısı ve K1 uyumluluk doğrulama ────────────────────

async def _validate_person_link(
    club_id: uuid.UUID,
    role: str,
    person_id: Optional[uuid.UUID],
    db: AsyncSession,
) -> Optional[Person]:
    """
    K1: sporcu/antrenor rolü için person_id zorunlu + Person aktif + aynı kulüp.
    Diğer roller için person_id isteğe bağlı.
    Geçerliyse Person nesnesini döner; person_id None ise None döner.
    """
    if person_id is None:
        if role in ROLES_REQUIRING_PERSON:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"'{role}' rolü için person_id zorunludur.",
            )
        return None

    result = await db.execute(
        select(Person).where(
            Person.id == person_id,
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
        )
    )
    person = result.scalar_one_or_none()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Belirtilen kişi kaydı bulunamadı veya bu kulübe ait değil.",
        )
    if not person.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pasif kişi kaydına kullanıcı hesabı bağlanamaz.",
        )

    # K1: sporcu/antrenor User rolü → bağlı PersonRole uyumluluğu
    if role in ROLES_REQUIRING_PERSON:
        pr_result = await db.execute(
            select(PersonRole).where(
                PersonRole.person_id == person_id,
                PersonRole.role_code == role,
            )
        )
        if pr_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Kişi kaydında '{role}' rolü bulunmuyor. "
                    "Önce kişi kaydına ilgili rolü ekleyin."
                ),
            )

    return person


# ── create_user ───────────────────────────────────────────────────────────────

async def create_user(
    *,
    club_id: uuid.UUID,
    email: str,
    full_name: str,
    role: str,
    person_id: Optional[uuid.UUID],
    assigner_role: str,
    assigner_user_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[User, str]:
    """
    Yeni kullanıcı hesabı oluşturur.

    G8: assigner_role hangi rolleri atayabilir kontrol edilir.
    G9: Silinmiş hesabın e-postasıyla yeni hesap açılamaz → restore önerilir.

    Returns:
        (user, temp_password) — temp_password yalnızca bu yanıtta açıklanır.
    """
    # G8: Rol yükseltme kısıtı
    allowed = ASSIGNABLE_ROLES_BY_ROLE.get(assigner_role, set())
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"'{assigner_role}' rolü '{role}' rolü atayamaz.",
        )

    # G9: Mevcut kullanıcı (aktif ya da silinmiş) var mı?
    existing_result = await db.execute(
        select(User).where(
            User.club_id == club_id,
            User.email == email,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        if existing.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Bu e-posta adresiyle silinmiş bir hesap mevcut. "
                    f"Hesabı restore etmek için POST /users/{existing.id}/restore kullanın."
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta adresi zaten kullanımda.",
        )

    # K1 + Person doğrulama
    await _validate_person_link(club_id, role, person_id, db)

    # Geçici parola (G5: loglanmaz)
    temp_password = secrets.token_urlsafe(_TEMP_PASSWORD_BYTES)

    user = User(
        id=uuid.uuid4(),
        club_id=club_id,
        email=email,
        password_hash=hash_password(temp_password),
        full_name=full_name,
        role=role,
        is_active=True,
        is_deleted=False,
        person_id=person_id,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()

    # G7: Audit log
    await log_action(
        db,
        action="user_created",
        resource_type="user",
        club_id=club_id,
        user_id=assigner_user_id,
        resource_id=str(user.id),
        after={"email": email, "role": role, "person_id": str(person_id) if person_id else None},
    )

    logger.info("Kullanıcı oluşturuldu: %s (rol=%s, club=%s)", user.id, role, club_id)
    return user, temp_password


# ── update_user ───────────────────────────────────────────────────────────────

async def update_user(
    *,
    target_user: User,
    role: Optional[str],
    is_active: Optional[bool],
    full_name: Optional[str],
    assigner_role: str,
    assigner_user_id: uuid.UUID,
    db: AsyncSession,
) -> User:
    """Kullanıcı rol/aktiflik/isim güncelleme."""
    before = {
        "role": target_user.role,
        "is_active": target_user.is_active,
        "full_name": target_user.full_name,
    }

    if role is not None and role != target_user.role:
        # G8: Rol yükseltme kısıtı
        allowed = ASSIGNABLE_ROLES_BY_ROLE.get(assigner_role, set())
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"'{assigner_role}' rolü '{role}' rolü atayamaz.",
            )
        target_user.role = role

    if is_active is not None and is_active != target_user.is_active:
        if not is_active:
            # G3: son yönetici koruması
            await _assert_not_last_admin(target_user, db, "pasifleştirilemez")
        target_user.is_active = is_active

    if full_name is not None:
        target_user.full_name = full_name

    after = {
        "role": target_user.role,
        "is_active": target_user.is_active,
        "full_name": target_user.full_name,
    }

    if before != after:
        # G1: Refresh token revoke (rol veya aktiflik değişti)
        if before["role"] != after["role"] or before["is_active"] != after["is_active"]:
            revoked = await _revoke_all_refresh_tokens(target_user.id, db)
            logger.info(
                "Kullanıcı güncellendi, %d refresh token revoke edildi: %s",
                revoked, target_user.id,
            )

        await log_action(
            db,
            action="user_updated",
            resource_type="user",
            club_id=target_user.club_id,
            user_id=assigner_user_id,
            resource_id=str(target_user.id),
            before=before,
            after=after,
        )

    return target_user


# ── delete_user (soft delete) ─────────────────────────────────────────────────

async def delete_user(
    *,
    target_user: User,
    assigner_user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Soft delete. G1: refresh token revoke. G3: son yönetici koruması."""
    await _assert_not_last_admin(target_user, db, "silinemez")

    target_user.is_deleted = True
    target_user.is_active = False

    # G1: Refresh token revoke
    revoked = await _revoke_all_refresh_tokens(target_user.id, db)
    logger.info(
        "Kullanıcı silindi, %d refresh token revoke edildi: %s",
        revoked, target_user.id,
    )

    # G7: Audit log
    await log_action(
        db,
        action="user_deleted",
        resource_type="user",
        club_id=target_user.club_id,
        user_id=assigner_user_id,
        resource_id=str(target_user.id),
        after={"email": target_user.email, "role": target_user.role},
    )


# ── restore_user ──────────────────────────────────────────────────────────────

async def restore_user(
    *,
    target_user: User,
    assigner_user_id: uuid.UUID,
    db: AsyncSession,
) -> User:
    """Soft-delete geri alma. G9: e-posta tekrarını önler.

    G10: Restore öncesinde person_id çakışması kontrol edilir. Silinmiş
    kullanıcının person_id'si başka aktif bir kullanıcıya bağlıysa
    IntegrityError yerine açıklayıcı 409 döner.
    """
    if not target_user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu hesap zaten aktif.",
        )

    # G10: person_id çakışma kontrolü
    if target_user.person_id is not None:
        conflict = await db.execute(
            select(User).where(
                User.person_id == target_user.person_id,
                User.club_id == target_user.club_id,
                User.is_deleted.is_(False),
                User.id != target_user.id,
            )
        )
        if conflict.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Bu kullanıcının bağlı olduğu Person kaydı başka aktif "
                    "bir hesaba atanmış. Restore için önce o hesabı silin veya "
                    "person_id bağlantısını kaldırın."
                ),
            )

    target_user.is_deleted = False
    target_user.is_active = True
    target_user.must_change_password = True  # restore sonrası yeniden giriş zorunlu

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Restore sırasında benzersizlik ihlali oluştu (person_id çakışması).",
        )

    await log_action(
        db,
        action="user_restored",
        resource_type="user",
        club_id=target_user.club_id,
        user_id=assigner_user_id,
        resource_id=str(target_user.id),
        after={"email": target_user.email, "role": target_user.role},
    )

    logger.info("Kullanıcı restore edildi: %s", target_user.id)
    return target_user


# ── reset_password ────────────────────────────────────────────────────────────

async def reset_password(
    *,
    target_user: User,
    assigner_user_id: uuid.UUID,
    db: AsyncSession,
) -> str:
    """Geçici parola üretir. G1: refresh token revoke. G5: loglanmaz."""
    temp_password = secrets.token_urlsafe(_TEMP_PASSWORD_BYTES)

    target_user.password_hash = hash_password(temp_password)
    target_user.must_change_password = True

    # G1: Refresh token revoke
    revoked = await _revoke_all_refresh_tokens(target_user.id, db)
    logger.info(
        "Parola sıfırlandı, %d refresh token revoke edildi: %s",
        revoked, target_user.id,
    )

    # G7: Audit log (temp_password loglanmaz)
    await log_action(
        db,
        action="user_password_reset",
        resource_type="user",
        club_id=target_user.club_id,
        user_id=assigner_user_id,
        resource_id=str(target_user.id),
    )

    return temp_password  # G5: yalnızca yanıtta döner


# ── membership_approval uyumluluğu ────────────────────────────────────────────

async def find_or_create_user_for_approval(
    *,
    club_id: uuid.UUID,
    email: Optional[str],
    full_name: str,
    person_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[Optional[User], Optional[str]]:
    """
    Üyelik onayında kullanıcı hesabı aç/bul.

    membership_approval.py tarafından çağrılır; assigner kontrolü yapılmaz
    (sistem işlemi). Yönetici rolü kısıtlamaları uygulanmaz.

    Returns:
        (user, temp_password) — e-posta yoksa (None, None).
        Mevcut hesap varsa (user, None) — parola değiştirilmez.
    """
    if not email:
        return None, None

    # Mevcut aktif hesap var mı?
    result = await db.execute(
        select(User).where(
            User.club_id == club_id,
            User.email == email,
            User.is_deleted.is_(False),
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        if existing.person_id is None:
            existing.person_id = person_id
            await db.flush()
        return existing, None

    # Yeni hesap — geçici parola (G5)
    temp_password = secrets.token_urlsafe(_TEMP_PASSWORD_BYTES)
    user = User(
        id=uuid.uuid4(),
        club_id=club_id,
        email=email,
        password_hash=hash_password(temp_password),
        full_name=full_name,
        role="uye",
        is_active=True,
        is_deleted=False,
        person_id=person_id,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    logger.info("Üyelik onayı: yeni kullanıcı oluşturuldu (id=%s)", user.id)
    return user, temp_password
