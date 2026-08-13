#!/usr/bin/env python3
"""DMS Production Import CLI — Sprint 14C Adım 2.

VARSAYILAN DAVRANIŞ (--apply YOK): preflight kontrolü yapar, DB/storage'a
hiçbir şey yazmaz.

APPLY MODU (--apply): preflight + gerçek DB + MinIO write.
  - --confirm-production-import flag'i zorunludur (kazara çalıştırmayı engeller)
  - --expected-plan-sha256 ZORUNLUDUR (artifact bütünlüğü)

Kullanım:

  # Dry-run preflight:
  python scripts/import_documents_apply.py \\
    --plan import_plan_ready_r01.json \\
    --source-dir /opt/myk/imports/sprint14c_ready_r01/source \\
    --club-id c145c694-0934-45bc-b316-dcc0c4f3aa82 \\
    --report /tmp/preflight_report.json

  # Gerçek import (production'da):
  python scripts/import_documents_apply.py \\
    --plan import_plan_ready_r01.json \\
    --source-dir /opt/myk/imports/sprint14c_ready_r01/source \\
    --club-id c145c694-0934-45bc-b316-dcc0c4f3aa82 \\
    --expected-plan-sha256 dfc77c8fb11ace5c1776cf7843e71cd9aec321c91ffd9fc91792792e80740f32 \\
    --apply \\
    --confirm-production-import \\
    --report /opt/myk/imports/sprint14c_ready_r01/import_result.json

Exit codes:
  0  başarı
  2  validation / preflight hatası
  3  write / import hatası
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config import get_settings  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
from app.dependencies.documents_storage import get_dms_storage  # noqa: E402
from app.services.document_bulk_import import import_document_plan  # noqa: E402


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()

    # ── Apply guard ───────────────────────────────────────────────────────────
    if args.apply:
        if not args.confirm_production_import:
            print(
                "HATA: --apply kullanmak için --confirm-production-import flag'i "
                "de gereklidir.",
                file=sys.stderr,
            )
            return 2
        if not args.expected_plan_sha256:
            print(
                "HATA: --apply kullanmak için --expected-plan-sha256 gereklidir.",
                file=sys.stderr,
            )
            return 2
        if settings.is_production:
            print(
                "UYARI: PRODUCTION ortamı tespit edildi. İmport başlıyor...",
                file=sys.stderr,
            )
        else:
            print(
                f"Ortam: {settings.myk_env} | apply=True",
                file=sys.stderr,
            )
    else:
        print("Mod: PREFLIGHT (--apply yok — DB/storage'a yazma yapılmayacak)")

    # ── club_id parse ─────────────────────────────────────────────────────────
    try:
        club_id = uuid.UUID(args.club_id)
    except ValueError:
        print(f"HATA: Geçersiz club-id: {args.club_id}", file=sys.stderr)
        return 2

    # ── Import çalıştır ───────────────────────────────────────────────────────
    storage = get_dms_storage()

    async with AsyncSessionLocal() as db:
        result = await import_document_plan(
            db,
            storage,
            club_id=club_id,
            plan_path=args.plan,
            source_dir=args.source_dir,
            expected_plan_sha256=args.expected_plan_sha256,
            apply=args.apply,
        )

    # ── Rapor ─────────────────────────────────────────────────────────────────
    report = result.to_dict()
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Rapor: {report_path}")

    # ── Özet çıktı ────────────────────────────────────────────────────────────
    print()
    if args.apply:
        print("=== Import Sonucu ===")
    else:
        print("=== Preflight Sonucu ===")

    print(f"  Başarı    : {result.success}")
    print(f"  Uygulanan : {result.applied}")
    print(f"  Oluşturulan belgeler : {result.created_documents}")
    print(f"  Oluşturulan revizyon : {result.created_revisions}")
    print(f"  Oluşturulan dosyalar : {result.created_files}")
    print(f"  Atlanan belgeler     : {result.skipped_documents}")
    if args.apply:
        print(f"  Yüklenen objeler     : {len(result.uploaded_objects)}")
    print(f"  Süre                 : {result.duration_seconds:.2f}s")

    if result.errors:
        print("\nHATALAR:")
        for err in result.errors:
            print(f"  ✗ {err}")
        return 3 if args.apply else 2

    print("\n✅ OK")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DMS Production Import CLI — Sprint 14C",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--plan",
        required=True,
        help="dry-run import plan JSON dosyası",
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        dest="source_dir",
        help="Kaynak PDF/DOCX dizini",
    )
    parser.add_argument(
        "--club-id",
        required=True,
        dest="club_id",
        help="Hedef kulüp UUID'si",
    )
    parser.add_argument(
        "--expected-plan-sha256",
        default=None,
        dest="expected_plan_sha256",
        help="Plan dosyasının beklenen SHA-256 hash'i (apply modunda zorunlu)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="DB + storage'a gerçek yazma yap (varsayılan: preflight only)",
    )
    parser.add_argument(
        "--confirm-production-import",
        action="store_true",
        default=False,
        dest="confirm_production_import",
        help="Kazara çalıştırmayı önlemek için --apply ile birlikte gerekli",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Sonuç JSON raporunun yazılacağı dosya yolu",
    )

    args = parser.parse_args()
    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
