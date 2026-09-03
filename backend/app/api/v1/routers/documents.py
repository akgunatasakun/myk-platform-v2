"""Documents router — Belge Yönetim Sistemi (DMS) API.

RBAC:
  okuma   → belge:read
  yazma   → belge:create
  silme   → belge:delete

Tenant izolasyonu: her sorgu club_id ile filtrelenir.
Storage: DMS ayrı bucket kullanır (myk-documents).
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid

logger = logging.getLogger(__name__)
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.audit import log_action
from app.core.rbac import has_permission, require_permission, is_own_scope_only
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.dependencies.documents_storage import get_dms_storage
from app.models.documents import Document, DocumentCategory, DocumentRevision, DocumentRevisionFile
from app.models.person_guardian import PersonGuardian
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.schemas.documents import (
    CategoryCreate,
    CategoryOut,
    DocumentCreate,
    DocumentDetailOut,
    DocumentOut,
    DocumentUpdate,
    RevisionCreate,
    RevisionDetailOut,
    RevisionFileOut,
    RevisionOut,
)
from app.services.storage import ObjectStorageService

router = APIRouter(prefix="/documents", tags=["documents"])


async def _get_doc_person_ids(
    user_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
    role: str,
) -> list[uuid.UUID]:
    """Own-scope için erişilebilir person_id listesi (belge owner_id'ye karşı)."""
    result = await db.execute(select(User.person_id).where(User.id == user_id))
    person_id: uuid.UUID | None = result.scalar_one_or_none()
    if not person_id:
        return []
    if role == "sporcu":
        return [person_id]
    if role == "veli":
        result = await db.execute(
            select(PersonGuardian.athlete_person_id).where(
                PersonGuardian.guardian_person_id == person_id,
                PersonGuardian.club_id == club_id,
            )
        )
        return list(result.scalars().all())
    return []

settings = get_settings()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/zip",
    "application/octet-stream",
}


def _safe_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)


async def _get_category_for_club(
    category_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> DocumentCategory:
    """category_id'nin aynı club'a ait olduğunu doğrular; değilse 404 fırlatır."""
    result = await db.execute(
        select(DocumentCategory).where(
            DocumentCategory.id == category_id,
            DocumentCategory.club_id == club_id,
        )
    )
    cat = result.scalar_one_or_none()
    if cat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kategori bulunamadı veya bu kulübe ait değil.",
        )
    return cat


async def _get_document_or_404(
    document_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
    *,
    load_revisions: bool = False,
) -> Document:
    q = select(Document).where(
        Document.id == document_id,
        Document.club_id == club_id,
        Document.is_deleted.is_(False),
    )
    if load_revisions:
        q = q.options(
            selectinload(Document.revisions).selectinload(DocumentRevision.files)
        )
    result = await db.execute(q)
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Belge bulunamadı.")
    return doc


async def _get_revision_or_404(
    revision_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession,
    *,
    load_files: bool = False,
) -> DocumentRevision:
    q = select(DocumentRevision).where(
        DocumentRevision.id == revision_id,
        DocumentRevision.document_id == document_id,
    )
    if load_files:
        q = q.options(selectinload(DocumentRevision.files))
    result = await db.execute(q)
    rev = result.scalar_one_or_none()
    if rev is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Revizyon bulunamadı."
        )
    return rev


# ── Belge listesi ─────────────────────────────────────────────────────────────

@router.get("", response_model=List[DocumentOut])
async def list_documents(
    q: Optional[str] = Query(default=None),
    document_type: Optional[str] = Query(default=None),
    content_status: Optional[str] = Query(default=None),
    owner_type: Optional[str] = Query(default=None),
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("belge:read")),
    db: AsyncSession = Depends(get_db),
) -> List[DocumentOut]:
    stmt = select(Document).where(
        Document.club_id == club_id,
        Document.is_deleted.is_(False),
    )
    # Own-scope: sporcu/veli yalnızca kendilerine ait (owner_type="person") belgeleri görür
    if is_own_scope_only(current_user.role, "belge:read"):
        person_ids = await _get_doc_person_ids(
            uuid.UUID(current_user.sub), club_id, db, current_user.role
        )
        if not person_ids:
            return []
        stmt = stmt.where(
            Document.owner_type == "person",
            Document.owner_id.in_(person_ids),
        )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Document.title.ilike(like) | Document.code.ilike(like)
        )
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    if owner_type:
        stmt = stmt.where(Document.owner_type == owner_type)
    if content_status:
        stmt = stmt.where(Document.content_status == content_status)

    result = await db.execute(stmt.order_by(Document.code.asc()))
    docs = result.scalars().all()
    return [DocumentOut.model_validate(d) for d in docs]


# ── Eğitim Kütüphanesi (kutuphane:read) ──────────────────────────────────────
# Bu rotalar /{document_id}'den önce tanımlanmalı (literal path önceliği).

TYF_CODE_PREFIX = "TYF-"


@router.get("/kutuphane", response_model=List[DocumentOut])
async def list_kutuphane_documents(
    q: Optional[str] = Query(default=None),
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("kutuphane:read")),
    db: AsyncSession = Depends(get_db),
) -> List[DocumentOut]:
    """TYF Eğitim Kütüphanesi — yalnızca TYF-* kodlu dokümanlar."""
    stmt = select(Document).where(
        Document.club_id == club_id,
        Document.is_deleted.is_(False),
        Document.code.like(f"{TYF_CODE_PREFIX}%"),
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Document.title.ilike(like) | Document.code.ilike(like))
    result = await db.execute(stmt.order_by(Document.code.asc()))
    return [DocumentOut.model_validate(d) for d in result.scalars().all()]


@router.get("/kutuphane/{document_id}", response_model=DocumentDetailOut)
async def get_kutuphane_document(
    document_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("kutuphane:read")),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailOut:
    """TYF Eğitim Kütüphanesi — tek doküman detayı (revizyon + dosyalar)."""
    doc = await _get_document_or_404(document_id, club_id, db, load_revisions=True)
    if not doc.code.startswith(TYF_CODE_PREFIX):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu belge kütüphane kapsamında değil.")
    return DocumentDetailOut.model_validate(doc)


# ── Kategori listesi ──────────────────────────────────────────────────────────
# Bu rotalar /{document_id} dinamik rotasından önce tanımlanmalıdır.

@router.get("/categories", response_model=List[CategoryOut])
async def list_categories(
    club_id: uuid.UUID = Depends(get_club_id),
    _: None = Depends(require_permission("belge:read")),
    db: AsyncSession = Depends(get_db),
) -> List[CategoryOut]:
    """Kulübe ait tüm belge kategorilerini döner (sort_order, name sırasıyla)."""
    result = await db.execute(
        select(DocumentCategory)
        .where(DocumentCategory.club_id == club_id)
        .order_by(DocumentCategory.sort_order.asc(), DocumentCategory.name.asc())
    )
    return [CategoryOut.model_validate(c) for c in result.scalars().all()]


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("belge:create")),
    db: AsyncSession = Depends(get_db),
) -> CategoryOut:
    """Yeni belge kategorisi oluşturur. (club_id, code) çifti benzersiz olmalıdır."""
    existing = await db.execute(
        select(DocumentCategory).where(
            DocumentCategory.club_id == club_id,
            DocumentCategory.code == body.code,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bu kulüpte '{body.code}' kodlu kategori zaten mevcut.",
        )

    cat = DocumentCategory(
        id=uuid.uuid4(),
        club_id=club_id,
        **body.model_dump(),
    )
    db.add(cat)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bu kulüpte '{body.code}' kodlu kategori zaten mevcut.",
        )

    await log_action(
        db,
        action="category_created",
        resource_type="doc_category",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(cat.id),
        after={"code": cat.code, "name": cat.name, "sort_order": cat.sort_order},
        request=request,
    )

    await db.refresh(cat)
    return CategoryOut.model_validate(cat)


# ── Belge detayı ──────────────────────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("belge:read")),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailOut:
    doc = await _get_document_or_404(document_id, club_id, db, load_revisions=True)
    # Own-scope: sporcu/veli yalnızca kendi belgesine erişebilir
    if is_own_scope_only(current_user.role, "belge:read"):
        person_ids = await _get_doc_person_ids(
            uuid.UUID(current_user.sub), club_id, db, current_user.role
        )
        if doc.owner_type != "person" or doc.owner_id not in person_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu belgeye erişim yetkiniz yok.",
            )
    return DocumentDetailOut.model_validate(doc)


# ── Belge oluştur ─────────────────────────────────────────────────────────────

@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("belge:create")),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    # Duplicate code kontrolü
    existing = await db.execute(
        select(Document).where(
            Document.club_id == club_id,
            Document.code == body.code,
            Document.is_deleted.is_(False),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bu kulüpte '{body.code}' kodlu belge zaten mevcut.",
        )

    # category_id tenant doğrulaması
    if body.category_id is not None:
        await _get_category_for_club(body.category_id, club_id, db)

    doc = Document(
        id=uuid.uuid4(),
        club_id=club_id,
        code=body.code,
        title=body.title,
        document_type=body.document_type,
        content_status=body.content_status,
        category_id=body.category_id,
        owner_type=body.owner_type,
        owner_id=body.owner_id,
        created_by_user_id=uuid.UUID(current_user.sub),
    )
    db.add(doc)
    await db.flush()

    await log_action(
        db,
        action="document_created",
        resource_type="document",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(doc.id),
        after={"code": doc.code, "title": doc.title, "document_type": doc.document_type},
        request=request,
    )

    await db.refresh(doc)
    return DocumentOut.model_validate(doc)


# ── Belge güncelle ────────────────────────────────────────────────────────────

@router.patch("/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: uuid.UUID,
    body: DocumentUpdate,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("belge:create")),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    doc = await _get_document_or_404(document_id, club_id, db)
    update_data = body.model_dump(exclude_unset=True)

    if not update_data:
        return DocumentOut.model_validate(doc)

    # category_id tenant doğrulaması
    if "category_id" in update_data and update_data["category_id"] is not None:
        await _get_category_for_club(update_data["category_id"], club_id, db)

    # code uniqueness kontrolü
    if "code" in update_data and update_data["code"] != doc.code:
        existing = await db.execute(
            select(Document).where(
                Document.club_id == club_id,
                Document.code == update_data["code"],
                Document.is_deleted.is_(False),
                Document.id != document_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bu kulüpte '{update_data['code']}' kodlu belge zaten mevcut.",
            )

    for field, value in update_data.items():
        setattr(doc, field, value)

    await db.flush()
    await db.refresh(doc)
    return DocumentOut.model_validate(doc)


# ── Belge sil (soft delete) ───────────────────────────────────────────────────

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_document(
    document_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("belge:delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    doc = await _get_document_or_404(document_id, club_id, db)
    doc.is_deleted = True
    await db.flush()


# ── Revizyon listesi ──────────────────────────────────────────────────────────

@router.get("/{document_id}/revisions", response_model=List[RevisionDetailOut])
async def list_revisions(
    document_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("belge:read")),
    db: AsyncSession = Depends(get_db),
) -> List[RevisionDetailOut]:
    doc = await _get_document_or_404(document_id, club_id, db)
    # Own-scope: sporcu/veli yalnızca kendi belgesinin revizyonlarını görür
    if is_own_scope_only(current_user.role, "belge:read"):
        person_ids = await _get_doc_person_ids(
            uuid.UUID(current_user.sub), club_id, db, current_user.role
        )
        if doc.owner_type != "person" or doc.owner_id not in person_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu belgeye erişim yetkiniz yok.",
            )

    result = await db.execute(
        select(DocumentRevision)
        .options(selectinload(DocumentRevision.files))
        .where(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.created_at.asc())
    )
    revisions = result.scalars().all()
    return [RevisionDetailOut.model_validate(r) for r in revisions]


# ── Revizyon oluştur ──────────────────────────────────────────────────────────

@router.post(
    "/{document_id}/revisions",
    response_model=RevisionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_revision(
    document_id: uuid.UUID,
    body: RevisionCreate,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("belge:create")),
    db: AsyncSession = Depends(get_db),
) -> RevisionOut:
    doc = await _get_document_or_404(document_id, club_id, db)

    # Duplicate revision_code kontrolü
    existing = await db.execute(
        select(DocumentRevision).where(
            DocumentRevision.document_id == document_id,
            DocumentRevision.revision_code == body.revision_code,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{body.revision_code}' kodlu revizyon zaten mevcut.",
        )

    # is_current=True ise önceki current revizyon(lar)ı sıfırla
    if body.is_current:
        await db.execute(
            update(DocumentRevision)
            .where(
                DocumentRevision.document_id == document_id,
                DocumentRevision.is_current.is_(True),
            )
            .values(is_current=False)
        )

    rev = DocumentRevision(
        id=uuid.uuid4(),
        document_id=document_id,
        revision_code=body.revision_code,
        revision_no=body.revision_no,
        revision_date=body.revision_date,
        status=body.status,
        effective_date=body.effective_date,
        expiry_date=body.expiry_date,
        description=body.description,
        source=body.source,
        manifest_row_id=body.manifest_row_id,
        is_current=body.is_current,
        created_by_user_id=uuid.UUID(current_user.sub),
    )
    db.add(rev)
    await db.flush()

    # Document.current_revision_id güncelle
    if body.is_current:
        doc.current_revision_id = rev.id
        await db.flush()

    await log_action(
        db,
        action="revision_created",
        resource_type="doc_revision",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(rev.id),
        after={
            "document_id": str(document_id),
            "revision_code": rev.revision_code,
            "is_current": rev.is_current,
        },
        request=request,
    )

    await db.refresh(rev)
    return RevisionOut.model_validate(rev)


# ── Dosya yükleme ─────────────────────────────────────────────────────────────

@router.post(
    "/{document_id}/revisions/{revision_id}/files",
    response_model=RevisionFileOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_revision_file(
    document_id: uuid.UUID,
    revision_id: uuid.UUID,
    file: UploadFile,
    request: Request,
    file_role: str = Form(default="source"),
    is_primary: bool = Form(default=False),
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("belge:create")),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorageService = Depends(get_dms_storage),
) -> RevisionFileOut:
    # Tenant + varlık kontrolü
    await _get_document_or_404(document_id, club_id, db)
    await _get_revision_or_404(revision_id, document_id, db)

    # Dosya oku
    file_bytes = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.",
        )

    # MIME kontrolü
    mime = file.content_type or "application/octet-stream"
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Desteklenmeyen dosya türü: {mime}",
        )

    # SHA-256
    sha256 = hashlib.sha256(file_bytes).hexdigest()

    # Duplicate SHA-256 kontrolü (aynı revizyon içinde)
    dup = await db.execute(
        select(DocumentRevisionFile).where(
            DocumentRevisionFile.revision_id == revision_id,
            DocumentRevisionFile.sha256 == sha256,
        )
    )
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu revizyon için aynı içerikli dosya zaten yüklenmiş.",
        )

    original_filename = file.filename or "upload"
    safe_name = _safe_filename(original_filename)
    file_id = uuid.uuid4()

    storage_key = (
        f"clubs/{club_id}/documents/{document_id}"
        f"/revisions/{revision_id}/{file_id}/{safe_name}"
    )
    storage_bucket = settings.storage_bucket_documents

    # Storage upload — DB insert sırasında hata olursa orphan nesneyi temizle
    await storage.upload(storage_key, file_bytes, mime)

    try:
        rev_file = DocumentRevisionFile(
            id=file_id,
            revision_id=revision_id,
            file_role=file_role,
            original_filename=original_filename,
            mime_type=mime,
            file_size=len(file_bytes),
            sha256=sha256,
            storage_bucket=storage_bucket,
            storage_key=storage_key,
            is_primary=is_primary,
        )
        db.add(rev_file)
        await db.flush()
        await db.refresh(rev_file)
    except Exception:
        # DB işlemi başarısız — storage'a yüklenen nesneyi best-effort sil
        try:
            await storage.delete(storage_key)
        except Exception:
            logger.warning(
                "Orphan storage nesnesi temizlenemedi: bucket=%s key=%s",
                storage_bucket, storage_key,
            )
        raise

    await log_action(
        db,
        action="file_uploaded",
        resource_type="doc_revision_file",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(rev_file.id),
        after={
            "document_id": str(document_id),
            "revision_id": str(revision_id),
            "original_filename": original_filename,
            "mime_type": mime,
            "file_size": len(file_bytes),
            "sha256": sha256,
        },
        request=request,
    )

    return RevisionFileOut.model_validate(rev_file)


# ── Dosya indir (backend streaming — MinIO URL client'a sızmaz) ──────────────

@router.get(
    "/{document_id}/revisions/{revision_id}/files/{file_id}/download",
)
async def download_revision_file(
    document_id: uuid.UUID,
    revision_id: uuid.UUID,
    file_id: uuid.UUID,
    inline: bool = Query(False, description="True ise PDF'ler tarayıcıda inline açılır."),
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorageService = Depends(get_dms_storage),
) -> Response:
    """Dosyayı backend üzerinden stream et.

    MinIO endpoint, presigned URL veya storage kimlik bilgileri
    hiçbir şekilde istemciye dönmez.

    Query params:
      inline=true  → PDF'ler Content-Disposition: inline olarak döner (browser içi görüntüleme).
                     DOCX ve diğer türler her zaman attachment olarak döner.
    """
    # Tenant + izin kontrolü
    doc = await _get_document_or_404(document_id, club_id, db)
    has_belge = has_permission(current_user.role, "belge:read")
    has_kutuphane = has_permission(current_user.role, "kutuphane:read")
    if not has_belge and not has_kutuphane:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Yetkiniz yok.")
    if has_kutuphane and not has_belge:
        # Kütüphane erişimi: yalnızca TYF dokümanları
        if not doc.code.startswith(TYF_CODE_PREFIX):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu dosyaya erişim yetkiniz yok.")
    elif has_belge and is_own_scope_only(current_user.role, "belge:read"):
        person_ids = await _get_doc_person_ids(
            uuid.UUID(current_user.sub), club_id, db, current_user.role
        )
        if doc.owner_type != "person" or doc.owner_id not in person_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu dosyaya erişim yetkiniz yok.",
            )
    await _get_revision_or_404(revision_id, document_id, db)

    result = await db.execute(
        select(DocumentRevisionFile).where(
            DocumentRevisionFile.id == file_id,
            DocumentRevisionFile.revision_id == revision_id,
        )
    )
    rev_file = result.scalar_one_or_none()
    if rev_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dosya bulunamadı.")

    try:
        data = await storage.download(rev_file.storage_key)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Depolama nesnesi bulunamadı.",
        )

    safe_name = _safe_filename(rev_file.original_filename)
    mime = rev_file.mime_type or "application/octet-stream"

    # PDF → inline (tarayıcıda görüntüle); diğerleri her zaman attachment
    is_pdf = mime == "application/pdf"
    disposition = "inline" if (inline and is_pdf) else "attachment"

    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f'{disposition}; filename="{safe_name}"',
            "Content-Length": str(len(data)),
        },
    )
