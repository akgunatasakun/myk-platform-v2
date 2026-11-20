"""Kulüp poliçe/sözleşmeleri için nesne bazlı, tüm DMS yollarında ortak erişim."""

from sqlalchemy import or_, select

from app.models.documents import Document
from app.models.renewal import DocumentRenewal

MANAGEMENT_DOCUMENT_READERS = {
    "super_admin",
    "kulup_yonetici",
    "genel_sekreter",
    "baskan",
    "yk_uyesi",
}


def management_document_filter():
    # Kodlar mevcut kayıtları migration öncesi/sonrası da korur. Yenileme geçmişi
    # kapatılmış olsa da belgenin erişimi genel kullanıma dönmez.
    return or_(
        Document.management_only.is_(True),
        Document.code.like("MYK-POL-%"),
        Document.code.like("MYK-SOZ-%"),
        select(DocumentRenewal.id)
        .where(
            DocumentRenewal.document_id == Document.id,
            DocumentRenewal.club_id == Document.club_id,
        )
        .exists(),
    )


async def is_management_document(db, document_id, club_id):
    return (
        await db.execute(
            select(Document.id).where(
                Document.id == document_id,
                Document.club_id == club_id,
                management_document_filter(),
            )
        )
    ).scalar_one_or_none() is not None
