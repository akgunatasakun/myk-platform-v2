"""Athlete profiles — sporcu profillerinin 1:1 uzantısı.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-11

Değişiklikler (1 tablo):
  athlete_profiles — persons.id ile 1:1 ilişkili sporcu profil tablosu.

Tasarım notları:
  - persons tablosu ana kimlik kaynağı olmaya devam eder.
    ad/soyad/tc/doğum/cinsiyet/kan_grubu/acil kişi/veli bağlantısı oradadır.
  - athlete_profiles yalnızca sporcuya özgü alanlara ev sahipliği yapar:
      sınıf, seviye, lisans, vize, sağlık raporu, yüzme yeterliliği,
      alerji/özel durum, KVKK/foto-video izinleri, branş bağlantısı.
  - UNIQUE(person_id) → bir kişinin en fazla bir sporcu profili olabilir.
  - FK club_id: tenant izolasyonunu constraint düzeyinde garanti eder.
  - Sağlık alanları (allergies, special_conditions, health_report_expiry_date)
    servis katmanında rol bazlı maskelenir.

Flask eşlemesi:
  sporcular.sinif                → class_name
  sporcular.seviye               → level
  sporcular.lisans_no            → license_no
  sporcular.lisans_bitis         → license_expiry_date
  sporcular.vize_bitis           → visa_expiry_date
  sporcular.saglik_raporu_bitis  → health_report_expiry_date
  sporcular.yuzme_yeterliligi    → swimming_qualified
  sporcular.alerji               → allergies
  sporcular.ozel_durum           → special_conditions
  sporcular.kvkk_onay            → kvkk_consent
  sporcular.kvkk_onay_tarihi     → kvkk_consent_at
  sporcular.kvkk_metin_versiyonu → kvkk_text_version
  sporcular.foto_video_izni      → photo_video_consent
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    _u = UUID(as_uuid=True) if is_pg else sa.String(36)

    op.create_table(
        "athlete_profiles",
        sa.Column("id", _u, primary_key=True),
        sa.Column("club_id", _u, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", _u, sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),

        # Branş & sportif sınıf
        sa.Column("sports_branch_id", _u,
                  sa.ForeignKey("sports_branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("class_name", sa.Text(), nullable=True),      # Optimist, ILCA, 420…
        sa.Column("level", sa.String(30), nullable=True, server_default="baslangic"),

        # Lisans / vize
        sa.Column("license_no", sa.String(100), nullable=True),
        sa.Column("license_expiry_date", sa.Date(), nullable=True),
        sa.Column("visa_expiry_date", sa.Date(), nullable=True),

        # Sağlık
        sa.Column("health_report_expiry_date", sa.Date(), nullable=True),
        sa.Column("swimming_qualified", sa.Boolean(), nullable=False, server_default="false"),

        # Tıbbi / özel durum (rol bazlı maskelenir)
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("special_conditions", sa.Text(), nullable=True),

        # KVKK & izinler
        sa.Column("kvkk_consent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("kvkk_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kvkk_text_version", sa.String(20), nullable=True),
        sa.Column("photo_video_consent", sa.Boolean(), nullable=False, server_default="false"),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # UNIQUE: bir person'a ait tek bir sporcu profili olabilir
    op.create_index(
        "uq_athlete_profiles_person_id",
        "athlete_profiles",
        ["person_id"],
        unique=True,
    )

    # Tenant sorguları için: tüm sporcular, sınıfa göre filtre, branşa göre filtre
    op.create_index("ix_athlete_profiles_club_id", "athlete_profiles", ["club_id"])
    op.create_index(
        "ix_athlete_profiles_club_class",
        "athlete_profiles",
        ["club_id", "class_name"],
    )
    op.create_index(
        "ix_athlete_profiles_club_branch",
        "athlete_profiles",
        ["club_id", "sports_branch_id"],
    )

    if is_pg:
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON athlete_profiles TO myk_app;")


def downgrade() -> None:
    op.drop_index("ix_athlete_profiles_club_branch", "athlete_profiles")
    op.drop_index("ix_athlete_profiles_club_class", "athlete_profiles")
    op.drop_index("ix_athlete_profiles_club_id", "athlete_profiles")
    op.drop_index("uq_athlete_profiles_person_id", "athlete_profiles")
    op.drop_table("athlete_profiles")
