"""Üyelik başvurusu CRUD + PDF + imza endpoint'leri.

Güvenlik kuralları:
  - club_id JWT'den alınır, request body/path/query'den asla.
  - pdf_object_key ve signature_object_key istemciye açılmaz.
  - Onay/ret işlemleri kisi:approve izni gerektirir.
  - WeasyPrint bağımlılıkları bu dosyada yok — yalnızca pdf-service'e HTTP isteği atılır.
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.core.rbac import require_permission
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.dependencies.storage import get_storage
from app.models.membership_application import (
    MembershipApplication,
    NO_DELETE_STATUSES,
    APPROVE_REQUIRED_TRANSITIONS,
    is_valid_transition,
    requires_approval,
)
from app.schemas.auth import TokenPayload
from app.schemas.membership import (
    MembershipApplicationCreate,
    MembershipApplicationListOut,
    MembershipApplicationOut,
    MembershipApplicationUpdate,
    MembershipPdfOut,
    MembershipSignatureOut,
    MembershipStatusTransition,
)
from app.services.storage import ObjectStorageService
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/membership-applications", tags=["membership-applications"])

# URL TTL sabit
PDF_SIG_URL_EXPIRES = 900   # 15 dakika
SIGNATURE_MAX_BYTES = 4 * 1024 * 1024   # 4 MB

ALLOWED_SIGNATURE_MIMES = {"image/png", "image/jpeg", "image/webp"}
MAGIC_BYTES: dict[bytes, str] = {
    b"\x89PNG":  "image/png",
    b"\xff\xd8": "image/jpeg",
    b"RIFF":     "image/webp",   # RIFF....WEBP
}


def _detect_mime(data: bytes) -> Optional[str]:
    for magic, mime in MAGIC_BYTES.items():
        if data[:len(magic)] == magic:
            if mime == "image/webp" and data[8:12] != b"WEBP":
                continue
            return mime
    return None


async def _get_application(
    app_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> MembershipApplication:
    result = await db.execute(
        select(MembershipApplication).where(
            MembershipApplication.id == app_id,
            MembershipApplication.club_id == club_id,
            MembershipApplication.is_deleted.is_(False),
        )
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Başvuru bulunamadı.")
    return app


async def _generate_application_number(
    club_id: uuid.UUID,
    year: int,
    db: AsyncSession,
) -> str:
    """Yarış koşuluna dayanıklı başvuru numarası üret.

    PostgreSQL ve SQLite 3.24+ üzerinde atomic upsert ile çalışır.
    Format: MYK-{YYYY}-{N:06d}
    """
    # SQLite ve PostgreSQL uyumlu dialect-aware upsert
    bind = db.get_bind() if hasattr(db, "get_bind") else None

    # dialect adını async bağlamda almak için sync_engine kullan
    try:
        engine = db.get_bind()
        dialect = engine.dialect.name if engine else "postgresql"
    except Exception:
        dialect = "postgresql"

    if dialect == "postgresql":
        sql = text("""
            INSERT INTO application_counters (club_id, year, last_number)
            VALUES (:club_id, :year, 1)
            ON CONFLICT (club_id, year)
            DO UPDATE SET last_number = application_counters.last_number + 1
            RETURNING last_number
        """)
    else:
        # SQLite 3.24+ upsert sözdizimi
        sql = text("""
            INSERT INTO application_counters (club_id, year, last_number)
            VALUES (:club_id, :year, 1)
            ON CONFLICT (club_id, year)
            DO UPDATE SET last_number = last_number + 1
            RETURNING last_number
        """)

    result = await db.execute(sql, {"club_id": str(club_id), "year": year})
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Başvuru numarası üretilemedi.",
        )
    return f"MYK-{year}-{row[0]:06d}"


def _build_out(
    app: MembershipApplication,
    pdf_url: Optional[str] = None,
    signature_url: Optional[str] = None,
) -> MembershipApplicationOut:
    return MembershipApplicationOut.from_orm_safe(app, pdf_url=pdf_url, signature_url=signature_url)


# ── POST /membership-applications ────────────────────────────────────────────

@router.post("", response_model=MembershipApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application(
    body: MembershipApplicationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("kisi:write")),
) -> MembershipApplicationOut:
    app = MembershipApplication(
        club_id=club_id,
        status="draft",
        **body.model_dump(exclude_unset=True),
    )
    db.add(app)
    await db.flush()   # id üretilsin

    await log_action(
        db,
        action="membership_application_created",
        resource_type="membership_application",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(app.id),
        after={"status": app.status},
        request=request,
    )
    await db.commit()
    await db.refresh(app)
    return _build_out(app)


# ── GET /membership-applications ─────────────────────────────────────────────

@router.get("", response_model=MembershipApplicationListOut)
async def list_applications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    storage: ObjectStorageService = Depends(get_storage),
    _: None = Depends(require_permission("kisi:read")),
) -> MembershipApplicationListOut:
    q = select(MembershipApplication).where(
        MembershipApplication.club_id == club_id,
        MembershipApplication.is_deleted.is_(False),
    )
    if status_filter:
        q = q.where(MembershipApplication.status == status_filter)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.offset(skip).limit(limit).order_by(MembershipApplication.created_at.desc())
    rows = (await db.execute(q)).scalars().all()

    # Batch pre-signed URL üretimi
    pdf_keys = [r.pdf_object_key for r in rows if r.pdf_object_key]
    sig_keys = [r.signature_object_key for r in rows if r.signature_object_key]
    all_keys = list(set(pdf_keys + sig_keys))
    url_map: dict[str, str] = {}
    if all_keys:
        url_map = await storage.presigned_url_batch(all_keys, expires=PDF_SIG_URL_EXPIRES)

    items = [
        _build_out(
            r,
            pdf_url=url_map.get(r.pdf_object_key) if r.pdf_object_key else None,
            signature_url=url_map.get(r.signature_object_key) if r.signature_object_key else None,
        )
        for r in rows
    ]
    return MembershipApplicationListOut(items=items, total=total, skip=skip, limit=limit)


# ── GET /membership-applications/{id} ────────────────────────────────────────

@router.get("/{app_id}", response_model=MembershipApplicationOut)
async def get_application(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    storage: ObjectStorageService = Depends(get_storage),
    _: None = Depends(require_permission("kisi:read")),
) -> MembershipApplicationOut:
    app = await _get_application(app_id, club_id, db)

    pdf_url = None
    sig_url = None
    if app.pdf_object_key:
        pdf_url = await storage.presigned_url(app.pdf_object_key, expires=PDF_SIG_URL_EXPIRES)
    if app.signature_object_key:
        sig_url = await storage.presigned_url(app.signature_object_key, expires=PDF_SIG_URL_EXPIRES)

    return _build_out(app, pdf_url=pdf_url, signature_url=sig_url)


# ── PATCH /membership-applications/{id} (alan güncelleme) ─────────────────────

@router.patch("/{app_id}", response_model=MembershipApplicationOut)
async def update_application(
    app_id: uuid.UUID,
    body: MembershipApplicationUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    storage: ObjectStorageService = Depends(get_storage),
    _: None = Depends(require_permission("kisi:write")),
) -> MembershipApplicationOut:
    app = await _get_application(app_id, club_id, db)

    if app.status not in {"draft", "submitted"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{app.status}' durumundaki başvuru güncellenemez.",
        )

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(app, field, value)

    await log_action(
        db,
        action="membership_application_updated",
        resource_type="membership_application",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(app.id),
        after={"fields_updated": list(updates.keys())},
        request=request,
    )
    await db.commit()
    await db.refresh(app)

    pdf_url = None
    sig_url = None
    if app.pdf_object_key:
        pdf_url = await storage.presigned_url(app.pdf_object_key, expires=PDF_SIG_URL_EXPIRES)
    if app.signature_object_key:
        sig_url = await storage.presigned_url(app.signature_object_key, expires=PDF_SIG_URL_EXPIRES)

    return _build_out(app, pdf_url=pdf_url, signature_url=sig_url)


# ── PATCH /membership-applications/{id}/status ────────────────────────────────

@router.patch("/{app_id}/status", response_model=MembershipApplicationOut)
async def transition_status(
    app_id: uuid.UUID,
    body: MembershipStatusTransition,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    storage: ObjectStorageService = Depends(get_storage),
) -> MembershipApplicationOut:
    from app.core.rbac import has_permission

    app = await _get_application(app_id, club_id, db)
    from_status = app.status
    to_status = body.to_status

    if not is_valid_transition(from_status, to_status):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{from_status}' → '{to_status}' geçişi geçerli değil.",
        )

    # Onay/ret yalnızca kisi:approve yetkisiyle
    if requires_approval(from_status, to_status):
        if not has_permission(current_user.role, "kisi:approve"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için 'kisi:approve' yetkisi gerekiyor.",
            )

    # kisi:write olmadan draft/submitted/cancelled geçişleri de yapılamaz
    if not requires_approval(from_status, to_status):
        if not has_permission(current_user.role, "kisi:write"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için 'kisi:write' yetkisi gerekiyor.",
            )

    now = datetime.now(timezone.utc)
    app.status = to_status

    if to_status == "submitted":
        app.submitted_at = now
        # İlk gönderimde application_number üret
        if not app.application_number:
            app.application_number = await _generate_application_number(
                club_id, now.year, db
            )
        # Rıza zaman damgası
        if body.reason is None and not app.consent_accepted_at:
            app.consent_accepted_at = now
    elif to_status == "approved":
        app.approved_at = now
        app.approved_by_user_id = uuid.UUID(current_user.sub)
    elif to_status == "rejected":
        app.rejected_at = now
        if body.reason:
            app.rejection_reason = body.reason
    elif to_status == "cancelled":
        app.cancelled_at = now
        if body.reason:
            app.cancellation_reason = body.reason
    elif to_status == "draft":
        # Reddedilmiş başvuru yeniden taslak durumuna alınır
        app.rejected_at = None
        app.rejection_reason = None

    await log_action(
        db,
        action="membership_application_status_changed",
        resource_type="membership_application",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(app.id),
        before={"status": from_status},
        after={"status": to_status, "application_number": app.application_number},
        request=request,
    )
    await db.commit()
    await db.refresh(app)

    pdf_url = None
    sig_url = None
    if app.pdf_object_key:
        pdf_url = await storage.presigned_url(app.pdf_object_key, expires=PDF_SIG_URL_EXPIRES)
    if app.signature_object_key:
        sig_url = await storage.presigned_url(app.signature_object_key, expires=PDF_SIG_URL_EXPIRES)

    return _build_out(app, pdf_url=pdf_url, signature_url=sig_url)


# ── DELETE /membership-applications/{id} ──────────────────────────────────────

@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_application(
    app_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("kisi:write")),
) -> None:
    app = await _get_application(app_id, club_id, db)

    if app.status in NO_DELETE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{app.status}' durumundaki başvuru silinemez.",
        )

    app.is_deleted = True
    await log_action(
        db,
        action="membership_application_deleted",
        resource_type="membership_application",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(app.id),
        before={"status": app.status},
        request=request,
    )
    await db.commit()


# ── PDF Endpoint'leri ─────────────────────────────────────────────────────────

@router.post("/{app_id}/generate-pdf", response_model=MembershipPdfOut)
async def generate_pdf(
    app_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    storage: ObjectStorageService = Depends(get_storage),
    _: None = Depends(require_permission("kisi:write")),
) -> MembershipPdfOut:
    app = await _get_application(app_id, club_id, db)
    settings = get_settings()

    # pdf-service'e render isteği gönder
    payload = {
        "application_number": app.application_number,
        "first_name": app.first_name,
        "last_name": app.last_name,
        "national_id": app.national_id,
        "birth_date": app.birth_date.isoformat() if app.birth_date else None,
        "gender": app.gender,
        "phone": app.phone,
        "email": app.email,
        "address": app.address,
        "guardian_name": app.guardian_name,
        "guardian_phone": app.guardian_phone,
        "status": app.status,
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.pdf_service_url}/render/membership-application",
                json=payload,
            )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PDF servisi başarısız yanıt döndürdü.",
            )
        pdf_bytes = resp.content
    except httpx.RequestError as exc:
        logger.error("pdf-service bağlantı hatası: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF servisi erişilemiyor.",
        )

    # Object storage'a yükle
    object_key = f"clubs/{club_id}/membership-applications/{app_id}/application.pdf"
    await storage.upload(object_key, pdf_bytes, content_type="application/pdf")

    # SHA-256
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    now = datetime.now(timezone.utc)

    app.pdf_object_key = object_key
    app.pdf_sha256 = sha256
    app.pdf_generated_at = now

    await log_action(
        db,
        action="membership_pdf_generated",
        resource_type="membership_application",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(app.id),
        after={"pdf_generated_at": now.isoformat(), "pdf_size_bytes": len(pdf_bytes)},
        request=request,
    )
    await db.commit()

    pdf_url = await storage.presigned_url(object_key, expires=PDF_SIG_URL_EXPIRES)
    return MembershipPdfOut(
        has_pdf=True,
        pdf_url=pdf_url,
        expires_in=PDF_SIG_URL_EXPIRES,
        generated_at=now,
    )


@router.get("/{app_id}/pdf-url", response_model=MembershipPdfOut)
async def get_pdf_url(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    storage: ObjectStorageService = Depends(get_storage),
    _: None = Depends(require_permission("kisi:read")),
) -> MembershipPdfOut:
    app = await _get_application(app_id, club_id, db)

    if not app.pdf_object_key:
        return MembershipPdfOut(has_pdf=False)

    pdf_url = await storage.presigned_url(app.pdf_object_key, expires=PDF_SIG_URL_EXPIRES)
    return MembershipPdfOut(
        has_pdf=True,
        pdf_url=pdf_url,
        expires_in=PDF_SIG_URL_EXPIRES,
        generated_at=app.pdf_generated_at,
    )


# ── İmza Endpoint'leri ────────────────────────────────────────────────────────

@router.post("/{app_id}/signature", response_model=MembershipSignatureOut)
async def upload_signature(
    app_id: uuid.UUID,
    file: UploadFile = File(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    storage: ObjectStorageService = Depends(get_storage),
    _: None = Depends(require_permission("kisi:write")),
) -> MembershipSignatureOut:
    app = await _get_application(app_id, club_id, db)

    raw = await file.read(SIGNATURE_MAX_BYTES + 1)
    if len(raw) > SIGNATURE_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"İmza dosyası {SIGNATURE_MAX_BYTES // (1024*1024)} MB sınırını aşıyor.",
        )

    mime = _detect_mime(raw)
    if mime not in ALLOWED_SIGNATURE_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Desteklenen formatlar: {sorted(ALLOWED_SIGNATURE_MIMES)}",
        )

    object_key = f"clubs/{club_id}/membership-applications/{app_id}/signature{_ext_for(mime)}"
    await storage.upload(object_key, raw, content_type=mime)

    sha256 = hashlib.sha256(raw).hexdigest()
    now = datetime.now(timezone.utc)

    app.signature_object_key = object_key
    app.signature_sha256 = sha256
    app.signed_at = now
    app.signed_by_user_id = uuid.UUID(current_user.sub)

    await log_action(
        db,
        action="membership_signature_uploaded",
        resource_type="membership_application",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(app.id),
        after={"mime_type": mime, "size_bytes": len(raw)},
        request=request,
    )
    await db.commit()

    sig_url = await storage.presigned_url(object_key, expires=PDF_SIG_URL_EXPIRES)
    return MembershipSignatureOut(
        has_signature=True,
        signature_url=sig_url,
        expires_in=PDF_SIG_URL_EXPIRES,
        signed_at=now,
    )


@router.delete("/{app_id}/signature", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_signature(
    app_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    storage: ObjectStorageService = Depends(get_storage),
    _: None = Depends(require_permission("kisi:write")),
) -> None:
    app = await _get_application(app_id, club_id, db)

    if app.signature_object_key:
        await storage.delete(app.signature_object_key)

    app.signature_object_key = None
    app.signature_sha256 = None
    app.signed_at = None
    app.signed_by_user_id = None

    await log_action(
        db,
        action="membership_signature_deleted",
        resource_type="membership_application",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(app.id),
        request=request,
    )
    await db.commit()


@router.get("/{app_id}/signature-url", response_model=MembershipSignatureOut)
async def get_signature_url(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
    club_id: uuid.UUID = Depends(get_club_id),
    storage: ObjectStorageService = Depends(get_storage),
    _: None = Depends(require_permission("kisi:read")),
) -> MembershipSignatureOut:
    app = await _get_application(app_id, club_id, db)

    if not app.signature_object_key:
        return MembershipSignatureOut(has_signature=False)

    sig_url = await storage.presigned_url(app.signature_object_key, expires=PDF_SIG_URL_EXPIRES)
    return MembershipSignatureOut(
        has_signature=True,
        signature_url=sig_url,
        expires_in=PDF_SIG_URL_EXPIRES,
        signed_at=app.signed_at,
    )


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _ext_for(mime: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(mime, ".bin")
