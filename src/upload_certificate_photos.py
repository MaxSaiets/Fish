# -*- coding: utf-8 -*-
"""
Заливає згенеровані брендовані фото для 9 сертифікатів (артикули
3509-3511, 3685-3690) через перевірений check->AWS->assign канал.

  python src/upload_certificate_photos.py
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from horoshop_bulk_photo_uploader import load_env, login_and_tokens, upload_one  # noqa: E402

ARTICLES = ["3509", "3510", "3511", "3685", "3686", "3687", "3688", "3689", "3690"]
SRC_DIR = ROOT / "public" / "certificate-images"


def main() -> int:
    env = load_env()
    sess, base, meta = login_and_tokens(env)
    print("Auth OK", flush=True)

    ok = fail = 0
    for art in ARTICLES:
        path = SRC_DIR / f"{art}@gallery_common.jpg"
        res = upload_one(sess, base, meta, path, clean_gallery=True)
        status = res.get("status")
        if status == "uploaded":
            ok += 1
        else:
            fail += 1
        print(f"  {art}: {res}", flush=True)
        time.sleep(0.3)

    print(f"\nГотово: ok={ok} fail={fail}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
