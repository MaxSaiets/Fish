# -*- coding: utf-8 -*-
"""
Відтворення 9 товарів-сертифікатів (1000-5000 грн), видалених раніше в цій
сесії. БЕЗ фото (за прямою вимогою власниці — тільки реальні фото або
взагалі без фото, ніяких згенерованих заглушок). Категорія: "Подарункові
сертифікати" (parent=1323).

  python src/recreate_certificates.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from apply_horoshop_menu_fixes import auth, get_base_url, load_env  # noqa: E402
from create_missing_products_by_form import create_product  # noqa: E402
import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

CATEGORY_ID = "1323"

CERTIFICATES = [
    {"article": "3509", "title": "Сертифікат 1000 грн.", "price": 1000},
    {"article": "3510", "title": "Сертифікат 1500 грн.", "price": 1500},
    {"article": "3511", "title": "Сертифікат 2000 грн.", "price": 2000},
    {"article": "3685", "title": "Сертифікат 2500 грн.", "price": 2500},
    {"article": "3686", "title": "Сертифікат 3000 грн.", "price": 3000},
    {"article": "3687", "title": "Сертифікат 3500 грн.", "price": 3500},
    {"article": "3688", "title": "Сертифікат 4000 грн.", "price": 4000},
    {"article": "3689", "title": "Сертифікат 4500 грн.", "price": 4500},
    {"article": "3690", "title": "Сертифікат 5000 грн.", "price": 5000},
]

DESCRIPTION = (
    "Подарунковий сертифікат — безпрограшний подарунок для рибалки: "
    "власник сам обере саме те, що йому потрібно, з понад семи тисяч позицій "
    "каталогу. Сертифікат діє на весь асортимент — снасті, прикормки, "
    "спорядження, одяг."
)


def main() -> int:
    env = load_env()
    base_url = get_base_url(env)
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-recreate-certs/1.0"
    auth(session, base_url, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])
    print("Auth OK", flush=True)

    for cert in CERTIFICATES:
        cp = {
            "title": cert["title"],
            "article": cert["article"],
            "price": cert["price"],
            "presence": "В наявності",
            "description": DESCRIPTION,
        }
        try:
            create_product(session, base_url, cp, CATEGORY_ID)
            print(f"  OK  {cert['article']}  {cert['title']}", flush=True)
        except Exception as exc:
            print(f"  FAIL {cert['article']}  {cert['title']}: {exc}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
