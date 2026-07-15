# -*- coding: utf-8 -*-
"""
Створення категорії «Силіконові приманки» (Приманки/1250) + slug + SEO.
Виправляє системну помилку: 916 силіконових приманок сидять у «Мандула».
"""
from __future__ import annotations

import io
import re
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
    LegacyFormParser, auth, fetch_full_form_payload, fetch_slug,
    get_base_url, load_env, post_form,
)

PARENT = "1250"  # Приманки
TITLE = "Силіконові приманки"


def main() -> int:
    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-cat-create/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    # 1) скаффолд форми нової категорії
    url = (f"{base}/adminLegacy/edit.php?id=addnew&parent={PARENT}"
           f"&handler=4&checkcode=yamete_kudasai&showPages")
    r = s.get(url, timeout=60, verify=False)
    r.raise_for_status()
    p = LegacyFormParser(); p.feed(r.text)
    payload = {k: v for k, v in p.fields.items() if str(v) != ""}
    payload.update({
        "checkcode": "yamete_kudasai",
        "id": "addnew",
        "handler": "4",
        "handlertable": "pages",
        "back": "index.php",
        "names[parent]": PARENT,
        "names[handler]": "381",      # шаблон товарів — обовʼязково
        "extra_handler": "381",
        "names[i18n][3][title]": TITLE,
        "names[i18n][3][h1_title]": TITLE,
        "names[inmenu]": "1",
        "names[insitemap]": "1",
        "names[noindex]": "0",
        "names[nofollow]": "0",
    })
    resp = post_form(s, f"{base}/adminLegacy/save.php", payload,
                     f"{base}/adminLegacy/edit.php?id=addnew&parent={PARENT}&handler=4")
    m = re.search(r"id=(\d+)", resp.url)
    if not m:
        # шукаємо у датагріді
        r2 = s.get(f"{base}/adminLegacy/data.php?parent={PARENT}&handler=381&showPages"
                   f"&checkcode=yamete_kudasai", timeout=30, verify=False)
        m = re.search(r'data\.php\?parent=(\d+)[^>]*>\s*' + re.escape(TITLE), r2.text)
    new_id = m.group(1) if m else None
    print("створено, id =", new_id, "| resp.url:", resp.url[:100])
    if not new_id:
        return 1
    time.sleep(1.5)

    # 2) slug + SEO
    slug, url_parent = fetch_slug(s, base, new_id, TITLE)
    payload2 = fetch_full_form_payload(s, base, new_id, PARENT)
    seo_title = f"{TITLE} — купити в Україні, ціни від виробника | Все для рибалки"
    seo_desc = (f"{TITLE} в наявності: віброхвости, твістери, черв'яки, раки ✓ Keitech, "
                f"Select, Fanatik, Lucky John ✓ Доставка Новою поштою по Україні, "
                f"самовивіз у Хмельницькому ✓ Обмін 14 днів.")
    payload2.update({
        "checkcode": "yamete_kudasai",
        "id": new_id,
        "handler": "4",
        "handlertable": "pages",
        "back": "index.php",
        "names[parent]": PARENT,
        "names[name][slug]": slug,
        "names[name][parent]": url_parent,
        "names[name][forceUpdate]": "1",
        "names[i18n][3][title]": TITLE,
        "names[i18n][3][h1_title]": TITLE,
        "names[i18n][3][seo_title]": seo_title,
        "names[i18n][3][seo_description]": seo_desc,
        "names[i18n][3][seo_keywords]": ("силіконові приманки, купити силікон, віброхвіст, твістер, "
                                          "їстівний силікон, силікон на судака, силікон на окуня, "
                                          "keitech, select, fanatik, приманки Хмельницький"),
    })
    post_form(s, f"{base}/adminLegacy/save.php", payload2,
              f"{base}/adminLegacy/edit.php?id={new_id}&parent={PARENT}&handler=4")
    print(f"slug: {slug} | SEO встановлено")
    print("NEW_ID=" + new_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
