"""Dashboard istatistikleri API router — v2 (Dashboard 2.0).

Tek endpoint, tek DB round-trip grubu:
  GET /dashboard/stats

Veri kaynakları:
  persons / person_roles → kişi sayaçları
  membership_applications → bekleyen başvurular
  payments               → vadesi geçen ödemeler (count + toplam)
  training_courses       → aktif kurs sayısı
  training_sessions      → bugünün oturumları + yaklaşan 7 gün
  equipment              → bakım/hasarlı ekipman sayısı
  audit_logs             → son 15 aktivite
"""
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.audit import AuditLog
from app.models.equipment import Equipment
from app.models.membership_application import MembershipApplication
from app.models.payment import Payment
from app.models.person import Person, PersonRole
from app.models.training import TrainingCourse, TrainingSession
from app.schemas.auth import TokenPayload

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ── Alt schema'lar ────────────────────────────────────────────────────────────

class OturumOut(BaseModel):
    session_id: uuid.UUID
    course_id: uuid.UUID
    course_name: str
    session_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    instructor_name: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


class AktiviteOut(BaseModel):
    id: uuid.UUID
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Ana schema ────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    # ── Kişi sayaçları ────────────────────────────────────────────────────────
    toplam_kisi: int
    aktif_sporcu: int
    aktif_uye: int
    antrenor_sayisi: int

    # ── Uyarı sayaçları ───────────────────────────────────────────────────────
    bekleyen_basvuru: int
    vadesi_gecen_odeme: int           # count
    vadesi_gecen_odeme_toplami: float  # TL cinsinden toplam tutar
    bakim_bekleyen_ekipman: int

    # ── Eğitim ────────────────────────────────────────────────────────────────
    aktif_kurs_sayisi: int
    yaklasan_egitim: int              # today + next 7 days session count
    bugunun_oturumlari: List[OturumOut]
    yaklasan_oturumlar: List[OturumOut]   # yarın → +7 gün, max 10

    # ── Feed ──────────────────────────────────────────────────────────────────
    son_aktiviteler: List[AktiviteOut]


# ── Yardımcı ─────────────────────────────────────────────────────────────────

def _oturum_out(s: TrainingSession) -> OturumOut:
    instructor_name: Optional[str] = None
    if s.instructor is not None:
        # Oturuma özgü eğitmen varsa onu kullan
        instructor_name = f"{s.instructor.first_name} {s.instructor.last_name}"
    elif s.course is not None and s.course.instructor is not None:
        # Yoksa kursun ana eğitmenine geri dön
        instructor_name = f"{s.course.instructor.first_name} {s.course.instructor.last_name}"
    return OturumOut(
        session_id=s.id,
        course_id=s.course_id,
        course_name=s.course.name if s.course else "—",
        session_date=s.session_date,
        start_time=s.start_time,
        end_time=s.end_time,
        instructor_name=instructor_name,
        status=s.status,
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    club_id: uuid.UUID = Depends(get_club_id),
    _current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    next7 = today + timedelta(days=7)

    # ── Kişi sayaçları ────────────────────────────────────────────────────────
    total_r = await db.execute(
        select(func.count(Person.id)).where(
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
        )
    )
    toplam_kisi: int = total_r.scalar_one()

    sporcu_r = await db.execute(
        select(func.count(Person.id.distinct())).where(
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
            Person.is_active.is_(True),
            Person.id.in_(
                select(PersonRole.person_id).where(PersonRole.role_code == "sporcu")
            ),
        )
    )
    aktif_sporcu: int = sporcu_r.scalar_one()

    uye_r = await db.execute(
        select(func.count(Person.id.distinct())).where(
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
            Person.is_active.is_(True),
            Person.id.in_(
                select(PersonRole.person_id).where(PersonRole.role_code == "uye")
            ),
        )
    )
    aktif_uye: int = uye_r.scalar_one()

    antrenor_r = await db.execute(
        select(func.count(Person.id.distinct())).where(
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
            Person.is_active.is_(True),
            Person.id.in_(
                select(PersonRole.person_id).where(PersonRole.role_code == "antrenor")
            ),
        )
    )
    antrenor_sayisi: int = antrenor_r.scalar_one()

    # ── Bekleyen başvurular ───────────────────────────────────────────────────
    basvuru_r = await db.execute(
        select(func.count(MembershipApplication.id)).where(
            MembershipApplication.club_id == club_id,
            MembershipApplication.status == "submitted",
            MembershipApplication.is_deleted.is_(False),
        )
    )
    bekleyen_basvuru: int = basvuru_r.scalar_one()

    # ── Vadesi geçen ödemeler ─────────────────────────────────────────────────
    odeme_r = await db.execute(
        select(
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount), Decimal("0")),
        ).where(
            Payment.club_id == club_id,
            Payment.status == "pending",
            Payment.due_date < today,
            Payment.is_deleted.is_(False),
        )
    )
    odeme_count, odeme_toplam = odeme_r.one()
    vadesi_gecen_odeme: int = int(odeme_count)
    vadesi_gecen_odeme_toplami: float = float(odeme_toplam or 0)

    # ── Bakım bekleyen ekipman ────────────────────────────────────────────────
    bakim_r = await db.execute(
        select(func.count(Equipment.id)).where(
            Equipment.club_id == club_id,
            Equipment.status.in_(["bakimda", "hasarli"]),
            Equipment.is_deleted.is_(False),
        )
    )
    bakim_bekleyen_ekipman: int = bakim_r.scalar_one()

    # ── Aktif / Planlanan kurs sayısı ────────────────────────────────────────
    # "iptal" ve "tamamlandi" hariç; "aktif" + "planlandi" statüsündeki kurslar
    kurs_r = await db.execute(
        select(func.count(TrainingCourse.id)).where(
            TrainingCourse.club_id == club_id,
            TrainingCourse.is_active.is_(True),
            TrainingCourse.is_deleted.is_(False),
            TrainingCourse.status.in_(["aktif", "planlandi"]),
        )
    )
    aktif_kurs_sayisi: int = kurs_r.scalar_one()

    # ── Yaklaşan oturum sayısı (bugün + 7 gün, cap yok, gerçek COUNT) ────────
    yaklasan_count_r = await db.execute(
        select(func.count(TrainingSession.id)).where(
            TrainingSession.club_id == club_id,
            TrainingSession.session_date >= today,
            TrainingSession.session_date <= next7,
            TrainingSession.status != "iptal",
        )
    )
    yaklasan_egitim: int = yaklasan_count_r.scalar_one()

    # ── Bugünün oturumları ────────────────────────────────────────────────────
    bugun_r = await db.execute(
        select(TrainingSession)
        .options(
            selectinload(TrainingSession.course).selectinload(TrainingCourse.instructor),
            selectinload(TrainingSession.instructor),
        )
        .where(
            TrainingSession.club_id == club_id,
            TrainingSession.session_date == today,
            TrainingSession.status != "iptal",
        )
        .order_by(TrainingSession.start_time)
    )
    bugun_sessions = bugun_r.scalars().all()
    bugunun_oturumlari = [_oturum_out(s) for s in bugun_sessions]

    # ── Yaklaşan oturumlar (yarın → +7 gün, max 10, tablo için) ─────────────
    yaklasan_r = await db.execute(
        select(TrainingSession)
        .options(
            selectinload(TrainingSession.course).selectinload(TrainingCourse.instructor),
            selectinload(TrainingSession.instructor),
        )
        .where(
            TrainingSession.club_id == club_id,
            TrainingSession.session_date >= tomorrow,
            TrainingSession.session_date <= next7,
            TrainingSession.status != "iptal",
        )
        .order_by(TrainingSession.session_date, TrainingSession.start_time)
        .limit(10)
    )
    yaklasan_sessions = yaklasan_r.scalars().all()
    yaklasan_oturumlar = [_oturum_out(s) for s in yaklasan_sessions]

    # ── Son aktiviteler ───────────────────────────────────────────────────────
    audit_r = await db.execute(
        select(AuditLog)
        .where(AuditLog.club_id == club_id)
        .order_by(AuditLog.created_at.desc())
        .limit(15)
    )
    audit_rows = audit_r.scalars().all()
    son_aktiviteler = [
        AktiviteOut(
            id=a.id,
            action=a.action,
            resource_type=a.resource_type,
            resource_id=a.resource_id,
            created_at=a.created_at,
        )
        for a in audit_rows
    ]

    return DashboardStats(
        toplam_kisi=toplam_kisi,
        aktif_sporcu=aktif_sporcu,
        aktif_uye=aktif_uye,
        antrenor_sayisi=antrenor_sayisi,
        bekleyen_basvuru=bekleyen_basvuru,
        vadesi_gecen_odeme=vadesi_gecen_odeme,
        vadesi_gecen_odeme_toplami=vadesi_gecen_odeme_toplami,
        bakim_bekleyen_ekipman=bakim_bekleyen_ekipman,
        aktif_kurs_sayisi=aktif_kurs_sayisi,
        yaklasan_egitim=yaklasan_egitim,
        bugunun_oturumlari=bugunun_oturumlari,
        yaklasan_oturumlar=yaklasan_oturumlar,
        son_aktiviteler=son_aktiviteler,
    )
