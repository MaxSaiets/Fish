# -*- coding: utf-8 -*-
"""
Крок 1: знайти статті блогу без фото (preview порожній) і підготувати
для кожної НЕСКІЛЬКА кандидатів фото з Openverse (CC0/PDM) локально,
щоб їх можна було візуально перевірити (Read tool) ПЕРЕД заливкою —
за вимогою власниці "аналізуй фото перед додаванням".

Нічого не заливає в Horoshop і не змінює статті. Лише готує кандидатів.

  python src/prepare_missing_blog_photo_candidates.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import re
import requests
import urllib3
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

from fill_horoshop_content_pages import load_env, parse_form_payload
from replace_blog_images_openverse import active_blog_records, query_for_title, openverse_candidates, retry_get

urllib3.disable_warnings()

OUT_DIR = ROOT / "public" / "blog-missing-photo-candidates"
MANIFEST = ROOT / "data" / "blog_missing_photo_candidates_20260713.json"

CANDIDATES_PER_ARTICLE = 6


def download_candidate(session: requests.Session, item: dict, target: Path) -> dict | None:
    try:
        response = retry_get(session, item["url"], timeout=60, stream=True)
        response.raise_for_status()
        raw = response.content
        if len(raw) < 20_000:
            return None
        source_path = target.with_suffix(".source")
        source_path.write_bytes(raw)
        image = Image.open(source_path).convert("RGB")
        if image.width < 500 or image.height < 350:
            source_path.unlink(missing_ok=True)
            return None
        prepared = ImageOps.fit(image, (1200, 800), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        prepared = ImageEnhance.Color(prepared).enhance(1.04)
        prepared = ImageEnhance.Contrast(prepared).enhance(1.04)
        prepared.save(target, "JPEG", quality=86, optimize=True, progressive=True)
        source_path.unlink(missing_ok=True)
        return {**item, "local_path": str(target)}
    except (requests.RequestException, UnidentifiedImageError, OSError):
        return None


def main() -> int:
    env = load_env()
    base_url = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-blog-photo-audit/1.0"
    session.post(
        f"{base_url}/core-api/admin/security/login",
        json={"login": env["HOROSHOP_LOGIN"], "password": env["HOROSHOP_PASS"]},
        timeout=60,
        verify=False,
    ).raise_for_status()

    records = active_blog_records(session, base_url)
    print(f"активних статей: {len(records)}", flush=True)

    missing: list[dict] = []
    for record in records:
        edit_url = f"{base_url}/adminLegacy/edit.php?id={record['id']}&action=edit&handler=172&checkcode=yamete_kudasai&parent=1001&showPages"
        response = retry_get(session, edit_url, timeout=60, verify=False)
        payload = parse_form_payload(response.text)
        preview = payload.get("names[img][value]", "")
        body = payload.get("names[i18n][3][text]", "")
        has_body_img = bool(re.search(r"<img[^>]+src=", body, flags=re.I))
        if not preview or not has_body_img:
            missing.append({**record, "preview": preview, "has_body_img": has_body_img})

    print(f"статей без фото: {len(missing)}", flush=True)
    for m in missing:
        print(f"  id={m['id']} preview={'OK' if m['preview'] else 'ПОРОЖНЬО'} body_img={m['has_body_img']} :: {m['title']}", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for record in missing:
        query = query_for_title(record["title"])
        candidates = openverse_candidates(query, pages=3)
        prepared = []
        idx = 0
        for cand in candidates:
            if len(prepared) >= CANDIDATES_PER_ARTICLE:
                break
            idx += 1
            target = OUT_DIR / f"art{record['id']}_{len(prepared)+1}.jpg"
            result = download_candidate(session, cand, target)
            if result:
                prepared.append(result)
        manifest.append({
            "id": record["id"],
            "title": record["title"],
            "slug": record["slug"],
            "query": query,
            "candidates": prepared,
        })
        print(f"  готово id={record['id']}: {len(prepared)} кандидатів (query='{query}')", flush=True)

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nManifest: {MANIFEST}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
