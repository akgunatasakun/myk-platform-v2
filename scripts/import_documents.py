#!/usr/bin/env python3
"""DMS Dry-Run Import Script — CLI wrapper.

İş mantığı backend/app/services/document_import.py içindedir.
Bu dosya yalnızca argparse + sys.path bootstrap içerir.

Kullanım:
    python scripts/import_documents.py \\
        --manifest PHASE2_FILE_MANIFEST.csv \\
        --source-dir /path/to/documents \\
        --output import_plan.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# backend/ klasörünü Python path'e ekle — hem doğrudan çalıştırma
# hem de repo root'tan çalıştırma senaryolarını destekler.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.document_import import run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DMS dry-run import — manifestı analiz et, DB'ye yazmaz."
    )
    parser.add_argument("--manifest", required=True, help="CSV manifest dosyası yolu")
    parser.add_argument(
        "--source-dir", required=True, help="Fiziksel dosyaların bulunduğu klasör"
    )
    parser.add_argument(
        "--output",
        default="import_plan.json",
        help="Çıktı JSON dosyası (varsayılan: import_plan.json)",
    )
    args = parser.parse_args()
    run(args.manifest, args.source_dir, args.output)


if __name__ == "__main__":
    main()
