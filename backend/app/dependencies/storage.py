"""Storage dependency injection.

Testlerde `app.dependency_overrides[get_storage]` ile mock storage
inject edilebilir. Production'da MinIO implementasyonu kullanılır.
"""
from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.services.storage import ObjectStorageService


@lru_cache(maxsize=1)
def _build_minio_service() -> ObjectStorageService:
    """MinioStorageService singleton — uygulama başına tek örnek."""
    from app.services.storage_minio import MinioStorageService

    s = get_settings()
    return MinioStorageService(
        endpoint=s.storage_endpoint,
        access_key=s.storage_access_key,
        secret_key=s.storage_secret_key,
        bucket=s.storage_bucket,
        secure=s.storage_secure,
        region=s.storage_region,
    )


def get_storage() -> ObjectStorageService:
    """FastAPI dependency: storage servisini döndür.

    Testlerde::

        app.dependency_overrides[get_storage] = lambda: InMemoryStorageService()
    """
    return _build_minio_service()
