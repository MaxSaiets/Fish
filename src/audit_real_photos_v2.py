# -*- coding: utf-8 -*-
"""
Свіжий аудит реальних vs фейкових фото по всьому каталогу (2026-07-13),
джерело — sitemap image:loc (актуальний, без застарілих локальних кешів).
Range-запит bytes=0-0 -> Content-Range дає точний розмір без завантаження.
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

THRESHOLD = 180_000
U = {"User-Agent": "Mozilla/5.0 Chrome/126", "Range": "bytes=0-0"}


def main() -> int:
    records = json.load(open(ROOT / "data" / "sitemap_product_images.json", encoding="utf-8"))
    print(f"товарів з фото у sitemap: {len(records)}", flush=True)

    s = requests.Session()
    s.headers.update(U)

    out = []
    real = fake = err = 0
    for i, rec in enumerate(records, 1):
        try:
            r = s.get(rec["image"], timeout=15, verify=False)
            cr = r.headers.get("Content-Range", "")
            total = int(cr.split("/")[-1]) if "/" in cr else len(r.content)
        except Exception:
            total = -1
        is_real = total >= THRESHOLD
        if total < 0:
            err += 1
        elif is_real:
            real += 1
        else:
            fake += 1
        out.append({"url": rec["url"], "image": rec["image"], "size": total, "real": is_real})
        if i % 500 == 0:
            print(f"[{i}/{len(records)}] реальних={real} заглушок={fake} помилок={err}", flush=True)
            json.dump(out, open(ROOT / "data" / "real_photo_audit_v2_partial.json", "w", encoding="utf-8"), ensure_ascii=False)

    json.dump(out, open(ROOT / "data" / "real_photo_audit_v2_full.json", "w", encoding="utf-8"), ensure_ascii=False)
    total_catalog = 8354
    print(f"\nГОТОВО: реальних={real}, заглушок={fake}, помилок={err}, "
          f"без фото-поля={total_catalog - len(records)}, всього каталог={total_catalog}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
