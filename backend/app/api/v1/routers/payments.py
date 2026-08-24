"""Payments router — ödeme/tahsilat domain'i.

Flask karşılıkları:
  GET  /api/odemeler              → GET  /payments
  POST /api/odemeler              → POST /payments
  GET  /api/odemeler/:id          → GET  /payments/{id}
  PUT  /api/odemeler/:id          → PUT  /payments/{id}
  (soft delete yok Flask'ta)      → DELETE /payments/{id}  ← ek
  GET  /api/odemeler/gecikmusler  → GET  /payments/overdue
  GET  /api/raporlar/gelir        → GET  /reports/revenue

RBAC:
  okuma   → odeme:read
  yazma   → odeme:write
  rapor   → rapor:read (gelir raporu)
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac import require_permission, is_own_scope_only
from app.core.audit import log_action
from app.services.event_service import emit_event
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.models.payment import Payment
from app.models.person import Person
from app.models.person_guardian import PersonGuardian
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.schemas.payment import (
    OverduePaymentOut,
    PaymentCreate,
    PaymentListOut,
    PaymentOut,
    PaymentUpdate,
    RevenueByMonth,
    RevenueReport,
)

router = APIRouter(prefix="/payments", tags=["payments"])


# ─── Own-scope yardımcıları ──────────────────────────────────────────────────

async def _get_ward_ids(
    user_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> list[uuid.UUID]:
    """Veli'nin bağlı sporcularının (ward) person_id listesini döndür."""
    # Önce user'ın person_id'sini bul
    result = await db.execute(
        select(User.person_id).where(User.id == user_id)
    )
    person_id = result.scalar_one_or_none()
    if not person_id:
        return []
    # Guardian bağlantısından ward'ları al
    result = await db.execute(
        select(PersonGuardian.athlete_person_id).where(
            PersonGuardian.guardian_person_id == person_id,
            PersonGuardian.club_id == club_id,
        )
    )
    return list(result.scalars().all())


# ─── Yardımcılar ─────────────────────────────────────────────────────────────

def _person_name(person: Optional[Person]) -> Optional[str]:
    if person is None:
        return None
    return f"{person.first_name} {person.last_name}".strip()


async def _get_payment(
    payment_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> Payment:
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.person))
        .where(
            Payment.id == payment_id,
            Payment.club_id == club_id,
            Payment.is_deleted.is_(False),
        )
    )
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ödeme kaydı bulunamadı.",
        )
    return p


def _to_out(payment: Payment) -> PaymentOut:
    out = PaymentOut.model_validate(payment)
    out.person_name = _person_name(payment.person)
    return out


# ─── Ödeme listesi ───────────────────────────────────────────────────────────

@router.get("", response_model=PaymentListOut)
async def list_payments(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    person_id: Optional[uuid.UUID] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("odeme:read")),
    db: AsyncSession = Depends(get_db),
) -> PaymentListOut:
    q = (
        select(Payment)
        .options(selectinload(Payment.person))
        .where(
            Payment.club_id == club_id,
            Payment.is_deleted.is_(False),
        )
    )
    # Own-scope: veli yalnızca bağlı sporcuların ödemelerini görür
    if is_own_scope_only(current_user.role, "odeme:read"):
        ward_ids = await _get_ward_ids(uuid.UUID(current_user.sub), club_id, db)
        if not ward_ids:
            return PaymentListOut(items=[], total=0, skip=skip, limit=limit)
        q = q.where(Payment.person_id.in_(ward_ids))
        person_id = None  # own-scope'da dışarıdan person_id filtresi kabul edilmez

    if status_filter:
        q = q.where(Payment.status == status_filter)
    if person_id:
        q = q.where(Payment.person_id == person_id)

    total_result = await db.execute(
        select(func.count()).select_from(q.subquery())
    )
    total = total_result.scalar_one()

    result = await db.execute(
        q.order_by(Payment.due_date.asc().nulls_last(), Payment.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    payments = result.scalars().all()

    return PaymentListOut(
        items=[_to_out(p) for p in payments],
        total=total,
        skip=skip,
        limit=limit,
    )


# ─── Gecikmiş ödemeler ───────────────────────────────────────────────────────

@router.get("/overdue", response_model=List[OverduePaymentOut])
async def list_overdue(
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("odeme:read")),
    db: AsyncSession = Depends(get_db),
) -> List[OverduePaymentOut]:
    """Flask /api/odemeler/gecikmusler karşılığı.

    Koşul: status='pending' AND due_date < today
    gecikme_gun: Python katmanında hesaplanır (julianday yerine).
    """
    today = date.today()
    q = (
        select(Payment)
        .options(selectinload(Payment.person))
        .where(
            Payment.club_id == club_id,
            Payment.status == "pending",
            Payment.due_date < today,
            Payment.is_deleted.is_(False),
        )
        .order_by(Payment.due_date.asc())
    )
    # Own-scope: veli yalnızca ward'larının gecikmiş ödemelerini görür
    if is_own_scope_only(current_user.role, "odeme:read"):
        ward_ids = await _get_ward_ids(uuid.UUID(current_user.sub), club_id, db)
        if not ward_ids:
            return []
        q = q.where(Payment.person_id.in_(ward_ids))
    result = await db.execute(q)
    payments = result.scalars().all()

    items = []
    for p in payments:
        base = _to_out(p)
        gecikme = (today - p.due_date).days if p.due_date else 0
        items.append(OverduePaymentOut(**base.model_dump(), gecikme_gun=gecikme))

    # gecikme_gun azalan sıra (en çok geciken başta — Flask ORDER BY gecikme_gun DESC)
    items.sort(key=lambda x: x.gecikme_gun, reverse=True)
    return items


# ─── Gelir raporu ─────────────────────────────────────────────────────────────

@router.get("/revenue-report", response_model=RevenueReport)
async def revenue_report(
    months: int = Query(default=12, ge=1, le=60),
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("rapor:read")),
    db: AsyncSession = Depends(get_db),
) -> RevenueReport:
    """Flask /api/raporlar/gelir karşılığı.

    Son N ay içinde durum='paid' ödemeler, ay + ödeme_türü bazında gruplandırılır.
    """

    # PostgreSQL: date_trunc; SQLite: strftime
    bind = db.get_bind() if hasattr(db, "get_bind") else None
    is_pg = True  # AsyncSession ile dialect kontrolü

    # Güvenli yol: SQLAlchemy func kullanarak dialect-agnostic yaz
    # PostgreSQL: to_char(paid_at, 'YYYY-MM'); SQLite: strftime('%Y-%m', paid_at)
    # Her iki dialect'te çalışan tek yol: Python'da group etmek
    cutoff = date.today().replace(day=1)
    # months ay geriye git
    y, m = cutoff.year, cutoff.month
    for _ in range(months - 1):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    cutoff = date(y, m, 1)

    result = await db.execute(
        select(Payment)
        .where(
            Payment.club_id == club_id,
            Payment.status == "paid",
            Payment.is_deleted.is_(False),
            Payment.paid_at >= cutoff,
        )
        .order_by(Payment.paid_at.asc())
    )
    payments = result.scalars().all()

    # Python'da gruplama — dialect-agnostic, test edilmesi kolay
    from collections import defaultdict
    groups: dict[tuple, list[Decimal]] = defaultdict(list)
    for p in payments:
        ay = p.paid_at.strftime("%Y-%m") if p.paid_at else "unknown"
        groups[(ay, p.payment_type)].append(p.amount)

    items = []
    for (ay, ptype), amounts in sorted(groups.items()):
        items.append(
            RevenueByMonth(
                ay=ay,
                payment_type=ptype,
                toplam=sum(amounts),
                adet=len(amounts),
            )
        )

    # Son N ay sıralı (en yeni önce — Flask ORDER BY ay DESC)
    items.sort(key=lambda x: x.ay, reverse=True)

    toplam_gelir = sum(i.toplam for i in items)
    return RevenueReport(items=items, toplam_gelir=toplam_gelir)


# ─── Tekil ödeme ─────────────────────────────────────────────────────────────

@router.get("/{payment_id}", response_model=PaymentOut)
async def get_payment(
    payment_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("odeme:read")),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    p = await _get_payment(payment_id, club_id, db)
    # Own-scope: veli yalnızca ward'larının ödemesini görebilir
    if is_own_scope_only(current_user.role, "odeme:read"):
        ward_ids = await _get_ward_ids(uuid.UUID(current_user.sub), club_id, db)
        if p.person_id not in ward_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu ödemeye erişim yetkiniz yok.",
            )
    return _to_out(p)


# ─── Ödeme oluştur ────────────────────────────────────────────────────────────

@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: PaymentCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("odeme:write")),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    # person_id bu kulübe ait mi?
    if body.person_id is not None:
        pr = await db.execute(
            select(Person).where(
                Person.id == body.person_id,
                Person.club_id == club_id,
                Person.is_deleted.is_(False),
            )
        )
        if pr.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Belirtilen kişi bu kulüpte bulunamadı.",
            )

    payment = Payment(
        id=uuid.uuid4(),
        club_id=club_id,
        recorded_by_user_id=uuid.UUID(current_user.sub),
        person_id=body.person_id,
        amount=body.amount,
        payment_type=body.payment_type,
        payment_method=body.payment_method,
        due_date=body.due_date,
        paid_at=body.paid_at,
        status=body.status,
        receipt_no=body.receipt_no,
        notes=body.notes,
    )
    db.add(payment)
    await db.flush()
    await db.refresh(payment)

    await log_action(
        db,
        action="payment_created",
        resource_type="payment",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(payment.id),
        after={
            "amount": str(payment.amount),
            "status": payment.status,
            "payment_type": payment.payment_type or "",
        },
        request=request,
    )

    await emit_event(
        db,
        club_id=club_id,
        event_type="payment.created",
        aggregate_type="payment",
        aggregate_id=payment.id,
        payload={
            "amount": str(payment.amount),
            "payment_type": payment.payment_type,
            "status": payment.status,
            "due_date": str(payment.due_date) if payment.due_date else None,
            "person_id": str(payment.person_id) if payment.person_id else None,
        },
    )

    # person ilişkisini yükle
    if payment.person_id:
        await db.refresh(payment, ["person"])
    return _to_out(payment)


# ─── Ödeme güncelle ──────────────────────────────────────────────────────────

@router.put("/{payment_id}", response_model=PaymentOut)
async def update_payment(
    payment_id: uuid.UUID,
    body: PaymentUpdate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("odeme:write")),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    payment = await _get_payment(payment_id, club_id, db)
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        return _to_out(payment)

    before = {k: str(getattr(payment, k, "")) for k in update_data}
    for field, value in update_data.items():
        setattr(payment, field, value)
    await db.flush()
    # server-side updated_at için refresh (6A dersi)
    await db.refresh(payment)

    await log_action(
        db,
        action="payment_updated",
        resource_type="payment",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(payment.id),
        before=before,
        after={k: str(v) for k, v in update_data.items()},
        request=request,
    )

    return _to_out(payment)


# ─── Ödeme sil (soft delete) ─────────────────────────────────────────────────

@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    payment_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("odeme:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    payment = await _get_payment(payment_id, club_id, db)
    payment.is_deleted = True
    await db.flush()

    await log_action(
        db,
        action="payment_deleted",
        resource_type="payment",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(payment.id),
        request=request,
    )
