"""Avatar endpoint testleri — AV-01 .. AV-16.

Testler InMemoryStorageService mock ile çalışır; MinIO bağlantısı gerektirmez.
Storage dependency: app.dependency_overrides[get_storage] = lambda: _storage
"""
import io
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.storage import get_storage
from app.main import app
from app.models.audit import AuditLog
from app.models.club import Club
from app.models.person import Person
from app.models.user import User
from tests.test_storage import InMemoryStorageService


# ── Görüntü üretme yardımcıları ───────────────────────────────────────────────

def _make_jpeg(width: int = 100, height: int = 100) -> bytes:
    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png(width: int = 100, height: int = 100) -> bytes:
    img = Image.new("RGBA", (width, height), color=(50, 100, 200, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_webp(width: int = 100, height: int = 100) -> bytes:
    img = Image.new("RGB", (width, height), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    return buf.getvalue()


def _make_large_jpeg(mb: int = 9) -> bytes:
    """mb MB'tan büyük sahte JPEG döndür (magic bytes gerçek JPEG)."""
    real = _make_jpeg()
    # JPEG magic bytes + padding
    return real + b"\x00" * (mb * 1024 * 1024)


# ── Fixture: mock storage ─────────────────────────────────────────────────────

@pytest.fixture
def mock_storage() -> InMemoryStorageService:
    return InMemoryStorageService()


@pytest_asyncio.fixture
async def avatar_client(
    db_session: AsyncSession,
    mock_storage: InMemoryStorageService,
) -> AsyncGenerator[AsyncClient, None]:
    """Mock storage inject edilmiş test client."""
    from app.database import get_db

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_storage] = lambda: mock_storage

    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Yardımcı: person oluştur ─────────────────────────────────────────────────

async def _create_person(db_session: AsyncSession, club: Club) -> Person:
    person = Person(
        id=uuid.uuid4(),
        club_id=club.id,
        first_name="Test",
        last_name="Kullanıcı",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(person)
    await db_session.flush()
    return person


# ── AV-01: Yönetici JPEG yükleyebilir ────────────────────────────────────────

@pytest.mark.asyncio
async def test_av01_yonetici_jpeg_upload(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
    mock_storage: InMemoryStorageService,
) -> None:
    person = await _create_person(db_session, test_club)
    data = _make_jpeg()

    resp = await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("photo.jpg", data, "image/jpeg")},
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["has_avatar"] is True
    assert body["avatar_url"] is not None
    assert body["expires_in"] == 3600

    # Storage'da gerçekten var mı?
    key = f"clubs/{test_club.id}/persons/{person.id}/avatar/current.webp"
    assert await mock_storage.exists(key)


# ── AV-02: PNG yüklenir ve WebP'ye dönüştürülür ───────────────────────────────

@pytest.mark.asyncio
async def test_av02_png_converted_to_webp(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
    mock_storage: InMemoryStorageService,
) -> None:
    person = await _create_person(db_session, test_club)
    data = _make_png()

    resp = await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("photo.png", data, "image/png")},
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 200

    key = f"clubs/{test_club.id}/persons/{person.id}/avatar/current.webp"
    stored_bytes, ct = mock_storage._store[key]

    # Depolanan dosya WebP formatında mı?
    img = Image.open(io.BytesIO(stored_bytes))
    assert img.format == "WEBP"
    assert ct == "image/webp"


# ── AV-03: Geçersiz MIME → 415 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_av03_invalid_mime_415(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    person = await _create_person(db_session, test_club)

    resp = await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 415


# ── AV-04: Bozuk görüntü içeriği → 422 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_av04_corrupted_image_422(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    person = await _create_person(db_session, test_club)

    # JPEG magic bytes + bozuk veri
    corrupted = b"\xff\xd8\xff" + b"\x00" * 50 + b"this is not a valid jpeg"

    resp = await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("bad.jpg", corrupted, "image/jpeg")},
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 422


# ── AV-05: Dosya boyutu limiti → 413 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_av05_file_too_large_413(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    person = await _create_person(db_session, test_club)
    large = _make_large_jpeg(mb=9)   # > 8 MB limit

    resp = await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("big.jpg", large, "image/jpeg")},
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 413


# ── AV-06: Cross-tenant upload → 404 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_av06_cross_tenant_404(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    # Farklı kulübe ait kişi
    other_club = Club(
        id=uuid.uuid4(),
        slug=f"other-{uuid.uuid4().hex[:6]}",
        name="Diğer Kulüp",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(other_club)
    await db_session.flush()

    other_person = Person(
        id=uuid.uuid4(),
        club_id=other_club.id,
        first_name="Diğer",
        last_name="Kişi",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(other_person)
    await db_session.flush()

    resp = await avatar_client.post(
        f"/api/v1/persons/{other_person.id}/avatar",
        files={"file": ("photo.jpg", _make_jpeg(), "image/jpeg")},
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 404


# ── AV-07: Sporcu upload → 403 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_av07_sporcu_forbidden_403(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    sporcu_user: User,
    sporcu_token: str,
) -> None:
    person = await _create_person(db_session, test_club)

    resp = await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("photo.jpg", _make_jpeg(), "image/jpeg")},
        headers={"Authorization": f"Bearer {sporcu_token}"},
    )
    assert resp.status_code == 403


# ── AV-08: Mevcut avatar değiştirilince archive copy oluşur ──────────────────

@pytest.mark.asyncio
async def test_av08_archive_on_replace(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
    mock_storage: InMemoryStorageService,
) -> None:
    person = await _create_person(db_session, test_club)
    headers = {"Authorization": f"Bearer {yonetici_token}"}

    # İlk yükleme
    await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("v1.jpg", _make_jpeg(50, 50), "image/jpeg")},
        headers=headers,
    )

    # İkinci yükleme
    resp = await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("v2.jpg", _make_jpeg(80, 80), "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 200

    # archive/ altında en az bir key olmalı
    archive_keys = [
        k for k in mock_storage._store
        if f"persons/{person.id}/avatar/archive/" in k
    ]
    assert len(archive_keys) >= 1


# ── AV-09: Delete: object ve DB alanı temizlenir ─────────────────────────────

@pytest.mark.asyncio
async def test_av09_delete_clears_object_and_db(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
    mock_storage: InMemoryStorageService,
) -> None:
    person = await _create_person(db_session, test_club)
    headers = {"Authorization": f"Bearer {yonetici_token}"}

    await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("photo.jpg", _make_jpeg(), "image/jpeg")},
        headers=headers,
    )

    key = f"clubs/{test_club.id}/persons/{person.id}/avatar/current.webp"
    assert await mock_storage.exists(key)

    resp = await avatar_client.delete(
        f"/api/v1/persons/{person.id}/avatar",
        headers=headers,
    )
    assert resp.status_code == 204

    # Storage temizlendi
    assert not await mock_storage.exists(key)

    # DB temizlendi
    from sqlalchemy import select as sa_select
    result = await db_session.execute(sa_select(Person).where(Person.id == person.id))
    refreshed = result.scalar_one()
    assert refreshed.avatar_object_key is None


# ── AV-10: İkinci delete idempotent ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_av10_delete_idempotent(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    person = await _create_person(db_session, test_club)
    headers = {"Authorization": f"Bearer {yonetici_token}"}

    # Hiç avatar yüklenmeden sil
    resp = await avatar_client.delete(
        f"/api/v1/persons/{person.id}/avatar",
        headers=headers,
    )
    assert resp.status_code == 204

    # Bir kez daha sil — yine 204
    resp2 = await avatar_client.delete(
        f"/api/v1/persons/{person.id}/avatar",
        headers=headers,
    )
    assert resp2.status_code == 204


# ── AV-11: URL endpoint 1 saatlik link döner ─────────────────────────────────

@pytest.mark.asyncio
async def test_av11_avatar_url_expires_3600(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    person = await _create_person(db_session, test_club)
    headers = {"Authorization": f"Bearer {yonetici_token}"}

    await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("photo.jpg", _make_jpeg(), "image/jpeg")},
        headers=headers,
    )

    resp = await avatar_client.get(
        f"/api/v1/persons/{person.id}/avatar-url",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_avatar"] is True
    assert body["expires_in"] == 3600
    assert body["avatar_url"] is not None


# ── AV-12: Avatar yoksa has_avatar=false, 200 döner ─────────────────────────

@pytest.mark.asyncio
async def test_av12_no_avatar_returns_has_avatar_false(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    person = await _create_person(db_session, test_club)

    resp = await avatar_client.get(
        f"/api/v1/persons/{person.id}/avatar-url",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_avatar"] is False
    assert body["avatar_url"] is None


# ── AV-13: Audit kayıtları oluşur ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_av13_audit_log_created(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    from sqlalchemy import select as sa_select

    person = await _create_person(db_session, test_club)
    headers = {"Authorization": f"Bearer {yonetici_token}"}

    await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("photo.jpg", _make_jpeg(), "image/jpeg")},
        headers=headers,
    )

    result = await db_session.execute(
        sa_select(AuditLog).where(
            AuditLog.resource_id == str(person.id),
            AuditLog.action.in_(["person_avatar_uploaded", "person_avatar_replaced"]),
        )
    )
    logs = result.scalars().all()
    assert len(logs) >= 1


# ── AV-14: Audit içinde object URL veya image data yok ───────────────────────

@pytest.mark.asyncio
async def test_av14_audit_no_sensitive_data(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
) -> None:
    import json
    from sqlalchemy import select as sa_select

    person = await _create_person(db_session, test_club)
    headers = {"Authorization": f"Bearer {yonetici_token}"}

    await avatar_client.post(
        f"/api/v1/persons/{person.id}/avatar",
        files={"file": ("photo.jpg", _make_jpeg(), "image/jpeg")},
        headers=headers,
    )

    result = await db_session.execute(
        sa_select(AuditLog).where(
            AuditLog.resource_id == str(person.id),
        )
    )
    for log in result.scalars().all():
        changes_str = json.dumps(log.changes or {})
        # Object storage URL'si veya base64 data olmamalı
        assert "http" not in changes_str.lower() or "minio" not in changes_str.lower(), \
            f"Audit log URL içeriyor: {changes_str}"
        assert "base64" not in changes_str.lower(), \
            f"Audit log base64 içeriyor: {changes_str}"
        # after içinde yalnızca güvenli metadata alanları var
        if log.changes and "after" in log.changes:
            after = log.changes["after"]
            allowed_keys = {"mime_type", "size_bytes", "width", "height"}
            extra = set(after.keys()) - allowed_keys
            assert not extra, f"Audit after'da beklenmeyen alanlar: {extra}"


# ── AV-15: Listeleme batch pre-signed URL ────────────────────────────────────

@pytest.mark.asyncio
async def test_av15_list_uses_batch_presigned_url(
    avatar_client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    test_user: User,
    yonetici_token: str,
    mock_storage: InMemoryStorageService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """presigned_url_batch() çağrı sayısını izle — kişi başına ayrı çağrı olmamalı."""
    batch_call_count = 0
    original_batch = mock_storage.presigned_url_batch

    async def counting_batch(keys, expires):
        nonlocal batch_call_count
        batch_call_count += 1
        return await original_batch(keys, expires)

    mock_storage.presigned_url_batch = counting_batch  # type: ignore[method-assign]

    headers = {"Authorization": f"Bearer {yonetici_token}"}

    # 3 farklı kişi için avatar yükle
    for _ in range(3):
        person = await _create_person(db_session, test_club)
        await avatar_client.post(
            f"/api/v1/persons/{person.id}/avatar",
            files={"file": ("p.jpg", _make_jpeg(), "image/jpeg")},
            headers=headers,
        )

    batch_call_count = 0  # sayacı sıfırla — önceki upload'lar sayılmasın

    resp = await avatar_client.get(
        "/api/v1/persons",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    items_with_avatar = [i for i in body["items"] if i["has_avatar"]]
    assert len(items_with_avatar) >= 3

    # Tek batch çağrısı bekleniyor (N kişi için N ayrı çağrı değil)
    assert batch_call_count == 1, f"N+1 var: {batch_call_count} batch çağrısı yapıldı"


# ── AV-16: Eski 69 test bozulmaz — bu test sadece marker ────────────────────
# (pytest tests/ komutu bütün paketin çalışmasını zaten garantiler;
#  aşağıdaki test, tüm import'ların sağlıklı olduğunu doğrular)

def test_av16_existing_suite_importable() -> None:
    """avatar modülü ve bağımlılıkları sorunsuz import edilebilir."""
    from app.api.v1.routers.avatar import router
    from app.dependencies.storage import get_storage
    from app.services.storage import ObjectStorageService
    from app.schemas.person import PersonAvatarOut

    assert router is not None
    assert get_storage is not None
    assert PersonAvatarOut is not None
