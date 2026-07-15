# -*- coding: utf-8 -*-
"""
Виправлення сертифікатів у категорії "Подарункові сертифікати" (parent=1323):
1) артикул 3509 (id=15889, "Сертифкат 1000 грн.") має ціну 500 замість 1000
   (опис товару підтверджує "номінал 1000 грн" - баг у полі ціни).
2) 7 товарів мають одруківку "Сертифкат" замість "Сертифікат" в назві.
Форма save.php дає 503 для цих товарів (відомий баг, задокументовано в пам'яті) -
використовуємо той самий pricelist-імпорт канал, що й для brand/parent.

  python src/fix_certificate_price_title.py --dry-run
  python src/fix_certificate_price_title.py
"""
from __future__ import annotations

import argparse
import html as html_mod
import io
import sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from import_parent_brand import build_xls, run_import  # noqa: E402
from sync_content_playwright import load_env  # noqa: E402

ART_TD = "<td style=\"mso-number-format:'\\@';\">"

# article -> (correct_price, correct_title)
FIXES: dict[str, tuple[str, str]] = {
    "3685": ("2500", "Сертифікат 2500 грн."),
    "3686": ("3000", "Сертифікат 3000 грн."),
    "3687": ("3500", "Сертифікат 3500 грн."),
    "3688": ("4000", "Сертифікат 4000 грн."),
    "3689": ("4500", "Сертифікат 4500 грн."),
    "3690": ("5000", "Сертифікат 5000 грн."),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    items = list(FIXES.items())
    if args.dry_run:
        items = items[:1]

    rows = [
        f"<tr>{ART_TD}{html_mod.escape(art)}</td>"
        f"<td>{html_mod.escape(price)}</td>"
        f"<td>{html_mod.escape(title)}</td></tr>"
        for art, (price, title) in items
    ]
    xls = build_xls(rows, ["Артикул", "Ціна", "Назва"])
    out = ROOT / "tmp" / f"import_cert_fix{'_sample' if args.dry_run else ''}.xls"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(xls)

    env = load_env()
    base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    print(f"Імпорт: {len(items)} товарів (артикули {[a for a, _ in items]})", flush=True)
    res = run_import(out, ["article", "price", "title"], base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])
    print("Результат:", res, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
