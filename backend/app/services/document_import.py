"""DMS Dry-Run Import Service — Belge Manifesti Analiz Motoru v2.

Sprint 14C: Manifest column alias desteği + disk artifact auto-pairing.

Gerçek DB bağlantısı KURMAZ. Salt okunur analiz yapar.

Dışarıdan çağrı:
    from app.services.document_import import run

    run(manifest_path, source_dir, output_path)
    run(manifest_path, source_dir, output_path, content_status_filter="R01-tamamlanmış")

CLI wrapper:
    scripts/import_documents.py bu modülü kullanır.

Desteklenen manifest formatları:
    v1 (eski): dosya_adi, belge_kodu, baslik, belge_turu, icerik_durumu
    v2 (yeni): kaynak_dosya, belge_kodu_mevcut, belge_adi, dokuman_tipi, içerik_durumu

Mantık:
  1. CSV'yi parse et (UTF-8 BOM destekli)
  2. Her satır için canonical alanları _first_value() ile çöz
  3. Optional content_status_filter uygula (conflict tespitinden önce)
  4. Conflict satırlarını ayır (çelişki_durumu dolu)
  5. Disk indeksini normalized stem ile oluştur (bir kez, rglob)
  6. Aynı stem'e sahip PDF+DOCX'leri tek mantıksal belge say
  7. Manifest'te yalnızca PDF varsa disk'te tam 1 DOCX sibling → auto-pair
  8. Aynı document_code → farklı stem → duplicate_codes bucket
  9. Diskte var ama manifeste girmeyen → unmatched_disk
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


# ── İçerik durumu normalizasyon tablosu ─────────────────────────────────────

_CONTENT_STATUS_MAP: dict[str, str] = {
    "tamamlandi": "tamamlandi",
    "tamamlandı": "tamamlandi",
    "r01-tamamlanmış": "tamamlandi",
    "r01-tamamlanmis": "tamamlandi",
    "taslak": "taslak",
    "taslak-içerik-eksik": "eksik",
    "taslak-icerik-eksik": "eksik",
    "eksik": "eksik",
    "placeholder": "placeholder",
    "kaynak-pdf": "kaynak",
    "bilinmiyor": "bilinmiyor",
    "": "bilinmiyor",
}


def _normalize_content_status(raw: str) -> str:
    key = raw.strip().lower()
    return _CONTENT_STATUS_MAP.get(key, "bilinmiyor")


# ── Canonical field resolver ─────────────────────────────────────────────────

def _first_value(row: dict[str, str], *keys: str) -> str:
    """Satırdaki ilk dolu değeri döndür; tümü boşsa '' döner."""
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _resolve_fields(row: dict[str, str]) -> dict[str, str]:
    """Manifest satırından canonical alanları çöz.

    Yeni (kaynak_dosya bazlı) ve eski (dosya_adi bazlı) manifest formatlarını
    birlikte destekler.  Kod fallback sırası:
        önerilen_MYK_kodu → belge_kodu_mevcut → belge_kodu → stem'den ilk token.
    """
    filename = _first_value(row, "kaynak_dosya", "dosya_adi", "filename", "file_name")

    document_code = _first_value(
        row,
        "önerilen_MYK_kodu",
        "belge_kodu_mevcut",
        "belge_kodu",
        "doc_code",
        "code",
    )
    # Kod hâlâ boşsa filename stem'inden ilk token'ı al
    if not document_code and filename:
        document_code = Path(filename).stem.split("_")[0]

    title = _first_value(row, "belge_adi", "baslik", "başlık", "title")

    document_type = _first_value(
        row, "dokuman_tipi", "belge_turu", "belge_türü", "document_type"
    )
    if not document_type:
        document_type = "diger"

    content_status_raw = _first_value(
        row, "içerik_durumu", "icerik_durumu", "content_status"
    )
    conflict_val = _first_value(row, "çelişki_durumu", "celiski_durumu", "conflict")

    return {
        "filename": filename,
        "document_code": document_code,
        "title": title,
        "document_type": document_type,
        "content_status_raw": content_status_raw,
        "conflict_val": conflict_val,
    }


# ── Stem normalizasyon ────────────────────────────────────────────────────────

def _normalize_stem(raw: str) -> str:
    """Unicode NFC + casefold (Türkçe dahil) ile string normalize et."""
    return unicodedata.normalize("NFC", raw).casefold()


# ── Dosya SHA-256 ─────────────────────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Disk indeksi ─────────────────────────────────────────────────────────────

def _build_disk_index(
    source_dir: Path,
) -> tuple[dict[str, list[Path]], dict[str, list[Path]]]:
    """source_dir altındaki dosyaları normalized name ve stem ile indeksle.

    Her rglob çağrısında arama yapmak yerine tek seferlik indeks oluşturur.

    Returns:
        disk_by_name:  normalized_basename → [Path, ...]
        disk_by_stem:  normalized_stem     → [Path, ...]
    """
    disk_by_name: dict[str, list[Path]] = defaultdict(list)
    disk_by_stem: dict[str, list[Path]] = defaultdict(list)
    for p in source_dir.rglob("*"):
        if p.is_file():
            disk_by_name[_normalize_stem(p.name)].append(p)
            disk_by_stem[_normalize_stem(p.stem)].append(p)
    return dict(disk_by_name), dict(disk_by_stem)


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def run(
    manifest_path: str,
    source_dir: str,
    output_path: str,
    *,
    content_status_filter: str | None = None,
) -> None:
    """Manifestı analiz et, import planını JSON olarak yaz.

    Args:
        manifest_path:         CSV manifest dosyasının yolu.
        source_dir:            Fiziksel belge dosyalarının bulunduğu klasör.
        output_path:           Sonucun yazılacağı JSON dosyasının yolu.
        content_status_filter: Sadece bu raw içerik_durumu değerini işle
                               (ör. "R01-tamamlanmış"). None = tümünü işle.
                               Filtre, conflict tespitinden önce uygulanır.

    Raises:
        SystemExit: manifest_path bulunamazsa (CLI kullanımı için).
    """
    manifest_file = Path(manifest_path)
    src_dir = Path(source_dir)

    if not manifest_file.exists():
        print(f"[HATA] Manifest bulunamadı: {manifest_file}", file=sys.stderr)
        sys.exit(1)

    # ── CSV parse ──────────────────────────────────────────────────────────────
    rows: list[dict[str, Any]] = []
    with open(manifest_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))

    print(f"Manifest okundu: {len(rows)} satır")
    if content_status_filter:
        print(f"Filtre: içerik_durumu == {content_status_filter!r}")

    # ── Disk indeksi ──────────────────────────────────────────────────────────
    disk_by_name: dict[str, list[Path]] = {}
    disk_by_stem: dict[str, list[Path]] = {}
    if src_dir.exists():
        disk_by_name, disk_by_stem = _build_disk_index(src_dir)
        total_disk = sum(len(v) for v in disk_by_name.values())
        print(f"Disk tarandı: {total_disk} dosya bulundu")
    else:
        print(
            f"[UYARI] source-dir bulunamadı: {src_dir} — disk eşleştirmesi atlanıyor"
        )

    # ── Satır işleme ──────────────────────────────────────────────────────────
    unmatched_manifest: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    ambiguous_pairs: list[dict[str, Any]] = []

    # normalized_stem → [ { row_info } ]
    basename_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    # Eşleştirilen disk dosyalarının absolute path string seti
    matched_disk: set[str] = set()

    for i, row in enumerate(rows):
        fields = _resolve_fields(row)
        filename = fields["filename"]
        document_code = fields["document_code"]
        title = fields["title"]
        document_type = fields["document_type"]
        content_status_raw = fields["content_status_raw"]
        conflict_val = fields["conflict_val"]

        # Content status filter — conflict tespitinden önce uygula
        if (
            content_status_filter is not None
            and content_status_raw.strip() != content_status_filter
        ):
            continue

        # Conflict kayıtları → conflicts listesi (plan'a dahil edilmez)
        if conflict_val:
            conflicts.append(
                {
                    "row": i + 2,
                    "filename": filename,
                    "doc_code": document_code,
                    "conflict": conflict_val,
                }
            )
            continue

        if not filename:
            continue

        content_status = _normalize_content_status(content_status_raw)

        # ── Disk eşleştirme ───────────────────────────────────────────────────
        norm_name = _normalize_stem(filename)
        file_info: dict[str, Any] | None = None
        candidates = disk_by_name.get(norm_name, [])
        if candidates:
            abs_path = candidates[0]
            matched_disk.add(str(abs_path))
            try:
                sha256 = _sha256_file(abs_path)
                file_size = abs_path.stat().st_size
                rel: str
                try:
                    rel = str(abs_path.relative_to(src_dir))
                except ValueError:
                    rel = abs_path.name
                file_info = {
                    "rel_path": rel,
                    "sha256": sha256,
                    "file_size": file_size,
                }
            except Exception as e:
                file_info = {"rel_path": filename, "error": str(e)}
        elif src_dir.exists():
            unmatched_manifest.append(
                {
                    "row": i + 2,
                    "filename": filename,
                    "doc_code": document_code,
                }
            )

        raw_stem = Path(filename).stem
        norm_stem_val = _normalize_stem(raw_stem)

        basename_groups[norm_stem_val].append(
            {
                "row": i + 2,
                "filename": filename,
                "original_stem": raw_stem,
                "doc_code": document_code,
                "doc_title": title,
                "document_type": document_type,
                "content_status": content_status,
                "content_status_raw": content_status_raw,
                "conflict": None,
                "file_info": file_info,
                "source": "manifest",
            }
        )

    # ── DOCX disk auto-pairing ────────────────────────────────────────────────
    # Manifest'te yalnızca PDF olan gruplar için disk'te aynı normalized stem'e
    # sahip tam 1 DOCX varsa otomatik pair oluştur.
    for norm_stem_val, group in basename_groups.items():
        manifest_exts = {
            Path(r["filename"]).suffix.lower()
            for r in group
            if r.get("source") == "manifest"
        }
        has_manifest_pdf = ".pdf" in manifest_exts
        has_manifest_docx = ".docx" in manifest_exts

        if not (has_manifest_pdf and not has_manifest_docx):
            continue  # Zaten DOCX var ya da PDF yok — auto-pairing gerekmez

        docx_siblings = [
            p
            for p in disk_by_stem.get(norm_stem_val, [])
            if p.suffix.lower() == ".docx"
        ]

        if len(docx_siblings) == 1:
            docx_path = docx_siblings[0]
            matched_disk.add(str(docx_path))
            try:
                sha256 = _sha256_file(docx_path)
                file_size = docx_path.stat().st_size
                try:
                    rel = str(docx_path.relative_to(src_dir))
                except ValueError:
                    rel = docx_path.name
                docx_file_info: dict[str, Any] = {
                    "rel_path": rel,
                    "sha256": sha256,
                    "file_size": file_size,
                    "auto_paired": True,
                }
            except Exception as e:
                docx_file_info = {
                    "rel_path": docx_path.name,
                    "error": str(e),
                    "auto_paired": True,
                }

            primary = next(
                r for r in group if Path(r["filename"]).suffix.lower() == ".pdf"
            )
            group.append(
                {
                    "row": "disk-auto",
                    "filename": docx_path.name,
                    "original_stem": docx_path.stem,
                    "doc_code": primary["doc_code"],
                    "doc_title": primary["doc_title"],
                    "document_type": primary["document_type"],
                    "content_status": primary["content_status"],
                    "content_status_raw": primary["content_status_raw"],
                    "conflict": None,
                    "file_info": docx_file_info,
                    "source": "disk_auto_paired",
                }
            )

        elif len(docx_siblings) > 1:
            pdf_row = next(
                (r for r in group if Path(r["filename"]).suffix.lower() == ".pdf"),
                group[0],
            )
            ambiguous_pairs.append(
                {
                    "stem": norm_stem_val,
                    "manifest_pdf": pdf_row["filename"],
                    "doc_code": pdf_row["doc_code"],
                    "docx_candidates": [str(p) for p in docx_siblings],
                    "reason": "multiple_docx_candidates",
                }
            )

    # ── Duplicate code tespiti ────────────────────────────────────────────────
    # Aynı document_code → farklı normalized stem → otomatik merge edilmez.
    code_to_stems: dict[str, set[str]] = defaultdict(set)
    for norm_stem_val, group in basename_groups.items():
        for r in group:
            if r.get("source") == "disk_auto_paired":
                continue
            code = r["doc_code"]
            if code:
                code_to_stems[code].add(norm_stem_val)

    duplicate_code_set: set[str] = {
        code for code, stems in code_to_stems.items() if len(stems) > 1
    }

    duplicate_codes_report: list[dict[str, Any]] = []
    for code in sorted(duplicate_code_set):
        stems_list = sorted(code_to_stems[code])
        filenames_in_dup: list[str] = []
        for s in stems_list:
            for r in basename_groups.get(s, []):
                if r.get("source") != "disk_auto_paired":
                    filenames_in_dup.append(r["filename"])
        duplicate_codes_report.append(
            {
                "doc_code": code,
                "stems": stems_list,
                "filenames": filenames_in_dup,
            }
        )

    # ── Mantıksal belge planı ─────────────────────────────────────────────────
    document_plan: list[dict[str, Any]] = []
    pdf_docx_pairs = 0
    single_files = 0
    placeholder_documents = 0

    for norm_stem_val, group in basename_groups.items():
        doc_code = group[0]["doc_code"] if group else ""

        # Duplicate code → documents'a dahil etme
        if doc_code in duplicate_code_set:
            continue

        ext_set_all = {Path(r["filename"]).suffix.lower() for r in group}

        pdf_files_all = [
            r for r in group if Path(r["filename"]).suffix.lower() == ".pdf"
        ]
        docx_files_all = [
            r for r in group if Path(r["filename"]).suffix.lower() == ".docx"
        ]

        is_clean_pair = len(pdf_files_all) == 1 and len(docx_files_all) == 1
        is_ambiguous = (
            ".pdf" in ext_set_all and ".docx" in ext_set_all and not is_clean_pair
        )

        if is_ambiguous:
            for r in [x for x in group if x.get("source") == "manifest"]:
                unmatched_manifest.append(
                    {
                        "row": r.get("row", "?"),
                        "filename": r["filename"],
                        "doc_code": r["doc_code"],
                        "reason": "ambiguous_pair",
                    }
                )
            continue

        if is_clean_pair:
            pdf_docx_pairs += 1
        else:
            single_files += 1

        primary = pdf_files_all[0] if pdf_files_all else group[0]
        if primary["content_status"] in ("eksik", "placeholder"):
            placeholder_documents += 1

        files_list: list[dict[str, Any]] = [
            {
                "filename": r["filename"],
                "file_role": (
                    "published"
                    if Path(r["filename"]).suffix.lower() == ".pdf"
                    else "source"
                ),
                "file_info": r["file_info"],
                "source": r.get("source", "manifest"),
            }
            for r in group
        ]

        document_plan.append(
            {
                "code": primary["doc_code"] or norm_stem_val,
                "title": primary["doc_title"] or norm_stem_val,
                "document_type": primary["document_type"],
                "content_status": primary["content_status"],
                "is_pdf_docx_pair": is_clean_pair,
                "files": files_list,
            }
        )

    # ── Diskte var, manifeste/filtreye göre eşleşmeyen ───────────────────────
    all_disk_paths: set[str] = set()
    for paths in disk_by_name.values():
        for p in paths:
            all_disk_paths.add(str(p))
    unmatched_disk = sorted(all_disk_paths - matched_disk)

    # ── Özet ──────────────────────────────────────────────────────────────────
    duplicate_code_doc_count = sum(
        len(r["filenames"]) for r in duplicate_codes_report
    )

    summary: dict[str, Any] = {
        "total_manifest_rows": len(rows),
        "logical_documents": len(document_plan),
        "revisions": len(document_plan),
        "pdf_docx_pairs": pdf_docx_pairs,
        "single_files": single_files,
        "unmatched_manifest": len(unmatched_manifest),
        "unmatched_disk": len(unmatched_disk),
        "placeholder_documents": placeholder_documents,
        "conflict_documents": len(conflicts),
        "duplicate_code_documents": duplicate_code_doc_count,
        "ambiguous_pairs": len(ambiguous_pairs),
    }

    output: dict[str, Any] = {
        "summary": summary,
        "documents": document_plan,
        "unmatched_manifest": unmatched_manifest,
        "unmatched_disk": unmatched_disk,
        "conflicts": conflicts,
        "duplicate_codes": duplicate_codes_report,
        "ambiguous_pairs": ambiguous_pairs,
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print("\n=== Import Dry-Run Özeti ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\nÇıktı dosyası: {output_file}")
