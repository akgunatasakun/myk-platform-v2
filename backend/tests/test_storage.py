"""ObjectStorageService mock adapter testleri — ST-01 .. ST-07.

Bu testler gerçek MinIO bağlantısı gerektirmez; InMemoryStorageService
kullanarak tüm arayüz davranışlarını doğrular.
"""
import pytest

from app.services.storage import ObjectStorageService


# ── In-memory test implementasyonu ────────────────────────────────────────


class InMemoryStorageService(ObjectStorageService):
    """Test/geliştirme ortamı için bellek içi storage implementasyonu."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[bytes, str]] = {}  # key → (data, content_type)

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        self._store[key] = (data, content_type)
        return key

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._store

    async def copy(self, src_key: str, dst_key: str) -> None:
        if src_key not in self._store:
            raise KeyError(f"Source key not found: {src_key}")
        self._store[dst_key] = self._store[src_key]

    async def presigned_url(self, key: str, expires: int) -> str:
        return f"http://test-storage/{key}?expires={expires}"


# ── Fixture ────────────────────────────────────────────────────────────────


@pytest.fixture
def storage() -> InMemoryStorageService:
    return InMemoryStorageService()


# ── Testler ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_st01_upload_and_exists(storage: InMemoryStorageService) -> None:
    """ST-01: Upload sonrası exists() True döner."""
    key = "clubs/abc/persons/xyz/avatar/current.webp"
    assert not await storage.exists(key)

    returned_key = await storage.upload(key, b"fake-image-data", "image/webp")

    assert returned_key == key
    assert await storage.exists(key)


@pytest.mark.asyncio
async def test_st02_delete_removes_object(storage: InMemoryStorageService) -> None:
    """ST-02: Delete sonrası exists() False döner."""
    key = "clubs/abc/persons/xyz/avatar/current.webp"
    await storage.upload(key, b"data", "image/webp")
    assert await storage.exists(key)

    await storage.delete(key)

    assert not await storage.exists(key)


@pytest.mark.asyncio
async def test_st03_delete_nonexistent_is_silent(storage: InMemoryStorageService) -> None:
    """ST-03: Olmayan nesneyi silmek exception atmaz."""
    await storage.delete("nonexistent/key")  # exception beklenmez


@pytest.mark.asyncio
async def test_st04_copy_creates_dst(storage: InMemoryStorageService) -> None:
    """ST-04: copy() sonrası hem src hem dst exists() True döner."""
    src = "clubs/abc/persons/xyz/avatar/current.webp"
    dst = "clubs/abc/persons/xyz/avatar/archive/20260804_120000.webp"
    await storage.upload(src, b"img", "image/webp")

    await storage.copy(src, dst)

    assert await storage.exists(src)
    assert await storage.exists(dst)


@pytest.mark.asyncio
async def test_st05_copy_nonexistent_raises(storage: InMemoryStorageService) -> None:
    """ST-05: Olmayan src key'den copy() KeyError atar."""
    with pytest.raises(KeyError):
        await storage.copy("nonexistent/src", "some/dst")


@pytest.mark.asyncio
async def test_st06_presigned_url_contains_key(storage: InMemoryStorageService) -> None:
    """ST-06: presigned_url() dönen URL içinde key geçer."""
    key = "clubs/abc/persons/xyz/avatar/current.webp"
    url = await storage.presigned_url(key, expires=3600)

    assert key in url


@pytest.mark.asyncio
async def test_st07_presigned_url_batch(storage: InMemoryStorageService) -> None:
    """ST-07: presigned_url_batch() tüm key'ler için URL döner, fazlası yok."""
    keys = [
        "clubs/a/persons/1/avatar/current.webp",
        "clubs/a/persons/2/avatar/current.webp",
        "clubs/a/persons/3/avatar/current.webp",
    ]
    url_map = await storage.presigned_url_batch(keys, expires=3600)

    assert set(url_map.keys()) == set(keys)
    for k, url in url_map.items():
        assert k in url


@pytest.mark.asyncio
async def test_st08_upload_overwrites(storage: InMemoryStorageService) -> None:
    """ST-08: Aynı key'e iki kez upload → yeni içerik kazanır."""
    key = "clubs/abc/file.webp"
    await storage.upload(key, b"old-data", "image/webp")
    await storage.upload(key, b"new-data", "image/webp")

    data, _ = storage._store[key]
    assert data == b"new-data"


@pytest.mark.asyncio
async def test_st09_avatar_archive_workflow(storage: InMemoryStorageService) -> None:
    """ST-09: Avatar versiyonlama iş akışı — copy → upload → eski arşivde kalır."""
    current_key = "clubs/abc/persons/xyz/avatar/current.webp"
    archive_key = "clubs/abc/persons/xyz/avatar/archive/20260804_120000.webp"

    # İlk yükleme
    await storage.upload(current_key, b"avatar-v1", "image/webp")

    # Yeni yükleme öncesi: eski current → archive
    await storage.copy(current_key, archive_key)
    await storage.delete(current_key)
    await storage.upload(current_key, b"avatar-v2", "image/webp")

    # current yeni, archive eski içeriği taşıyor
    assert storage._store[current_key][0] == b"avatar-v2"
    assert storage._store[archive_key][0] == b"avatar-v1"
