"""Kişisel evrak API — tenant, guardian, scan ve hassas veri korumalı."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit import log_action
from app.core.rbac import has_permission
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.dependencies.documents_storage import get_dms_storage
from app.dependencies.person_document_scan import get_person_document_scanner
from app.dependencies.person_document_policy import get_health_document_legal_gate
from app.models.person_document import DOCUMENT_TYPES, PersonDocument
from app.schemas.auth import TokenPayload
from app.schemas.person_document import (
    DeleteRequestBody,
    DeleteRequestOut,
    HealthDocumentSummaryOut,
    PersonDocumentOut,
    RejectionBody,
)
from app.services.malware_scan import MalwareScanner
from app.services.person_document_service import (
    enforce_upload_quota,
    assert_guardian_upload_age,
    get_active_guardian_link,
    get_active_user,
    get_subject_or_404,
    validate_file,
)
from app.services.storage import ObjectStorageService
from app.services.training_scope_service import get_antrenor_enrolled_person_ids

router = APIRouter(prefix="/person-documents", tags=["person-documents"])
settings = get_settings()
DOWNLOADABLE_SCAN_STATUSES = {"clean", "skipped_dev"}
ADMIN_ROLES = {"super_admin", "kulup_yonetici"}


async def _access_context(
    subject_person_id: uuid.UUID,
    club_id: uuid.UUID,
    current_user: TokenPayload,
    db: AsyncSession,
):
    user = await get_active_user(current_user, club_id, db)
    subject = await get_subject_or_404(subject_person_id, club_id, db)
    link = None
    if current_user.role == "veli":
        assert_guardian_upload_age(subject.birth_date)
        link = await get_active_guardian_link(
            user.person_id, subject_person_id, club_id, db  # type: ignore[arg-type]
        )
    elif current_user.role not in ADMIN_ROLES and current_user.role != "saglik_sorumlusu":
        raise HTTPException(status_code=403, detail="Bu evraklara erişim yetkiniz yok.")
    return user, link


async def _get_document_or_404(
    document_id: uuid.UUID, club_id: uuid.UUID, db: AsyncSession
) -> PersonDocument:
    result = await db.execute(
        select(PersonDocument).where(
            PersonDocument.id == document_id,
            PersonDocument.club_id == club_id,
            PersonDocument.is_deleted.is_(False),
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Evrak bulunamadı.")
    return document


@router.post("", response_model=PersonDocumentOut, status_code=201)
async def upload_person_document(
    request: Request,
    subject_person_id: uuid.UUID = Form(...),
    document_type: str = Form(...),
    valid_until: date | None = Form(None),
    processing_basis: str | None = Form(None),
    file: UploadFile = File(...),
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorageService = Depends(get_dms_storage),
    scanner: MalwareScanner | None = Depends(get_person_document_scanner),
    health_legal_gate: bool = Depends(get_health_document_legal_gate),
) -> PersonDocumentOut:
    user, guardian_link = await _access_context(
        subject_person_id, club_id, current_user, db
    )
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail="Geçersiz evrak türü.")
    basis = processing_basis.strip() if processing_basis else None
    if document_type == "health_report" and not basis:
        raise HTTPException(status_code=403, detail="Sağlık verisi işleme dayanağı tanımlı değil.")
    if (
        document_type == "health_report"
        and settings.myk_env == "production"
        and not health_legal_gate
    ):
        raise HTTPException(
            status_code=403,
            detail="Sağlık evrakı için onaylı hukuki metin etkin değil.",
        )
    if settings.myk_env == "production" and scanner is None:
        raise HTTPException(status_code=503, detail="Dosya tarama servisi kullanılamıyor.")

    data = await file.read()
    mime = validate_file(data, file.content_type)
    await enforce_upload_quota(
        club_id=club_id,
        user_id=user.id,
        subject_person_id=subject_person_id,
        incoming_size=len(data),
        db=db,
    )

    scan_status = "skipped_dev" if scanner is None else await scanner.scan(data, mime)
    if scan_status == "skipped_dev" and settings.myk_env == "production":
        raise HTTPException(status_code=503, detail="Production taraması atlanamaz.")

    document_id = uuid.uuid4()
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in (file.filename or "upload"))
    storage_key = f"clubs/{club_id}/person-documents/{subject_person_id}/{document_id}/{safe_name}"
    await storage.upload(storage_key, data, mime)
    document = PersonDocument(
        id=document_id,
        club_id=club_id,
        subject_person_id=subject_person_id,
        uploaded_by_user_id=user.id,
        guardian_link_id=guardian_link.id if guardian_link else None,
        document_type=document_type,
        original_filename=file.filename or "upload",
        storage_key=storage_key,
        mime_type=mime,
        size_bytes=len(data),
        valid_until=valid_until,
        processing_basis=basis,
        scan_status=scan_status,
        is_sensitive=document_type == "health_report",
    )
    try:
        db.add(document)
        await db.flush()
        await db.refresh(document)
    except Exception:
        await storage.delete(storage_key)
        raise
    await log_action(
        db,
        action="person_document_uploaded",
        resource_type="person_document",
        resource_id=str(document.id),
        club_id=club_id,
        user_id=user.id,
        after={"subject_person_id": str(subject_person_id), "document_type": document_type, "size_bytes": len(data), "scan_status": scan_status},
        request=request,
    )
    return PersonDocumentOut.model_validate(document)


@router.get("/health-summary/{subject_person_id}", response_model=HealthDocumentSummaryOut)
async def health_document_summary(
    subject_person_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HealthDocumentSummaryOut:
    await get_subject_or_404(subject_person_id, club_id, db)
    if current_user.role not in ADMIN_ROLES | {"saglik_sorumlusu", "antrenor", "basantrenor", "sportif_direktor"}:
        raise HTTPException(status_code=403, detail="Sağlık evrakı özetine erişim yetkiniz yok.")
    if current_user.role in {"antrenor", "basantrenor"}:
        allowed = await get_antrenor_enrolled_person_ids(
            uuid.UUID(current_user.sub), club_id, db
        )
        if subject_person_id not in allowed:
            raise HTTPException(status_code=403, detail="Bu sporcu için yetkiniz yok.")
    result = await db.execute(
        select(PersonDocument).where(
            PersonDocument.club_id == club_id,
            PersonDocument.subject_person_id == subject_person_id,
            PersonDocument.document_type == "health_report",
            PersonDocument.is_deleted.is_(False),
            PersonDocument.review_status != "superseded",
        ).order_by(PersonDocument.uploaded_at.desc())
    )
    document = result.scalars().first()
    return HealthDocumentSummaryOut(
        subject_person_id=subject_person_id,
        exists=document is not None,
        valid_until=document.valid_until if document else None,
    )


@router.get("", response_model=list[PersonDocumentOut])
async def list_person_documents(
    subject_person_id: uuid.UUID = Query(...),
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PersonDocumentOut]:
    await _access_context(subject_person_id, club_id, current_user, db)
    result = await db.execute(
        select(PersonDocument).where(
            PersonDocument.club_id == club_id,
            PersonDocument.subject_person_id == subject_person_id,
            PersonDocument.is_deleted.is_(False),
        ).order_by(PersonDocument.uploaded_at.desc())
    )
    return [PersonDocumentOut.model_validate(row) for row in result.scalars().all()]


@router.get("/{document_id}", response_model=PersonDocumentOut)
async def view_person_document(
    document_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PersonDocumentOut:
    document = await _get_document_or_404(document_id, club_id, db)
    user, _ = await _access_context(document.subject_person_id, club_id, current_user, db)
    await log_action(db, action="person_document_metadata_viewed", resource_type="person_document", resource_id=str(document.id), club_id=club_id, user_id=user.id, request=request)
    return PersonDocumentOut.model_validate(document)


def _assert_file_access(document: PersonDocument, current_user: TokenPayload) -> None:
    if document.document_type == "health_report" and current_user.role != "veli" and not has_permission(current_user.role, "health_file:read"):
        raise HTTPException(status_code=403, detail="Sağlık raporu dosyasına erişim yetkiniz yok.")
    if document.scan_status in {"pending", "infected", "failed"}:
        raise HTTPException(status_code=423, detail="Dosya tarama bekleniyor veya güvenli değil")
    elif document.scan_status not in DOWNLOADABLE_SCAN_STATUSES:
        raise HTTPException(status_code=423, detail="Dosya güvenlik taramasını geçmedi.")
    if document.scan_status == "skipped_dev" and settings.myk_env == "production":
        raise HTTPException(status_code=423, detail="Production dosyası taranmamış.")


async def _stream_document(
    document: PersonDocument,
    *,
    inline: bool,
    action: str,
    request: Request,
    club_id: uuid.UUID,
    current_user: TokenPayload,
    user_id: uuid.UUID,
    db: AsyncSession,
    storage: ObjectStorageService,
) -> Response:
    _assert_file_access(document, current_user)
    try:
        data = await storage.download(document.storage_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.") from exc
    await log_action(db, action=action, resource_type="person_document", resource_id=str(document.id), club_id=club_id, user_id=user_id, request=request)
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in document.original_filename)
    disposition = "inline" if inline else "attachment"
    return Response(content=data, media_type=document.mime_type, headers={"Content-Disposition": f'{disposition}; filename="{safe_name}"'})


@router.get("/{document_id}/view")
async def view_person_document_file(
    document_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorageService = Depends(get_dms_storage),
) -> Response:
    document = await _get_document_or_404(document_id, club_id, db)
    user, _ = await _access_context(document.subject_person_id, club_id, current_user, db)
    return await _stream_document(document, inline=True, action="person_document_viewed", request=request, club_id=club_id, current_user=current_user, user_id=user.id, db=db, storage=storage)


@router.get("/{document_id}/download")
async def download_person_document(
    document_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorageService = Depends(get_dms_storage),
) -> Response:
    document = await _get_document_or_404(document_id, club_id, db)
    user, _ = await _access_context(document.subject_person_id, club_id, current_user, db)
    return await _stream_document(document, inline=False, action="person_document_downloaded", request=request, club_id=club_id, current_user=current_user, user_id=user.id, db=db, storage=storage)


_REVIEWER_ROLES = ADMIN_ROLES | {"antrenor", "basantrenor"}


@router.patch("/{document_id}/approve", response_model=PersonDocumentOut)
async def approve_person_document(
    document_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PersonDocumentOut:
    if current_user.role not in _REVIEWER_ROLES:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok.")
    document = await _get_document_or_404(document_id, club_id, db)
    if document.is_sensitive and current_user.role in {"antrenor", "basantrenor"}:
        raise HTTPException(status_code=403, detail="Hassas belgeyi onaylama yetkiniz yok.")
    user = await get_active_user(current_user, club_id, db)
    document.review_status = "approved"
    document.reviewed_by_user_id = user.id
    document.reviewed_at = datetime.now(timezone.utc)
    document.rejection_reason = None
    await db.flush()
    await db.refresh(document)
    await log_action(
        db,
        action="person_document_approved",
        resource_type="person_document",
        resource_id=str(document.id),
        club_id=club_id,
        user_id=user.id,
        request=request,
    )
    return PersonDocumentOut.model_validate(document)


@router.patch("/{document_id}/reject", response_model=PersonDocumentOut)
async def reject_person_document(
    document_id: uuid.UUID,
    body: RejectionBody,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PersonDocumentOut:
    if current_user.role not in _REVIEWER_ROLES:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok.")
    document = await _get_document_or_404(document_id, club_id, db)
    if document.is_sensitive and current_user.role in {"antrenor", "basantrenor"}:
        raise HTTPException(status_code=403, detail="Hassas belgeyi reddetme yetkiniz yok.")
    user = await get_active_user(current_user, club_id, db)
    document.review_status = "rejected"
    document.rejection_reason = body.rejection_reason
    document.reviewed_by_user_id = user.id
    document.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(document)
    await log_action(
        db,
        action="person_document_rejected",
        resource_type="person_document",
        resource_id=str(document.id),
        club_id=club_id,
        user_id=user.id,
        request=request,
    )
    return PersonDocumentOut.model_validate(document)


# ─────────────────────────────────────────────────────────────────────────────
# Silme isteği akışı
# ─────────────────────────────────────────────────────────────────────────────

_DELETE_REQUEST_ROLES = {"veli", "kulup_yonetici", "super_admin"}


@router.post("/{document_id}/delete-request", response_model=DeleteRequestOut, status_code=201)
async def request_document_delete(
    document_id: uuid.UUID,
    body: DeleteRequestBody,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeleteRequestOut:
    if current_user.role not in _DELETE_REQUEST_ROLES:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok.")
    document = await _get_document_or_404(document_id, club_id, db)
    user = await get_active_user(current_user, club_id, db)

    if current_user.role == "veli":
        # Velinin kendi çocuğunun evrakı olduğunu doğrula
        await get_active_guardian_link(
            user.person_id, document.subject_person_id, club_id, db  # type: ignore[arg-type]
        )

    # Zaten bekleyen bir istek varsa yeni istek açılmaz
    if document.delete_request:
        existing = json.loads(document.delete_request) if isinstance(document.delete_request, str) else document.delete_request
        if existing.get("status") == "pending":
            raise HTTPException(status_code=409, detail="Bu evrak için zaten bekleyen bir silme isteği var.")

    now = datetime.now(timezone.utc)
    payload = {
        "reason": body.reason,
        "requested_by_user_id": str(user.id),
        "status": "pending",
        "created_at": now.isoformat(),
    }
    document.delete_request = json.dumps(payload)
    await db.flush()
    await log_action(
        db,
        action="person_document_delete_requested",
        resource_type="person_document",
        resource_id=str(document.id),
        club_id=club_id,
        user_id=user.id,
        after={"reason": body.reason},
        request=request,
    )
    return DeleteRequestOut(
        id=document.id,
        document_id=document.id,
        requested_by_user_id=user.id,
        reason=body.reason,
        created_at=now,
        status="pending",
    )


@router.post("/{document_id}/delete-request/approve", response_model=PersonDocumentOut)
async def approve_document_delete_request(
    document_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PersonDocumentOut:
    if current_user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok.")
    document = await _get_document_or_404(document_id, club_id, db)
    if not document.delete_request:
        raise HTTPException(status_code=404, detail="Bu evrak için silme isteği bulunamadı.")
    dr = json.loads(document.delete_request) if isinstance(document.delete_request, str) else document.delete_request
    if dr.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Bekleyen bir silme isteği yok.")
    user = await get_active_user(current_user, club_id, db)
    dr["status"] = "approved"
    document.delete_request = json.dumps(dr)
    document.is_deleted = True
    await db.flush()
    await db.refresh(document)
    await log_action(
        db,
        action="document_deleted",
        resource_type="person_document",
        resource_id=str(document.id),
        club_id=club_id,
        user_id=user.id,
        after={"via": "delete_request_approved"},
        request=request,
    )
    return PersonDocumentOut.model_validate(document)


@router.post("/{document_id}/delete-request/reject", response_model=DeleteRequestOut)
async def reject_document_delete_request(
    document_id: uuid.UUID,
    body: RejectionBody,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeleteRequestOut:
    if current_user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok.")
    document = await _get_document_or_404(document_id, club_id, db)
    if not document.delete_request:
        raise HTTPException(status_code=404, detail="Bu evrak için silme isteği bulunamadı.")
    dr = json.loads(document.delete_request) if isinstance(document.delete_request, str) else document.delete_request
    if dr.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Bekleyen bir silme isteği yok.")
    user = await get_active_user(current_user, club_id, db)
    dr["status"] = "rejected"
    document.delete_request = json.dumps(dr)
    await db.flush()
    await log_action(
        db,
        action="person_document_delete_request_rejected",
        resource_type="person_document",
        resource_id=str(document.id),
        club_id=club_id,
        user_id=user.id,
        after={"rejection_reason": body.rejection_reason},
        request=request,
    )
    return DeleteRequestOut(
        id=document.id,
        document_id=document.id,
        requested_by_user_id=uuid.UUID(dr["requested_by_user_id"]),
        reason=dr.get("reason", ""),
        created_at=datetime.fromisoformat(dr["created_at"]),
        status="rejected",
    )


@router.delete("/{document_id}")
async def delete_person_document(
    document_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if current_user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok.")
    document = await _get_document_or_404(document_id, club_id, db)
    user = await get_active_user(current_user, club_id, db)
    document.is_deleted = True
    await db.flush()
    await log_action(
        db,
        action="document_deleted",
        resource_type="person_document",
        resource_id=str(document.id),
        club_id=club_id,
        user_id=user.id,
        after={"via": "admin_direct_delete"},
        request=request,
    )
    return {"deleted": True}
