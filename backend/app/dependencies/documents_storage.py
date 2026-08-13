"""DMS (Document Management System) storage dependency injection.

Testlerde `app.dependency_overrides[get_dms_storage]` ile mock storage
inject edilebilir. Production'da MinIO implementasyonu kullanılır.

DMS ayrı bir bucket kullanır: storage_bucket_documents (myk-documents).
"""
from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.services.storage import ObjectStorageService


@lru_cache(maxsize=1)
def _build_dms_minio_service() -> ObjectStorageService:
    """DMS MinioStorageService singleton — uygulama başına tek örnek."""
    from app.services.storage_minio import MinioStorageService

    s = get_settings()
    return MinioStorageService(
        endpoint=s.storage_endpoint,
        access_key=s.storage_access_key,
        secret_key=s.storage_secret_key,
        bucket=s.storage_bucket_documents,
        secure=s.storage_secure,
        region=s.storage_region,
    )


def get_dms_storage() -> ObjectStorageService:
    """FastAPI dependency: DMS storage servisini döndür.

    Testlerde::

        app.dependency_overrides[get_dms_storage] = lambda: InMemoryStorageService()
    """
    return _build_dms_minio_service()
