"""
generate_mass_photo_import_xlsx.py

Generates a Horoshop-compatible photo import Excel from the processed
images in public/mass-photo-utility/.

The Excel has two columns: Артикул, Галерея (public URL of the image).

Usage:
    # First start serve.py and get ngrok URL
    python src/serve.py &
    # Then:
    python src/generate_mass_photo_import_xlsx.py --base-url https://xxxx.ngrok-free.app
    # Then import the xlsx in Horoshop admin → Імпорт

Output: public/horoshop_mass_photo_import.xlsx
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(r"D:\FISH\fish-sync")
UTILITY_DIR = ROOT / "public" / "mass-photo-utility"
CHECKPOINT_PATH = ROOT / "data" / "mass_photo_checkpoint.json"
OUTPUT_XLSX = ROOT / "public" / "horoshop_mass_photo_import.xlsx"
OUTPUT_REPORT = ROOT / "data" / "mass_photo_import_xlsx_report.json"

# The serve.py serves files from public/ at /
# So mass-photo-utility/3к08638@gallery_common.jpg → {base}/mass-photo-utility/3к08638@gallery_common.jpg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True,
                   help="Public base URL where serve.py is accessible (e.g. https://xxxx.ngrok-free.app)")
    p.add_argument("--limit", type=int, default=0, help="Max articles to include (0=all)")
    p.add_argument("--skip-done", action="store_true",
                   help="Skip articles already in the upload checkpoint done list")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")

    # Load checkpoint to optionally skip already-uploaded
    done_articles: set = set()
    if args.skip_done and CHECKPOINT_PATH.exists():
        cp = json.loads(CHECKPOINT_PATH.read_text("utf-8"))
        done_articles = set(cp.get("done", {}).keys())
        print(f"Checkpoint: {len(done_articles)} already done, will skip")

    # Scan utility dir for processed images
    image_files = sorted(UTILITY_DIR.glob("*@gallery_common.jpg"))
    print(f"Found {len(image_files)} processed images in utility dir")

    wb = Workbook()
    ws = wb.active
    ws.title = "Фото"
    ws.append(["Артикул", "Галерея"])

    rows_added = 0
    skipped = 0
    included: list[dict] = []

    for img_path in image_files:
        # Extract article from filename: {article}@gallery_common.jpg
        article = img_path.stem.split("@")[0].strip()

        if args.skip_done and article in done_articles:
            skipped += 1
            continue

        # Build public URL
        rel = img_path.relative_to(ROOT / "public")
        photo_url = f"{base_url}/{rel.as_posix()}"

        ws.append([article, photo_url])
        rows_added += 1
        included.append({"article": article, "url": photo_url})

        if args.limit and rows_added >= args.limit:
            break

    wb.save(OUTPUT_XLSX)

    report = {
        "base_url": base_url,
        "total_images_found": len(image_files),
        "rows_in_xlsx": rows_added,
        "skipped_already_done": skipped,
        "output_xlsx": str(OUTPUT_XLSX),
        "sample": included[:10],
    }
    OUTPUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")

    print(f"\nGenerated: {OUTPUT_XLSX}")
    print(f"Rows: {rows_added} articles")
    print(f"Skipped (done): {skipped}")
    print(f"\nNext steps:")
    print(f"  1. Make sure serve.py is running:")
    print(f"     python src/serve.py")
    print(f"  2. Start ngrok if needed:")
    print(f"     ngrok http 8080")
    print(f"  3. Import {OUTPUT_XLSX.name} in Horoshop admin:")
    print(f"     Admin → Товари → Імпорт → вибрати файл → Тільки фото")


if __name__ == "__main__":
    main()
