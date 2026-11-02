"""DMS revizyon onaylama / yayımlama servisi.

Kullanım: ``scripts/publish_document_revisions.py`` CLI'ı üzerinden.

Plan JSON yapısı::

    {
      "items": [
        {
          "code": "MYK-SEA-MAN-001",
          "revision_code": "R00",
          "target_status": "yayinda",          # veya "onaylandi"
          "effective_date": "2026-11-02",       # opsiyonel (YYYY-AA-GG)
          "note": "YK onayı 02.11.2026",        # opsiyonel, revizyon açıklamasına eklenir
          "replace_files": [                    # opsiyonel: onaylı nihai dosyalar
            {"filename": "X.pdf",  "file_role": "published", "sha256": "..."},
            {"filename": "X.docx", "file_role": "source",    "sha256": "..."}
          ]
        }
      ]
    }

Kurallar:
    - ``apply=False`` iken DB veya storage'a hiçbir yazma yapılmaz.
    - Plan SHA-256 verilmişse uyuşmazlık işlemi başlatmadan durdurur.
    - Kaynak revizyon ``taslak``, ``incelemede`` veya ``onaylandi`` olmalıdır;
      revizyon zaten hedef durumdaysa öğe atlanır (idempotent).
    - ``yayinda``: belgenin diğer yürürlükteki revizyonları ``arsivlendi`` olur,
      hedef revizyon güncel revizyon yapılır, belge ``tamamlandi`` olur.
    - ``onaylandi``: yalnızca revizyon durumu değişir; güncel revizyon değişmez.
    - ``replace_files``: yeni dosyalar yüklenir; revizyonun önceki birincil
      dosyaları silinmez, ``other`` rolüne alınır ve birincil olmaktan çıkar.
    - Hepsi ya da hiçbiri: tek öğe hata verirse tüm işlem geri alınır ve bu
      çalıştırmada yüklenen objeler silinir.
    - Her durum değişikliği audit log'a yazılır.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_action
from app.models.documents import Document, DocumentRevision, DocumentRevisionFile
from app.services.document_bulk_import import (
    _MIME_BY_EXT,
    _sha256_bytes,
    _sha256_file,
    _storage_key,
    _verify_club,
    settings,
)
from app.services.storage import ObjectStorageService

TARGET_STATUSES = frozenset({"onaylandi", "yayinda"})
SOURCE_STATUSES = frozenset({"taslak", "incelemede", "onaylandi"})
FILE_ROLES = frozenset({"published", "source"})


@dataclass
class PublishItemResult:
    code: str
    revision_code: str
    target_status: str
    previous_status: str = ""
    skipped: bool = False
    archived_revisions: list[str] = field(default_factory=list)
    replaced_files: int = 0
    error: str | None = None


@dataclass
class PublishResult:
    club_id: str
    applied: bool
    plan_sha256: str = ""
    items: list[PublishItemResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    uploaded_objects: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "applied": self.applied,
            "club_id": self.club_id,
            "plan_sha256": self.plan_sha256,
            "changed": sum(1 for i in self.items if not i.skipped and not i.error),
            "skipped": sum(1 for i in self.items if i.skipped),
            "errors": self.errors,
            "uploaded_objects_count": len(self.uploaded_objects),
            "items": [i.__dict__ for i in self.items],
        }


def _validate_item(item: dict[str, Any]) -> tuple[str, str, str, date | None]:
    code = item.get("code") or ""
    rev_code = item.get("revision_code") or ""
    target = item.get("target_status") or ""
    if not code or not rev_code:
        raise ValueError("code ve revision_code zorunludur")
    if target not in TARGET_STATUSES:
        raise ValueError(f"{code}: geçersiz target_status {target!r}")
    eff = item.get("effective_date")
    eff_date = date.fromisoformat(eff) if eff else None
    for f in item.get("replace_files") or []:
        if f.get("file_role") not in FILE_ROLES:
            raise ValueError(f"{code}: geçersiz file_role {f.get('file_role')!r}")
        if not f.get("filename") or not f.get("sha256"):
            raise ValueError(f"{code}: replace_files için filename ve sha256 zorunludur")
    return code, rev_code, target, eff_date


async def _process_item(
    db: AsyncSession,
    storage: ObjectStorageService,
    club_id: uuid.UUID,
    item: dict[str, Any],
    source_dir: Path,
    apply: bool,
    actor_user_id: uuid.UUID | None,
    uploaded: list[str],
) -> PublishItemResult:
    code, rev_code, target, eff_date = _validate_item(item)
    res = PublishItemResult(code=code, revision_code=rev_code, target_status=target)

    doc = (await db.execute(select(Document).where(
        Document.club_id == club_id, Document.code == code, Document.is_deleted.is_(False)
    ))).scalar_one_or_none()
    if doc is None:
        raise ValueError(f"{code}: belge bulunamadı")
    rev = (await db.execute(select(DocumentRevision).where(
        DocumentRevision.document_id == doc.id, DocumentRevision.revision_code == rev_code
    ))).scalar_one_or_none()
    if rev is None:
        raise ValueError(f"{code}: {rev_code} revizyonu bulunamadı")

    res.previous_status = rev.status
    if rev.status == target:
        res.skipped = True
        return res
    if rev.status not in SOURCE_STATUSES:
        raise ValueError(f"{code} {rev_code}: {rev.status!r} durumundan {target!r} yapılamaz")

    # Dosya doğrulaması (yazmadan önce)
    new_files: list[tuple[dict[str, Any], bytes]] = []
    for f in item.get("replace_files") or []:
        p = source_dir / f["filename"]
        if not p.exists():
            raise ValueError(f"{code}: kaynak dosya bulunamadı: {f['filename']}")
        data = p.read_bytes()
        if _sha256_bytes(data) != f["sha256"].lower():
            raise ValueError(f"{code}: SHA-256 uyuşmazlığı: {f['filename']}")
        new_files.append((f, data))
    res.replaced_files = len(new_files)

    others: list[DocumentRevision] = []
    if target == "yayinda":
        others = list((await db.execute(select(DocumentRevision).where(
            DocumentRevision.document_id == doc.id,
            DocumentRevision.id != rev.id,
            DocumentRevision.is_current.is_(True),
        ))).scalars().all())
        res.archived_revisions = [o.revision_code for o in others]

    if not apply:
        return res

    # ── Yazma ─────────────────────────────────────────────────────────────────
    if new_files:
        old_files = (await db.execute(select(DocumentRevisionFile).where(
            DocumentRevisionFile.revision_id == rev.id,
            DocumentRevisionFile.file_role.in_(tuple(FILE_ROLES)),
        ))).scalars().all()
        for of in old_files:
            of.is_primary = False
            of.file_role = "other"
        for f, data in new_files:
            file_id = uuid.uuid4()
            fname = f["filename"]
            key = _storage_key(club_id, doc.id, rev.id, file_id, fname)
            mime = _MIME_BY_EXT.get(Path(fname).suffix.lower(), "application/octet-stream")
            await storage.upload(key, data, mime)
            uploaded.append(key)
            db.add(DocumentRevisionFile(
                id=file_id, revision_id=rev.id, file_role=f["file_role"],
                original_filename=fname, mime_type=mime, file_size=len(data),
                sha256=_sha256_bytes(data), storage_bucket=settings.storage_bucket_documents,
                storage_key=key, is_primary=(f["file_role"] == "published"),
            ))

    for o in others:
        o.is_current = False
        o.status = "arsivlendi"
    rev.status = target
    if eff_date:
        rev.effective_date = eff_date
        if rev.revision_date is None:
            rev.revision_date = eff_date
    if item.get("note"):
        rev.description = ((rev.description + "\n") if rev.description else "") + item["note"]
    doc.content_status = "tamamlandi"
    if target == "yayinda":
        rev.is_current = True
        doc.current_revision_id = rev.id

    await log_action(
        db,
        action="document_revision_status_changed",
        resource_type="doc_revision",
        club_id=club_id,
        user_id=actor_user_id,
        resource_id=str(rev.id),
        before={"code": code, "revision_code": rev_code, "status": res.previous_status},
        after={"code": code, "revision_code": rev_code, "status": target,
               "archived_revisions": res.archived_revisions,
               "replaced_files": res.replaced_files, "note": item.get("note")},
    )
    await db.flush()
    return res


async def publish_revisions(
    db: AsyncSession,
    storage: ObjectStorageService,
    *,
    club_id: uuid.UUID,
    plan_path: str | Path,
    source_dir: str | Path | None = None,
    expected_plan_sha256: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    apply: bool = False,
) -> PublishResult:
    plan_path = Path(plan_path)
    source_dir = Path(source_dir) if source_dir else plan_path.parent
    result = PublishResult(club_id=str(club_id), applied=apply)
    try:
        result.plan_sha256 = _sha256_file(plan_path)
        if expected_plan_sha256 and result.plan_sha256 != expected_plan_sha256.lower():
            raise ValueError("Plan SHA-256 uyuşmazlığı")
        if apply and not expected_plan_sha256:
            raise ValueError("apply için expected_plan_sha256 zorunludur")
        await _verify_club(db, club_id)
        items = json.loads(plan_path.read_text(encoding="utf-8")).get("items", [])
        if not items:
            raise ValueError("Plan boş")
        for item in items:
            result.items.append(await _process_item(
                db, storage, club_id, item, source_dir, apply, actor_user_id,
                result.uploaded_objects,
            ))
    except Exception as exc:  # tek hata tüm işlemi geri alır
        result.errors.append(str(exc))

    if not apply:
        return result
    if result.errors:
        await db.rollback()
        for key in result.uploaded_objects:
            try:
                await storage.delete(key)
            except Exception:
                pass
        result.uploaded_objects = []
        return result

    await db.commit()
    return result
