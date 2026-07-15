# -*- coding: utf-8 -*-
"""
Виправлення порядку фото для товарів з кількома клієнтськими фото:
головне фото (без коми, напр. "11.jpg") мало опинятись ПІСЛЯ додаткових
ракурсів ("11,1.jpg","11,2.jpg") через рядкове сортування файлів
(prepare_real_client_photo_utility.py, виправлено). Перезаливає ВЕСЬ
галерею для уражених артикулів у правильному порядку (clean_gallery=True
на першому фото, False — на решті, щоб додались після, а не замінили).

  python src/reorder_multi_photo_gallery.py --dry-run
  python src/reorder_multi_photo_gallery.py
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from horoshop_bulk_photo_uploader import load_env, login_and_tokens, upload_one  # noqa: E402

UTILITY_DIR = ROOT / "public" / "real-client-photo-utility"
PROGRESS_FILE = ROOT / "data" / "reorder_gallery_progress.json"
FILE_RE = re.compile(r"^(.+?)@gallery_common(?:@(\d+))?\.jpg$")


def group_by_article() -> dict[str, list[Path]]:
    groups: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    for f in UTILITY_DIR.glob("*@gallery_common*.jpg"):
        m = FILE_RE.match(f.name)
        if not m:
            continue
        article, idx = m.group(1), int(m.group(2) or 1)
        groups[article].append((idx, f))
    return {a: [p for _, p in sorted(files)] for a, files in groups.items() if len(files) > 1}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    groups = group_by_article()
    articles = sorted(groups.keys())
    print(f"артикулів з кількома фото: {len(articles)}", flush=True)
    if args.limit:
        articles = articles[: args.limit]

    if args.dry_run:
        for a in articles[:10]:
            print(f"  {a}: {[p.name for p in groups[a]]}")
        return 0

    done: set[str] = set()
    if PROGRESS_FILE.exists():
        done = set(json.loads(PROGRESS_FILE.read_text(encoding="utf-8")))
        print(f"Resume: {len(done)} вже готово", flush=True)

    env = load_env()
    sess, base, meta = login_and_tokens(env)
    print("Auth OK", flush=True)

    ok = fail = 0
    for i, art in enumerate(articles, 1):
        if art in done:
            continue
        files = groups[art]
        try:
            results = []
            for pos, f in enumerate(files):
                res = upload_one(sess, base, meta, f, clean_gallery=(pos == 0))
                results.append(res["status"])
                if res["status"] != "uploaded":
                    raise RuntimeError(f"{f.name}: {res}")
                time.sleep(0.3)
            done.add(art)
            ok += 1
        except Exception as exc:
            print(f"  [FAIL] {art}: {exc}", flush=True)
            fail += 1
        if i % 10 == 0 or i == len(articles):
            PROGRESS_FILE.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
            print(f"[{i}/{len(articles)}] ok={ok} fail={fail}", flush=True)
        time.sleep(0.5)

    PROGRESS_FILE.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
    print(f"ГОТОВО: ok={ok} fail={fail}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
