"""Üyelik başvurusu endpoint testleri — MA-01 .. MA-22.

InMemoryStorageService + SQLite in-memory DB ile çalışır.
PDF service httpx çağrısı mock'lanır.
"""
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, Response as HttpxResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.database import get_db
from app.dependencies.storage import get_storage
from app.main import app
from app.models.club import Club
from app.models.membership_application import MembershipApplication
from app.models.user import User
from tests.test_storage import InMemoryStorageService


# ── Fixture yardımcıları ──────────────────────────────────────────────────────

@pytest.fixture
def mock_storage() -> InMemoryStorageService:
    return InMemoryStorageService()


def _yonetici_headers(club: Club, user: User) -> dict:
    token = create_access_token(str(user.id), str(club.id), user.role)
    return {"Authorization": f"Bearer {token}"}


def _sporcu_headers(club: Club, user: User) -> dict:
    token = create_access_token(str(user.id), str(club.id), user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def membership_client(
    db_session: AsyncSession,
    mock_storage: InMemoryStorageService,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_storage] = lambda: mock_storage

    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_storage, None)


BASE = "/api/v1/membership-applications"


# ── MA-01: Başvuru oluştur — 201, draft ──────────────────────────────────────

@pytest.mark.asyncio
async def test_ma01_create_application(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    headers = _yonetici_headers(test_club, test_user)
    resp = await membership_client.post(BASE, json={
        "first_name": "Ali",
        "last_name": "Yılmaz",
        "phone": "05001234567",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "draft"
    assert data["first_name"] == "Ali"
    assert "pdf_object_key" not in data
    assert "signature_object_key" not in data


# ── MA-02: Liste — boş kulüp ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ma02_list_empty(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
    db_session: AsyncSession,
):
    # Diğer kulüp başvuruları listemizi kirletmesin diye yeni kulüp
    other_club = Club(
        id=uuid.uuid4(), slug=f"empty-{uuid.uuid4().hex[:6]}",
        name="Empty Club", plan="starter", is_active=True, settings={},
    )
    db_session.add(other_club)
    from app.core.security import hash_password
    other_user = User(
        id=uuid.uuid4(), club_id=other_club.id,
        email=f"empty-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Test1234!"),
        full_name="Empty User", role="kulup_yonetici",
        is_active=True, is_deleted=False,
    )
    db_session.add(other_user)
    await db_session.flush()

    token = create_access_token(str(other_user.id), str(other_club.id), "kulup_yonetici")
    resp = await membership_client.get(BASE, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


# ── MA-03: Tek başvuru GET ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ma03_get_application(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    headers = _yonetici_headers(test_club, test_user)
    create_resp = await membership_client.post(BASE, json={"first_name": "Mehmet"}, headers=headers)
    app_id = create_resp.json()["id"]

    resp = await membership_client.get(f"{BASE}/{app_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == app_id
    assert resp.json()["first_name"] == "Mehmet"


# ── MA-04: Alan güncelleme PATCH ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ma04_update_application(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    headers = _yonetici_headers(test_club, test_user)
    create_resp = await membership_client.post(BASE, json={"first_name": "Ayşe"}, headers=headers)
    app_id = create_resp.json()["id"]

    resp = await membership_client.patch(
        f"{BASE}/{app_id}",
        json={"last_name": "Kaya", "phone": "05559876543"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_name"] == "Kaya"
    assert data["phone"] == "05559876543"


# ── MA-05: Soft delete ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ma05_delete_draft_application(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    headers = _yonetici_headers(test_club, test_user)
    create_resp = await membership_client.post(BASE, json={"first_name": "Zeynep"}, headers=headers)
    app_id = create_resp.json()["id"]

    del_resp = await membership_client.delete(f"{BASE}/{app_id}", headers=headers)
    assert del_resp.status_code == 204

    get_resp = await membership_client.get(f"{BASE}/{app_id}", headers=headers)
    assert get_resp.status_code == 404


# ── MA-06: draft→submitted geçişi + application_number üretimi ───────────────

@pytest.mark.asyncio
async def test_ma06_submit_generates_number(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    headers = _yonetici_headers(test_club, test_user)
    create_resp = await membership_client.post(BASE, json={"first_name": "Can"}, headers=headers)
    app_id = create_resp.json()["id"]
    assert create_resp.json()["application_number"] is None

    resp = await membership_client.patch(
        f"{BASE}/{app_id}/status",
        json={"to_status": "submitted"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"
    assert resp.json()["application_number"] is not None


# ── MA-07: application_number format MYK-YYYY-000001 ─────────────────────────

@pytest.mark.asyncio
async def test_ma07_application_number_format(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    from datetime import datetime
    headers = _yonetici_headers(test_club, test_user)
    create_resp = await membership_client.post(BASE, json={"first_name": "Fatma"}, headers=headers)
    app_id = create_resp.json()["id"]

    resp = await membership_client.patch(
        f"{BASE}/{app_id}/status",
        json={"to_status": "submitted"},
        headers=headers,
    )
    number = resp.json()["application_number"]
    year = datetime.now().year
    assert number.startswith(f"MYK-{year}-"), f"Beklenmeyen format: {number}"
    seq = number.split("-")[-1]
    assert seq.isdigit() and len(seq) == 6, f"Sıra numarası 6 hane olmalı: {seq}"


# ── MA-08: İki farklı gönderim benzersiz numaralar alır ──────────────────────

@pytest.mark.asyncio
async def test_ma08_unique_application_numbers(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    headers = _yonetici_headers(test_club, test_user)
    numbers = set()
    for name in ["Birinci", "İkinci", "Üçüncü"]:
        cr = await membership_client.post(BASE, json={"first_name": name}, headers=headers)
        aid = cr.json()["id"]
        sr = await membership_client.patch(
            f"{BASE}/{aid}/status", json={"to_status": "submitted"}, headers=headers
        )
        numbers.add(sr.json()["application_number"])
    assert len(numbers) == 3, f"Tekrarlanan numara: {numbers}"


# ── MA-09: Sporcu onay yapamaz → 403 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_ma09_sporcu_cannot_approve(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
    sporcu_user: User,
):
    yonetici_h = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={"first_name": "Onay"}, headers=yonetici_h)
    app_id = cr.json()["id"]
    await membership_client.patch(f"{BASE}/{app_id}/status", json={"to_status": "submitted"}, headers=yonetici_h)

    sporcu_h = _sporcu_headers(test_club, sporcu_user)
    resp = await membership_client.patch(
        f"{BASE}/{app_id}/status",
        json={"to_status": "approved"},
        headers=sporcu_h,
    )
    assert resp.status_code == 403


# ── MA-10: Yönetici onay yapabilir → 200 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_ma10_yonetici_can_approve(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    headers = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={"first_name": "Onay2"}, headers=headers)
    app_id = cr.json()["id"]
    await membership_client.patch(f"{BASE}/{app_id}/status", json={"to_status": "submitted"}, headers=headers)

    resp = await membership_client.patch(
        f"{BASE}/{app_id}/status",
        json={"to_status": "approved"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


# ── MA-11: Geçersiz durum geçişi → 422 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_ma11_invalid_transition(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    headers = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={}, headers=headers)
    app_id = cr.json()["id"]

    # draft → approved geçişi geçersiz
    resp = await membership_client.patch(
        f"{BASE}/{app_id}/status",
        json={"to_status": "approved"},
        headers=headers,
    )
    assert resp.status_code == 422


# ── MA-12: Onaylanmış başvuru silinemez → 422 ─────────────────────────────────

@pytest.mark.asyncio
async def test_ma12_cannot_delete_approved(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    headers = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={"first_name": "Sil"}, headers=headers)
    app_id = cr.json()["id"]
    await membership_client.patch(f"{BASE}/{app_id}/status", json={"to_status": "submitted"}, headers=headers)
    await membership_client.patch(f"{BASE}/{app_id}/status", json={"to_status": "approved"}, headers=headers)

    resp = await membership_client.delete(f"{BASE}/{app_id}", headers=headers)
    assert resp.status_code == 422


# ── MA-13: Farklı kulüp başvurusu → 404 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_ma13_cross_tenant_404(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
    db_session: AsyncSession,
):
    from app.core.security import hash_password

    other_club = Club(
        id=uuid.uuid4(), slug=f"other-{uuid.uuid4().hex[:6]}",
        name="Diğer Kulüp", plan="starter", is_active=True, settings={},
    )
    db_session.add(other_club)
    other_app = MembershipApplication(
        id=uuid.uuid4(), club_id=other_club.id, status="draft",
    )
    db_session.add(other_app)
    await db_session.flush()

    headers = _yonetici_headers(test_club, test_user)
    resp = await membership_client.get(f"{BASE}/{other_app.id}", headers=headers)
    assert resp.status_code == 404


# ── MA-14: Sporcu yeni başvuru yapamaz → 403 ─────────────────────────────────

@pytest.mark.asyncio
async def test_ma14_sporcu_cannot_create(
    membership_client: AsyncClient,
    test_club: Club,
    sporcu_user: User,
):
    headers = _sporcu_headers(test_club, sporcu_user)
    resp = await membership_client.post(BASE, json={"first_name": "Hız"}, headers=headers)
    assert resp.status_code == 403


# ── MA-15: signature_object_key response'da yok ───────────────────────────────

@pytest.mark.asyncio
async def test_ma15_signature_object_key_not_exposed(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
    db_session: AsyncSession,
):
    headers = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={"first_name": "Gizli"}, headers=headers)
    app_id = cr.json()["id"]

    # Doğrudan DB'ye set et
    result = await db_session.get(MembershipApplication, uuid.UUID(app_id))
    result.signature_object_key = "clubs/x/y/sig.png"
    await db_session.flush()

    resp = await membership_client.get(f"{BASE}/{app_id}", headers=headers)
    assert resp.status_code == 200
    assert "signature_object_key" not in resp.json()
    assert resp.json()["has_signature"] is True


# ── MA-16: pdf_object_key response'da yok ────────────────────────────────────

@pytest.mark.asyncio
async def test_ma16_pdf_object_key_not_exposed(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
    db_session: AsyncSession,
):
    from datetime import datetime, timezone
    headers = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={"first_name": "PDFGizli"}, headers=headers)
    app_id = cr.json()["id"]

    result = await db_session.get(MembershipApplication, uuid.UUID(app_id))
    result.pdf_object_key = "clubs/x/y/app.pdf"
    result.pdf_generated_at = datetime.now(timezone.utc)
    await db_session.flush()

    resp = await membership_client.get(f"{BASE}/{app_id}", headers=headers)
    assert resp.status_code == 200
    assert "pdf_object_key" not in resp.json()
    assert resp.json()["has_pdf"] is True


# ── MA-17: İmza yükleme → has_signature=true ─────────────────────────────────

@pytest.mark.asyncio
async def test_ma17_upload_signature(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
    mock_storage: InMemoryStorageService,
):
    from PIL import Image
    import io
    headers = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={"first_name": "İmza"}, headers=headers)
    app_id = cr.json()["id"]

    img = Image.new("RGBA", (100, 100))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    resp = await membership_client.post(
        f"{BASE}/{app_id}/signature",
        files={"file": ("sig.png", buf, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_signature"] is True
    assert data["signature_url"] is not None
    assert data["expires_in"] == 900


# ── MA-18: İmza silme → 204, has_signature=false ─────────────────────────────

@pytest.mark.asyncio
async def test_ma18_delete_signature(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
):
    from PIL import Image
    import io
    headers = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={"first_name": "DelSig"}, headers=headers)
    app_id = cr.json()["id"]

    img = Image.new("RGB", (50, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    await membership_client.post(
        f"{BASE}/{app_id}/signature",
        files={"file": ("sig.jpg", buf, "image/jpeg")},
        headers=headers,
    )

    del_resp = await membership_client.delete(f"{BASE}/{app_id}/signature", headers=headers)
    assert del_resp.status_code == 204

    url_resp = await membership_client.get(f"{BASE}/{app_id}/signature-url", headers=headers)
    assert url_resp.json()["has_signature"] is False


# ── MA-19: İmza URL endpoint ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ma19_signature_url_endpoint(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
    db_session: AsyncSession,
    mock_storage: InMemoryStorageService,
):
    headers = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={"first_name": "SigURL"}, headers=headers)
    app_id = cr.json()["id"]

    # Doğrudan storage'a yükle + DB'yi güncelle
    key = f"clubs/{test_club.id}/membership-applications/{app_id}/signature.png"
    await mock_storage.upload(key, b"fake-png-data", "image/png")
    result = await db_session.get(MembershipApplication, uuid.UUID(app_id))
    result.signature_object_key = key
    await db_session.flush()

    resp = await membership_client.get(f"{BASE}/{app_id}/signature-url", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_signature"] is True
    assert data["signature_url"] is not None
    assert data["expires_in"] == 900


# ── MA-20: PDF üretimi — httpx mock ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_ma20_generate_pdf(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
    mock_storage: InMemoryStorageService,
):
    headers = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={
        "first_name": "PDF",
        "last_name": "Test",
    }, headers=headers)
    app_id = cr.json()["id"]

    fake_pdf = b"%PDF-1.4 fake content"

    with patch("app.api.v1.routers.memberships.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = HttpxResponse(
            200, content=fake_pdf,
            headers={"content-type": "application/pdf"},
        )

        resp = await membership_client.post(f"{BASE}/{app_id}/generate-pdf", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_pdf"] is True
    assert data["pdf_url"] is not None
    assert data["expires_in"] == 900

    # Storage'da gerçekten var mı?
    obj_key = f"clubs/{test_club.id}/membership-applications/{app_id}/application.pdf"
    assert await mock_storage.exists(obj_key)


# ── MA-21: PDF URL endpoint ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ma21_get_pdf_url(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
    db_session: AsyncSession,
    mock_storage: InMemoryStorageService,
):
    from datetime import datetime, timezone
    headers = _yonetici_headers(test_club, test_user)
    cr = await membership_client.post(BASE, json={"first_name": "PDFURL"}, headers=headers)
    app_id = cr.json()["id"]

    key = f"clubs/{test_club.id}/membership-applications/{app_id}/application.pdf"
    await mock_storage.upload(key, b"%PDF-1.4", "application/pdf")
    result = await db_session.get(MembershipApplication, uuid.UUID(app_id))
    result.pdf_object_key = key
    result.pdf_generated_at = datetime.now(timezone.utc)
    await db_session.flush()

    resp = await membership_client.get(f"{BASE}/{app_id}/pdf-url", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_pdf"] is True
    assert data["pdf_url"] is not None


# ── MA-22: is_deleted kayıtlar listede görünmez ───────────────────────────────

@pytest.mark.asyncio
async def test_ma22_deleted_excluded_from_list(
    membership_client: AsyncClient,
    test_club: Club,
    test_user: User,
    db_session: AsyncSession,
):
    headers = _yonetici_headers(test_club, test_user)

    # Bu kulübe özgü temiz sayım için yeni kulüp kullan
    from app.core.security import hash_password
    fresh_club = Club(
        id=uuid.uuid4(), slug=f"fresh-{uuid.uuid4().hex[:6]}",
        name="Fresh Club", plan="starter", is_active=True, settings={},
    )
    db_session.add(fresh_club)
    fresh_user = User(
        id=uuid.uuid4(), club_id=fresh_club.id,
        email=f"fresh-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Test1234!"),
        full_name="Fresh User", role="kulup_yonetici",
        is_active=True, is_deleted=False,
    )
    db_session.add(fresh_user)
    await db_session.flush()

    fresh_headers = {"Authorization": f"Bearer {create_access_token(str(fresh_user.id), str(fresh_club.id), 'kulup_yonetici')}"}

    # İki başvuru oluştur
    cr1 = await membership_client.post(BASE, json={"first_name": "Görünür"}, headers=fresh_headers)
    cr2 = await membership_client.post(BASE, json={"first_name": "Silinecek"}, headers=fresh_headers)

    # İkincisini sil
    await membership_client.delete(f"{BASE}/{cr2.json()['id']}", headers=fresh_headers)

    # Liste 1 kayıt göstermeli
    list_resp = await membership_client.get(BASE, headers=fresh_headers)
    assert list_resp.json()["total"] == 1
    names = [item["first_name"] for item in list_resp.json()["items"]]
    assert "Görünür" in names
    assert "Silinecek" not in names
