"""
Застосовує готові превʼю як ФОТО КАТЕГОРІЇ через нативний multipart-upload у save.php
(поле extra_parent[image][file]). Так сітка категорій на головній показує курований
знімок, а не випадкове перше фото товару.

Слаг категорії читається прямо з форми (names[name][slug]) → мапиться на превʼю
через data/horoshop_category_visuals_report.json (category_map: /slug/ -> key).

  python src/apply_category_previews.py --top-only     # лише кореневі (сітка головної, parent=97)
  python src/apply_category_previews.py                # усі категорії
  python src/apply_category_previews.py --force        # перепризначити навіть якщо фото вже є

Resumable: data/category_preview_apply_progress.json. Throttle 2.0с.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import auth, get_base_url, load_env  # noqa: E402
from fill_category_seo import fetch_form, walk_categories  # noqa: E402

REPORT = ROOT / "data" / "horoshop_category_visuals_report.json"
PROGRESS = ROOT / "data" / "category_preview_apply_progress.json"
ASSET_DIRS = [
    ROOT / "public" / "site-category-assets-v2",
    ROOT / "public" / "site-category-assets-real-no-text",
    ROOT / "public" / "site-category-assets",
]


def preview_file(key: str) -> Path | None:
    if not key:
        return None
    for d in ASSET_DIRS:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            p = d / f"{key}{ext}"
            if p.exists():
                return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--throttle", type=float, default=2.0)
    args = ap.parse_args()

    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    cmap = {k.strip("/"): v for k, v in (rep.get("category_map") or {}).items()}
    done = set(json.loads(PROGRESS.read_text(encoding="utf-8"))) if PROGRESS.exists() else set()

    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-cat-preview/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    cats = walk_categories(s, base)
    if args.top_only:
        cats = [c for c in cats if str(c.get("parent")) == "97"]
    cats.sort(key=lambda c: str(c["id"]))
    print(f"категорій до обходу: {len(cats)} (top_only={args.top_only})")

    ok = skipped_noprev = skipped_hasimg = 0
    fail = []
    processed = 0
    for c in cats:
        cid, parent = str(c["id"]), str(c["parent"])
        marker = cid
        if marker in done and not args.force:
            continue
        try:
            payload = fetch_form(s, base, cid, parent)
            slug = str(payload.get("names[name][slug]", "")).strip().strip("/")
            key = cmap.get(slug)
            img = preview_file(key)
            if not img:
                skipped_noprev += 1
                done.add(marker)
                continue
            if not args.force and str(payload.get("extra_parent[image][value]", "")).strip():
                skipped_hasimg += 1
                done.add(marker)
                continue
            payload.update({"checkcode": "yamete_kudasai", "id": cid, "handler": "4",
                            "handlertable": "pages", "back": "index.php"})
            payload.pop("extra_parent[image][file]", None)
            with img.open("rb") as fh:
                r = s.post(f"{base}/adminLegacy/save.php", data=payload,
                           files={"extra_parent[image][file]": (img.name, fh, "image/jpeg")},
                           headers={"X-Requested-With": "XMLHttpRequest"}, timeout=120, verify=False)
            r.raise_for_status()
            ok += 1
            done.add(marker)
            print(f"  ✓ {slug} (id{cid}) ← {img.name}", flush=True)
        except Exception as exc:
            fail.append({"id": cid, "error": str(exc)[:120]})
        processed += 1
        time.sleep(args.throttle)
        if args.limit and processed >= args.limit:
            break

    PROGRESS.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
    print(f"ГОТОВО: застосовано={ok} | вже мали фото={skipped_hasimg} | без превʼю={skipped_noprev} | fail={len(fail)}")
    if fail:
        print("fails:", fail[:5])
    return 0


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.exit(main())
