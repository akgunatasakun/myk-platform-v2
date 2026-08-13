"""DMS ORM modelleri — Belge Yönetim Sistemi.

4 model:
  DocumentCategory   — belge kategorileri
  Document           — belgeler (metadata, soft-delete)
  DocumentRevision   — revizyon geçmişi
  DocumentRevisionFile — revizyon başına depolanan dosyalar
"""
import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentCategory(Base):
    """Belge kategorileri."""

    __tablename__ = "doc_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="category"
    )

    def __repr__(self) -> str:
        return f"<DocumentCategory code={self.code!r} name={self.name!r}>"


class Document(Base):
    """Belge metadata kaydı — soft delete destekli."""

    __tablename__ = "doc_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("doc_categories.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content_status: Mapped[str] = mapped_column(String(32), nullable=False, default="taslak")
    owner_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    # current_revision_id: NO FK constraint (circular ref — service manages)
    current_revision_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    category: Mapped[Optional["DocumentCategory"]] = relationship(
        "DocumentCategory", back_populates="documents"
    )
    revisions: Mapped[List["DocumentRevision"]] = relationship(
        "DocumentRevision",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentRevision.created_at",
    )

    def __repr__(self) -> str:
        return f"<Document code={self.code!r} title={self.title!r}>"


class DocumentRevision(Base):
    """Belge revizyonu — R00, R01, R02 şeklinde kodlanır."""

    __tablename__ = "doc_revisions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_code: Mapped[str] = mapped_column(String(32), nullable=False)
    revision_no: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    revision_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="taslak")
    effective_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manifest_row_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="revisions")
    files: Mapped[List["DocumentRevisionFile"]] = relationship(
        "DocumentRevisionFile",
        back_populates="revision",
        cascade="all, delete-orphan",
        order_by="DocumentRevisionFile.created_at",
    )

    def __repr__(self) -> str:
        return f"<DocumentRevision document_id={self.document_id} code={self.revision_code!r}>"


class DocumentRevisionFile(Base):
    """Revizyon başına depolanan dosya kaydı."""

    __tablename__ = "doc_revision_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc_revisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_role: Mapped[str] = mapped_column(String(32), nullable=False, default="source")
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger(), nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text(), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    revision: Mapped["DocumentRevision"] = relationship(
        "DocumentRevision", back_populates="files"
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentRevisionFile revision_id={self.revision_id} "
            f"filename={self.original_filename!r}>"
        )
