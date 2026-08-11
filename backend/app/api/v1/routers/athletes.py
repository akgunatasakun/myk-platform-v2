"""Sporcu profil API — AthleteProfile CRUD + uyarılar.

Endpoint'ler:
  GET  /athletes                 — Sporcu listesi (role_code=sporcu filtreli persons)
  GET  /athletes/alerts          — Belge/lisans/vize uyarıları
  GET  /athletes/{person_id}     — Sporcu detayı (Person + AthleteProfile)
  PATCH /athletes/{person_id}    — Sporcu profili oluştur veya güncelle (upsert)

Tasarım notları:
  - "Sporcu" tanımı: role_codes içinde 'sporcu' olan Person kaydıdır.
  - AthleteProfile yoksa GET → has_profile=False, boş profil alanları döner.
  - PATCH → profil varsa günceller, yoksa oluşturur (upsert).
  - Hassas alanlar (allergies, special_conditions, health_report_expiry_date)
    SENSITIVE_FIELD_MASK_ROLES içindeki roller için None olarak döner.
"""
import uuid
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_action
from app.core.rbac import SENSITIVE_FIELD_MASK_ROLES, require_permission
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.athlete_profile import AthleteProfile
from app.models.person import Person, PersonRole
from app.schemas.athlete import (
    AthleteAlertItem,
    AthleteListItem,
    AthleteListOut,
    AthleteProfileOut,
    AthleteProfileUpdate,
    _doc_status,
)
from app.schemas.auth import TokenPayload
from fastapi import Request

router = APIRouter(prefix="/athletes", tags=["athletes"])

ALERT_HORIZON_DAYS = 30


def _should_mask(role: str) -> bool:
    return role in SENSITIVE_FIELD_MASK_ROLES


def _build_list_item(person: Person, mask: bool) -> AthleteListItem:
    ap: Optional[AthleteProfile] = person.athlete_profile  # type: ignore[assignment]
    if ap is None:
        return AthleteListItem(
            person_id=person.id,
            first_name=person.first_name,
            last_name=person.last_name,
            birth_date=person.birth_date,
            gender=person.gender,
            member_number=person.member_number,
            is_active=person.is_active,
            has_profile=False,
        )

    return AthleteListItem(
        person_id=person.id,
        first_name=person.first_name,
        last_name=person.last_name,
        birth_date=person.birth_date,
        gender=person.gender,
        member_number=person.member_number,
        is_active=person.is_active,
        sports_branch_name=ap.sports_branch.name if ap.sports_branch else None,
        class_name=ap.class_name,
        level=ap.level,
        license_no=ap.license_no,
        license_expiry_date=ap.license_expiry_date,
        license_status=_doc_status(ap.license_expiry_date),
        visa_expiry_date=ap.visa_expiry_date,
        visa_status=_doc_status(ap.visa_expiry_date),
        health_report_expiry_date=None if mask else ap.health_report_expiry_date,
        health_status="eksik" if mask else _doc_status(ap.health_report_expiry_date),
        swimming_qualified=ap.swimming_qualified,
        kvkk_consent=ap.kvkk_consent,
        photo_video_consent=ap.photo_video_consent,
        has_profile=True,
    )


async def _get_athlete_person(
    person_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> Person:
    """role_code=sporcu olan Person'ı yükle; bulunamazsa 404."""
    result = await db.execute(
        select(Person)
        .options(
            selectinload(Person.roles),
            selectinload(Person.athlete_profile).selectinload(AthleteProfile.sports_branch),
            selectinload(Person.athlete_guardian_links),
        )
        .join(PersonRole, PersonRole.person_id == Person.id)
        .where(
            Person.id == person_id,
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
            PersonRole.role_code == "sporcu",
        )
    )
    person = result.scalar_one_or_none()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sporcu bulunamadı.",
        )
    return person


# ── GET /athletes ─────────────────────────────────────────────────────────────

@router.get("", response_model=AthleteListOut)
async def list_athletes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    class_name: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("sporcu:read")),
    db: AsyncSession = Depends(get_db),
) -> AthleteListOut:
    base_query = (
        select(Person)
        .options(
            selectinload(Person.roles),
            selectinload(Person.athlete_profile).selectinload(AthleteProfile.sports_branch),
        )
        .join(PersonRole, PersonRole.person_id == Person.id)
        .where(
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
            PersonRole.role_code == "sporcu",
        )
        .distinct()
    )

    if search:
        pattern = f"%{search}%"
        base_query = base_query.where(
            Person.first_name.ilike(pattern) | Person.last_name.ilike(pattern)
        )

    if is_active is not None:
        base_query = base_query.where(Person.is_active.is_(is_active))

    if class_name is not None:
        base_query = base_query.join(
            AthleteProfile, AthleteProfile.person_id == Person.id, isouter=True
        ).where(AthleteProfile.class_name == class_name)

    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    result = await db.execute(
        base_query.order_by(Person.last_name, Person.first_name).offset(skip).limit(limit)
    )
    persons = result.scalars().all()

    mask = _should_mask(current_user.role)
    items = [_build_list_item(p, mask) for p in persons]

    return AthleteListOut(items=items, total=total, skip=skip, limit=limit)


# ── GET /athletes/alerts ──────────────────────────────────────────────────────

@router.get("/alerts", response_model=list[AthleteAlertItem])
async def get_athlete_alerts(
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("sporcu:read")),
    db: AsyncSession = Depends(get_db),
) -> list[AthleteAlertItem]:
    """Belgesi eksik, dolmuş veya 30 gün içinde dolacak sporcular + KVKK eksikleri."""
    result = await db.execute(
        select(Person)
        .options(
            selectinload(Person.roles),
            selectinload(Person.athlete_profile).selectinload(AthleteProfile.sports_branch),
        )
        .join(PersonRole, PersonRole.person_id == Person.id)
        .where(
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
            Person.is_active.is_(True),
            PersonRole.role_code == "sporcu",
        )
        .distinct()
    )
    persons = result.scalars().all()

    horizon = date.today() + timedelta(days=ALERT_HORIZON_DAYS)
    mask = _should_mask(current_user.role)
    alerts_out: list[AthleteAlertItem] = []

    for p in persons:
        ap: Optional[AthleteProfile] = p.athlete_profile  # type: ignore[assignment]
        person_alerts: list[str] = []

        if ap is None:
            # Profili hiç girilmemiş sporcular da uyarı listesine girer
            person_alerts.append("Sporcu profili henüz girilmemiş.")
        else:
            lic_status = _doc_status(ap.license_expiry_date)
            if lic_status in ("dolmus", "yaklasan", "eksik"):
                label = {"dolmus": "Lisans süresi dolmuş", "yaklasan": "Lisans süresi yaklaşıyor", "eksik": "Lisans girilmemiş"}[lic_status]
                person_alerts.append(label)

            vis_status = _doc_status(ap.visa_expiry_date)
            if vis_status in ("dolmus", "yaklasan", "eksik"):
                label = {"dolmus": "Vize süresi dolmuş", "yaklasan": "Vize süresi yaklaşıyor", "eksik": "Vize girilmemiş"}[vis_status]
                person_alerts.append(label)

            if not mask:
                hlt_status = _doc_status(ap.health_report_expiry_date)
                if hlt_status in ("dolmus", "yaklasan", "eksik"):
                    label = {"dolmus": "Sağlık raporu dolmuş", "yaklasan": "Sağlık raporu yaklaşıyor", "eksik": "Sağlık raporu girilmemiş"}[hlt_status]
                    person_alerts.append(label)

            if not ap.kvkk_consent:
                person_alerts.append("KVKK onayı eksik")

        if person_alerts:
            alerts_out.append(
                AthleteAlertItem(
                    person_id=p.id,
                    first_name=p.first_name,
                    last_name=p.last_name,
                    class_name=ap.class_name if ap else None,
                    license_expiry_date=ap.license_expiry_date if ap else None,
                    license_status=_doc_status(ap.license_expiry_date) if ap else "eksik",
                    visa_expiry_date=ap.visa_expiry_date if ap else None,
                    visa_status=_doc_status(ap.visa_expiry_date) if ap else "eksik",
                    health_report_expiry_date=(None if (mask or ap is None) else ap.health_report_expiry_date),
                    health_status=("eksik" if (mask or ap is None) else _doc_status(ap.health_report_expiry_date)),
                    kvkk_consent=ap.kvkk_consent if ap else False,
                    alerts=person_alerts,
                )
            )

    return alerts_out


# ── GET /athletes/{person_id} ─────────────────────────────────────────────────

class AthleteDetailOut(AthleteListItem):
    athlete_profile: Optional[AthleteProfileOut] = None


@router.get("/{person_id}", response_model=AthleteDetailOut)
async def get_athlete(
    person_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("sporcu:read")),
    db: AsyncSession = Depends(get_db),
) -> AthleteDetailOut:
    person = await _get_athlete_person(person_id, club_id, db)
    mask = _should_mask(current_user.role)
    base = _build_list_item(person, mask)
    ap: Optional[AthleteProfile] = person.athlete_profile  # type: ignore[assignment]
    profile_out = AthleteProfileOut.from_model(ap, mask=mask) if ap else None
    return AthleteDetailOut(**base.model_dump(), athlete_profile=profile_out)


# ── PATCH /athletes/{person_id} ───────────────────────────────────────────────

@router.patch("/{person_id}", response_model=AthleteDetailOut)
async def upsert_athlete_profile(
    person_id: uuid.UUID,
    body: AthleteProfileUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("sporcu:*")),
    db: AsyncSession = Depends(get_db),
) -> AthleteDetailOut:
    """Sporcu profilini oluştur (profil yoksa) veya güncelle (varsa)."""
    person = await _get_athlete_person(person_id, club_id, db)

    update_data = body.model_dump(exclude_unset=True)
    ap: Optional[AthleteProfile] = person.athlete_profile  # type: ignore[assignment]

    if ap is None:
        # Yeni profil oluştur
        ap = AthleteProfile(
            club_id=club_id,
            person_id=person_id,
        )
        db.add(ap)
        action = "athlete_profile_created"
    else:
        action = "athlete_profile_updated"

    # kvkk_consent True'ya dönüyorsa zamanı kaydet
    if update_data.get("kvkk_consent") is True and not ap.kvkk_consent:
        from datetime import datetime as _dt
        ap.kvkk_consent_at = _dt.now()
        if "kvkk_text_version" not in update_data:
            ap.kvkk_text_version = "v1.0"

    for field, value in update_data.items():
        setattr(ap, field, value)

    await db.flush()

    # Güncel veriyi reload et (sports_branch eager load için)
    result = await db.execute(
        select(Person)
        .options(
            selectinload(Person.roles),
            selectinload(Person.athlete_profile).selectinload(AthleteProfile.sports_branch),
        )
        .where(Person.id == person_id)
    )
    person = result.scalar_one()

    await log_action(
        db,
        action=action,
        resource_type="athlete_profile",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(person_id),
        after={k: str(v) if v is not None else None for k, v in update_data.items()},
        request=request,
    )

    mask = _should_mask(current_user.role)
    base = _build_list_item(person, mask)
    ap_reloaded: Optional[AthleteProfile] = person.athlete_profile  # type: ignore[assignment]
    profile_out = AthleteProfileOut.from_model(ap_reloaded, mask=mask) if ap_reloaded else None
    return AthleteDetailOut(**base.model_dump(), athlete_profile=profile_out)
