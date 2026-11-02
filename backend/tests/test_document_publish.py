"""DMS revizyon onaylama / yayımlama testleri — DPB-01 .. DPB-08."""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.club import Club
from app.models.documents import Document, DocumentRevision, DocumentRevisionFile
from app.services.document_bulk_import import import_document_plan
from app.services.document_publish import publish_revisions
from tests.test_document_bulk_import import _build_plan, _setup_single_doc, _write_plan_to
from tests.test_storage import InMemoryStorageService  # type: ignore[import-not-found]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest_asyncio.fixture
async def club(db_session) -> Club:
    c = Club(id=uuid.uuid4(), slug=f"pub-{uuid.uuid4().hex[:8]}", name="Yayın Test",
             plan="starter", is_active=True, settings={})
    db_session.add(c)
    await db_session.flush()
    return c


async def _import(db, storage, club, tmp_path, code, *, rev="R00", status="incelemede",
                  name="v1", pdf=b"pdf", docx=b"docx"):
    src = tmp_path / name
    src.mkdir()
    _, _, e = _setup_single_doc(src, code, pdf_content=pdf, docx_content=docx)
    if status:
        e["revision_code"], e["revision_status"] = rev, status
    r = await import_document_plan(db, storage, club_id=club.id,
                                   plan_path=_write_plan_to(tmp_path / f"{name}.json", _build_plan([e])),
                                   source_dir=src, apply=True)
    assert r.success, r.errors


def _plan(tmp_path: Path, items: list[dict], name="pub.json") -> tuple[Path, str]:
    p = tmp_path / name
    p.write_text(json.dumps({"items": items}), encoding="utf-8")
    return p, _sha(p.read_bytes())


async def _revs(db, code):
    doc = (await db.execute(select(Document).where(Document.code == code))).scalar_one()
    revs = {r.revision_code: r for r in (await db.execute(
        select(DocumentRevision).where(DocumentRevision.document_id == doc.id))).scalars().all()}
    return doc, revs


@pytest.mark.asyncio
async def test_dpb01_preflight_writes_nothing(db_session, club, tmp_path):
    st = InMemoryStorageService()
    await _import(db_session, st, club, tmp_path, "MYK-DPB01-001")
    p, _ = _plan(tmp_path, [{"code": "MYK-DPB01-001", "revision_code": "R00", "target_status": "yayinda"}])
    r = await publish_revisions(db_session, st, club_id=club.id, plan_path=p, apply=False)
    assert r.success, r.errors
    _, revs = await _revs(db_session, "MYK-DPB01-001")
    assert revs["R00"].status == "incelemede"


@pytest.mark.asyncio
async def test_dpb02_publish_new_document(db_session, club, tmp_path):
    st = InMemoryStorageService()
    await _import(db_session, st, club, tmp_path, "MYK-DPB02-001")
    p, sha = _plan(tmp_path, [{"code": "MYK-DPB02-001", "revision_code": "R00",
                               "target_status": "yayinda", "effective_date": "2026-11-02",
                               "note": "YK onayı"}])
    r = await publish_revisions(db_session, st, club_id=club.id, plan_path=p,
                                expected_plan_sha256=sha, apply=True)
    assert r.success, r.errors
    doc, revs = await _revs(db_session, "MYK-DPB02-001")
    assert revs["R00"].status == "yayinda" and revs["R00"].is_current
    assert str(revs["R00"].effective_date) == "2026-11-02"
    assert doc.current_revision_id == revs["R00"].id and doc.content_status == "tamamlandi"
    audit = (await db_session.execute(select(AuditLog).where(
        AuditLog.action == "document_revision_status_changed"))).scalars().all()
    assert len(audit) >= 1


@pytest.mark.asyncio
async def test_dpb03_publish_archives_previous_current(db_session, club, tmp_path):
    st = InMemoryStorageService()
    code = "MYK-DPB03-001"
    await _import(db_session, st, club, tmp_path, code, status=None, name="a", pdf=b"a", docx=b"ad")
    await _import(db_session, st, club, tmp_path, code, rev="R02", name="b", pdf=b"b", docx=b"bd")
    p, sha = _plan(tmp_path, [{"code": code, "revision_code": "R02", "target_status": "yayinda"}])
    r = await publish_revisions(db_session, st, club_id=club.id, plan_path=p,
                                expected_plan_sha256=sha, apply=True)
    assert r.success, r.errors
    doc, revs = await _revs(db_session, code)
    assert revs["R01"].status == "arsivlendi" and not revs["R01"].is_current
    assert revs["R02"].status == "yayinda" and revs["R02"].is_current
    assert doc.current_revision_id == revs["R02"].id


@pytest.mark.asyncio
async def test_dpb04_approve_only_keeps_current(db_session, club, tmp_path):
    st = InMemoryStorageService()
    code = "MYK-DPB04-001"
    await _import(db_session, st, club, tmp_path, code, status=None, name="a", pdf=b"a", docx=b"ad")
    await _import(db_session, st, club, tmp_path, code, rev="R02", name="b", pdf=b"b", docx=b"bd")
    p, sha = _plan(tmp_path, [{"code": code, "revision_code": "R02", "target_status": "onaylandi"}])
    r = await publish_revisions(db_session, st, club_id=club.id, plan_path=p,
                                expected_plan_sha256=sha, apply=True)
    assert r.success, r.errors
    doc, revs = await _revs(db_session, code)
    assert revs["R02"].status == "onaylandi" and revs["R01"].status == "yayinda"
    assert doc.current_revision_id == revs["R01"].id


@pytest.mark.asyncio
async def test_dpb05_replace_files(db_session, club, tmp_path):
    st = InMemoryStorageService()
    code = "MYK-DPB05-001"
    await _import(db_session, st, club, tmp_path, code)
    src = tmp_path / "onayli"
    src.mkdir()
    (src / "son.pdf").write_bytes(b"final pdf")
    (src / "son.docx").write_bytes(b"final docx")
    p, sha = _plan(tmp_path, [{"code": code, "revision_code": "R00", "target_status": "yayinda",
                               "replace_files": [
                                   {"filename": "son.pdf", "file_role": "published", "sha256": _sha(b"final pdf")},
                                   {"filename": "son.docx", "file_role": "source", "sha256": _sha(b"final docx")}]}])
    r = await publish_revisions(db_session, st, club_id=club.id, plan_path=p, source_dir=src,
                                expected_plan_sha256=sha, apply=True)
    assert r.success, r.errors
    _, revs = await _revs(db_session, code)
    files = (await db_session.execute(select(DocumentRevisionFile).where(
        DocumentRevisionFile.revision_id == revs["R00"].id))).scalars().all()
    primary = [f for f in files if f.is_primary]
    assert len(primary) == 1 and primary[0].original_filename == "son.pdf"
    assert sum(1 for f in files if f.file_role == "other") == 2
    assert len(files) == 4


@pytest.mark.asyncio
async def test_dpb06_bad_sha_rolls_back_everything(db_session, club, tmp_path):
    st = InMemoryStorageService()
    await _import(db_session, st, club, tmp_path, "MYK-DPB06-001", name="a", pdf=b"a", docx=b"ad")
    await _import(db_session, st, club, tmp_path, "MYK-DPB06-002", name="b", pdf=b"b", docx=b"bd")
    before = len(st._store)
    src = tmp_path / "onayli"
    src.mkdir()
    (src / "x.pdf").write_bytes(b"x")
    p, sha = _plan(tmp_path, [
        {"code": "MYK-DPB06-001", "revision_code": "R00", "target_status": "yayinda"},
        {"code": "MYK-DPB06-002", "revision_code": "R00", "target_status": "yayinda",
         "replace_files": [{"filename": "x.pdf", "file_role": "published", "sha256": "0" * 64}]}])
    r = await publish_revisions(db_session, st, club_id=club.id, plan_path=p, source_dir=src,
                                expected_plan_sha256=sha, apply=True)
    assert not r.success
    assert len(st._store) == before


@pytest.mark.asyncio
async def test_dpb07_apply_requires_plan_sha(db_session, club, tmp_path):
    st = InMemoryStorageService()
    await _import(db_session, st, club, tmp_path, "MYK-DPB07-001")
    p, _ = _plan(tmp_path, [{"code": "MYK-DPB07-001", "revision_code": "R00", "target_status": "yayinda"}])
    r = await publish_revisions(db_session, st, club_id=club.id, plan_path=p, apply=True)
    assert not r.success


@pytest.mark.asyncio
async def test_dpb08_already_target_is_skipped(db_session, club, tmp_path):
    st = InMemoryStorageService()
    code = "MYK-DPB08-001"
    await _import(db_session, st, club, tmp_path, code, status=None)
    p, sha = _plan(tmp_path, [{"code": code, "revision_code": "R01", "target_status": "yayinda"}])
    r = await publish_revisions(db_session, st, club_id=club.id, plan_path=p,
                                expected_plan_sha256=sha, apply=True)
    assert r.success and r.items[0].skipped
