"""MinIO / S3-uyumlu ObjectStorageService implementasyonu.

Bağımlılık: miniopy-async (async MinIO Python client)

Env değişkenleri (app/config.py aracılığıyla):
    STORAGE_ENDPOINT   http://minio:9000
    STORAGE_ACCESS_KEY ...
    STORAGE_SECRET_KEY ...
    STORAGE_BUCKET     myk-person-media
    STORAGE_REGION     us-east-1
"""
from __future__ import annotations

import datetime
import io

import aiohttp
from miniopy_async import Minio
from miniopy_async.deleteobjects import DeleteObject
from miniopy_async.error import S3Error

from app.services.storage import ObjectStorageService


class MinioStorageService(ObjectStorageService):
    """MinIO / AWS S3 implementasyonu."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        *,
        secure: bool = False,
        region: str = "us-east-1",
    ) -> None:
        # endpoint http(s):// prefix'ini strip et — Minio client host:port ister
        host = endpoint.removeprefix("https://").removeprefix("http://")
        self._client = Minio(
            host,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )
        self._bucket = bucket
        self._bucket_ready = False  # lazy provisioning bayrağı

    # ── Bucket idempotent hazırlık ────────────────────────────────────────

    async def _ensure_bucket(self) -> None:
        """Bucket yoksa oluştur. Idempotent; race-safe."""
        if self._bucket_ready:
            return
        if not await self._client.bucket_exists(self._bucket):
            await self._client.make_bucket(self._bucket)
        self._bucket_ready = True

    # ── Temel işlemler ────────────────────────────────────────────────────

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        await self._ensure_bucket()
        stream = io.BytesIO(data)
        await self._client.put_object(
            self._bucket,
            key,
            stream,
            length=len(data),
            content_type=content_type,
        )
        return key

    async def delete(self, key: str) -> None:
        try:
            await self._client.remove_object(self._bucket, key)
        except Exception:
            # Nesne yoksa veya başka hata — sessizce geç
            pass

    async def exists(self, key: str) -> bool:
        try:
            await self._client.stat_object(self._bucket, key)
            return True
        except Exception:
            return False

    async def copy(self, src_key: str, dst_key: str) -> None:
        from miniopy_async.commonconfig import CopySource

        await self._client.copy_object(
            self._bucket,
            dst_key,
            CopySource(self._bucket, src_key),
        )

    async def presigned_url(self, key: str, expires: int) -> str:
        url = await self._client.presigned_get_object(
            self._bucket,
            key,
            expires=datetime.timedelta(seconds=expires),
        )
        return url

    async def download(self, key: str) -> bytes:
        """key altındaki nesneyi bayt olarak döndür.

        Nesne yoksa (NoSuchKey / NoSuchBucket) KeyError fırlatır.
        Diğer I/O veya auth hataları RuntimeError olarak yükselir —
        bunlar storage servis problemidir, 404 döndürülmemeli.
        """
        async with aiohttp.ClientSession() as session:
            response = None
            try:
                response = await self._client.get_object(
                    self._bucket, key, session
                )
                data = await response.read()
                return data
            except S3Error as exc:
                if exc.code in ("NoSuchKey", "NoSuchBucket"):
                    raise KeyError(key) from exc
                raise RuntimeError(
                    f"MinIO S3 error downloading {key!r}: {exc.code}"
                ) from exc
            finally:
                if response is not None:
                    try:
                        response.close()
                        await response.release()
                    except Exception:
                        pass
