"""Calendar read-model — tarih aralığındaki etkinlikleri tek endpoint'te birleştirir.

Veri kaynakları (fiziksel tablo):
  training_sessions  → training_session   (eğitim oturumları)
  payments           → payment            (vade tarihi, pending)
  equipment          → equipment_maintenance / equipment_insurance
  athlete_profiles   → athlete_license / athlete_visa / athlete_health

Yeni tablo oluşturulmaz; her kaynak kendi tablosundan salt okunur projeksiyon üretir.

Endpoint:
  GET /api/v1/calendar/events
    ?date_from=YYYY-MM-DD  (default: bugün)
    ?date_to=YYYY-MM-DD    (default: bugün+90gün, maks 90 gün aralık)

RBAC:
  Projection bloklarına kulüp-geneli izin gereklidir (:own izinler yeterli değil).
  | Kategori     | Gerekli permission |
  |---|---|
  | training     | egitim:read        |
  | payment      | odeme:read         |
  | equipment    | ekipman:read       |
  | athlete docs | sporcu:read        |

  Sağlık raporu bitiş tarihi hassas veri sayılır;
  SENSITIVE_FIELD_MASK_ROLES içindeki roller göremez.

  :own kapsamındaki roller (veli, sporcu, uye, misafir) hiçbir kategoriyi göremez.
"""
import uuid
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac import PERMISSIONS, SENSITIVE_FIELD_MASK_ROLES
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.athlete_profile import AthleteProfile
from app.models.equipment import Equipment
from app.models.payment import Payment
from app.models.person import Person as PersonModel
from app.models.training import TrainingCourse, TrainingSession
from app.schemas.auth import TokenPayload

router = APIRouter(prefix="/calendar", tags=["calendar"])


# ── Şemalar ───────────────────────────────────────────────────────────────────


class CalendarEvent(BaseModel):
    id: str                          # "{source_type}:{source_id}"
    source_type: str                 # training_session | payment | equipment_maintenance | ...
    category: str                    # training | payment | equipment | athlete
    title: str
    date: date
    severity: str                    # info | warning | critical
    detail: Optional[str] = None
    person_name: Optional[str] = None


class CalendarEventsOut(BaseModel):
    events: List[CalendarEvent]
    date_from: date
    date_to: date
    total: int


# ── RBAC yardımcısı ───────────────────────────────────────────────────────────


def _has_global_permission(role: str, permission: str) -> bool:
    """Kulüp-geneli permission kontrolü — :own izinleri kabul edilmez.

    Operational Calendar toplu veriyi projekte ettiğinden :own kapsamındaki
    roller (veli, sporcu, uye, misafir) bu endpoint'ten data alamaz.
    :own kapsam takvimi ileride ayrı bir endpoint/contract gerektirir.
    """
    perms = PERMISSIONS.get(role, set())
    if "*" in perms:
        return True
    if permission in perms:
        return True
    # Namespace wildcard: "ekipman:*" → "ekipman:read" sağlar
    namespace = permission.split(":", 1)[0]
    if f"{namespace}:*" in perms:
        return True
    # :own izinlere bilinçli olarak düşmüyoruz
    return False


# ── Yardımcılar ───────────────────────────────────────────────────────────────


def _severity(event_date: date, threshold_warning: int) -> str:
    """Bugünden gün farkına göre severity döndürür.

    Geçmiş → critical
    0 <= delta <= threshold_warning → warning
    delta > threshold_warning → info
    """
    delta = (event_date - date.today()).days
    if delta < 0:
        return "critical"
    if delta <= threshold_warning:
        return "warning"
    return "info"


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.get("/events", response_model=CalendarEventsOut)
async def list_calendar_events(
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    date_from: Optional[date] = Query(default=None, description="Başlangıç tarihi (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(default=None, description="Bitiş tarihi (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventsOut:
    """Takvim etkinliklerini döndür.

    date_from / date_to verilmezse bugünden +90 gün kullanılır.
    Aralık 90 günü aşarsa date_to kırpılır.
    """
    today = date.today()
    if date_from is None:
        date_from = today
    if date_to is None:
        date_to = today + timedelta(days=90)
    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bitiş tarihi başlangıç tarihinden önce olamaz.",
        )
    # 90 gün sınırı
    if (date_to - date_from).days > 90:
        date_to = date_from + timedelta(days=90)

    role = current_user.role
    events: List[CalendarEvent] = []

    # ── 1. Eğitim oturumları ──────────────────────────────────────────────────
    if _has_global_permission(role, "egitim:read"):
        stmt = (
            select(TrainingSession, TrainingCourse.name.label("course_name"))
            .join(TrainingCourse, TrainingSession.course_id == TrainingCourse.id)
            .where(
                TrainingSession.club_id == club_id,
                TrainingCourse.is_deleted.is_(False),
                TrainingSession.status != "iptal",
                TrainingSession.session_date >= date_from,
                TrainingSession.session_date <= date_to,
            )
            .order_by(TrainingSession.session_date, TrainingSession.start_time)
        )
        rows = (await db.execute(stmt)).all()
        for session, course_name in rows:
            time_str = ""
            if session.start_time:
                time_str = f" {session.start_time.strftime('%H:%M')}"
                if session.end_time:
                    time_str += f"–{session.end_time.strftime('%H:%M')}"
            events.append(CalendarEvent(
                id=f"training_session:{session.id}",
                source_type="training_session",
                category="training",
                title=f"{course_name}{time_str}",
                date=session.session_date,
                severity="info",
                detail=session.notes,
            ))

    # ── 2. Bekleyen ödemeler (vade tarihi) ───────────────────────────────────
    if _has_global_permission(role, "odeme:read"):
        stmt = (
            select(Payment)
            .options(selectinload(Payment.person))
            .where(
                Payment.club_id == club_id,
                Payment.status == "pending",
                Payment.is_deleted.is_(False),
                Payment.due_date >= date_from,
                Payment.due_date <= date_to,
            )
            .order_by(Payment.due_date)
        )
        payments = (await db.execute(stmt)).scalars().all()
        for p in payments:
            person_name: Optional[str] = None
            if p.person:
                person_name = f"{p.person.first_name} {p.person.last_name}"
            events.append(CalendarEvent(
                id=f"payment:{p.id}",
                source_type="payment",
                category="payment",
                title=f"Ödeme vadesi — {person_name or 'Genel'}",
                date=p.due_date,
                severity=_severity(p.due_date, threshold_warning=7),
                detail=p.payment_type,
                person_name=person_name,
            ))

    # ── 3. Ekipman bakım tarihleri ────────────────────────────────────────────
    if _has_global_permission(role, "ekipman:read"):
        stmt = (
            select(Equipment)
            .where(
                Equipment.club_id == club_id,
                Equipment.is_deleted.is_(False),
                Equipment.is_active.is_(True),
                Equipment.next_maintenance_date >= date_from,
                Equipment.next_maintenance_date <= date_to,
            )
            .order_by(Equipment.next_maintenance_date)
        )
        eqs = (await db.execute(stmt)).scalars().all()
        for eq in eqs:
            events.append(CalendarEvent(
                id=f"equipment_maintenance:{eq.id}",
                source_type="equipment_maintenance",
                category="equipment",
                title=f"Bakım — {eq.name}",
                date=eq.next_maintenance_date,
                severity=_severity(eq.next_maintenance_date, threshold_warning=14),
                detail=eq.equipment_type,
            ))

        # ── 4. Ekipman sigorta tarihleri ──────────────────────────────────────
        # Sigorta da ekipman:read ile korunur (ayrı blok değil)
        stmt = (
            select(Equipment)
            .where(
                Equipment.club_id == club_id,
                Equipment.is_deleted.is_(False),
                Equipment.is_active.is_(True),
                Equipment.insurance_expiry_date >= date_from,
                Equipment.insurance_expiry_date <= date_to,
            )
            .order_by(Equipment.insurance_expiry_date)
        )
        eqs = (await db.execute(stmt)).scalars().all()
        for eq in eqs:
            events.append(CalendarEvent(
                id=f"equipment_insurance:{eq.id}",
                source_type="equipment_insurance",
                category="equipment",
                title=f"Sigorta sonu — {eq.name}",
                date=eq.insurance_expiry_date,
                severity=_severity(eq.insurance_expiry_date, threshold_warning=30),
                detail=eq.equipment_type,
            ))

    # ── 5. Sporcu belgeleri ───────────────────────────────────────────────────
    if _has_global_permission(role, "sporcu:read"):
        stmt = (
            select(AthleteProfile)
            .join(PersonModel, AthleteProfile.person_id == PersonModel.id)
            .options(selectinload(AthleteProfile.person))
            .where(
                AthleteProfile.club_id == club_id,
                PersonModel.is_deleted.is_(False),
                PersonModel.is_active.is_(True),
            )
        )
        athletes = (await db.execute(stmt)).scalars().all()

        # Sağlık raporu hassas alandır; SENSITIVE_FIELD_MASK_ROLES göremez.
        include_health = role not in SENSITIVE_FIELD_MASK_ROLES

        ATHLETE_FIELDS = [
            ("license_expiry_date",       "athlete_license", "Lisans",        30),
            ("visa_expiry_date",           "athlete_visa",    "Vize",          30),
            ("health_report_expiry_date",  "athlete_health",  "Sağlık raporu", 30),
        ]
        for ap in athletes:
            ap_person_name: Optional[str] = None
            if ap.person:
                ap_person_name = f"{ap.person.first_name} {ap.person.last_name}"
            for field_name, source_type, label, warn_days in ATHLETE_FIELDS:
                if source_type == "athlete_health" and not include_health:
                    continue
                field_val: Optional[date] = getattr(ap, field_name)
                if field_val and date_from <= field_val <= date_to:
                    events.append(CalendarEvent(
                        id=f"{source_type}:{ap.id}",
                        source_type=source_type,
                        category="athlete",
                        title=f"{label} sonu — {ap_person_name or '?'}",
                        date=field_val,
                        severity=_severity(field_val, threshold_warning=warn_days),
                        person_name=ap_person_name,
                    ))

    # Tarihe göre genel sıralama
    events.sort(key=lambda e: e.date)

    return CalendarEventsOut(
        events=events,
        date_from=date_from,
        date_to=date_to,
        total=len(events),
    )
