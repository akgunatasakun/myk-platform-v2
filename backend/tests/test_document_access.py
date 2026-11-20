"""Yönetim belgelerinin liste/detay/dosya yollarında rol matrisi."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.core.rbac import has_permission
from app.core.security import create_access_token
from app.dependencies.documents_storage import get_dms_storage
from app.main import app
from app.models.documents import Document, DocumentRevision, DocumentRevisionFile
from app.models.person import Person
from app.models.person_guardian import PersonGuardian
from app.models.renewal import DocumentRenewal

pytestmark = pytest.mark.asyncio
READERS = {"super_admin", "kulup_yonetici", "genel_sekreter", "baskan", "yk_uyesi"}
ROLES = list(READERS) + [
    "muhasebe",
    "sportif_direktor",
    "basantrenor",
    "antrenor",
    "personel",
    "saglik_sorumlusu",
    "guvenlik_operasyon",
    "veli",
    "sporcu",
    "uye",
    "misafir",
]


def headers(user, club):
    return {
        "Authorization": "Bearer "
        + create_access_token(str(user.id), str(club.id), user.role)
    }


async def seed(db, club, user, code="MYK-POL-TEST", private=False):
    athlete = Person(club_id=club.id, first_name="Deniz", last_name="Test")
    guardian = Person(club_id=club.id, first_name="Veli", last_name="Test")
    db.add_all([athlete, guardian])
    await db.flush()
    db.add(
        PersonGuardian(
            club_id=club.id,
            athlete_person_id=athlete.id,
            guardian_person_id=guardian.id,
        )
    )
    user.person_id = guardian.id if user.role == "veli" else athlete.id
    doc = Document(
        club_id=club.id,
        code=code,
        title="Gizli Poliçe",
        document_type="diger",
        management_only=private,
        owner_type="person",
        owner_id=athlete.id,
    )
    db.add(doc)
    await db.flush()
    revision = DocumentRevision(document_id=doc.id, revision_code="R00")
    db.add(revision)
    await db.flush()
    file = DocumentRevisionFile(
        revision_id=revision.id,
        original_filename="police.pdf",
        mime_type="application/pdf",
        file_size=8,
        sha256="0" * 64,
        storage_bucket="private",
        storage_key="secret.pdf",
    )
    db.add(file)
    await db.flush()
    return doc, revision, file


@pytest.mark.parametrize("role", ROLES)
async def test_policy_matrix_all_paths(client, db_session, test_club, test_user, role):
    test_user.role = role
    doc, rev, file = await seed(db_session, test_club, test_user)
    download = AsyncMock(return_value=b"%PDF-test")
    app.dependency_overrides[get_dms_storage] = lambda: SimpleNamespace(
        download=download
    )
    h = headers(test_user, test_club)
    path = f"/api/v1/documents/{doc.id}"
    listing = await client.get("/api/v1/documents", headers=h)
    detail = await client.get(path, headers=h)
    revisions = await client.get(path + "/revisions", headers=h)
    response = await client.get(
        path + f"/revisions/{rev.id}/files/{file.id}/download", headers=h
    )
    if role in READERS:
        assert (
            listing.status_code
            == detail.status_code
            == revisions.status_code
            == response.status_code
            == 200
        )
        assert any(d["id"] == str(doc.id) for d in listing.json())
        download.assert_awaited_once()
    else:
        assert listing.status_code == 403 or listing.json() == []
        assert detail.status_code in (403, 404)
        assert revisions.status_code in (403, 404)
        assert response.status_code in (403, 404)
        download.assert_not_awaited()


@pytest.mark.parametrize("protection", ["flag", "renewal", "closed_renewal"])
async def test_library_cannot_bypass_restriction(
    client, db_session, test_club, test_user, protection
):
    test_user.role = "sportif_direktor"
    doc, rev, file = await seed(
        db_session,
        test_club,
        test_user,
        code="TYF-PRIVATE",
        private=protection == "flag",
    )
    if protection != "flag":
        db_session.add(
            DocumentRenewal(
                club_id=test_club.id,
                document_id=doc.id,
                kind="sozlesme",
                is_closed=protection == "closed_renewal",
            )
        )
        await db_session.flush()
    h = headers(test_user, test_club)
    assert (await client.get("/api/v1/documents/kutuphane", headers=h)).json() == []
    for suffix in ("", "/revisions"):
        assert (
            await client.get(f"/api/v1/documents/{doc.id}" + suffix, headers=h)
        ).status_code == 404
    assert (
        await client.get(f"/api/v1/documents/kutuphane/{doc.id}", headers=h)
    ).status_code in (403, 404)
    download = AsyncMock()
    app.dependency_overrides[get_dms_storage] = lambda: SimpleNamespace(
        download=download
    )
    assert (
        await client.get(
            f"/api/v1/documents/{doc.id}/revisions/{rev.id}/files/{file.id}/download",
            headers=h,
        )
    ).status_code == 404
    download.assert_not_awaited()


@pytest.mark.parametrize("role", ["sporcu", "veli"])
async def test_personal_documents_remain_readable_but_not_writable(
    client, db_session, test_club, test_user, role
):
    test_user.role = role
    doc, _rev, _file = await seed(
        db_session, test_club, test_user, code="ATHLETE-LICENSE"
    )
    h = headers(test_user, test_club)
    path = f"/api/v1/documents/{doc.id}"
    assert (await client.get(path, headers=h)).status_code == 200
    assert (await client.get(path + "/revisions", headers=h)).status_code == 200
    assert (
        await client.post(
            "/api/v1/documents",
            headers=h,
            json={"code": "NEW", "title": "x", "document_type": "diger"},
        )
    ).status_code == 403
    assert (
        await client.patch(path, headers=h, json={"title": "Yetkisiz"})
    ).status_code == 403
    assert (await client.delete(path, headers=h)).status_code == 403
    assert (
        await client.post(path + "/revisions", headers=h, json={"revision_code": "R01"})
    ).status_code == 403


async def test_protection_cannot_be_removed(client, db_session, test_club, test_user):
    doc, _, _ = await seed(
        db_session, test_club, test_user, code="PRIVATE", private=True
    )
    h = headers(test_user, test_club)
    assert (
        await client.patch(
            f"/api/v1/documents/{doc.id}", headers=h, json={"management_only": False}
        )
    ).status_code == 409
    assert (
        await client.patch(
            f"/api/v1/documents/{doc.id}", headers=h, json={"management_only": None}
        )
    ).status_code == 422


async def test_own_permission_matches_action():
    for role in ("veli", "sporcu"):
        assert has_permission(role, "belge:read")
        for action in ("create", "update", "delete", "publish"):
            assert not has_permission(role, f"belge:{action}")
    assert has_permission("veli", "person_document:create")
    assert not has_permission("veli", "person_document:delete")
