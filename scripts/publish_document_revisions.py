#!/usr/bin/env python3
"""DMS revizyon onaylama / yayımlama CLI.

VARSAYILAN (--apply YOK): yalnızca doğrulama; DB/storage'a yazmaz.
APPLY: --apply + --confirm-production-publish + --expected-plan-sha256 zorunlu.

Örnek:
  python scripts/publish_document_revisions.py \\
    --plan /import/publish_plan.json --source-dir /import/onayli \\
    --club-id <uuid> --report /import/out/publish_preflight.json

Exit kodları: 0 başarı · 2 doğrulama hatası · 3 yazma hatası
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (_REPO_ROOT / "backend", _REPO_ROOT):
    if (_p / "app").is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.database import AsyncSessionLocal  # noqa: E402
from app.dependencies.documents_storage import get_dms_storage  # noqa: E402
from app.services.document_publish import publish_revisions  # noqa: E402


async def _run(args: argparse.Namespace) -> int:
    if args.apply and not (args.confirm_production_publish and args.expected_plan_sha256):
        print("HATA: --apply için --confirm-production-publish ve --expected-plan-sha256 gerekir.",
              file=sys.stderr)
        return 2
    try:
        club_id = uuid.UUID(args.club_id)
    except ValueError:
        print(f"HATA: Geçersiz club-id: {args.club_id}", file=sys.stderr)
        return 2
    print("Mod:", "APPLY" if args.apply else "PREFLIGHT (yazma yok)")
    async with AsyncSessionLocal() as db:
        result = await publish_revisions(
            db, get_dms_storage(), club_id=club_id, plan_path=args.plan,
            source_dir=args.source_dir, expected_plan_sha256=args.expected_plan_sha256,
            apply=args.apply,
        )
    report = result.to_dict()
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Rapor:", args.report)
    for it in result.items:
        print(f"  {it.code} {it.revision_code}: {it.previous_status} -> {it.target_status}"
              f"{' (atlandı)' if it.skipped else ''}"
              f"{' | arşivlenecek: ' + ','.join(it.archived_revisions) if it.archived_revisions else ''}"
              f"{f' | yeni dosya: {it.replaced_files}' if it.replaced_files else ''}")
    if result.errors:
        print("HATALAR:")
        for e in result.errors:
            print("  ✗", e)
        return 3 if args.apply else 2
    print("✅ OK")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="DMS revizyon onaylama/yayımlama")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--source-dir", default=None)
    ap.add_argument("--club-id", required=True)
    ap.add_argument("--expected-plan-sha256", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirm-production-publish", action="store_true")
    ap.add_argument("--report", default=None)
    sys.exit(asyncio.run(_run(ap.parse_args())))


if __name__ == "__main__":
    main()
