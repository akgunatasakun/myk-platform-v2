"""DMS (Belge Yönetim Sistemi) API testleri — DMS-01 .. DMS-26.

Test kapsamı:
  - RBAC / kimlik doğrulama
  - Belge CRUD ve soft delete
  - Tenant izolasyonu
  - Revizyon yaşam döngüsü
  - Dosya yükleme + backend streaming download (MinIO URL sızmaz)
  - Dry-run importer unit testleri

InMemoryStorageService: test ortamı — MinIO bağlantısı yoktur.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.dependencies.documents_storage import get_dms_storage
from app.main import app
from app.models.club import Club
from app.models.documents import Document, DocumentRevision
from app.models.user import User
from app.services.storage import ObjectStorageService

pytestmark = pytest.mark.asyncio

DOCS_URL = "/api/v1/documents"


# ── InMemory storage mock ─────────────────────────────────────────────────────

class InMemoryStorageService(ObjectStorageService):
    """Test için bellek içi storage."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[bytes, str]] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        self._store[key] = (data, content_type)
        return key

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._store

    async def copy(self, src_key: str, dst_key: str) -> None:
        if src_key not in self._store:
            raise KeyError(src_key)
        self._store[dst_key] = self._store[src_key]

    async def presigned_url(self, key: str, expires: int) -> str:
        return f"http://test-storage/{key}?expires={expires}"

    async def download(self, key: str) -> bytes:
        if key not in self._store:
            raise KeyError(key)
        data, _ = self._store[key]
        return data


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client_with_storage(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Client + InMemoryStorageService inject edilmiş."""
    from app.database import get_db
    from httpx import ASGITransport

    storage = InMemoryStorageService()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_dms_storage] = lambda: storage

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def antrenor_user(db_session: AsyncSession, test_club: Club) -> User:
    from app.core.security import hash_password
    user = User(
        id=uuid.uuid4(),
        club_id=test_club.id,
        email=f"antrenor-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Antrenor99!"),
        full_name="Test Antrenör",
        role="antrenor",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
def antrenor_token(test_club: Club, antrenor_user: User) -> str:
    return create_access_token(str(antrenor_user.id), str(test_club.id), antrenor_user.role)


async def _create_doc(client: AsyncClient, token: str, code: str = "DOC-001", title: str = "Test Belgesi") -> dict:
    resp = await client.post(
        DOCS_URL,
        json={"code": code, "title": title, "document_type": "prosedur"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_revision(
    client: AsyncClient,
    token: str,
    doc_id: str,
    rev_code: str = "R00",
    is_current: bool = False,
) -> dict:
    resp = await client.post(
        f"{DOCS_URL}/{doc_id}/revisions",
        json={"revision_code": rev_code, "is_current": is_current},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── DMS-01: Kimlik doğrulama gerektiren endpoint 401 ─────────────────────────

async def test_list_documents_unauthorized(client: AsyncClient) -> None:
    """DMS-01: Token olmadan 401."""
    resp = await client.get(DOCS_URL)
    assert resp.status_code == 401


# ── DMS-02: antrenor belge oluşturamaz ───────────────────────────────────────

async def test_create_document_forbidden(
    client: AsyncClient,
    antrenor_token: str,
) -> None:
    """DMS-02: antrenor rolü belge:create yetkisine sahip değil → 403."""
    resp = await client.post(
        DOCS_URL,
        json={"code": "DOC-X", "title": "Test", "document_type": "diger"},
        headers=_auth(antrenor_token),
    )
    assert resp.status_code == 403


# ── DMS-03: Belge başarıyla oluşturulur ───────────────────────────────────────

async def test_create_document_success(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-03: Yönetici belge oluşturabilir."""
    resp = await client.post(
        DOCS_URL,
        json={"code": f"DOC-{uuid.uuid4().hex[:4]}", "title": "Oluştur Testi", "document_type": "form"},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["document_type"] == "form"
    assert data["content_status"] == "taslak"


# ── DMS-04: Bulunamayan belge 404 ─────────────────────────────────────────────

async def test_get_document_not_found(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-04: Olmayan UUID → 404."""
    resp = await client.get(f"{DOCS_URL}/{uuid.uuid4()}", headers=_auth(yonetici_token))
    assert resp.status_code == 404


# ── DMS-05: Belge detayı revizyonları içerir ─────────────────────────────────

async def test_get_document_detail(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-05: GET /documents/{id} → revisions listesi embedded."""
    doc = await _create_doc(client, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    resp = await client.get(f"{DOCS_URL}/{doc['id']}", headers=_auth(yonetici_token))
    assert resp.status_code == 200
    assert "revisions" in resp.json()


# ── DMS-06: Belge güncelle ───────────────────────────────────────────────────

async def test_update_document(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-06: PATCH /documents/{id} → başlık güncellenir."""
    doc = await _create_doc(client, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    resp = await client.patch(
        f"{DOCS_URL}/{doc['id']}",
        json={"title": "Güncellenmiş Başlık", "content_status": "tamamlandi"},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["title"] == "Güncellenmiş Başlık"
    assert updated["content_status"] == "tamamlandi"


# ── DMS-07: Soft delete ──────────────────────────────────────────────────────

async def test_soft_delete_document(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-07: DELETE → 204; GET → 404 (soft deleted)."""
    doc = await _create_doc(client, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    del_resp = await client.delete(f"{DOCS_URL}/{doc['id']}", headers=_auth(yonetici_token))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"{DOCS_URL}/{doc['id']}", headers=_auth(yonetici_token))
    assert get_resp.status_code == 404


# ── DMS-08: Tenant izolasyonu (belge) ────────────────────────────────────────

async def test_tenant_isolation_document(
    client: AsyncClient,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    """DMS-08: Başka kulübün belgesi → 404."""
    from app.core.security import hash_password
    from app.models.club import Club

    # Farklı kulüp + kullanıcı oluştur
    other_club = Club(
        id=uuid.uuid4(),
        slug=f"other-{uuid.uuid4().hex[:6]}",
        name="Diğer Kulüp",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(other_club)
    other_user = User(
        id=uuid.uuid4(),
        club_id=other_club.id,
        email=f"other-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Other1234!"),
        full_name="Other User",
        role="kulup_yonetici",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(other_user)
    await db_session.flush()

    other_token = create_access_token(str(other_user.id), str(other_club.id), other_user.role)

    # Diğer kulüp belge oluşturur
    resp = await client.post(
        DOCS_URL,
        json={"code": f"OTHER-{uuid.uuid4().hex[:4]}", "title": "Diğer Belge", "document_type": "diger"},
        headers=_auth(other_token),
    )
    assert resp.status_code == 201
    other_doc_id = resp.json()["id"]

    # Orijinal yönetici diğer kulübün belgesine erişemez
    resp2 = await client.get(f"{DOCS_URL}/{other_doc_id}", headers=_auth(yonetici_token))
    assert resp2.status_code == 404


# ── DMS-09: Revizyon oluştur ─────────────────────────────────────────────────

async def test_create_revision_success(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-09: POST /documents/{id}/revisions → 201."""
    doc = await _create_doc(client, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    resp = await client.post(
        f"{DOCS_URL}/{doc['id']}/revisions",
        json={"revision_code": "R00", "status": "taslak"},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 201
    rev = resp.json()
    assert rev["revision_code"] == "R00"


# ── DMS-10: Duplicate revizyon kodu 409 ──────────────────────────────────────

async def test_create_revision_duplicate_code(
    client: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-10: Aynı revision_code → 409."""
    doc = await _create_doc(client, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    await _create_revision(client, yonetici_token, doc["id"], "R00")
    resp = await client.post(
        f"{DOCS_URL}/{doc['id']}/revisions",
        json={"revision_code": "R00"},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 409


# ── DMS-11: is_current=True öncekini sıfırlar ────────────────────────────────

async def test_set_current_revision_clears_previous(
    client: AsyncClient,
    yonetici_token: str,
    db_session: AsyncSession,
) -> None:
    """DMS-11: Yeni is_current=True → eski current is_current=False olur."""
    from sqlalchemy import select

    doc = await _create_doc(client, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev1 = await _create_revision(client, yonetici_token, doc["id"], "R00", is_current=True)

    # R01 güncel olarak işaretle
    await _create_revision(client, yonetici_token, doc["id"], "R01", is_current=True)

    # R00 artık güncel olmamalı
    result = await db_session.execute(
        select(DocumentRevision).where(DocumentRevision.id == uuid.UUID(rev1["id"]))
    )
    r0 = result.scalar_one()
    assert r0.is_current is False


# ── DMS-12: DOCX dosyası yükle ───────────────────────────────────────────────

async def test_upload_docx_file(
    client_with_storage: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-12: DOCX yükleme → 201, storage_key dolu."""
    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")

    fake_docx = b"PK\x03\x04" + b"\x00" * 100  # zip magic bytes (docx)
    resp = await client_with_storage.post(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files",
        files={"file": ("test.docx", fake_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 201
    file_data = resp.json()
    assert file_data["storage_key"] != ""
    assert "sha256" in file_data


# ── DMS-13: PDF dosyası yükle ─────────────────────────────────────────────────

async def test_upload_pdf_file(
    client_with_storage: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-13: PDF yükleme → 201."""
    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")

    fake_pdf = b"%PDF-1.4 fake content"
    resp = await client_with_storage.post(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files",
        files={"file": ("test.pdf", fake_pdf, "application/pdf")},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 201
    assert resp.json()["mime_type"] == "application/pdf"


# ── DMS-14: Geçersiz MIME → 415 ──────────────────────────────────────────────

async def test_upload_invalid_mime(
    client_with_storage: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-14: Desteklenmeyen MIME → 415."""
    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")

    resp = await client_with_storage.post(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files",
        files={"file": ("test.exe", b"MZ\x00\x00", "application/x-msdownload")},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 415


# ── DMS-15: Aynı revizyona iki farklı dosya yükle ────────────────────────────

async def test_upload_two_files_same_revision(
    client_with_storage: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-15: Aynı revizyona iki farklı dosya → her ikisi de 201."""
    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")
    url = f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files"
    headers = _auth(yonetici_token)

    r1 = await client_with_storage.post(
        url,
        files={"file": ("file1.pdf", b"%PDF-1.4 file1", "application/pdf")},
        headers=headers,
    )
    assert r1.status_code == 201

    r2 = await client_with_storage.post(
        url,
        files={"file": ("file2.pdf", b"%PDF-1.4 file2 different content", "application/pdf")},
        headers=headers,
    )
    assert r2.status_code == 201


# ── DMS-16: Duplicate SHA-256 aynı revizyonda 409 ────────────────────────────

async def test_upload_duplicate_sha256_same_revision(
    client_with_storage: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-16: Aynı içerikli dosya aynı revizyona → 409."""
    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")
    url = f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files"
    headers = _auth(yonetici_token)
    content = b"%PDF-1.4 same content"

    r1 = await client_with_storage.post(
        url,
        files={"file": ("file_a.pdf", content, "application/pdf")},
        headers=headers,
    )
    assert r1.status_code == 201

    r2 = await client_with_storage.post(
        url,
        files={"file": ("file_b.pdf", content, "application/pdf")},  # Aynı içerik
        headers=headers,
    )
    assert r2.status_code == 409


# ── DMS-17: Download response 200 (backend streaming) ────────────────────────

async def test_download_streams_content(
    client_with_storage: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-17: GET .../files/{id}/download → 200, body == yüklenen bytes."""
    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")

    content = b"%PDF-1.4 download test content"
    upload_resp = await client_with_storage.post(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files",
        files={"file": ("dl_test.pdf", content, "application/pdf")},
        headers=_auth(yonetici_token),
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    dl_resp = await client_with_storage.get(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files/{file_id}/download",
        headers=_auth(yonetici_token),
    )
    assert dl_resp.status_code == 200
    assert dl_resp.content == content


# ── DMS-18: Tenant izolasyonu (revizyon) ─────────────────────────────────────

async def test_tenant_isolation_revision(
    client: AsyncClient,
    db_session: AsyncSession,
    yonetici_token: str,
) -> None:
    """DMS-18: Başka kulübün belgesine revizyon eklenemez."""
    from app.core.security import hash_password
    from app.models.club import Club

    other_club = Club(
        id=uuid.uuid4(),
        slug=f"isol2-{uuid.uuid4().hex[:6]}",
        name="İzolasyon Kulübü 2",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(other_club)
    other_user = User(
        id=uuid.uuid4(),
        club_id=other_club.id,
        email=f"isol2-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Isol2_99!"),
        full_name="Isol User 2",
        role="kulup_yonetici",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(other_user)
    await db_session.flush()
    other_token = create_access_token(str(other_user.id), str(other_club.id), other_user.role)

    # Diğer kulüp belge oluşturur
    other_doc_resp = await client.post(
        DOCS_URL,
        json={"code": f"ISO-{uuid.uuid4().hex[:4]}", "title": "İzolasyon Belgesi", "document_type": "diger"},
        headers=_auth(other_token),
    )
    assert other_doc_resp.status_code == 201
    other_doc_id = other_doc_resp.json()["id"]

    # Orijinal yönetici diğer kulübün belgesine revizyon ekleyemez → 404
    resp = await client.post(
        f"{DOCS_URL}/{other_doc_id}/revisions",
        json={"revision_code": "R00"},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 404


# ── DMS-19: Import dry-run CSV parse ─────────────────────────────────────────

async def test_import_dry_run_parses_manifest() -> None:
    """DMS-19: document_import.run() CSV parse eder, özet döner (no DB)."""
    from app.services.document_import import run

    # Geçici CSV manifest + source-dir oluştur
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "manifest.csv")
        src_dir = os.path.join(tmpdir, "docs")
        os.makedirs(src_dir)
        output_path = os.path.join(tmpdir, "plan.json")

        # Basit manifest
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("belge_kodu,baslik,belge_turu,icerik_durumu,dosya_adi\n")
            f.write("PRO-001,Prosedür 1,prosedur,tamamlandi,pro001.pdf\n")
            f.write("PRO-002,Prosedür 2,prosedur,taslak-içerik-eksik,pro002.pdf\n")

        # Bir dosyayı diske koy
        with open(os.path.join(src_dir, "pro001.pdf"), "wb") as pf:
            pf.write(b"%PDF-1.4 content")

        run(csv_path, src_dir, output_path)

        with open(output_path, encoding="utf-8") as jf:
            plan = json.load(jf)

    summary = plan["summary"]
    assert summary["total_manifest_rows"] == 2
    assert summary["logical_documents"] == 2
    # pro002.pdf diskte yok → unmatched_manifest
    assert summary["unmatched_manifest"] >= 1


# ── DMS-20: Import PDF+DOCX pair tespiti ─────────────────────────────────────

async def test_import_pairs_pdf_docx() -> None:
    """DMS-20: Aynı basename PDF + DOCX → tek mantıksal belge, pair sayılır."""
    from app.services.document_import import run

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "manifest.csv")
        src_dir = os.path.join(tmpdir, "docs")
        os.makedirs(src_dir)
        output_path = os.path.join(tmpdir, "plan.json")

        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("belge_kodu,baslik,belge_turu,icerik_durumu,dosya_adi\n")
            f.write("PRO-010,Belge A,prosedur,tamamlandi,belge_a.pdf\n")
            f.write("PRO-010,Belge A,prosedur,tamamlandi,belge_a.docx\n")

        # Her iki dosyayı diske koy
        with open(os.path.join(src_dir, "belge_a.pdf"), "wb") as pf:
            pf.write(b"%PDF-1.4")
        with open(os.path.join(src_dir, "belge_a.docx"), "wb") as df:
            df.write(b"PK\x03\x04")

        run(csv_path, src_dir, output_path)

        with open(output_path, encoding="utf-8") as jf:
            plan = json.load(jf)

    summary = plan["summary"]
    # belge_a.pdf + belge_a.docx aynı stem → 1 mantıksal belge
    assert summary["logical_documents"] == 1
    assert summary["pdf_docx_pairs"] == 1
    assert summary["single_files"] == 0


# ── DMS-21: Content-Type doğru ───────────────────────────────────────────────

async def test_download_content_type(
    client_with_storage: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-21: download → Content-Type == yüklenen MIME."""
    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")

    resp = await client_with_storage.post(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files",
        files={"file": ("ct_test.pdf", b"%PDF-1.4 ct", "application/pdf")},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    dl = await client_with_storage.get(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files/{file_id}/download",
        headers=_auth(yonetici_token),
    )
    assert dl.status_code == 200
    assert "application/pdf" in dl.headers.get("content-type", "")


# ── DMS-22: Content-Disposition orijinal dosya adını içerir ──────────────────

async def test_download_content_disposition(
    client_with_storage: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-22: download → Content-Disposition attachment; filename=<original>."""
    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")

    resp = await client_with_storage.post(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files",
        files={"file": ("myreport.pdf", b"%PDF-1.4 cd", "application/pdf")},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    dl = await client_with_storage.get(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files/{file_id}/download",
        headers=_auth(yonetici_token),
    )
    assert dl.status_code == 200
    cd = dl.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert "myreport.pdf" in cd


# ── DMS-23: MinIO internal hostname response'a sızmaz ────────────────────────

async def test_download_no_storage_url_leak(
    client_with_storage: AsyncClient,
    yonetici_token: str,
) -> None:
    """DMS-23: download response header/body'de minio:9000 geçmemeli."""
    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")

    resp = await client_with_storage.post(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files",
        files={"file": ("leak_test.pdf", b"%PDF-1.4 leak", "application/pdf")},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    dl = await client_with_storage.get(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files/{file_id}/download",
        headers=_auth(yonetici_token),
    )
    assert dl.status_code == 200

    # Header'larda storage internal hostname veya presigned query param geçmemeli
    headers_str = " ".join(f"{k}: {v}" for k, v in dl.headers.items()).lower()
    assert "minio" not in headers_str
    assert "x-amz" not in headers_str
    assert "x-amz-signature" not in headers_str

    # Body text değil binary — ama paranoya olarak kontrol et
    body_str = dl.content.decode("latin-1")
    assert "minio:9000" not in body_str


# ── DMS-24: Depolama nesnesi eksikse 404 ─────────────────────────────────────

async def test_download_missing_storage_object(
    client_with_storage: AsyncClient,
    yonetici_token: str,
    db_session: AsyncSession,
) -> None:
    """DMS-24: DB kaydı var ama storage'da nesne yoksa → 404."""
    from sqlalchemy import select as sa_select

    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")

    resp = await client_with_storage.post(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files",
        files={"file": ("ghost.pdf", b"%PDF-1.4 ghost", "application/pdf")},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    # Storage'daki nesneyi elle sil (InMemory)
    storage: InMemoryStorageService = app.dependency_overrides[get_dms_storage]()
    storage_key = resp.json()["storage_key"]
    await storage.delete(storage_key)

    dl = await client_with_storage.get(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files/{file_id}/download",
        headers=_auth(yonetici_token),
    )
    assert dl.status_code == 404


# ── DMS-25: RBAC — antrenor download yapamaz ─────────────────────────────────

async def test_download_rbac_antrenor_forbidden(
    client_with_storage: AsyncClient,
    yonetici_token: str,
    antrenor_token: str,
) -> None:
    """DMS-25: antrenor belge:read yetkisi yok → download 403."""
    doc = await _create_doc(client_with_storage, yonetici_token, code=f"DOC-{uuid.uuid4().hex[:4]}")
    rev = await _create_revision(client_with_storage, yonetici_token, doc["id"], "R00")

    resp = await client_with_storage.post(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files",
        files={"file": ("rbac_test.pdf", b"%PDF-1.4 rbac", "application/pdf")},
        headers=_auth(yonetici_token),
    )
    assert resp.status_code == 201
    file_id = resp.json()["id"]

    dl = await client_with_storage.get(
        f"{DOCS_URL}/{doc['id']}/revisions/{rev['id']}/files/{file_id}/download",
        headers=_auth(antrenor_token),
    )
    assert dl.status_code == 403


# ── DMS-26: InMemoryStorage ensure_bucket idempotent ─────────────────────────

async def test_inmemory_storage_download_key_error() -> None:
    """DMS-26: InMemoryStorageService.download() eksik key → KeyError."""
    storage = InMemoryStorageService()
    try:
        await storage.download("nonexistent/key.pdf")
        assert False, "KeyError bekleniyor"
    except KeyError:
        pass  # beklenen
