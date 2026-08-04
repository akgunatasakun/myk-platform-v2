"""Tenant izolasyon testleri."""
import uuid

import pytest
from fastapi import HTTPException

from app.core.tenant import assert_same_club


def test_same_club_passes() -> None:
    club_id = uuid.uuid4()
    assert_same_club(club_id, club_id)  # İstisna fırlatılmamalı


def test_different_club_raises_404() -> None:
    club_a = uuid.uuid4()
    club_b = uuid.uuid4()
    with pytest.raises(HTTPException) as exc_info:
        assert_same_club(club_a, club_b)
    assert exc_info.value.status_code == 404


def test_cross_tenant_raises_not_403() -> None:
    """Varlığı ifşa etmemek için 403 değil 404 döndürülmeli."""
    with pytest.raises(HTTPException) as exc_info:
        assert_same_club(uuid.uuid4(), uuid.uuid4())
    assert exc_info.value.status_code != 403


@pytest.mark.asyncio
async def test_auth_me_cross_tenant_returns_401_or_404(
    client, test_club, test_user, db_session
) -> None:
    """
    Kullanıcı token'ı A kulübüne ait fakat B kulübünün kaynağına erişmeye çalışıyor.
    404 veya 401 döndürmeli, asla 403 değil.
    """
    from app.core.security import create_access_token
    from app.models.club import Club
    from app.models.user import User
    from app.core.security import hash_password

    # B kulübü oluştur
    club_b = Club(
        id=uuid.uuid4(),
        slug="baska-kulup",
        name="Başka Kulüp",
        plan="starter",
        is_active=True,
        settings={},
    )
    db_session.add(club_b)

    user_b = User(
        id=uuid.uuid4(),
        club_id=club_b.id,
        email="userb@baska.com",
        password_hash=hash_password("Parola1234!"),
        full_name="B Kulüp Kullanıcısı",
        role="sporcu",
        is_active=True,
        is_deleted=False,
    )
    db_session.add(user_b)
    await db_session.commit()

    # A kulübü token'ı ile B kulübü /me erişimi — kendi user_id ile farklı club_id token
    malformed_token = create_access_token(
        str(test_user.id),   # A kulübü kullanıcısı
        str(club_b.id),      # Ama B kulübü claim'i
        "sporcu",
    )

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {malformed_token}"},
    )
    assert resp.status_code in (401, 404), f"Beklenmedik durum kodu: {resp.status_code}"
