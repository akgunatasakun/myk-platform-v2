#!/usr/bin/env python3
"""DMS Import Rollback CLI — Sprint 14C.

Import result JSON'undaki belgeler ve storage object'leri siler.
Varsayılan mod: DRY-RUN (yalnızca ne silineceğini gösterir).

Güvenlik kuralları:
    - Hard delete YOKTUR: belgeler is_deleted=true olarak işaretlenir.
    - Yalnızca report JSON'ında listelenen document_id'ler etkilenir.
    - current_revision_id bağlantıları da temizlenir (None yapılır).
    - MinIO object silme: yalnızca report.uploaded_objects listesindeki key'ler.
    - --apply verilmeden hiçbir mutation yapılmaz.

Kullanım:

  # Dry-run (ne silineceğini göster):
  python scripts/rollback_document_import.py \\
    --report /opt/myk/imports/sprint14c_ready_r01/import_result.json

  # Gerçek rollback:
  python scripts/rollback_document_import.py \\
    --report /opt/myk/imports/sprint14c_ready_r01/import_result.json \\
    --apply \\
    --confirm-rollback

Exit codes:
  0  başarı
  2  validation hatası
  3  rollback hatası
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import uuid  # noqa: E402

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.dependencies.documents_storage import get_dms_storage  # noqa: E402
from app.models.documents import Document, DocumentRevision  # noqa: E402


async def _rollback(args: argparse.Namespace) -> int:
    # ── Raporu yükle ──────────────────────────────────────────────────────────
    report_path = Path(args.report)
    if not report_path.exists():
        print(f"HATA: Rapor dosyası bulunamadı: {report_path}", file=sys.stderr)
        return 2

    with open(report_path, encoding="utf-8") as f:
        report: dict = json.load(f)

    if not report.get("applied", False):
        print(
            "HATA: Bu rapor 'applied=false' içeriyor; rollback edilecek gerçek "
            "import verisi yok.",
            file=sys.stderr,
        )
        return 2

    document_ids = [
        d["document_id"]
        for d in report.get("documents", [])
        if d.get("document_id") and not d.get("skipped") and not d.get("error")
    ]
    storage_keys = report.get("uploaded_objects", [])

    if not document_ids and not storage_keys:
        print("Rollback edilecek veri yok (boş import raporu).")
        return 0

    print(f"Rollback edilecek belge sayısı  : {len(document_ids)}")
    print(f"Silinecek storage object sayısı : {len(storage_keys)}")

    if not args.apply:
        print("\nMod: DRY-RUN — gerçek silme yapılmayacak (--apply yok)")
        print("\nSilinecek belge ID'leri:")
        for did in document_ids:
            print(f"  {did}")
        if storage_keys:
            print("\nSilinecek storage key'leri:")
            for key in storage_keys[:10]:
                print(f"  {key}")
            if len(storage_keys) > 10:
                print(f"  ... ve {len(storage_keys) - 10} adet daha")
        print("\n✅ DRY-RUN tamamlandı")
        return 0

    # ── Apply guard ───────────────────────────────────────────────────────────
    if not args.confirm_rollback:
        print(
            "HATA: --apply ile rollback için --confirm-rollback gereklidir.",
            file=sys.stderr,
        )
        return 2

    # ── DB soft-delete ────────────────────────────────────────────────────────
    errors: list[str] = []
    deleted_count = 0

    async with AsyncSessionLocal() as db:
        try:
            for did_str in document_ids:
                did = uuid.UUID(did_str)

                # current_revision_id → None yap
                await db.execute(
                    update(Document)
                    .where(Document.id == did)
                    .values(current_revision_id=None)
                )
                await db.flush()

                # Revision is_current → False
                await db.execute(
                    update(DocumentRevision)
                    .where(DocumentRevision.document_id == did)
                    .values(is_current=False)
                )
                await db.flush()

                # Belgeyi soft-delete
                await db.execute(
                    update(Document)
                    .where(Document.id == did)
                    .values(is_deleted=True, is_active=False)
                )
                await db.flush()
                deleted_count += 1

            await db.commit()
            print(f"DB: {deleted_count} belge soft-deleted ✅")

        except Exception as exc:
            await db.rollback()
            errors.append(f"DB rollback hatası: {exc}")
            print(f"HATA: DB rollback başarısız: {exc}", file=sys.stderr)
            return 3

    # ── Storage cleanup ───────────────────────────────────────────────────────
    if storage_keys:
        storage = get_dms_storage()
        storage_errors = 0
        for key in storage_keys:
            try:
                await storage.delete(key)
            except Exception as exc:
                storage_errors += 1
                errors.append(f"Storage silme hatası {key}: {exc}")

        if storage_errors:
            print(
                f"UYARI: {storage_errors} storage object silinemedi "
                "(manuel temizlik gerekebilir).",
                file=sys.stderr,
            )
        else:
            print(f"Storage: {len(storage_keys)} object silindi ✅")

    if errors:
        print("\nHATALAR:")
        for e in errors:
            print(f"  ✗ {e}")
        return 3

    print("\n✅ Rollback tamamlandı")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DMS Import Rollback CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--report",
        required=True,
        help="import_documents_apply.py --report çıktısı",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Gerçek silme yap (varsayılan: dry-run)",
    )
    parser.add_argument(
        "--confirm-rollback",
        action="store_true",
        default=False,
        dest="confirm_rollback",
        help="--apply ile birlikte zorunlu güvenlik flag'i",
    )

    args = parser.parse_args()
    exit_code = asyncio.run(_rollback(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
