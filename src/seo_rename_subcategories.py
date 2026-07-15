# -*- coding: utf-8 -*-
"""
SEO-перейменування підкатегорій: прикметникові назви → повні пошукові фрази
("Фідерні" → "Фідерні вудилища"), бо люди гуглять саме повну фразу.

ВАЖЛИВО: slug (URL) НЕ чіпаємо — жодного updateUriAutomatically/forceUpdate,
щоб не втратити вже проіндексовані адреси. Міняються тільки:
title, h1, seo_title, seo_description (+ локальний хвіст "самовивіз у Хмельницькому").

Запуск:
  python src/seo_rename_subcategories.py --dry-run   # показати план
  python src/seo_rename_subcategories.py             # застосувати
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import (  # noqa: E402
    auth, fetch_full_form_payload, get_base_url, load_env, post_form,
)

THROTTLE = 1.5

# id, parent_id, нова назва (повна пошукова фраза)
RENAMES = [
    ("1082", "1235", "Спінінгові вудилища"),
    ("1085", "1235", "Фідерні вудилища"),
    ("1086", "1235", "Коропові вудилища"),
    ("1253", "1235", "Махові вудилища"),
    ("1252", "1235", "Болонські вудилища"),
    ("1087", "1236", "Спінінгові котушки"),
    ("1088", "1236", "Фідерні котушки"),
    ("1089", "1236", "Коропові котушки"),
    ("1294", "1240", "Електронні сигналізатори клювання"),
    ("1195", "1240", "Механічні сигналізатори клювання"),
    ("1270", "1108", "Зернові прикормки"),
]

# сховати з меню та індексу (архівна категорія)
HIDE = [("1313", "1236")]  # Котушки архів


def build_seo(title: str) -> tuple[str, str]:
    seo_title = f"{title} — купити в Україні, ціни від виробника | Все для рибалки"
    seo_description = (
        f"{title} в наявності в інтернет-магазині «Все для рибалки» ✓ Перевірені бренди "
        f"✓ Доставка Новою поштою по Україні, самовивіз у Хмельницькому ✓ Обмін 14 днів."
    )
    return seo_title, seo_description


def save_rename(session, base_url: str, sec_id: str, parent_id: str, title: str) -> None:
    payload = fetch_full_form_payload(session, base_url, sec_id, parent_id)
    seo_t, seo_d = build_seo(title)
    payload.update({
        "checkcode": "yamete_kudasai",
        "id": sec_id,
        "handler": "4",
        "handlertable": "pages",
        "back": "index.php",
        "names[parent]": parent_id,
        "names[i18n][3][title]": title,
        "names[i18n][3][h1_title]": title,
        "names[i18n][3][seo_title]": seo_t,
        "names[i18n][3][seo_description]": seo_d,
    })
    # slug-поля лишаються рівно такими, як прийшли з форми — URL не змінюється
    post_form(session, f"{base_url}/adminLegacy/save.php", payload,
              f"{base_url}/adminLegacy/edit.php?id={sec_id}&parent={parent_id}&handler=4")


def save_hide(session, base_url: str, sec_id: str, parent_id: str) -> None:
    payload = fetch_full_form_payload(session, base_url, sec_id, parent_id)
    payload.update({
        "checkcode": "yamete_kudasai",
        "id": sec_id,
        "handler": "4",
        "handlertable": "pages",
        "back": "index.php",
        "names[parent]": parent_id,
        "names[inmenu]": "0",
        "names[insitemap]": "0",
        "names[noindex]": "1",
        "names[nofollow]": "1",
    })
    post_form(session, f"{base_url}/adminLegacy/save.php", payload,
              f"{base_url}/adminLegacy/edit.php?id={sec_id}&parent={parent_id}&handler=4")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        print("ПЛАН перейменувань (URL не змінюється):")
        for sec_id, parent, title in RENAMES:
            print(f"  id={sec_id}: → «{title}»")
        print("ПЛАН приховування:")
        for sec_id, parent in HIDE:
            print(f"  id={sec_id}: inmenu=0, noindex=1 (Котушки архів)")
        return 0

    env = load_env()
    base = get_base_url(env)
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-seo-rename/1.0"
    auth(session, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    ok, fail = 0, []
    for sec_id, parent, title in RENAMES:
        try:
            save_rename(session, base, sec_id, parent, title)
            ok += 1
            print(f"  ✓ {sec_id} → «{title}»")
        except Exception as exc:
            fail.append((sec_id, str(exc)[:120]))
            print(f"  ✗ {sec_id}: {exc}")
        time.sleep(THROTTLE)

    for sec_id, parent in HIDE:
        try:
            save_hide(session, base, sec_id, parent)
            print(f"  ✓ {sec_id} прихована (noindex)")
        except Exception as exc:
            fail.append((sec_id, str(exc)[:120]))
            print(f"  ✗ {sec_id}: {exc}")
        time.sleep(THROTTLE)

    print(f"\nГотово: {ok}/{len(RENAMES)} перейменовано, помилок: {len(fail)}")
    if fail:
        print(json.dumps(fail, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
