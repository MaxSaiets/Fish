# -*- coding: utf-8 -*-
"""
Крок 1b: точковий підбір кандидатів для 7 статей, де загальний
query_for_title() дав або порожній результат, або нерелевантні/брендовані
фото (перевірено візуально). Ручні query per-id замість regex-фолбеку.

  python src/prepare_missing_blog_photo_candidates_v2.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests
import urllib3
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

from replace_blog_images_openverse import openverse_candidates, retry_get

urllib3.disable_warnings()

OUT_DIR = ROOT / "public" / "blog-missing-photo-candidates"
MANIFEST = ROOT / "data" / "blog_missing_photo_candidates_v2_20260713.json"

# id -> (title, [queries in priority order])
TARGETS: dict[str, tuple[str, list[str]]] = {
    "135": ("Балансир взимку: як розловити і не розчаруватись", ["ice fishing hole", "ice fishing rod"]),
    "136": ("Силікон на судака і окуня: розмір, колір і їстівність", ["soft plastic lure", "fishing lure", "fishing jig"]),
    "140": ("Електронний сигналізатор чи свінгер: що обрати на коропову сесію", ["bite alarm", "carp fishing rod", "fishing rod holder"]),
    "141": ("Крісло, столик і порядок на точці: облаштування місця рибалки", ["fishing chair", "carp fishing swim"]),
}

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
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-blog-photo-audit/1.0"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for record_id, (title, queries) in TARGETS.items():
        prepared: list[dict] = []
        used_query = None
        for query in queries:
            if prepared:
                break
            candidates = openverse_candidates(query, pages=3)
            for cand in candidates:
                if len(prepared) >= CANDIDATES_PER_ARTICLE:
                    break
                target = OUT_DIR / f"art{record_id}v2_{len(prepared)+1}.jpg"
                result = download_candidate(session, cand, target)
                if result:
                    prepared.append(result)
                    used_query = query
        manifest.append({"id": record_id, "title": title, "query": used_query, "candidates": prepared})
        print(f"id={record_id}: {len(prepared)} кандидатів (query='{used_query}') :: {title}", flush=True)

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nManifest: {MANIFEST}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
