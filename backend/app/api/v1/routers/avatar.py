"""Avatar yönetimi — yükleme, silme ve pre-signed URL endpoint'leri.

Güvenlik notları:
  - club_id YALNIZCA JWT'den alınır (get_club_id dependency)
  - Object key asla request body/query'den gelmez; sunucu tarafında üretilir
  - avatar_object_key API response'ta yer almaz (PersonAvatarOut)
  - MIME doğrulaması magic bytes ile yapılır (Content-Type header'a güvenilmez)
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from PIL import Image, ExifTags
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_action
from app.core.rbac import require_permission
from app.core.security import get_current_user
from app.core.tenant import get_club_id
from app.database import get_db
from app.dependencies.storage import get_storage
from app.models.person import Person
from app.schemas.auth import TokenPayload
from app.schemas.person import PersonAvatarOut
from app.services.storage import ObjectStorageService

router = APIRouter(prefix="/persons", tags=["avatar"])

# ── Sabitler ─────────────────────────────────────────────────────────────────
AVATAR_MAX_BYTES = 8 * 1024 * 1024          # 8 MB
AVATAR_MAX_DIM = 1024                        # px, uzun kenar
AVATAR_QUALITY = 85
AVATAR_URL_EXPIRES = 3600                    # 1 saat

ALLOWED_MIME_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",          # JPEG
    b"\x89PNG\r\n\x1a\n": "image/png",      # PNG
    b"RIFF": None,                           # WebP — 4 byte header; tam kontrol aşağıda
}

ALLOWED_PILLOW_FORMATS = {"JPEG", "PNG", "WEBP"}


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _detect_mime(data: bytes) -> str | None:
    """Magic bytes ile MIME türünü tespit et. Tanınmıyorsa None döner."""
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    # WebP: RIFF????WEBP
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _fix_orientation(img: Image.Image) -> Image.Image:
    """EXIF orientation tag'ini uygulayarak görseli döndür."""
    try:
        exif = img._getexif()  # type: ignore[attr-defined]
        if exif is None:
            return img
        orientation_key = next(
            (k for k, v in ExifTags.TAGS.items() if v == "Orientation"), None
        )
        if orientation_key is None:
            return img
        orientation = exif.get(orientation_key)
        ops = {
            2: (Image.FLIP_LEFT_RIGHT,),
            3: (Image.ROTATE_180,),
            4: (Image.FLIP_TOP_BOTTOM,),
            5: (Image.FLIP_LEFT_RIGHT, Image.ROTATE_90),
            6: (Image.ROTATE_270,),
            7: (Image.FLIP_LEFT_RIGHT, Image.ROTATE_270),
            8: (Image.ROTATE_90,),
        }
        for op in ops.get(orientation, []):
            img = img.transpose(op)
    except Exception:
        pass
    return img


def _process_image(data: bytes) -> tuple[bytes, int, int]:
    """
    Ham görüntü byte'larını al; EXIF düzelt, RGB/A dönüştür,
    en fazla AVATAR_MAX_DIM×AVATAR_MAX_DIM boyutuna küçült (oran koru),
    WebP olarak çıkar.

    Returns:
        (webp_bytes, width, height)

    Raises:
        HTTPException 422 — bozuk veya tanımsız görüntü formatı
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()          # bozuk dosyayı yakala
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Görüntü dosyası bozuk veya desteklenmeyen formatta.",
        )

    # verify() sonrası dosyayı yeniden aç (verify stream'i tüketir)
    img = Image.open(io.BytesIO(data))

    if img.format not in ALLOWED_PILLOW_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Desteklenmeyen format: {img.format}. JPEG, PNG veya WebP yükleyin.",
        )

    img = _fix_orientation(img)

    # RGB/RGBA dönüşümü
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    # En fazla AVATAR_MAX_DIM×AVATAR_MAX_DIM — oran koru
    if img.width > AVATAR_MAX_DIM or img.height > AVATAR_MAX_DIM:
        img.thumbnail((AVATAR_MAX_DIM, AVATAR_MAX_DIM), Image.LANCZOS)

    w, h = img.size

    # WebP çıktı — RGBA ise lossless alpha destekli
    output = io.BytesIO()
    if img.mode == "RGBA":
        img.save(output, format="WEBP", quality=AVATAR_QUALITY, method=4)
    else:
        img = img.convert("RGB")
        img.save(output, format="WEBP", quality=AVATAR_QUALITY, method=4)

    return output.getvalue(), w, h


def _make_current_key(club_id: uuid.UUID, person_id: uuid.UUID) -> str:
    return f"clubs/{club_id}/persons/{person_id}/avatar/current.webp"


def _make_archive_key(club_id: uuid.UUID, person_id: uuid.UUID) -> str:
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"clubs/{club_id}/persons/{person_id}/avatar/archive/{ts}.webp"


async def _get_person_or_404(
    person_id: uuid.UUID,
    club_id: uuid.UUID,
    db: AsyncSession,
) -> Person:
    result = await db.execute(
        select(Person)
        .options(selectinload(Person.roles))
        .where(
            Person.id == person_id,
            Person.club_id == club_id,
            Person.is_deleted.is_(False),
        )
    )
    person = result.scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kişi bulunamadı.")
    return person


# ── Endpoint'ler ─────────────────────────────────────────────────────────────

@router.post(
    "/{person_id}/avatar",
    response_model=PersonAvatarOut,
    status_code=status.HTTP_200_OK,
    summary="Avatar yükle",
)
async def upload_avatar(
    person_id: uuid.UUID,
    file: UploadFile,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kisi:write")),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorageService = Depends(get_storage),
) -> PersonAvatarOut:
    # ── 1. Kişiyi yükle (tenant koruması) ────────────────────────────────
    person = await _get_person_or_404(person_id, club_id, db)

    # ── 2. Boyut kontrolü ────────────────────────────────────────────────
    raw = await file.read()
    if len(raw) > AVATAR_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dosya boyutu {AVATAR_MAX_BYTES // (1024*1024)} MB sınırını aşıyor.",
        )

    # ── 3. MIME doğrulama (magic bytes) ──────────────────────────────────
    mime = _detect_mime(raw)
    if mime is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Desteklenmeyen dosya türü. Yalnızca JPEG, PNG ve WebP kabul edilir.",
        )

    # ── 4. Pillow: EXIF düzelt, küçült, WebP dönüştür ───────────────────
    webp_bytes, width, height = _process_image(raw)

    # ── 5. Mevcut avatar arşivle ─────────────────────────────────────────
    current_key = _make_current_key(club_id, person_id)
    action = "person_avatar_uploaded"

    if person.avatar_object_key:
        archive_key = _make_archive_key(club_id, person_id)
        await storage.copy(person.avatar_object_key, archive_key)
        action = "person_avatar_replaced"

    # ── 6. Yükle ──────────────────────────────────────────────────────────
    await storage.upload(current_key, webp_bytes, "image/webp")

    # ── 7. DB güncelle ───────────────────────────────────────────────────
    person.avatar_object_key = current_key
    await db.flush()

    # ── 8. Audit (dosya içeriği veya URL yok) ────────────────────────────
    await log_action(
        db,
        action=action,
        resource_type="person",
        club_id=club_id,
        user_id=uuid.UUID(current_user.sub),
        resource_id=str(person.id),
        after={
            "mime_type": "image/webp",
            "size_bytes": len(webp_bytes),
            "width": width,
            "height": height,
        },
        request=request,
    )

    # ── 9. Pre-signed URL üret ───────────────────────────────────────────
    url = await storage.presigned_url(current_key, expires=AVATAR_URL_EXPIRES)

    return PersonAvatarOut(
        has_avatar=True,
        avatar_url=url,
        expires_in=AVATAR_URL_EXPIRES,
    )


@router.delete(
    "/{person_id}/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Avatar sil",
)
async def delete_avatar(
    person_id: uuid.UUID,
    request: Request,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kisi:write")),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorageService = Depends(get_storage),
) -> None:
    person = await _get_person_or_404(person_id, club_id, db)

    prev_key = person.avatar_object_key

    # İdempotent: avatar zaten yoksa sessizce geç
    if prev_key:
        await storage.delete(prev_key)
        person.avatar_object_key = None
        await db.flush()

        await log_action(
            db,
            action="person_avatar_deleted",
            resource_type="person",
            club_id=club_id,
            user_id=uuid.UUID(current_user.sub),
            resource_id=str(person.id),
            request=request,
            # after yok — nesne silindi; before'a key yazma (storage path iç veri)
        )


@router.get(
    "/{person_id}/avatar-url",
    response_model=PersonAvatarOut,
    summary="Avatar pre-signed URL",
)
async def get_avatar_url(
    person_id: uuid.UUID,
    club_id: uuid.UUID = Depends(get_club_id),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission("kisi:read")),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorageService = Depends(get_storage),
) -> PersonAvatarOut:
    person = await _get_person_or_404(person_id, club_id, db)

    if not person.avatar_object_key:
        return PersonAvatarOut(has_avatar=False, avatar_url=None)

    url = await storage.presigned_url(person.avatar_object_key, expires=AVATAR_URL_EXPIRES)
    return PersonAvatarOut(
        has_avatar=True,
        avatar_url=url,
        expires_in=AVATAR_URL_EXPIRES,
    )
