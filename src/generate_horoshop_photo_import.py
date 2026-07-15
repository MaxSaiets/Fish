from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from openpyxl import Workbook

from photo_sync import ALLOWED_EXT, META_DB, ROOT, iter_image_sources, load_index, load_overrides, match_file


PUBLIC_DIR = ROOT / "public" / "photo-import"
OUTPUT_XLSX = ROOT / "public" / "horoshop_photo_import.xlsx"
OUTPUT_JSON = ROOT / "data" / "horoshop_photo_import_report.json"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    value = value.replace("’", "").replace("'", "")
    value = "".join(ch if ch.isalnum() else "-" for ch in value)
    value = "-".join(part for part in value.split("-") if part)
    return value or "archive"


def build_import(src: Path, public_base_url: str, clear: bool = False) -> dict:
    conn = sqlite3.connect(META_DB)
    kod_to_parent, model_kods, variant_index = load_index(conn)
    overrides = load_overrides()
    sources, branding_assets, category_assets, archives_scanned, temp_root = iter_image_sources(src)
    archive_to_images: dict[str, list[dict]] = {}
    kod_to_urls: dict[str, list[str]] = {}
    file_matches: list[dict] = []
    unmatched_files: list[dict] = []

    try:
        if clear and PUBLIC_DIR.exists():
            shutil.rmtree(PUBLIC_DIR)
        PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        ws = wb.active
        ws.title = "Фото"
        ws.append(["Артикул", "Галерея"])

        report_archives: list[dict] = []
        total_rows = 0

        for item in sources:
            archive_name = item.get("archive") or item.get("context") or item["path"].stem
            archive_to_images.setdefault(archive_name, []).append(item)

        archive_file_counters: dict[str, int] = {}
        for archive_name in sorted(archive_to_images):
            images = sorted(archive_to_images[archive_name], key=lambda item: item["path"].name)
            archive_slug = slugify(Path(archive_name).stem)
            dest_dir = PUBLIC_DIR / archive_slug
            dest_dir.mkdir(parents=True, exist_ok=True)

            matched_kods: set[str] = set()
            unmatched_in_archive = 0
            for item in images:
                src_path = item["path"]
                kods = match_file(
                    src_path,
                    kod_to_parent,
                    model_kods,
                    variant_index,
                    overrides,
                    context_hint=item.get("context"),
                    container_hint=item.get("container"),
                )
                if not kods:
                    unmatched_in_archive += 1
                    if len(unmatched_files) < 200:
                        unmatched_files.append(
                            {
                                "archive": archive_name,
                                "file": src_path.name,
                                "container": item.get("container"),
                            }
                        )
                    continue

                archive_file_counters[archive_name] = archive_file_counters.get(archive_name, 0) + 1
                idx = archive_file_counters[archive_name]
                ext = src_path.suffix.lower()
                if ext == ".jpeg":
                    ext = ".jpg"
                dest_name = f"{idx}{ext}"
                dest_path = dest_dir / dest_name
                shutil.copy2(src_path, dest_path)
                url = f"{public_base_url.rstrip('/')}/photo-import/{archive_slug}/{dest_name}"
                for kod in kods:
                    kod_to_urls.setdefault(kod, []).append(url)
                    matched_kods.add(kod)
                if len(file_matches) < 500:
                    file_matches.append(
                        {
                            "archive": archive_name,
                            "file": src_path.name,
                            "matched_kods": sorted(kods),
                        }
                    )

            report_archives.append(
                {
                    "archive": archive_name,
                    "archive_slug": archive_slug,
                    "image_count": len(images),
                    "matched_kods": sorted(matched_kods),
                    "matched_file_count": len(images) - unmatched_in_archive,
                    "unmatched_file_count": unmatched_in_archive,
                    "url_count": sum(1 for _ in (PUBLIC_DIR / archive_slug).glob("*")),
                }
            )

        for kod in sorted(kod_to_urls):
            gallery_value = ";".join(kod_to_urls[kod])
            ws.append([kod, gallery_value])
            total_rows += 1

        wb.save(OUTPUT_XLSX)

        report = {
            "source_dir": str(src),
            "public_base_url": public_base_url,
            "archives_scanned": archives_scanned,
            "archives_prepared": len(report_archives),
            "rows_written": total_rows,
            "branding_assets_detected": branding_assets,
            "category_assets_detected": category_assets,
            "unmatched_files_count": len(unmatched_files),
            "unmatched_files_sample": unmatched_files,
            "file_matches_sample": file_matches,
            "archives": report_archives,
            "output_xlsx": str(OUTPUT_XLSX),
            "output_public_dir": str(PUBLIC_DIR),
        }
        OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        if temp_root and temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--public-base-url", required=True)
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()

    report = build_import(args.src, args.public_base_url, clear=args.clear)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
