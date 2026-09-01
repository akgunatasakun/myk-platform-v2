"""TYF Eğitim Kütüphanesi — idempotent seed script.

Her çalıştırmada mevcut kayıtları atlar; yalnızca eksik olanları ekler.
PDF dosyaları MinIO'ya yüklenir, metadata DB'ye yazılır.

Kullanım (production sunucusunda):
    cd /opt/myk/production/myk-platform-v2/backend
    source /etc/myk/production.env
    PDF_DIR=/path/to/pdfs python scripts/seed_tyf_library.py

PDF_DIR: 9 TYF PDF'sinin bulunduğu dizin (varsayılan: script dizini).
Env değişkenleri production.env'den okunur (DATABASE_URL, STORAGE_* vb.).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
import uuid
from pathlib import Path

# Proje kökünü sys.path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.documents import (
    Document,
    DocumentCategory,
    DocumentRevision,
    DocumentRevisionFile,
)
from app.services.storage_minio import MinioStorageService

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ── Kategori kataloğu ─────────────────────────────────────────────────────────

CATEGORIES = [
    {
        "code": "tyf-dingi",
        "name": "Dingi Yelken",
        "description": "TYF Optimist / ILCA eğitim dokümanları",
        "sort_order": 10,
    },
    {
        "code": "tyf-kite",
        "name": "Uçurtma Sörfü",
        "description": "TYF kite-surf (US) kademeli eğitim dokümanları",
        "sort_order": 20,
    },
    {
        "code": "tyf-wing",
        "name": "Kanat Sörfü",
        "description": "TYF wing-surf eğitim ve yarışa hazırlık",
        "sort_order": 30,
    },
    {
        "code": "tyf-staff",
        "name": "Eğitmen / Antrenör",
        "description": "TYF öğretici ve antrenör kademesi talimatları",
        "sort_order": 40,
    },
]

# ── Doküman kataloğu ──────────────────────────────────────────────────────────
# code: DB'de unique slug; filename: PDF_DIR altındaki dosya adı

DOCUMENTS = [
    {
        "code":          "TYF-D1",
        "title":         "D1 Eğitim Kitapçığı",
        "category_code": "tyf-dingi",
        "filename":      "D1-Egitim-Kitapcigi.pdf",
        "tags":          "temel,bağ,rüzgar,optimist,ilca",
        "description":   "Dingi yelken D1 kademe temel eğitim kitapçığı.",
    },
    {
        "code":          "TYF-D2",
        "title":         "D2 Gelişim Eğitim Dokümanı",
        "category_code": "tyf-dingi",
        "filename":      "D2-Egitim-Dokumani.pdf",
        "tags":          "apaz,manevra,gelişim,optimist,ilca",
        "description":   "Dingi yelken D2 kademe gelişim eğitim dokümanı.",
    },
    {
        "code":          "TYF-D3",
        "title":         "D3 İleri Eğitim Dokümanı",
        "category_code": "tyf-dingi",
        "filename":      "D3-Egitim-Dokumani.pdf",
        "tags":          "ileri,yarış,taktik,ilca",
        "description":   "Dingi yelken D3 kademe ileri eğitim dokümanı.",
    },
    {
        "code":          "TYF-US1",
        "title":         "US-1 Uçurtma Sörfü Eğitim Dokümanı",
        "category_code": "tyf-kite",
        "filename":      "us-1-ucurtma-sorfu-egitim-dokumani.pdf",
        "tags":          "temel,kite,çevre,rüzgar,kaldırma,güvenlik",
        "description":   "Kite-surf US-1 kademe: çevre, rüzgar penceresi, kaldırma kuvveti.",
    },
    {
        "code":          "TYF-US2",
        "title":         "US-2 Uçurtma Sörfü Eğitim Dokümanı",
        "category_code": "tyf-kite",
        "filename":      "us-2-ucurtma-sorfu-egitim-dokumanii.pdf",
        "tags":          "dönüş,topuk,zıplama,kurtarma,kite",
        "description":   "Kite-surf US-2 kademe: dönüş, topuk, zıplama, kurtarma.",
    },
    {
        "code":          "TYF-US3",
        "title":         "US-3 Uçurtma Sörfü Eğitim Dokümanı",
        "category_code": "tyf-kite",
        "filename":      "us-3-ucurtma-sorfu-egitim-dokumanii.pdf",
        "tags":          "serbest,stil,parkur,dalga,kite",
        "description":   "Kite-surf US-3 kademe: serbest stil, parkur, dalga sörfü.",
    },
    {
        "code":          "TYF-WS1",
        "title":         "Kanat Sörfü Eğitim ve Yarışa Hazırlık",
        "category_code": "tyf-wing",
        "filename":      "Kanat_Sorfu_Egitim_ve_Yarisa_Hazirlik.pdf",
        "tags":          "wing,kanat,12hafta,yarış,self-rescue",
        "description":   "12 haftalık kanat sörfü programı ve yarışa hazırlık el kitabı.",
    },
    {
        "code":          "TYF-OGR",
        "title":         "Yelken Öğretici / Eğitmen Talimatı",
        "category_code": "tyf-staff",
        "filename":      "yelken-ogretici-egitmen-talimati_r1.pdf",
        "tags":          "öğretici,eğitmen,kademe,vize,log-book",
        "description":   "TYF yelken öğretici ve eğitmen kademe talimatı (R1).",
    },
    {
        "code":          "TYF-ANT",
        "title":         "Antrenör Eğitim Talimatı",
        "category_code": "tyf-staff",
        "filename":      "antrenor-egitim-talimati_r1.pdf",
        "tags":          "antrenör,kademe,sınav,çocuk-koruma",
        "description":   "TYF antrenör eğitim ve kademe talimatı (R1).",
    },
]

SOURCE = "Türkiye Yelken Federasyonu"
MINIO_PREFIX = "academy/tyf"
OWNER_TYPE = "tyf_library"   # list_documents ?owner_type=tyf_library ile filtrelenir


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


async def _get_or_create_category(
    db: AsyncSession,
    club_id: uuid.UUID,
    cat: dict,
) -> DocumentCategory:
    result = await db.execute(
        sa.select(DocumentCategory).where(
            DocumentCategory.club_id == club_id,
            DocumentCategory.code == cat["code"],
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        log.info("  Kategori mevcut, atlanıyor: %s", cat["code"])
        return existing
    obj = DocumentCategory(
        club_id=club_id,
        code=cat["code"],
        name=cat["name"],
        description=cat["description"],
        sort_order=cat["sort_order"],
        is_active=True,
    )
    db.add(obj)
    await db.flush()
    log.info("  Kategori oluşturuldu: %s", cat["code"])
    return obj


async def _seed_document(
    db: AsyncSession,
    storage: MinioStorageService,
    club_id: uuid.UUID,
    doc_def: dict,
    category: DocumentCategory,
    pdf_dir: Path,
    bucket: str,
) -> None:
    # İdempotent: aynı code + club varsa atla
    result = await db.execute(
        sa.select(Document).where(
            Document.club_id == club_id,
            Document.code == doc_def["code"],
            Document.is_deleted.is_(False),
        )
    )
    if result.scalar_one_or_none():
        log.info("  Doküman mevcut, atlanıyor: %s", doc_def["code"])
        return

    pdf_path = pdf_dir / doc_def["filename"]
    if not pdf_path.exists():
        log.warning("  PDF bulunamadı, atlanıyor: %s", pdf_path)
        return

    file_size = pdf_path.stat().st_size
    sha = _sha256(pdf_path)
    storage_key = f"{MINIO_PREFIX}/{doc_def['filename']}"

    # MinIO'ya yükle
    log.info("  MinIO'ya yükleniyor: %s → %s/%s", doc_def["filename"], bucket, storage_key)
    with open(pdf_path, "rb") as f:
        data = f.read()
    await storage.upload(storage_key, data, "application/pdf")

    # Document kaydı
    doc = Document(
        club_id=club_id,
        category_id=category.id,
        code=doc_def["code"],
        title=doc_def["title"],
        document_type="egitim_materyali",
        content_status="yayinda",
        owner_type=OWNER_TYPE,
        owner_id=None,
        is_active=True,
        is_deleted=False,
    )
    db.add(doc)
    await db.flush()

    # Revision
    rev = DocumentRevision(
        document_id=doc.id,
        revision_code="R00",
        revision_no=0,
        status="yayinda",
        is_current=True,
        source=SOURCE,
        description=doc_def.get("description", ""),
    )
    db.add(rev)
    await db.flush()

    # Document.current_revision_id güncelle
    doc.current_revision_id = rev.id

    # File kaydı
    rev_file = DocumentRevisionFile(
        revision_id=rev.id,
        file_role="source",
        original_filename=doc_def["filename"],
        mime_type="application/pdf",
        file_size=file_size,
        sha256=sha,
        storage_bucket=bucket,
        storage_key=storage_key,
        is_primary=True,
    )
    db.add(rev_file)
    await db.flush()

    log.info("  ✓ Oluşturuldu: %s — %s", doc_def["code"], doc_def["title"])


# ── Ana akış ──────────────────────────────────────────────────────────────────

async def run() -> None:
    settings = get_settings()
    pdf_dir = Path(os.environ.get("PDF_DIR", Path(__file__).parent)).expanduser()

    log.info("PDF dizini: %s", pdf_dir)
    log.info("DB: %s", settings.database_url[:50] + "…")
    log.info("MinIO: %s  bucket: %s", settings.storage_endpoint, settings.storage_bucket_documents)

    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    storage = MinioStorageService(
        endpoint=settings.storage_endpoint,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key,
        bucket=settings.storage_bucket_documents,
        region=settings.storage_region,
        secure=settings.storage_secure,
    )
    bucket = settings.storage_bucket_documents

    # Kulüp ID'yi al (tek kulüp varsayımı)
    async with async_session() as db:
        from app.models.club import Club
        result = await db.execute(sa.select(Club.id).limit(1))
        club_id: uuid.UUID | None = result.scalar_one_or_none()
        if club_id is None:
            log.error("Veritabanında kulüp kaydı bulunamadı. Seed iptali.")
            return
        log.info("Kulüp ID: %s", club_id)

        # Kategorileri oluştur
        log.info("\n── Kategoriler ──")
        cat_map: dict[str, DocumentCategory] = {}
        for cat_def in CATEGORIES:
            cat_map[cat_def["code"]] = await _get_or_create_category(db, club_id, cat_def)

        # Dokümanları oluştur
        log.info("\n── Dokümanlar ──")
        for doc_def in DOCUMENTS:
            cat = cat_map[doc_def["category_code"]]
            await _seed_document(db, storage, club_id, doc_def, cat, pdf_dir, bucket)

        await db.commit()
        log.info("\n✓ Seed tamamlandı.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
