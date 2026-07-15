from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path


ROOT = Path(r"D:\FISH\fish-sync")
LIVE_AUDIT = ROOT / "data" / "live_product_media_audit_after_real_fish_images_full_20260531.json"
REAL_UPLOAD_REPORT = ROOT / "data" / "horoshop_image_upload_report_real_fish_images_20260531.json"
META_DB = ROOT / "data" / "meta_store.sqlite"
OUT = ROOT / "data" / "real_photo_backlog_20260531.json"


def load_meta() -> dict[str, dict]:
    conn = sqlite3.connect(META_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                v.kod,
                v.name_raw,
                m.display_name,
                m.brand,
                m.family,
                m.source_category
            FROM variants v
            JOIN models m ON m.parent_key = v.parent_key
            """
        ).fetchall()
        return {
            str(row["kod"]).strip(): {key: row[key] for key in row.keys()}
            for row in rows
            if str(row["kod"] or "").strip()
        }
    finally:
        conn.close()


def main() -> int:
    live = json.loads(LIVE_AUDIT.read_text(encoding="utf-8"))
    upload = json.loads(REAL_UPLOAD_REPORT.read_text(encoding="utf-8"))
    real_uploaded = {
        str(item.get("article") or "").strip()
        for item in upload.get("uploaded_articles", [])
        if str(item.get("article") or "").strip()
    }
    meta = load_meta()

    needs_real_photo: list[dict] = []
    already_real_from_archives: list[dict] = []
    css_fallback_items: list[dict] = []
    for item in live.get("results", []):
        article = str(item.get("article") or "").strip()
        if not article:
            continue
        row = {**item, **meta.get(article, {})}
        if article in real_uploaded:
            already_real_from_archives.append(row)
        else:
            needs_real_photo.append(row)
        if item.get("mode") == "css_fallback":
            css_fallback_items.append(row)

    by_family = Counter((item.get("family") or "unknown") for item in needs_real_photo)
    by_brand = Counter((item.get("brand") or "Без бренду") for item in needs_real_photo)
    payload = {
        "live_total": len(live.get("results", [])),
        "already_real_uploaded_from_archives": len(already_real_from_archives),
        "needs_real_photo": len(needs_real_photo),
        "css_fallback_needs_priority": len(css_fallback_items),
        "by_family_top": by_family.most_common(80),
        "by_brand_top": by_brand.most_common(80),
        "items": needs_real_photo,
        "css_fallback_items": css_fallback_items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "live_total": payload["live_total"],
                "already_real_uploaded_from_archives": payload["already_real_uploaded_from_archives"],
                "needs_real_photo": payload["needs_real_photo"],
                "css_fallback_needs_priority": payload["css_fallback_needs_priority"],
                "report": str(OUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
