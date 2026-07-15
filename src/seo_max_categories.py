# -*- coding: utf-8 -*-
"""
Максимізація SEO всіх категорій (легальні канали, без прихованого тексту):
  - seo_keywords: повний набір пошукових варіацій (невидимі людям, читають роботи)
  - seo_description: + локальна прив'язка "самовивіз у Хмельницькому"
  - seo_text: існуючий генератор + FAQ-блок з пошуковими фразами (видимий, внизу)

Запуск:
  python src/seo_max_categories.py --dry-run          # план без запису
  python src/seo_max_categories.py                    # всі категорії
  python src/seo_max_categories.py --ids 1235,1236    # вибірково
"""
from __future__ import annotations

import argparse
import html as html_mod
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import auth, get_base_url, load_env, post_form  # noqa: E402
from fill_category_seo import build_seo_text, fetch_form, walk_categories  # noqa: E402

SHOP_NAME = "Все для рибалки"
THROTTLE = 1.2
# 1313 Котушки архів (noindex); 1324 Ветеранський спорт і 1323 Сертифікати — ручні тексти, не чіпати
SKIP_IDS = {"1313", "1324", "1323"}


def build_keywords(title: str) -> str:
    tl = title.lower()
    kws = [
        tl, f"купити {tl}", f"{tl} ціна", f"{tl} купити Україна",
        f"{tl} Хмельницький", f"{tl} недорого", f"{tl} інтернет-магазин",
        f"{tl} для риболовлі", "рибальський магазин", "все для рибалки",
        "снасті купити", "рибальські товари Хмельницький",
    ]
    return ", ".join(kws)[:500]


def build_description(title: str) -> str:
    tl = title.lower()
    return (
        f"{title} в наявності в інтернет-магазині «{SHOP_NAME}» ✓ Перевірені бренди ✓ "
        f"Доставка Новою поштою по Україні, самовивіз у Хмельницькому ✓ Обмін 14 днів. "
        f"Обирайте {tl} за характеристиками."
    )[:250]


def build_faq(title: str) -> str:
    t = html_mod.escape(title)
    tl = html_mod.escape(title.lower())
    return (
        f"<h2>Часті запитання</h2>"
        f"<p><b>Скільки коштує {tl}?</b> Ціни в розділі актуальні: якщо товар видно в "
        f"каталозі — він є на складі за вказаною ціною. Сортуйте за ціною, щоб підібрати "
        f"варіант під бюджет.</p>"
        f"<p><b>Як купити {tl} з доставкою?</b> Додайте товар у кошик і оформіть замовлення — "
        f"відправляємо Новою поштою по всій Україні, зазвичай у день оплати. "
        f"У Хмельницькому можливий самовивіз з магазину.</p>"
        f"<p><b>Чи можна повернути або обміняти?</b> Так, обмін і повернення протягом "
        f"14 днів згідно із законодавством України.</p>"
        f"<p><b>Як вибрати {tl} новачку?</b> Зателефонуйте нам — підкажемо робочий варіант "
        f"під ваші водойми та спосіб ловлі, без нав'язування зайвого.</p>"
    )


def save_category(session, base_url: str, cid: str, parent: str) -> str:
    payload = fetch_form(session, base_url, cid, parent)
    title = payload.get("names[i18n][3][title]", "").strip()
    if not title:
        raise RuntimeError("no title in form")
    payload.update({
        "checkcode": "yamete_kudasai",
        "id": cid,
        "handler": "4",
        "handlertable": "pages",
        "back": "index.php",
        "names[i18n][3][seo_keywords]": build_keywords(title),
        "names[i18n][3][seo_description]": build_description(title),
        "extra_parent[i18n][3][seo_text]": build_seo_text(title) + build_faq(title),
    })
    post_form(session, f"{base_url}/adminLegacy/save.php", payload,
              f"{base_url}/adminLegacy/edit.php?id={cid}&parent={parent}&handler=4")
    return title


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ids", type=str, default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    env = load_env()
    base = get_base_url(env)
    session = requests.Session()
    session.headers["User-Agent"] = "fish-sync-seo-max/1.0"
    auth(session, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])

    cats = walk_categories(session, base)
    cats = [c for c in cats if c["id"] not in SKIP_IDS]
    if args.ids:
        want = set(args.ids.split(","))
        cats = [c for c in cats if c["id"] in want]
    if args.limit:
        cats = cats[: args.limit]

    print(f"Категорій до обробки: {len(cats)}")
    if args.dry_run:
        for c in cats[:15]:
            print(f"  id={c['id']} parent={c['parent']} «{c['title']}»")
        print("  … (dry-run, запису немає)")
        print("Приклад keywords:", build_keywords("Фідерні вудилища"))
        return 0

    ok, fail = 0, []
    for i, c in enumerate(cats, 1):
        try:
            title = save_category(session, base, c["id"], c["parent"])
            ok += 1
            if i % 10 == 0:
                print(f"  [{i}/{len(cats)}] ok={ok} fail={len(fail)} (остання: «{title}»)", flush=True)
        except Exception as exc:
            fail.append({"id": c["id"], "err": str(exc)[:120]})
        time.sleep(THROTTLE)

    print(f"\nГотово: {ok}/{len(cats)}, помилок: {len(fail)}")
    if fail:
        out = ROOT / "logs" / f"seo_max_fail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps(fail, ensure_ascii=False, indent=1), encoding="utf-8")
        print("Помилки:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
