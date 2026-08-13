"""DMS Production Bulk Importer — Sprint 14C Adım 2.

Kullanım:
    Bu modül doğrudan çağrılmaz; scripts/import_documents_apply.py CLI'ı
    aracılığıyla kullanılır.

Plan JSON yapısı (document_import.py dry-run çıktısı):
    {
      "summary": { "logical_documents": 36, ... },
      "documents": [
        {
          "code": "MYK-ARC-001",
          "title": "Kurumsal Arşiv El Kitabı",
          "document_type": "el_kitabi",
          "content_status": "tamamlandi",
          "is_pdf_docx_pair": true,
          "files": [
            {
              "filename": "MYK-ARC-001_..._R01.pdf",
              "file_role": "published",
              "file_info": {"sha256": "...", "file_size": 175803},
              "source": "manifest"
            },
            {
              "filename": "MYK-ARC-001_..._R01.docx",
              "file_role": "source",
              "file_info": {"sha256": "...", "file_size": 173311, "auto_paired": true},
              "source": "disk_auto_paired"
            }
          ]
        }
      ],
      "duplicate_codes": [
        {"doc_code": "MYK-COMP-001", "stems": [...], "filenames": [...]}
      ],
      ...
    }

Güvenlik sözleşmesi (değiştirilemez):
    - ``apply=False`` iken DB veya storage'a hiçbir yazma yapılmaz.
    - Plan JSON SHA-256 uyuşmazlığı işlemi başlatmadan durdurur.
    - Kaynak artifact SHA-256 uyuşmazlığı o belgeyi hatayla işaretler.
    - Duplicate-code plan item'ları write batch'e alınmaz.
    - Kod çakışması (başka belge) → hard fail, sessiz overwrite yok.
    - DB transaction rollback → bu run'da yüklenen MinIO object'ler
      best-effort silinir.
    - Partial commit yok: tek belge dahi fail ederse tüm batch rollback.
    - Hard delete yok; mevcut data overwrite edilmez.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.club import Club
from app.models.documents import Document, DocumentRevision, DocumentRevisionFile
from app.services.storage import ObjectStorageService

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Sabitler ─────────────────────────────────────────────────────────────────

_MIME_BY_EXT: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    ),
}

# Plan summary'de beklenen kesin değerler — import öncesi doğrulanır.
_PLAN_CONTRACT: dict[str, int] = {
    "logical_documents": 36,
    "revisions": 36,
    "pdf_docx_pairs": 36,
    "unmatched_manifest": 0,
    "conflict_documents": 0,
    "ambiguous_pairs": 0,
}


# ── Yardımcı Fonksiyonlar ─────────────────────────────────────────────────────

def _safe_filename(name: str) -> str:
    """Router'daki _safe_filename ile birebir aynı."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _storage_key(
    club_id: uuid.UUID,
    document_id: uuid.UUID,
    revision_id: uuid.UUID,
    file_id: uuid.UUID,
    filename: str,
) -> str:
    safe = _safe_filename(filename)
    return (
        f"clubs/{club_id}/documents/{document_id}"
        f"/revisions/{revision_id}/{file_id}/{safe}"
    )


# ── Sonuç Modelleri ────────────────────────────────────────────────────────────

@dataclass
class FileResult:
    file_id: str
    original_filename: str
    file_role: str
    storage_key: str
    sha256: str
    file_size: int
    skipped: bool = False


@dataclass
class DocumentResult:
    document_id: str
    code: str
    title: str
    skipped: bool = False
    error: str | None = None
    files: list[FileResult] = field(default_factory=list)


@dataclass
class ImportResult:
    created_documents: int = 0
    created_revisions: int = 0
    created_files: int = 0
    skipped_documents: int = 0
    skipped_revisions: int = 0
    skipped_files: int = 0
    documents: list[DocumentResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    uploaded_objects: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    club_id: str = ""
    plan_sha256: str = ""
    applied: bool = False

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "applied": self.applied,
            "created_documents": self.created_documents,
            "created_revisions": self.created_revisions,
            "created_files": self.created_files,
            "skipped_documents": self.skipped_documents,
            "skipped_revisions": self.skipped_revisions,
            "skipped_files": self.skipped_files,
            "errors": self.errors,
            "uploaded_objects_count": len(self.uploaded_objects),
            "duration_seconds": round(self.duration_seconds, 3),
            "club_id": self.club_id,
            "plan_sha256": self.plan_sha256,
            "documents": [
                {
                    "document_id": d.document_id,
                    "code": d.code,
                    "title": d.title,
                    "skipped": d.skipped,
                    "error": d.error,
                    "files": [
                        {
                            "file_id": f.file_id,
                            "original_filename": f.original_filename,
                            "file_role": f.file_role,
                            "storage_key": f.storage_key,
                            "sha256": f.sha256,
                            "file_size": f.file_size,
                            "skipped": f.skipped,
                        }
                        for f in d.files
                    ],
                }
                for d in self.documents
            ],
        }


# ── Preflight Kontrolleri ─────────────────────────────────────────────────────

def _verify_plan_sha256(plan_path: Path, expected: str | None) -> str:
    actual = _sha256_file(plan_path)
    if expected and actual != expected.lower():
        raise ValueError(
            f"Plan SHA-256 uyuşmazlığı — beklenen: {expected}, gerçek: {actual}"
        )
    return actual


def _verify_plan_contract(summary: dict[str, Any]) -> None:
    for key, expected_val in _PLAN_CONTRACT.items():
        actual_val = summary.get(key)
        if actual_val != expected_val:
            raise ValueError(
                f"Plan contract hatası — {key}: beklenen={expected_val}, "
                f"gerçek={actual_val}. "
                "Duplicate/conflict kodlar temizlenmeden import yapılamaz."
            )


async def _verify_club(db: AsyncSession, club_id: uuid.UUID) -> Club:
    result = await db.execute(select(Club).where(Club.id == club_id))
    club = result.scalar_one_or_none()
    if club is None:
        raise ValueError(f"Kulüp bulunamadı: {club_id}")
    if not club.is_active:
        raise ValueError(f"Kulüp aktif değil: {club_id}")
    return club


def _verify_source_files(
    documents: list[dict[str, Any]], source_dir: Path
) -> None:
    """Her artifact'ın mevcut ve SHA'sının plan ile eşleştiğini doğrula."""
    errors: list[str] = []
    for doc in documents:
        for f in doc.get("files", []):
            fname: str = f.get("filename", "")
            file_info: dict = f.get("file_info", {})
            expected_sha: str = file_info.get("sha256", "")
            p = source_dir / fname
            if not p.exists():
                errors.append(f"Kaynak dosya bulunamadı: {fname}")
                continue
            if expected_sha:
                actual_sha = _sha256_file(p)
                if actual_sha != expected_sha.lower():
                    errors.append(
                        f"SHA-256 uyuşmazlığı: {fname} — "
                        f"beklenen={expected_sha}, gerçek={actual_sha}"
                    )
    if errors:
        raise ValueError(
            f"{len(errors)} kaynak artifact hatası:\n" + "\n".join(errors)
        )


# ── Duplicate Code Tespiti ────────────────────────────────────────────────────

async def _check_existing_codes(
    db: AsyncSession, club_id: uuid.UUID, codes: list[str]
) -> dict[str, uuid.UUID]:
    """DB'de zaten mevcut olan kod → document_id eşleşmelerini döndür."""
    if not codes:
        return {}
    result = await db.execute(
        select(Document.code, Document.id).where(
            Document.club_id == club_id,
            Document.code.in_(codes),
            Document.is_deleted.is_(False),
        )
    )
    return {row.code: row.id for row in result}


async def _is_idempotent_duplicate(
    db: AsyncSession,
    existing_doc_id: uuid.UUID,
    primary_sha256: str,
) -> bool:
    """Mevcut document aynı primary file SHA256 ile zaten import edilmişse
    idempotent skip yapılabilir.
    """
    result = await db.execute(
        select(DocumentRevisionFile.id).where(
            DocumentRevisionFile.revision_id.in_(
                select(DocumentRevision.id).where(
                    DocumentRevision.document_id == existing_doc_id
                )
            ),
            DocumentRevisionFile.sha256 == primary_sha256.lower(),
            DocumentRevisionFile.is_primary.is_(True),
        )
    )
    return result.scalar_one_or_none() is not None


# ── Tek Belge Yazma ───────────────────────────────────────────────────────────

async def _write_document(
    db: AsyncSession,
    storage: ObjectStorageService,
    club_id: uuid.UUID,
    doc_plan: dict[str, Any],
    source_dir: Path,
    actor_user_id: uuid.UUID | None,
    existing_code_map: dict[str, uuid.UUID],
    run_uploaded_objects: list[str],
) -> DocumentResult:
    """Tek logical document + revision + file set yazar.

    Başarısız olursa bu belge için yüklenen object'leri temizler ve
    DocumentResult.error doldurur.  Batch transaction çağıran tarafından
    yönetilir.
    """
    code: str = doc_plan.get("code", "")
    title: str = doc_plan.get("title", code)
    files_in_plan: list[dict[str, Any]] = doc_plan.get("files", [])

    doc_result = DocumentResult(document_id="", code=code, title=title)

    # Primary file (PDF/published) SHA'sını bul — idempotency check için
    primary_sha = ""
    for f in files_in_plan:
        if f.get("file_role") == "published":
            primary_sha = f.get("file_info", {}).get("sha256", "")
            break

    # ── Duplicate code kontrolü ───────────────────────────────────────────────
    if code in existing_code_map:
        existing_id = existing_code_map[code]
        if primary_sha and await _is_idempotent_duplicate(
            db, existing_id, primary_sha
        ):
            doc_result.document_id = str(existing_id)
            doc_result.skipped = True
            return doc_result
        doc_result.error = (
            f"Kod çakışması: '{code}' zaten başka bir belgeye ait "
            f"(id={existing_id}). Sessiz overwrite engellendi."
        )
        return doc_result

    # ── Artifact'ları yükle ────────────────────────────────────────────────────
    document_id = uuid.uuid4()
    revision_id = uuid.uuid4()

    local_uploaded: list[str] = []
    file_records: list[tuple[DocumentRevisionFile, FileResult]] = []

    for f_entry in files_in_plan:
        fname: str = f_entry.get("filename", "")
        role: str = f_entry.get("file_role", "source")
        file_info: dict = f_entry.get("file_info", {})
        expected_sha: str = file_info.get("sha256", "")

        src_path = source_dir / fname
        try:
            file_bytes = src_path.read_bytes()
        except FileNotFoundError:
            doc_result.error = f"Kaynak dosya bulunamadı: {fname}"
            await _cleanup_local(storage, local_uploaded, run_uploaded_objects)
            return doc_result

        actual_sha = _sha256_bytes(file_bytes)
        if expected_sha and actual_sha != expected_sha.lower():
            doc_result.error = (
                f"SHA-256 uyuşmazlığı: {fname} — "
                f"beklenen={expected_sha}, gerçek={actual_sha}"
            )
            await _cleanup_local(storage, local_uploaded, run_uploaded_objects)
            return doc_result

        ext = Path(fname).suffix.lower()
        mime = _MIME_BY_EXT.get(ext, "application/octet-stream")
        is_primary = (role == "published")

        file_id = uuid.uuid4()
        key = _storage_key(club_id, document_id, revision_id, file_id, fname)

        await storage.upload(key, file_bytes, mime)
        local_uploaded.append(key)
        run_uploaded_objects.append(key)

        rev_file = DocumentRevisionFile(
            id=file_id,
            revision_id=revision_id,
            file_role=role,
            original_filename=fname,
            mime_type=mime,
            file_size=len(file_bytes),
            sha256=actual_sha,
            storage_bucket=settings.storage_bucket_documents,
            storage_key=key,
            is_primary=is_primary,
        )
        file_result = FileResult(
            file_id=str(file_id),
            original_filename=fname,
            file_role=role,
            storage_key=key,
            sha256=actual_sha,
            file_size=len(file_bytes),
        )
        file_records.append((rev_file, file_result))

    # ── DB kayıtları ─────────────────────────────────────────────────────────
    document_type = doc_plan.get("document_type", "diger")
    _valid_types = {
        "prosedur", "talimati", "form", "el_kitabi", "egitim_materyali",
        "operasyonel", "sporcu_belgesi", "ekipman_belgesi", "diger",
    }
    if document_type not in _valid_types:
        document_type = "diger"

    try:
        doc = Document(
            id=document_id,
            club_id=club_id,
            code=code,
            title=title,
            document_type=document_type,
            content_status="tamamlandi",
            current_revision_id=revision_id,
            is_active=True,
            is_deleted=False,
            created_by_user_id=actor_user_id,
        )
        db.add(doc)
        await db.flush()

        revision = DocumentRevision(
            id=revision_id,
            document_id=document_id,
            revision_code="R01",
            revision_no=1,
            status="yayinda",
            source="sprint14c_bulk_import",
            manifest_row_id=code,  # kod deduplication referansı
            is_current=True,
            created_by_user_id=actor_user_id,
        )
        db.add(revision)
        await db.flush()

        for rev_file, _ in file_records:
            db.add(rev_file)
        await db.flush()

    except Exception as exc:
        doc_result.error = f"DB yazma hatası: {exc}"
        await _cleanup_local(storage, local_uploaded, run_uploaded_objects)
        return doc_result

    doc_result.document_id = str(document_id)
    doc_result.files = [fr for _, fr in file_records]
    return doc_result


async def _cleanup_local(
    storage: ObjectStorageService,
    local_uploaded: list[str],
    run_uploaded_objects: list[str],
) -> None:
    """Bu belgeye ait yüklenen object'leri best-effort sil."""
    for key in local_uploaded:
        try:
            await storage.delete(key)
        except Exception:
            logger.warning("Cleanup başarısız: %s", key)
        try:
            run_uploaded_objects.remove(key)
        except ValueError:
            pass


# ── Ana Import Fonksiyonu ─────────────────────────────────────────────────────

async def import_document_plan(
    db: AsyncSession,
    storage: ObjectStorageService,
    *,
    club_id: uuid.UUID,
    plan_path: str | Path,
    source_dir: str | Path,
    actor_user_id: uuid.UUID | None = None,
    expected_plan_sha256: str | None = None,
    apply: bool = False,
) -> ImportResult:
    """READY_R01 import planını production DB + MinIO'ya uygular.

    Args:
        db: Async DB oturumu.  Bu fonksiyon commit yapar (success) veya
            rollback yapar (failure).
        storage: ObjectStorageService implementasyonu.
        club_id: Hedef kulüp UUID'si.
        plan_path: dry-run JSON çıktısı dosyasının yolu.
        source_dir: Kaynak PDF/DOCX dizini.
        actor_user_id: Import yapan kullanıcının UUID'si (opsiyonel audit).
        expected_plan_sha256: Plan dosyasının beklenen SHA-256 hash'i.
        apply: ``True`` olmadan DB veya storage'a hiçbir yazma yapılmaz.

    Returns:
        ImportResult (apply=False → preflight özeti, apply=True → tam sonuç)
    """
    t0 = time.monotonic()
    plan_path = Path(plan_path)
    source_dir = Path(source_dir)
    result = ImportResult(club_id=str(club_id), applied=apply)
    run_uploaded_objects: list[str] = []

    # ── 1. Plan SHA-256 ───────────────────────────────────────────────────────
    try:
        plan_sha256 = _verify_plan_sha256(plan_path, expected_plan_sha256)
        result.plan_sha256 = plan_sha256
    except ValueError as exc:
        result.errors.append(str(exc))
        result.duration_seconds = time.monotonic() - t0
        return result

    # ── 2. Plan yükle ─────────────────────────────────────────────────────────
    with open(plan_path, encoding="utf-8") as f:
        plan_data: dict[str, Any] = json.load(f)

    summary: dict[str, Any] = plan_data.get("summary", {})
    documents: list[dict[str, Any]] = plan_data.get("documents", [])

    # Duplicate code setini hazırla (plan içinde skip edilecek kodlar)
    duplicate_code_set: set[str] = {
        entry.get("doc_code", "")
        for entry in plan_data.get("duplicate_codes", [])
    }

    # ── 3. Plan contract ──────────────────────────────────────────────────────
    try:
        _verify_plan_contract(summary)
    except ValueError as exc:
        result.errors.append(str(exc))
        result.duration_seconds = time.monotonic() - t0
        return result

    # ── 4. Tenant kontrolü ────────────────────────────────────────────────────
    try:
        await _verify_club(db, club_id)
    except ValueError as exc:
        result.errors.append(str(exc))
        result.duration_seconds = time.monotonic() - t0
        return result

    # ── 5. Kaynak artifact preflight ──────────────────────────────────────────
    # Yalnızca write batch'e girecek belgeler için kontrol et
    write_documents = [
        d for d in documents
        if d.get("code", "") not in duplicate_code_set
    ]
    try:
        _verify_source_files(write_documents, source_dir)
    except ValueError as exc:
        result.errors.append(str(exc))
        result.duration_seconds = time.monotonic() - t0
        return result

    # ── 6. apply=False → preflight özeti ─────────────────────────────────────
    if not apply:
        result.created_documents = len(write_documents)
        result.created_files = sum(len(d.get("files", [])) for d in write_documents)
        result.duration_seconds = time.monotonic() - t0
        logger.info(
            "Preflight OK (apply=False) — %d belge %d dosya yazılmaya hazır",
            result.created_documents,
            result.created_files,
        )
        return result

    # ── 7. Mevcut kod çakışması kontrolü (DB) ────────────────────────────────
    all_codes = [d.get("code", "") for d in write_documents]
    existing_code_map = await _check_existing_codes(db, club_id, all_codes)

    # ── 8. Batch yazma ────────────────────────────────────────────────────────
    batch_failed = False

    for doc_plan in write_documents:
        doc_result = await _write_document(
            db=db,
            storage=storage,
            club_id=club_id,
            doc_plan=doc_plan,
            source_dir=source_dir,
            actor_user_id=actor_user_id,
            existing_code_map=existing_code_map,
            run_uploaded_objects=run_uploaded_objects,
        )
        result.documents.append(doc_result)

        if doc_result.error:
            result.errors.append(f"[{doc_result.code}] {doc_result.error}")
            batch_failed = True
            break  # İlk hata → batch abort (partial commit yok)

        if doc_result.skipped:
            result.skipped_documents += 1
            result.skipped_revisions += 1
            result.skipped_files += len(doc_result.files)
        else:
            result.created_documents += 1
            result.created_revisions += 1
            result.created_files += len(doc_result.files)

    # ── 9. Batch sonucu ───────────────────────────────────────────────────────
    if batch_failed:
        logger.error(
            "Batch hata — %d object cleanup, rollback başlatılıyor",
            len(run_uploaded_objects),
        )
        await db.rollback()
        for key in run_uploaded_objects:
            try:
                await storage.delete(key)
                logger.info("Cleanup: %s", key)
            except Exception as exc:
                logger.warning("Cleanup başarısız %s: %s", key, exc)
        result.uploaded_objects = []
    else:
        result.uploaded_objects = list(run_uploaded_objects)
        await db.commit()
        logger.info(
            "Import tamamlandı: %d belge / %d revizyon / %d dosya — %.2fs",
            result.created_documents,
            result.created_revisions,
            result.created_files,
            time.monotonic() - t0,
        )

    result.duration_seconds = time.monotonic() - t0
    return result
