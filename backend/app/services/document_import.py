"""DMS Dry-Run Import Service — Belge Manifesti Analiz Motoru.

Gerçek DB bağlantısı KURMAZ. Salt okunur analiz yapar.

Dışarıdan çağrı:
    from app.services.document_import import run

    result = run(manifest_path, source_dir, output_path)

CLI wrapper:
    scripts/import_documents.py bu modülü kullanır.

Mantık:
  1. CSV'yi parse et
  2. Her satır için source-dir altında fiziksel dosyayı ara
  3. Dosya varsa SHA-256 hesapla
  4. Aynı basename'e sahip PDF+DOCX çiftlerini tek mantıksal belge say
  5. çelişki_durumu dolu satırlar → conflicts listesi
  6. içerik_durumu=taslak-içerik-eksik → content_status=eksik
  7. Diskte var ama manifeste girmeyen → unmatched_disk
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


# ── İçerik durumu normalizasyon tablosu ────────────────────────────────────────

_CONTENT_STATUS_MAP: dict[str, str] = {
    "tamamlandi": "tamamlandi",
    "tamamlandı": "tamamlandi",
    "taslak": "taslak",
    "taslak-içerik-eksik": "eksik",
    "taslak-icerik-eksik": "eksik",
    "eksik": "eksik",
    "placeholder": "placeholder",
    "bilinmiyor": "bilinmiyor",
    "": "bilinmiyor",
}


def _normalize_content_status(raw: str) -> str:
    key = raw.strip().lower()
    return _CONTENT_STATUS_MAP.get(key, "bilinmiyor")


# ── Dosya SHA-256 hesapla ───────────────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Disk dosyalarını tara ───────────────────────────────────────────────────────

def _scan_disk(source_dir: Path) -> set[str]:
    """source_dir altındaki tüm dosyaları relative path olarak döndür."""
    all_files: set[str] = set()
    for root, _, files in os.walk(source_dir):
        for fname in files:
            rel = os.path.relpath(os.path.join(root, fname), source_dir)
            all_files.add(rel)
    return all_files


# ── Ana fonksiyon ───────────────────────────────────────────────────────────────

def run(manifest_path: str, source_dir: str, output_path: str) -> None:
    """Manifestı analiz et, import planını JSON olarak yaz.

    Args:
        manifest_path: CSV manifest dosyasının yolu.
        source_dir:    Fiziksel belge dosyalarının bulunduğu klasör.
        output_path:   Sonucun yazılacağı JSON dosyasının yolu.

    Raises:
        SystemExit: manifest_path bulunamazsa (CLI kullanımı için).
    """
    manifest_file = Path(manifest_path)
    src_dir = Path(source_dir)

    if not manifest_file.exists():
        print(f"[HATA] Manifest bulunamadı: {manifest_file}", file=sys.stderr)
        sys.exit(1)

    # ── CSV parse ───────────────────────────────────────────────────────────────
    rows: list[dict[str, Any]] = []
    with open(manifest_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))

    print(f"Manifest okundu: {len(rows)} satır")

    # ── Disk tarama ─────────────────────────────────────────────────────────────
    disk_files: set[str] = set()
    if src_dir.exists():
        disk_files = _scan_disk(src_dir)
        print(f"Disk tarandı: {len(disk_files)} dosya bulundu")
    else:
        print(
            f"[UYARI] source-dir bulunamadı: {src_dir} — disk eşleştirmesi atlanıyor"
        )

    # ── Satır işleme ─────────────────────────────────────────────────────────────
    document_plan: list[dict[str, Any]] = []
    unmatched_manifest: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    # basename → [satır listesi] (PDF + DOCX pair tespiti)
    basename_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    matched_disk: set[str] = set()

    for i, row in enumerate(rows):
        filename = (
            row.get("dosya_adi") or row.get("filename") or row.get("file_name") or ""
        ).strip()
        content_status_raw = (
            row.get("icerik_durumu")
            or row.get("içerik_durumu")
            or row.get("content_status")
            or ""
        ).strip()
        conflict_val = (
            row.get("celiski_durumu")
            or row.get("çelişki_durumu")
            or row.get("conflict")
            or ""
        ).strip()
        doc_code = (
            row.get("belge_kodu") or row.get("doc_code") or row.get("code") or ""
        ).strip()
        doc_title = (
            row.get("baslik") or row.get("başlık") or row.get("title") or ""
        ).strip()
        doc_type = (
            row.get("belge_turu")
            or row.get("belge_türü")
            or row.get("document_type")
            or "diger"
        ).strip()

        content_status = _normalize_content_status(content_status_raw)

        if conflict_val:
            conflicts.append(
                {
                    "row": i + 2,
                    "filename": filename,
                    "doc_code": doc_code,
                    "conflict": conflict_val,
                }
            )

        file_info: dict[str, Any] | None = None
        if filename and src_dir.exists():
            candidates = [
                p for p in disk_files if Path(p).name == filename or p == filename
            ]
            if candidates:
                rel_path = candidates[0]
                abs_path = src_dir / rel_path
                matched_disk.add(rel_path)
                try:
                    sha256 = _sha256_file(abs_path)
                    file_size = abs_path.stat().st_size
                    file_info = {
                        "rel_path": rel_path,
                        "sha256": sha256,
                        "file_size": file_size,
                    }
                except Exception as e:
                    file_info = {"rel_path": rel_path, "error": str(e)}
            else:
                unmatched_manifest.append(
                    {
                        "row": i + 2,
                        "filename": filename,
                        "doc_code": doc_code,
                    }
                )

        if filename:
            raw_stem = Path(filename).stem
            stem = unicodedata.normalize("NFC", raw_stem).lower()
            basename_groups[stem].append(
                {
                    "row": i + 2,
                    "filename": filename,
                    "doc_code": doc_code,
                    "doc_title": doc_title,
                    "document_type": doc_type,
                    "content_status": content_status,
                    "content_status_raw": content_status_raw,
                    "conflict": conflict_val or None,
                    "file_info": file_info,
                }
            )

    # ── Mantıksal belge grupları ────────────────────────────────────────────────
    pdf_docx_pairs = 0
    single_files = 0
    placeholder_documents = 0

    for stem, group in basename_groups.items():
        ext_set = {Path(r["filename"]).suffix.lower() for r in group}

        pdf_files = [
            r for r in group if Path(r["filename"]).suffix.lower() == ".pdf"
        ]
        docx_files = [
            r for r in group if Path(r["filename"]).suffix.lower() == ".docx"
        ]

        is_clean_pair = len(pdf_files) == 1 and len(docx_files) == 1
        is_ambiguous = (".pdf" in ext_set and ".docx" in ext_set) and not is_clean_pair

        if is_clean_pair:
            pdf_docx_pairs += 1
        else:
            single_files += 1

        if is_ambiguous:
            for r in group:
                unmatched_manifest.append(
                    {
                        "row": r.get("row", "?"),
                        "filename": r["filename"],
                        "doc_code": r["doc_code"],
                        "reason": "ambiguous_pair",
                    }
                )
            continue

        primary = pdf_files[0] if pdf_files else group[0]
        if primary["content_status"] == "placeholder":
            placeholder_documents += 1

        doc_entry: dict[str, Any] = {
            "code": primary["doc_code"] or stem,
            "title": primary["doc_title"] or stem,
            "document_type": primary["document_type"],
            "content_status": primary["content_status"],
            "is_pdf_docx_pair": is_clean_pair,
            "files": [
                {
                    "filename": r["filename"],
                    "file_role": (
                        "published"
                        if Path(r["filename"]).suffix.lower() == ".pdf"
                        else "source"
                    ),
                    "file_info": r["file_info"],
                }
                for r in group
            ],
        }
        document_plan.append(doc_entry)

    # ── Diskte var, manifeste yok ───────────────────────────────────────────────
    unmatched_disk = sorted(disk_files - matched_disk)

    # ── Özet ────────────────────────────────────────────────────────────────────
    logical_documents = len(basename_groups)
    total_revisions = sum(len(g) for g in basename_groups.values())

    summary = {
        "total_manifest_rows": len(rows),
        "logical_documents": logical_documents,
        "revisions": total_revisions,
        "pdf_docx_pairs": pdf_docx_pairs,
        "single_files": single_files,
        "unmatched_manifest": len(unmatched_manifest),
        "unmatched_disk": len(unmatched_disk),
        "placeholder_documents": placeholder_documents,
        "conflict_documents": len(conflicts),
    }

    output: dict[str, Any] = {
        "summary": summary,
        "documents": document_plan,
        "unmatched_manifest": unmatched_manifest,
        "unmatched_disk": unmatched_disk,
        "conflicts": conflicts,
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print("\n=== Import Dry-Run Özeti ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\nÇıktı dosyası: {output_file}")
