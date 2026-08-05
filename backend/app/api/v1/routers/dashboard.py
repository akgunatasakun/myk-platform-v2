"""Dashboard istatistikleri API router."""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.membership_application import MembershipApplication
from app.models.person import Person, PersonRole
from app.schemas.auth import TokenPayload

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardStats(BaseModel):
    toplam_kisi: int
    aktif_sporcu: int
    aktif_uye: int
    antrenor_sayisi: int
    bekleyen_basvuru: int
    vadesi_gecen_odeme: int
    yaklasan_egitim: int
    bakim_bekleyen_ekipman: int
    son_aktiviteler: list


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    # Toplam kişi sayısı
    total_result = await db.execute(
        select(func.count(Person.id)).where(
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
        )
    )
    toplam_kisi = total_result.scalar_one()

    # Aktif sporcu sayısı
    sporcu_result = await db.execute(
        select(func.count(Person.id.distinct())).where(
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
            Person.is_active.is_(True),
            Person.id.in_(
                select(PersonRole.person_id).where(PersonRole.role_code == "sporcu")
            ),
        )
    )
    aktif_sporcu = sporcu_result.scalar_one()

    # Aktif üye sayısı
    uye_result = await db.execute(
        select(func.count(Person.id.distinct())).where(
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
            Person.is_active.is_(True),
            Person.id.in_(
                select(PersonRole.person_id).where(PersonRole.role_code == "uye")
            ),
        )
    )
    aktif_uye = uye_result.scalar_one()

    # Antrenör sayısı
    antrenor_result = await db.execute(
        select(func.count(Person.id.distinct())).where(
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
            Person.is_active.is_(True),
            Person.id.in_(
                select(PersonRole.person_id).where(PersonRole.role_code == "antrenor")
            ),
        )
    )
    antrenor_sayisi = antrenor_result.scalar_one()

    # Bekleyen başvuru sayısı
    basvuru_result = await db.execute(
        select(func.count(MembershipApplication.id)).where(
            MembershipApplication.club_id == club_id,
            MembershipApplication.status == "submitted",
            MembershipApplication.is_deleted.is_(False),
        )
    )
    bekleyen_basvuru = basvuru_result.scalar_one()

    return DashboardStats(
        toplam_kisi=toplam_kisi,
        aktif_sporcu=aktif_sporcu,
        aktif_uye=aktif_uye,
        antrenor_sayisi=antrenor_sayisi,
        bekleyen_basvuru=bekleyen_basvuru,
        vadesi_gecen_odeme=0,
        yaklasan_egitim=0,
        bakim_bekleyen_ekipman=0,
        son_aktiviteler=[],
    )
