"""training_courses.is_registration_open admin API testleri — Sprint 0023.

Kapsam:
  - Kurs oluşturma: alan verilmezse default true
  - Kurs oluşturma: false gönderilince response + DB false
  - Kurs PATCH: true → false
  - Kurs GET/list response alanı içerir

Kirli test_training_endpoints.py stage edilmez; bu dosya temiz.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.club import Club
from app.models.training import TrainingCourse


# ─── Yardımcılar ─────────────────────────────────────────────────────────────

def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _course_payload(**kwargs) -> dict:
    base = {
        "name": f"Test Kurs {uuid.uuid4().hex[:6]}",
        "status": "planlandi",
    }
    base.update(kwargs)
    return base


# ─── Testler ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_course_default_registration_open(
    client: AsyncClient,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """is_registration_open verilmezse response'ta true olmalı."""
    payload = _course_payload(name="Default Açık Kurs")
    resp = await client.post(
        f"/api/v1/trainings",
        json=payload,
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "is_registration_open" in data, "is_registration_open response'ta yok"
    assert data["is_registration_open"] is True


@pytest.mark.asyncio
async def test_create_course_registration_closed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """is_registration_open=false gönderilince response + DB false olmalı."""
    payload = _course_payload(name="Kapalı Kurs", is_registration_open=False)
    resp = await client.post(
        f"/api/v1/trainings",
        json=payload,
        headers=_headers(yonetici_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_registration_open"] is False

    # DB doğrulama
    result = await db_session.execute(
        select(TrainingCourse).where(TrainingCourse.id == uuid.UUID(data["id"]))
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.is_registration_open is False, (
        f"DB'de is_registration_open False olmalı, alınan: {saved.is_registration_open!r}"
    )


@pytest.mark.asyncio
async def test_patch_course_closes_registration(
    client: AsyncClient,
    db_session: AsyncSession,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """PATCH ile is_registration_open true → false yapılabilmeli."""
    # Önce açık kurs oluştur
    create_resp = await client.post(
        f"/api/v1/trainings",
        json=_course_payload(name="Kapatılacak Kurs", is_registration_open=True),
        headers=_headers(yonetici_token),
    )
    assert create_resp.status_code == 201
    course_id = create_resp.json()["id"]

    # PATCH ile kapat
    patch_resp = await client.patch(
        f"/api/v1/trainings/{course_id}",
        json={"is_registration_open": False},
        headers=_headers(yonetici_token),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_registration_open"] is False

    # DB doğrulama
    result = await db_session.execute(
        select(TrainingCourse).where(TrainingCourse.id == uuid.UUID(course_id))
    )
    saved = result.scalar_one_or_none()
    assert saved is not None
    assert saved.is_registration_open is False


@pytest.mark.asyncio
async def test_get_course_includes_registration_open(
    client: AsyncClient,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """GET /trainings/{id} response'unda is_registration_open alanı bulunmalı."""
    create_resp = await client.post(
        f"/api/v1/trainings",
        json=_course_payload(name="Detail Alanı Test"),
        headers=_headers(yonetici_token),
    )
    assert create_resp.status_code == 201
    course_id = create_resp.json()["id"]

    get_resp = await client.get(
        f"/api/v1/trainings/{course_id}",
        headers=_headers(yonetici_token),
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert "is_registration_open" in data, "is_registration_open GET response'unda yok"


@pytest.mark.asyncio
async def test_list_courses_includes_registration_open(
    client: AsyncClient,
    test_club: Club,
    yonetici_token: str,
) -> None:
    """GET /trainings (list) response item'larında is_registration_open alanı bulunmalı."""
    await client.post(
        f"/api/v1/trainings",
        json=_course_payload(name="Liste Alanı Test"),
        headers=_headers(yonetici_token),
    )

    list_resp = await client.get(
        f"/api/v1/trainings",
        headers=_headers(yonetici_token),
    )
    assert list_resp.status_code == 200
    items = list_resp.json().get("items", [])
    assert len(items) > 0
    assert "is_registration_open" in items[0], (
        "is_registration_open liste response item'ında yok"
    )
