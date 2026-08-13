"""MYK Platform V2 — Uygulama Yapılandırması"""
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRETS = {"DEV_ONLY_CHANGE_IN_PRODUCTION", "CHANGE_ME", ""}
_MIN_SECRET_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ortam
    myk_env: Literal["development", "test", "production"] = "development"

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://myk_user:password@localhost:5432/myk_platform"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "DEV_ONLY_CHANGE_IN_PRODUCTION"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # Güvenlik
    secret_key: str = "DEV_ONLY_CHANGE_IN_PRODUCTION"
    allowed_origins: list[str] = ["http://localhost:5173"]
    cors_allow_credentials: bool = True

    # Kurulum
    # allow_public_setup: True → kurulum endpoint'i açık (development/test varsayılanı)
    # Production'da .env içinde ALLOW_PUBLIC_SETUP=false ile kapatılmalıdır.
    # Sistem hiç kulüp içermiyorsa setup endpoint her zaman çalışır (bkz. auth router).
    allow_public_setup: bool = True

    # Dosya yükleme
    max_upload_mb: int = 15
    storage_backend: Literal["local", "s3"] = "local"
    storage_path: str = "/app/storage"

    # Object Storage (MinIO / S3-uyumlu)
    storage_endpoint: str = "http://minio:9000"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_bucket: str = "myk-person-media"
    storage_bucket_documents: str = "myk-documents"
    storage_region: str = "us-east-1"
    storage_secure: bool = False

    # PDF Servisi
    pdf_service_url: str = "http://pdf-service:8001"

    # İlk yönetici (kurulum)
    initial_admin_email: str = ""
    initial_admin_password: str = ""
    initial_club_name: str = "Yelken Kulübü"
    initial_club_slug: str = "kulup"

    # E-posta / SMTP
    # Boş bırakılırsa e-postalar gönderilmez, sadece loglanır (dev/test modu).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "noreply@mersinyelken.org.tr"
    smtp_use_tls: bool = False
    smtp_start_tls: bool = True

    # Frontend base URL (şifre sıfırlama linkleri için)
    frontend_base_url: str = "http://localhost:5173"

    # Loglama
    log_level: str = "INFO"

    @model_validator(mode="after")
    def enforce_production_secrets(self) -> "Settings":
        """Production ortamında zayıf/kısa secret key ve açık setup endpoint'i reddet."""
        if self.myk_env == "production":
            for field_name, value in [
                ("JWT_SECRET_KEY", self.jwt_secret_key),
                ("SECRET_KEY", self.secret_key),
            ]:
                if value in _WEAK_SECRETS or "CHANGE_ME" in value.upper():
                    raise ValueError(
                        f"Production ortamında {field_name} varsayılan değer kullanılamaz."
                    )
                if len(value) < _MIN_SECRET_LEN:
                    raise ValueError(
                        f"Production ortamında {field_name} en az {_MIN_SECRET_LEN} karakter olmalıdır."
                    )
            if self.allow_public_setup:
                raise ValueError(
                    "Production ortamında ALLOW_PUBLIC_SETUP=true olamaz. "
                    ".env dosyasında ALLOW_PUBLIC_SETUP=false ayarlayın."
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.myk_env == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
