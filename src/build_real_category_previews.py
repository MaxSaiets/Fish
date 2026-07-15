from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests
import urllib3
from PIL import Image, ImageEnhance, ImageOps

from build_all_unique_category_previews import (
    choose_source,
    fetch_slug_titles,
    load_env,
    load_inventory,
    title_from_slug,
)


urllib3.disable_warnings()

ROOT = Path(r"D:\FISH\fish-sync")
REPORT = ROOT / "data" / "horoshop_category_visuals_report.json"
OUT_DIR = ROOT / "public" / "site-category-assets-real-no-text"


def render_real_preview(source: Path, target: Path, slug: str) -> None:
    """Create a real-photo category preview with no text, logo, badge, or overlay."""
    digest = sum(slug.encode("utf-8"))
    cx = 0.42 + ((digest % 17) / 100)
    cy = 0.42 + (((digest // 17) % 17) / 100)
    image = Image.open(source).convert("RGB")
    image = ImageOps.fit(image, (1200, 840), method=Image.Resampling.LANCZOS, centering=(cx, cy))
    image = ImageOps.autocontrast(image, cutoff=0.4)
    image = ImageEnhance.Color(image).enhance(1.05)
    image = ImageEnhance.Contrast(image).enhance(1.04)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "JPEG", quality=86, optimize=True, progressive=True)


def admin_login(session: requests.Session, base_url: str, login: str, password: str) -> None:
    response = session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": login, "password": password},
        timeout=90,
        verify=False,
    )
    response.raise_for_status()
    data = response.json()
    if int(data.get("status") or 0) != 200:
        raise RuntimeError(f"Horoshop auth failed: {data}")


def upload_asset(session: requests.Session, base_url: str, path: Path) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            with path.open("rb") as fh:
                response = session.post(
                    f"{base_url}/core-api/admin/app-json/upload-image",
                    files={"file": (path.name, fh)},
                    timeout=180,
                    verify=False,
                )
            response.raise_for_status()
            data = response.json()
            payload = data.get("payload") if isinstance(data, dict) else None
            if not payload:
                raise RuntimeError(f"Unexpected upload response for {path.name}: {data}")
            item = payload[0] if isinstance(payload, list) else payload
            uri = str(item.get("uri") or item.get("url") or "").strip()
            if uri.startswith("/content/"):
                uri = uri.replace("/content/", "/", 1)
            if uri.startswith("/"):
                uri = f"{base_url}{uri}"
            return {"local_path": str(path), "uri": uri, "response": item}
        except Exception as exc:
            last_error = exc
            time.sleep(2 * attempt)
    raise RuntimeError(f"Upload failed after retries for {path}: {last_error}")


def key_for_slug(slug: str) -> str:
    return "cat_real_" + re.sub(r"[^a-z0-9]+", "_", slug.strip("/")).strip("_")


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    slugs = sorted((report.get("category_map") or {}).keys())
    titles = fetch_slug_titles(base_url)
    inventory = load_inventory()
    used_hashes: set[str] = set()

    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-real-category-previews/1.0"
    admin_login(session, base_url, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    uploads = report.setdefault("uploads", {})
    category_map = dict(report.get("category_map") or {})
    prepared: dict[str, dict[str, str]] = {}
    source_counts: dict[str, int] = {}

    for slug in slugs:
        title = title_from_slug(slug, titles)
        key = key_for_slug(slug)
        source_type, source_path, source_note = choose_source(slug, title, inventory, used_hashes, report)
        if not source_path.exists():
            continue
        target = OUT_DIR / f"{key}.jpg"
        render_real_preview(source_path, target, slug)
        if not (isinstance(uploads.get(key), dict) and str(uploads[key].get("uri", "")).startswith("http")):
            uploads[key] = upload_asset(session, base_url, target)
        category_map[slug] = key
        prepared[key] = {
            "slug": slug,
            "title": title,
            "source_type": source_type,
            "source": str(source_path),
            "source_note": source_note,
            "local_path": str(target),
            "uri": uploads[key]["uri"],
        }
        source_counts[source_type] = source_counts.get(source_type, 0) + 1

    report["category_map"] = category_map
    report["real_no_text_previews"] = {
        "count": len(prepared),
        "expected": len(slugs),
        "source_counts": source_counts,
        "prepared": prepared,
        "not_prepared": sorted(set(slugs) - {item["slug"] for item in prepared.values()}),
        "policy": "Real-world category photos only: client archive matches where available, otherwise documented open-stock assets. No text, logo, badge, watermark removal, or generated mock cards.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["real_no_text_previews"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
