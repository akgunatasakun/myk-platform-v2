"""Sprint 26B-1 kişisel evrak API güvenlik testleri."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routers import person_documents as router_module
from app.core.security import create_access_token, hash_password
from app.database import get_db
from app.dependencies.documents_storage import get_dms_storage
from app.dependencies.person_document_scan import get_person_document_scanner
from app.dependencies.person_document_policy import get_health_document_legal_gate
from app.main import app
from app.models.audit import AuditLog
from app.models.club import Club
from app.models.person import Person
from app.models.person_document import PersonDocument
from app.models.person_guardian import PersonGuardian
from app.models.user import User
from app.services.malware_scan import MalwareScanner, ScanStatus
from app.services.storage import ObjectStorageService

pytestmark = pytest.mark.asyncio
URL = "/api/v1/person-documents"
PDF = b"%PDF-1.7\n" + b"test-content"


class MemoryStorage(ObjectStorageService):
    def __init__(self) -> None:
        self.data: dict[str, tuple[bytes, str]] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        self.data[key] = (data, content_type)
        return key

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.data

    async def copy(self, src_key: str, dst_key: str) -> None:
        self.data[dst_key] = self.data[src_key]

    async def presigned_url(self, key: str, expires: int) -> str:
        raise AssertionError("Kişisel evrak akışı presign kullanmamalı")

    async def download(self, key: str) -> bytes:
        if key not in self.data:
            raise KeyError(key)
        return self.data[key][0]


class FakeScanner(MalwareScanner):
    def __init__(self, result: ScanStatus = "clean") -> None:
        self.result = result

    async def scan(self, data: bytes, mime_type: str) -> ScanStatus:
        return self.result


@pytest_asyncio.fixture
async def document_client(
    db_session: AsyncSession,
) -> AsyncGenerator[tuple[AsyncClient, MemoryStorage, FakeScanner], None]:
    storage = MemoryStorage()
    scanner = FakeScanner()

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_dms_storage] = lambda: storage
    app.dependency_overrides[get_person_document_scanner] = lambda: scanner
    app.dependency_overrides[get_health_document_legal_gate] = lambda: False
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, storage, scanner
    app.dependency_overrides.clear()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _person(
    db: AsyncSession,
    club: Club,
    name: str = "Çocuk",
    *,
    birth_date: date | None = None,
) -> Person:
    person = Person(
        id=uuid.uuid4(), club_id=club.id, first_name=name, last_name="Test",
        birth_date=birth_date,
    )
    db.add(person)
    await db.flush()
    return person


async def _guardian_account(
    db: AsyncSession, club: Club, child: Person, *, active_link: bool = True
) -> tuple[User, PersonGuardian, str]:
    guardian = await _person(db, club, "Veli")
    user = User(
        id=uuid.uuid4(),
        club_id=club.id,
        person_id=guardian.id,
        email=f"veli-{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("Veli1234!"),
        full_name="Test Veli",
        role="veli",
        is_active=True,
        is_deleted=False,
    )
    db.add(user)
    await db.flush()
    link = PersonGuardian(
        id=uuid.uuid4(),
        club_id=club.id,
        athlete_person_id=child.id,
        guardian_person_id=guardian.id,
        is_primary=True,
        can_consent=True,
        is_active=active_link,
        revoked_at=None if active_link else datetime.now(timezone.utc),
    )
    db.add(link)
    await db.flush()
    token = create_access_token(str(user.id), str(club.id), "veli")
    return user, link, token


def _upload_data(subject_id: uuid.UUID, **extra: str) -> dict[str, str]:
    return {"subject_person_id": str(subject_id), "document_type": "identity_copy", **extra}


async def test_upload_magic_mime_and_response_hides_storage_key(
    document_client, db_session, test_club, yonetici_token
):
    client, storage, _ = document_client
    child = await _person(db_session, test_club)
    response = await client.post(
        URL,
        headers=_auth(yonetici_token),
        data=_upload_data(child.id),
        files={"file": ("kimlik.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "storage_key" not in body
    assert body["mime_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF)
    assert len(storage.data) == 1


async def test_cross_club_subject_is_404(
    document_client, db_session, test_club, yonetici_token
):
    client, _, _ = document_client
    other = Club(id=uuid.uuid4(), slug=f"other-{uuid.uuid4().hex[:8]}", name="Diğer")
    db_session.add(other)
    await db_session.flush()
    outsider = await _person(db_session, other)
    response = await client.post(
        URL,
        headers=_auth(yonetici_token),
        data=_upload_data(outsider.id),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 404


async def test_guardian_cannot_upload_for_unrelated_child(
    document_client, db_session, test_club
):
    client, _, _ = document_client
    own_child = await _person(db_session, test_club, "Kendi")
    stranger = await _person(db_session, test_club, "Yabancı")
    _, _, token = await _guardian_account(db_session, test_club, own_child)
    response = await client.post(
        URL,
        headers=_auth(token),
        data=_upload_data(stranger.id),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 403


async def test_revoked_guardian_is_403(document_client, db_session, test_club):
    client, _, _ = document_client
    child = await _person(db_session, test_club)
    _, _, token = await _guardian_account(
        db_session, test_club, child, active_link=False
    )
    response = await client.post(
        URL,
        headers=_auth(token),
        data=_upload_data(child.id),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 403


async def test_guardian_without_person_link_is_403(
    document_client, db_session, test_club
):
    client, _, _ = document_client
    child = await _person(db_session, test_club)
    user = User(
        id=uuid.uuid4(), club_id=test_club.id,
        email=f"unlinked-{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("Veli1234!"), full_name="Bağsız Veli",
        role="veli", is_active=True, is_deleted=False, person_id=None,
    )
    db_session.add(user)
    await db_session.flush()
    token = create_access_token(str(user.id), str(test_club.id), "veli")
    response = await client.get(
        URL, headers=_auth(token), params={"subject_person_id": str(child.id)}
    )
    assert response.status_code == 403


async def test_spoofed_mime_is_rejected(
    document_client, db_session, test_club, yonetici_token
):
    client, _, _ = document_client
    child = await _person(db_session, test_club)
    response = await client.post(
        URL,
        headers=_auth(yonetici_token),
        data=_upload_data(child.id),
        files={"file": ("fake.pdf", b"not-a-pdf", "application/pdf")},
    )
    assert response.status_code == 415


async def test_file_size_and_subject_quota(
    document_client, db_session, test_club, test_user, yonetici_token, monkeypatch
):
    client, _, _ = document_client
    child = await _person(db_session, test_club)
    monkeypatch.setattr("app.services.person_document_service.FILE_MAX_BYTES", 8)
    too_big = await client.post(
        URL, headers=_auth(yonetici_token), data=_upload_data(child.id),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert too_big.status_code == 413
    monkeypatch.setattr("app.services.person_document_service.FILE_MAX_BYTES", 20 * 1024 * 1024)

    db_session.add(PersonDocument(
        id=uuid.uuid4(), club_id=test_club.id, subject_person_id=child.id,
        uploaded_by_user_id=test_user.id, document_type="identity_copy",
        original_filename="old.pdf", storage_key=f"old/{uuid.uuid4()}",
        mime_type="application/pdf", size_bytes=100 * 1024 * 1024,
        scan_status="clean", is_sensitive=False,
    ))
    await db_session.flush()
    quota = await client.post(
        URL, headers=_auth(yonetici_token), data=_upload_data(child.id),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert quota.status_code == 507


async def test_daily_upload_quota(
    document_client, db_session, test_club, test_user, yonetici_token
):
    client, _, _ = document_client
    child = await _person(db_session, test_club)
    for index in range(20):
        db_session.add(PersonDocument(
            id=uuid.uuid4(), club_id=test_club.id, subject_person_id=child.id,
            uploaded_by_user_id=test_user.id, document_type="identity_copy",
            original_filename=f"{index}.pdf", storage_key=f"daily/{uuid.uuid4()}",
            mime_type="application/pdf", size_bytes=1, scan_status="clean",
            is_sensitive=False,
        ))
    await db_session.flush()
    response = await client.post(
        URL, headers=_auth(yonetici_token), data=_upload_data(child.id),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 429


@pytest.mark.parametrize("scan_result", ["pending", "infected", "failed"])
async def test_untrusted_scan_status_blocks_view_and_download(
    document_client, db_session, test_club, yonetici_token, scan_result
):
    client, _, scanner = document_client
    scanner.result = scan_result
    child = await _person(db_session, test_club)
    upload = await client.post(
        URL, headers=_auth(yonetici_token), data=_upload_data(child.id),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert upload.status_code == 201
    download = await client.get(
        f"{URL}/{upload.json()['id']}/download", headers=_auth(yonetici_token)
    )
    assert download.status_code == 423
    view = await client.get(
        f"{URL}/{upload.json()['id']}/view", headers=_auth(yonetici_token)
    )
    assert view.status_code == 423


async def test_health_requires_basis_and_denies_unauthorized_file(
    document_client, db_session, test_club, test_user, yonetici_token
):
    client, storage, _ = document_client
    child = await _person(db_session, test_club)
    missing_basis = await client.post(
        URL, headers=_auth(yonetici_token),
        data={"subject_person_id": str(child.id), "document_type": "health_report"},
        files={"file": ("health.pdf", PDF, "application/pdf")},
    )
    assert missing_basis.status_code == 403

    document = PersonDocument(
        id=uuid.uuid4(), club_id=test_club.id, subject_person_id=child.id,
        uploaded_by_user_id=test_user.id, document_type="health_report",
        original_filename="health.pdf", storage_key=f"health/{uuid.uuid4()}",
        mime_type="application/pdf", size_bytes=len(PDF), scan_status="clean",
        is_sensitive=True, processing_basis="test-basis",
    )
    db_session.add(document)
    await db_session.flush()
    await storage.upload(document.storage_key, PDF, "application/pdf")
    coach = User(
        id=uuid.uuid4(), club_id=test_club.id,
        email=f"coach-{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("Coach1234!"), full_name="Coach",
        role="antrenor", is_active=True, is_deleted=False,
    )
    db_session.add(coach)
    await db_session.flush()
    token = create_access_token(str(coach.id), str(test_club.id), "antrenor")
    response = await client.get(f"{URL}/{document.id}/download", headers=_auth(token))
    assert response.status_code == 403


async def test_production_without_scan_engine_is_503(
    document_client, db_session, test_club, yonetici_token, monkeypatch
):
    client, _, _ = document_client
    child = await _person(db_session, test_club)
    app.dependency_overrides[get_person_document_scanner] = lambda: None
    monkeypatch.setattr(router_module.settings, "myk_env", "production")
    response = await client.post(
        URL, headers=_auth(yonetici_token), data=_upload_data(child.id),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 503


async def test_production_health_requires_legal_gate(
    document_client, db_session, test_club, yonetici_token, monkeypatch
):
    client, _, _ = document_client
    child = await _person(db_session, test_club)
    monkeypatch.setattr(router_module.settings, "myk_env", "production")
    response = await client.post(
        URL,
        headers=_auth(yonetici_token),
        data={
            "subject_person_id": str(child.id),
            "document_type": "health_report",
            "processing_basis": "test-basis",
        },
        files={"file": ("health.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 403
    assert "hukuki metin" in response.json()["detail"]


async def test_health_gate_open_allows_health_report_upload(
    document_client, db_session, test_club, yonetici_token, monkeypatch
):
    """HEALTH_DOCUMENT_GATE_OPEN=true olduğunda health_report yüklenebilir."""
    client, _, _ = document_client
    child = await _person(db_session, test_club)
    app.dependency_overrides[get_health_document_legal_gate] = lambda: True
    monkeypatch.setattr(router_module.settings, "myk_env", "production")
    response = await client.post(
        URL,
        headers=_auth(yonetici_token),
        data={
            "subject_person_id": str(child.id),
            "document_type": "health_report",
            "processing_basis": "KVKK Madde 6 — sağlık verisi işleme onayı",
        },
        files={"file": ("health.pdf", PDF, "application/pdf")},
    )
    # FakeScanner(clean) + gate açık → 201
    assert response.status_code == 201
    body = response.json()
    assert body["is_sensitive"] is True
    assert body["document_type"] == "health_report"


async def test_guardian_access_closes_when_subject_turns_18(
    document_client, db_session, test_club
):
    client, _, _ = document_client
    today = date.today()
    child = await _person(
        db_session,
        test_club,
        birth_date=date(today.year - 18, today.month, today.day),
    )
    _, _, token = await _guardian_account(db_session, test_club, child)
    response = await client.post(
        URL,
        headers=_auth(token),
        data=_upload_data(child.id),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 403


async def test_upload_view_download_audit(
    document_client, db_session, test_club, test_user, yonetici_token
):
    client, _, _ = document_client
    child = await _person(db_session, test_club)
    upload = await client.post(
        URL, headers=_auth(yonetici_token), data=_upload_data(child.id),
        files={"file": ("x.pdf", PDF, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]
    assert (await client.get(f"{URL}/{document_id}", headers=_auth(yonetici_token))).status_code == 200
    assert (await client.get(f"{URL}/{document_id}/view", headers=_auth(yonetici_token))).status_code == 200
    assert (await client.get(f"{URL}/{document_id}/download", headers=_auth(yonetici_token))).status_code == 200
    rows = await db_session.execute(
        select(AuditLog.action).where(
            AuditLog.club_id == test_club.id,
            AuditLog.resource_id == document_id,
        )
    )
    assert set(rows.scalars().all()) >= {
        "person_document_uploaded", "person_document_viewed", "person_document_downloaded"
    }
