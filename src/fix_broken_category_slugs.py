# -*- coding: utf-8 -*-
"""
Виправлення зламаних slug'ів 4 підкатегорій котушок: у полі URL стоїть
літеральне "/{id}" (spininhovi/{id} тощо) → сміттєві %7Bid%7D адреси в sitemap
і зламані URL товарів. Генеруємо чистий slug з нової назви через штатний
віджет updateUriAutomatically + forceUpdate.

Ці сторінки ніколи не індексувались нормально, тому зміна URL безпечна.
"""
from __future__ import annotations

import io
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
    auth, fetch_full_form_payload, fetch_slug, get_base_url, load_env, post_form,
)

# id, parent, назва (вже перейменована раніше)
FIX = [
    ("1087", "1236", "Спінінгові котушки"),
    ("1088", "1236", "Фідерні котушки"),
    ("1089", "1236", "Коропові котушки"),
    ("1212", "1236", "Безінерційні котушки"),
]


def main() -> int:
    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-slug-fix/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    for sec_id, parent, title in FIX:
        slug, url_parent = fetch_slug(s, base, sec_id, title)
        payload = fetch_full_form_payload(s, base, sec_id, parent)
        old = payload.get("names[name][slug]", "?")
        payload.update({
            "checkcode": "yamete_kudasai",
            "id": sec_id,
            "handler": "4",
            "handlertable": "pages",
            "back": "index.php",
            "names[parent]": parent,
            "names[name][slug]": slug,
            "names[name][parent]": url_parent,
            "names[name][forceUpdate]": "1",
            "names[i18n][3][title]": title,
            "names[i18n][3][h1_title]": title,
        })
        post_form(s, f"{base}/adminLegacy/save.php", payload,
                  f"{base}/adminLegacy/edit.php?id={sec_id}&parent={parent}&handler=4")
        print(f"  ✓ {sec_id} «{title}»: slug '{old}' → '{slug}'")
        time.sleep(1.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
