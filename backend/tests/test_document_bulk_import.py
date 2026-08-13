"""DMS Production Bulk Import Testleri — DBI-01 .. DBI-18.

Test edilen: backend/app/services/document_bulk_import.py

Altyapı:
    - SQLite in-memory test DB (conftest.py)
    - InMemoryStorageService (test_storage.py)
    - Geçici plan JSON + kaynak dosyaları tmp_path ile oluşturulur
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.club import Club
from app.models.documents import Document, DocumentRevision, DocumentRevisionFile
from app.services.document_bulk_import import (
    _PLAN_CONTRACT,
    ImportResult,
    import_document_plan,
)
from tests.test_storage import InMemoryStorageService  # type: ignore[import-not-found]


# ── Plan / Kaynak Yardımcıları ────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_plan(
    documents: list[dict[str, Any]],
    *,
    summary_overrides: dict[str, Any] | None = None,
    duplicate_codes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Test plan JSON'u oluştur. summary her zaman geçerli contract değerlerini taşır."""
    base_summary: dict[str, Any] = dict(_PLAN_CONTRACT)
    if summary_overrides:
        base_summary.update(summary_overrides)
    return {
        "summary": base_summary,
        "documents": documents,
        "duplicate_codes": duplicate_codes or [],
        "unmatched_manifest": [],
        "unmatched_disk": [],
        "conflicts": [],
        "ambiguous_pairs": [],
    }


def _make_doc_entry(
    code: str,
    pdf_bytes: bytes,
    docx_bytes: bytes | None = None,
    *,
    title: str | None = None,
    document_type: str = "el_kitabi",
    override_pdf_sha: str | None = None,
) -> dict[str, Any]:
    """Tek belge için plan JSON entry'si üret."""
    pdf_sha = override_pdf_sha or _sha256(pdf_bytes)
    files: list[dict[str, Any]] = [
        {
            "filename": f"{code}_R01.pdf",
            "file_role": "published",
            "file_info": {"sha256": pdf_sha, "file_size": len(pdf_bytes)},
            "source": "manifest",
        }
    ]
    if docx_bytes is not None:
        files.append(
            {
                "filename": f"{code}_R01.docx",
                "file_role": "source",
                "file_info": {
                    "sha256": _sha256(docx_bytes),
                    "file_size": len(docx_bytes),
                    "auto_paired": True,
                },
                "source": "disk_auto_paired",
            }
        )
    return {
        "code": code,
        "title": title or f"{code} El Kitabı",
        "document_type": document_type,
        "content_status": "tamamlandi",
        "is_pdf_docx_pair": docx_bytes is not None,
        "files": files,
    }


def _write_plan(directory: Path, plan: dict[str, Any]) -> Path:
    """plan.json dosyasını belirtilen dizine yazar."""
    p = directory / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return p


def _write_plan_to(path: Path, plan: dict[str, Any]) -> Path:
    """plan JSON'u kesin dosya yoluna yazar."""
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return path


def _write_source(directory: Path, filename: str, data: bytes) -> Path:
    p = directory / filename
    p.write_bytes(data)
    return p


def _setup_single_doc(
    directory: Path,
    code: str,
    *,
    pdf_content: bytes | None = None,
    docx_content: bytes | None = None,
) -> tuple[bytes, bytes, dict[str, Any]]:
    """PDF + DOCX dosyaları yaz, plan entry'si döndür."""
    pdf = pdf_content or f"FAKE PDF {code}".encode()
    docx = docx_content or f"FAKE DOCX {code}".encode()
    _write_source(directory, f"{code}_R01.pdf", pdf)
    _write_source(directory, f"{code}_R01.docx", docx)
    return pdf, docx, _make_doc_entry(code, pdf, docx)


# ── Fixture: Aktif kulüp ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def active_club(db_session) -> Club:
    club = Club(
        id=uuid.uuid4(),
        slug=f"bulk-test-{uuid.uuid4().hex[:8]}",
        name="Bulk Import Test Kulübü",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(club)
    await db_session.flush()
    return club


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-01  apply=False → DB/storage mutation yok
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi01_no_apply_does_not_mutate(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()

    docs = []
    for i in range(1, 37):
        code = f"MYK-DBI01-{i:03d}"
        _, _, entry = _setup_single_doc(tmp_path, code)
        docs.append(entry)
    plan_path = _write_plan(tmp_path, _build_plan(docs))

    result = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=False,
    )

    assert result.success
    assert result.applied is False
    assert len(storage._store) == 0
    rows = (await db_session.execute(
        select(Document).where(Document.club_id == active_club.id)
    )).scalars().all()
    assert len(rows) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-02  Yanlış plan SHA-256 → işlem başlamadan dur
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi02_invalid_plan_hash_blocks(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()
    _, _, entry = _setup_single_doc(tmp_path, "MYK-DBI02-001")
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    result = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        expected_plan_sha256="a" * 64,
        apply=True,
    )

    assert not result.success
    assert any("SHA-256" in e for e in result.errors)
    assert len(storage._store) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-03  Inactive kulüp → işlem dur
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi03_inactive_club_blocks(db_session, tmp_path):
    storage = InMemoryStorageService()
    inactive = Club(
        id=uuid.uuid4(),
        slug=f"inactive-{uuid.uuid4().hex[:8]}",
        name="İnaktif Kulüp",
        plan="starter",
        is_active=False,
        settings={},
    )
    db_session.add(inactive)
    await db_session.flush()

    _, _, entry = _setup_single_doc(tmp_path, "MYK-DBI03-001")
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    result = await import_document_plan(
        db_session, storage,
        club_id=inactive.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )

    assert not result.success
    assert any("aktif değil" in e for e in result.errors)


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-04  Mevcut olmayan kulüp → işlem dur
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi04_missing_club_blocks(db_session, tmp_path):
    storage = InMemoryStorageService()
    _, _, entry = _setup_single_doc(tmp_path, "MYK-DBI04-001")
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    result = await import_document_plan(
        db_session, storage,
        club_id=uuid.uuid4(),
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )

    assert not result.success
    assert any("bulunamadı" in e for e in result.errors)


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-05  Kaynak dosya eksik → preflight'ta yakalanır
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi05_missing_source_file_blocks(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()
    pdf = b"FAKE PDF"
    docx = b"FAKE DOCX"
    entry = _make_doc_entry("MYK-DBI05-001", pdf, docx)
    # Kaynak dizinde dosya YOK — kasıtlı
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    result = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )

    assert not result.success
    assert any("bulunamadı" in e for e in result.errors)
    assert len(storage._store) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-06  Kaynak SHA-256 uyuşmazlığı → preflight'ta yakalanır
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi06_source_sha_mismatch_blocks(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()
    pdf = b"CORRECT PDF"
    docx = b"CORRECT DOCX"
    entry = _make_doc_entry("MYK-DBI06-001", pdf, docx)
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    # Bozuk içerik diske yaz (SHA uyuşmaz)
    _write_source(tmp_path, "MYK-DBI06-001_R01.pdf", b"TAMPERED CONTENT")
    _write_source(tmp_path, "MYK-DBI06-001_R01.docx", docx)

    result = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )

    assert not result.success
    assert any("SHA-256" in e for e in result.errors)
    assert len(storage._store) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-07  Duplicate kod (farklı içerik) → hard fail, overwrite yok
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi07_duplicate_document_code_blocks(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()
    code = "MYK-DBI07-001"

    src1 = tmp_path / "src1"
    src1.mkdir()
    _, _, entry1 = _setup_single_doc(src1, code,
                                     pdf_content=b"original pdf",
                                     docx_content=b"original docx")
    plan1_path = _write_plan_to(tmp_path / "plan1.json", _build_plan([entry1]))

    r1 = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan1_path,
        source_dir=src1,
        apply=True,
    )
    assert r1.success, r1.errors

    src2 = tmp_path / "src2"
    src2.mkdir()
    _, _, entry2 = _setup_single_doc(src2, code,
                                     pdf_content=b"different pdf",
                                     docx_content=b"different docx")
    plan2_path = _write_plan_to(tmp_path / "plan2.json", _build_plan([entry2]))

    r2 = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan2_path,
        source_dir=src2,
        apply=True,
    )

    assert not r2.success
    assert any("çakışma" in e.lower() for e in r2.errors)


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-08  Tek belge başarılı import (PDF + DOCX)
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi08_imports_single_document_pdf_docx(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()
    _, _, entry = _setup_single_doc(tmp_path, "MYK-DBI08-001")
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    result = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )

    assert result.success, result.errors
    assert result.created_documents == 1
    assert result.created_revisions == 1
    assert result.created_files == 2
    assert len(storage._store) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-09  PDF → file_role=published, is_primary=True
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi09_pdf_role_published_primary(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()
    pdf, _, entry = _setup_single_doc(tmp_path, "MYK-DBI09-001")
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    result = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )
    assert result.success

    db_files = (await db_session.execute(
        select(DocumentRevisionFile).where(
            DocumentRevisionFile.sha256 == _sha256(pdf)
        )
    )).scalars().all()
    assert len(db_files) == 1
    assert db_files[0].is_primary is True
    assert db_files[0].file_role == "published"


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-10  DOCX → file_role=source, is_primary=False
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi10_docx_role_source_not_primary(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()
    _, docx, entry = _setup_single_doc(tmp_path, "MYK-DBI10-001")
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    result = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )
    assert result.success

    db_files = (await db_session.execute(
        select(DocumentRevisionFile).where(
            DocumentRevisionFile.sha256 == _sha256(docx)
        )
    )).scalars().all()
    assert len(db_files) == 1
    assert db_files[0].is_primary is False
    assert db_files[0].file_role == "source"


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-11  current_revision_id doğru bağlanır, revision_code=R01, status=yayinda
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi11_current_revision_linked(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()
    _, _, entry = _setup_single_doc(tmp_path, "MYK-DBI11-001")
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    result = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )
    assert result.success

    doc_id = uuid.UUID(result.documents[0].document_id)
    db_doc = (await db_session.execute(
        select(Document).where(Document.id == doc_id)
    )).scalar_one()

    assert db_doc.current_revision_id is not None
    rev = (await db_session.execute(
        select(DocumentRevision).where(
            DocumentRevision.id == db_doc.current_revision_id
        )
    )).scalar_one()
    assert rev.is_current is True
    assert rev.revision_code == "R01"
    assert rev.status == "yayinda"
    assert rev.source == "sprint14c_bulk_import"


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-12  Batch atomicity: code_b clashes → code_a DB writes rolled back
#         + code_a's uploaded objects cleaned from storage
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi12_batch_transaction_atomic_on_failure(
    db_session, active_club, tmp_path
):
    storage = InMemoryStorageService()
    code_a = "MYK-DBI12-A"
    code_b = "MYK-DBI12-B"
    # Capture UUID before any rollback so we can query safely afterwards
    club_id = active_club.id

    # Step 1: import code_b v1 alone → commits (also commits active_club)
    src1 = tmp_path / "s1"
    src1.mkdir()
    _, _, entry_b1 = _setup_single_doc(src1, code_b,
                                        pdf_content=b"b v1",
                                        docx_content=b"b v1 docx")
    r1 = await import_document_plan(
        db_session, storage,
        club_id=club_id,
        plan_path=_write_plan_to(tmp_path / "p1.json", _build_plan([entry_b1])),
        source_dir=src1,
        apply=True,
    )
    assert r1.success, r1.errors

    # Reset storage: track only step 2 uploads
    storage._store.clear()

    # Step 2: code_a (new OK) + code_b v2 (different SHA → clash after code_a write)
    src2 = tmp_path / "s2"
    src2.mkdir()
    _, _, entry_a = _setup_single_doc(src2, code_a,
                                       pdf_content=b"a original",
                                       docx_content=b"a docx")
    _, _, entry_b2 = _setup_single_doc(src2, code_b,
                                        pdf_content=b"b v2 different",
                                        docx_content=b"b v2 docx diff")

    r2 = await import_document_plan(
        db_session, storage,
        club_id=club_id,
        plan_path=_write_plan_to(tmp_path / "p2.json", _build_plan([entry_a, entry_b2])),
        source_dir=src2,
        apply=True,
    )

    assert not r2.success
    assert any("çakışma" in e.lower() for e in r2.errors)
    # code_a's 2 uploaded objects must be cleaned up
    assert len(storage._store) == 0
    # code_a must not be in DB (rolled back); use captured club_id (not active_club.id
    # which would trigger a lazy-load on the expired object after rollback)
    db_docs = (await db_session.execute(
        select(Document).where(Document.club_id == club_id)
    )).scalars().all()
    codes_in_db = {d.code for d in db_docs}
    assert code_a not in codes_in_db
    assert code_b in codes_in_db  # committed in step 1


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-13  DB flush hatası (simüle) → yüklenen MinIO object'ler silinir
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi13_uploaded_objects_deleted_on_db_failure(
    db_session, active_club, tmp_path
):
    storage = InMemoryStorageService()
    _, _, entry = _setup_single_doc(tmp_path, "MYK-DBI13-001")
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    # Patch db.flush: fail on 2nd call (Document flushed, Revision flush raises)
    # Storage uploads happen BEFORE any DB flush in _write_document
    original_flush = db_session.flush
    call_count = [0]

    async def patched_flush(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("Simulated DB failure on revision flush")
        return await original_flush(*args, **kwargs)

    db_session.flush = patched_flush
    try:
        result = await import_document_plan(
            db_session, storage,
            club_id=active_club.id,
            plan_path=plan_path,
            source_dir=tmp_path,
            apply=True,
        )
    finally:
        db_session.flush = original_flush

    assert not result.success
    # Both uploaded objects must be cleaned up
    assert len(storage._store) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-14  İkinci aynı run → idempotent skip
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi14_second_identical_run_is_idempotent(
    db_session, active_club, tmp_path
):
    storage = InMemoryStorageService()
    _, _, entry = _setup_single_doc(tmp_path, "MYK-DBI14-001")
    plan_path = _write_plan(tmp_path, _build_plan([entry]))

    r1 = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )
    assert r1.success, r1.errors
    assert r1.created_documents == 1

    r2 = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )
    assert r2.success, r2.errors
    assert r2.skipped_documents == 1
    assert r2.created_documents == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-15  İkinci run farklı SHA → hard fail (overwrite engellenir)
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi15_second_run_different_hash_blocks(
    db_session, active_club, tmp_path
):
    storage = InMemoryStorageService()
    code = "MYK-DBI15-001"

    src1 = tmp_path / "v1"
    src1.mkdir()
    _, _, entry1 = _setup_single_doc(src1, code,
                                      pdf_content=b"v1 pdf",
                                      docx_content=b"v1 docx")
    r1 = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=_write_plan_to(tmp_path / "p1.json", _build_plan([entry1])),
        source_dir=src1,
        apply=True,
    )
    assert r1.success, r1.errors

    src2 = tmp_path / "v2"
    src2.mkdir()
    _, _, entry2 = _setup_single_doc(src2, code,
                                      pdf_content=b"v2 DIFFERENT",
                                      docx_content=b"v2 docx diff")
    r2 = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=_write_plan_to(tmp_path / "p2.json", _build_plan([entry2])),
        source_dir=src2,
        apply=True,
    )

    assert not r2.success
    assert any("çakışma" in e.lower() for e in r2.errors)


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-16  duplicate_codes listesindeki belgeler write batch'e alınmaz
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi16_duplicate_code_plan_items_skipped(
    db_session, active_club, tmp_path
):
    storage = InMemoryStorageService()
    code_clean = "MYK-DBI16-CLEAN"
    code_dup = "MYK-DBI16-DUP"

    _, _, entry_clean = _setup_single_doc(tmp_path, code_clean)
    _, _, entry_dup = _setup_single_doc(tmp_path, code_dup)

    plan = _build_plan(
        [entry_clean, entry_dup],
        duplicate_codes=[
            {
                "doc_code": code_dup,
                "stems": [f"{code_dup.lower()}_r01"],
                "filenames": [f"{code_dup}_R01.pdf"],
            }
        ],
    )
    plan_path = _write_plan(tmp_path, plan)

    result = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=plan_path,
        source_dir=tmp_path,
        apply=True,
    )

    assert result.success, result.errors
    assert result.created_documents == 1

    db_docs = (await db_session.execute(
        select(Document).where(Document.club_id == active_club.id)
    )).scalars().all()
    codes_in_db = {d.code for d in db_docs}
    assert code_clean in codes_in_db
    assert code_dup not in codes_in_db


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-17  Farklı kulüp → tenant isolation (aynı kod farklı kulüplerde OK)
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi17_wrong_club_isolation(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()

    other_club = Club(
        id=uuid.uuid4(),
        slug=f"other-{uuid.uuid4().hex[:8]}",
        name="Diğer Kulüp",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(other_club)
    await db_session.flush()

    code = "MYK-DBI17-ISO"
    pdf, docx, entry = _setup_single_doc(tmp_path, code)
    plan = _build_plan([entry])

    # active_club'a import → commit
    r1 = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=_write_plan(tmp_path, plan),
        source_dir=tmp_path,
        apply=True,
    )
    assert r1.success, r1.errors

    # other_club aynı kod → çakışma yok (farklı club_id) → commit
    other_src = tmp_path / "other"
    other_src.mkdir()
    _write_source(other_src, f"{code}_R01.pdf", pdf)
    _write_source(other_src, f"{code}_R01.docx", docx)
    r2 = await import_document_plan(
        db_session, storage,
        club_id=other_club.id,
        plan_path=_write_plan(other_src, plan),
        source_dir=other_src,
        apply=True,
    )
    assert r2.success, r2.errors

    active_docs = (await db_session.execute(
        select(Document).where(Document.club_id == active_club.id)
    )).scalars().all()
    other_docs = (await db_session.execute(
        select(Document).where(Document.club_id == other_club.id)
    )).scalars().all()

    assert len(active_docs) >= 1
    assert len(other_docs) >= 1
    assert {d.id for d in active_docs}.isdisjoint({d.id for d in other_docs})


# ═══════════════════════════════════════════════════════════════════════════════
# DBI-18  Import raporu sayımları doğru
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dbi18_import_report_counts_correct(db_session, active_club, tmp_path):
    storage = InMemoryStorageService()

    docs = []
    for i in range(1, 4):
        _, _, entry = _setup_single_doc(
            tmp_path, f"MYK-DBI18-{i:03d}",
            pdf_content=f"pdf-{i}".encode(),
            docx_content=f"docx-{i}".encode(),
        )
        docs.append(entry)

    result = await import_document_plan(
        db_session, storage,
        club_id=active_club.id,
        plan_path=_write_plan(tmp_path, _build_plan(docs)),
        source_dir=tmp_path,
        apply=True,
    )

    assert result.success, result.errors
    assert result.created_documents == 3
    assert result.created_revisions == 3
    assert result.created_files == 6        # 3 PDF + 3 DOCX
    assert result.skipped_documents == 0
    assert len(result.uploaded_objects) == 6
    assert len(result.documents) == 3
    assert result.applied is True
    assert result.plan_sha256 != ""
    assert result.duration_seconds > 0

    d = result.to_dict()
    assert d["success"] is True
    assert d["applied"] is True
    assert d["created_documents"] == 3
    assert d["created_files"] == 6
    assert d["uploaded_objects_count"] == 6
    assert len(d["documents"]) == 3
