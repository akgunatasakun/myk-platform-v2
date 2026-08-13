"""ObjectStorageService — storage abstraction.

Tüm storage işlemleri bu arayüz üzerinden yürütülür.
MinIO (staging) veya S3-uyumlu (production) implementasyonları
yalnızca .env değişkenleri değiştirilerek değiştirilebilir.
"""
from __future__ import annotations

import abc
from typing import Dict, List


class ObjectStorageService(abc.ABC):
    """Storage arayüzü — MinIO veya S3-uyumlu implementasyonlar bu sınıfı genişletir."""

    @abc.abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        """Veriyi belirtilen key altında yükle.

        Returns:
            Yüklenen nesnenin object key'i (``key`` parametresiyle aynı).
        """
        ...

    @abc.abstractmethod
    async def delete(self, key: str) -> None:
        """Belirtilen key'deki nesneyi sil. Nesne yoksa sessizce geç."""
        ...

    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        """Belirtilen key'deki nesnenin var olup olmadığını kontrol et."""
        ...

    @abc.abstractmethod
    async def copy(self, src_key: str, dst_key: str) -> None:
        """Nesneyi src_key'den dst_key'e kopyala.

        Sprint 4 belge versiyonlama ve avatar arşivleme için kullanılır.
        """
        ...

    @abc.abstractmethod
    async def presigned_url(self, key: str, expires: int) -> str:
        """Belirtilen key için expires saniye geçerli pre-signed URL üret."""
        ...

    @abc.abstractmethod
    async def download(self, key: str) -> bytes:
        """key altındaki nesnenin içeriğini bayt olarak döndür.

        Nesne yoksa KeyError fırlatır.
        Boyut sınırı max_upload_mb ile kontrol edilir (bkz. caller).
        """
        ...

    async def presigned_url_batch(
        self, keys: List[str], expires: int
    ) -> Dict[str, str]:
        """Birden fazla key için pre-signed URL'leri toplu üret.

        N+1 sorunu önleme: PersonList endpoint'i tüm avatar key'lerini tek
        çağrıyla işlemek için bu metodu kullanır.

        Varsayılan implementasyon presigned_url'i sırayla çağırır.
        MinIO/S3 implementasyonları bunu override edebilir.
        """
        result: Dict[str, str] = {}
        for key in keys:
            result[key] = await self.presigned_url(key, expires)
        return result
