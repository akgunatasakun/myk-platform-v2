"""Auth endpoint testleri."""
import pytest
from unittest.mock import patch
from httpx import AsyncClient

from app.config import Settings
from app.models.club import Club
from app.models.user import User


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient) -> None:
    """Health endpoint 200 döndürmeli (test ortamında Redis/PG yoksa degraded olabilir)."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
    assert "components" in data


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_club: Club, test_user: User) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "club_slug": test_club.slug,
            "email": test_user.email,
            "password": "Gizli1234!",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # HttpOnly cookie set edilmeli
    assert "access_token" in resp.cookies or "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_club: Club, test_user: User) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "club_slug": test_club.slug,
            "email": test_user.email,
            "password": "YanlisParola!99",
        },
    )
    assert resp.status_code == 401
    assert "Geçersiz" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_unknown_club(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "club_slug": "olmayan-kulup",
            "email": "test@test.com",
            "password": "Parola1234!",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(
    client: AsyncClient, db_session, test_club: Club, test_user: User
) -> None:
    test_user.is_active = False
    await db_session.commit()
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "club_slug": test_club.slug,
            "email": test_user.email,
            "password": "Gizli1234!",
        },
    )
    assert resp.status_code == 401
    # Temizlik
    test_user.is_active = True
    await db_session.commit()


@pytest.mark.asyncio
async def test_me_with_valid_token(
    client: AsyncClient, test_club: Club, test_user: User, yonetici_token: str
) -> None:
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {yonetici_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == test_user.email
    assert data["role"] == test_user.role


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, test_club: Club, test_user: User) -> None:
    # Önce login ol
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "club_slug": test_club.slug,
            "email": test_user.email,
            "password": "Gizli1234!",
        },
    )
    assert login_resp.status_code == 200

    logout_resp = await client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204


@pytest.mark.asyncio
async def test_setup_creates_club_and_admin(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/setup",
        json={
            "club_name": "Yeni Yelken Kulübü",
            "club_slug": "yeni-kulup",
            "admin_email": "admin@yeni.com",
            "admin_password": "Admin1234!",
            "admin_full_name": "Yeni Admin",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "admin@yeni.com"
    assert data["role"] == "kulup_yonetici"


@pytest.mark.asyncio
async def test_setup_duplicate_slug(client: AsyncClient, test_club: Club) -> None:
    resp = await client.post(
        "/api/v1/auth/setup",
        json={
            "club_name": "Kopya Kulüp",
            "club_slug": test_club.slug,
            "admin_email": "admin2@test.com",
            "admin_password": "Admin1234!",
            "admin_full_name": "Kopya Admin",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_setup_blocked_when_club_exists_and_not_allowed(
    client: AsyncClient, test_club: Club
) -> None:
    """Kulüp varken allow_public_setup=False ise setup 403 döndürmeli."""
    from app.config import get_settings
    original = get_settings()

    # allow_public_setup=False ayarını simüle et
    with patch("app.api.v1.routers.auth.settings") as mock_settings:
        mock_settings.allow_public_setup = False
        resp = await client.post(
            "/api/v1/auth/setup",
            json={
                "club_name": "İzinsiz Kulüp",
                "club_slug": "izinsiz-kulup",
                "admin_email": "izinsiz@test.com",
                "admin_password": "Admin1234!",
                "admin_full_name": "İzinsiz Admin",
            },
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_setup_allowed_when_public_setup_enabled(
    client: AsyncClient, test_club: Club
) -> None:
    """allow_public_setup=True (varsayılan dev ayarı) iken kulüp varsa bile setup çalışmalı."""
    # test_club DB'de mevcut; allow_public_setup varsayılan True → bloklanmaz
    resp = await client.post(
        "/api/v1/auth/setup",
        json={
            "club_name": "İkinci Test Kulübü",
            "club_slug": "ikinci-test-kulup",
            "admin_email": "ikinci@test.com",
            "admin_password": "Admin1234!",
            "admin_full_name": "İkinci Admin",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "ikinci@test.com"


@pytest.mark.asyncio
async def test_production_secret_validation() -> None:
    """Production'da zayıf secret key hata vermeli."""
    import pydantic
    with pytest.raises((pydantic.ValidationError, ValueError)):
        Settings(
            myk_env="production",
            jwt_secret_key="DEV_ONLY_CHANGE_IN_PRODUCTION",
            secret_key="DEV_ONLY_CHANGE_IN_PRODUCTION",
            database_url="postgresql+asyncpg://u:p@localhost/db",
        )


@pytest.mark.asyncio
async def test_production_short_secret_rejected() -> None:
    """Production'da 32 karakterden kısa secret hata vermeli."""
    import pydantic
    with pytest.raises((pydantic.ValidationError, ValueError)):
        Settings(
            myk_env="production",
            jwt_secret_key="short_key",
            secret_key="short_key",
            database_url="postgresql+asyncpg://u:p@localhost/db",
        )


@pytest.mark.asyncio
async def test_development_weak_secret_allowed() -> None:
    """Development'ta zayıf secret key kabul edilmeli (varsayılan geliştirme konfigürasyonu)."""
    s = Settings(
        myk_env="development",
        jwt_secret_key="DEV_ONLY_CHANGE_IN_PRODUCTION",
        secret_key="DEV_ONLY_CHANGE_IN_PRODUCTION",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    assert s.myk_env == "development"


@pytest.mark.asyncio
async def test_production_allow_public_setup_rejected() -> None:
    """Production ortamında ALLOW_PUBLIC_SETUP=true config hatası vermeli."""
    import pydantic
    # Uzun ve güçlü bir secret ile production dene, allow_public_setup=True ise hata
    strong_secret = "a" * 64  # 64 karakter, CHANGE_ME içermiyor
    with pytest.raises((pydantic.ValidationError, ValueError)):
        Settings(
            myk_env="production",
            jwt_secret_key=strong_secret,
            secret_key=strong_secret,
            database_url="postgresql+asyncpg://u:p@localhost/db",
            allow_public_setup=True,  # ← production'da yasak
        )


@pytest.mark.asyncio
async def test_production_allow_public_setup_false_ok() -> None:
    """Production ortamında ALLOW_PUBLIC_SETUP=false ile güçlü secret kabul edilmeli."""
    strong_secret = "b" * 64
    s = Settings(
        myk_env="production",
        jwt_secret_key=strong_secret,
        secret_key=strong_secret,
        database_url="postgresql+asyncpg://u:p@localhost/db",
        allow_public_setup=False,
    )
    assert s.myk_env == "production"
    assert not s.allow_public_setup


@pytest.mark.asyncio
async def test_production_setup_always_denied_when_club_exists(
    client: AsyncClient, test_club: Club
) -> None:
    """Production ortamında kulüp varsa setup her zaman 403 döndürmeli."""
    with patch("app.api.v1.routers.auth.settings") as mock_settings:
        mock_settings.allow_public_setup = True   # production'da geçersiz olsa da
        mock_settings.is_production = True        # production modu
        resp = await client.post(
            "/api/v1/auth/setup",
            json={
                "club_name": "Prod Test Kulübü",
                "club_slug": "prod-test",
                "admin_email": "prod@test.com",
                "admin_password": "Admin1234!",
                "admin_full_name": "Prod Admin",
            },
        )
    assert resp.status_code == 403
