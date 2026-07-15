# -*- coding: utf-8 -*-
"""
Перетворення характеристики на фільтрувальну (повний цикл):
  1. створити довідник (/book/createBook) або взяти існуючий
  2. наповнити його нормалізованими значеннями (/adminLegacy/savers/books.php)
  3. конвертувати характеристику в «Вибір зі списку» з цим довідником (saveParam)
  4. реімпортувати нормалізовані значення (import_type=characteristics)

  python src/make_filter_char.py --char "Тип воблера"
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

from apply_horoshop_menu_fixes import auth, get_base_url, load_env, post_form  # noqa: E402
from import_parent_brand import ART_TD, build_xls, run_import, scratch_file  # noqa: E402

THROTTLE = 1.2

# характеристика → (param_id, field-name, book_id якщо вже створений)
CHARS = {
    "Тип воблера":  {"pid": "6632", "name": "typ_voblera", "book": 382},
    "Тип блешні":   {"pid": "6624", "name": "typ_bleshni", "book": None},
    "Тип котушки":  {"pid": "6626", "name": "typ_kotushky", "book": None},
    "Плавучість":   {"pid": "6605", "name": "plavuchist", "book": None},
    "Підшипники":   {"pid": "6644", "name": "pidshypnyky", "book": None},
    "Передаточне число": {"pid": "6627", "name": "peredatochne_chyslo", "book": None},
    "Форма(ua)":    {"pid": "6621", "name": "forma", "book": None},
}

# нормалізація значень: сире → канонічне (нема в мапі → Капіталізоване сире)
NORM = {
    "Тип воблера": {
        "минноу": "Мінноу", "мінноу": "Мінноу", "кренк": "Кренк", "крєнк": "Кренк",
        "Крєнк": "Кренк", "попер": "Попер", "воблер": "Воблер",
        "плаваючий": "Воблер",
        "мінноу/крєнк/попер/джеркбейт/раттлін": "Набір воблерів",
    },
    "Тип блешні": {
        "вертушка": "Вертушка", "спінер": "Вертушка", "спіннер": "Вертушка",
        "Спіннер": "Вертушка", "коливалка": "Коливалка", "коливальна": "Коливалка",
        "коливна": "Коливалка", "блешня": "Блешня",
        "тел-спіннер": "Тейл-спіннер", "Тел-спіннер": "Тейл-спіннер",
    },
    "Тип котушки": {
        "безінерційна": "Безінерційна", "Безінерційна котушка": "Безінерційна",
        "Інерційна": "Інерційна",
    },
    "Плавучість": {
        "плаваючий": "Плаваючий", "Плаваюча": "Плаваючий",
        "тонучий": "Тонучий", "суспендер": "Суспендер",
        "плаваючий/тонучий/суспендер": "Різна (набір)",
    },
    "Форма(ua)": {
        "Лівід": "Ліквід", "лівід": "Ліквід",
        "Куля": "Кулька",
        "Круглий": "Кругла", "круглий": "Кругла", "круглий/циліндричний": "Кругла",
        "Циліндр": "Циліндрична", "циліндр": "Циліндрична",
        "Крапля": "Краплинка", "крапля": "Краплинка",
        "Паста / тісто": "Паста", "Тісто": "Паста", "паста": "Паста",
        "Пелети": "Пелетс", "пелетс": "Пелетс", "Pellets": "Пелетс", "Пеллети": "Пелетс",
        "циліндрична/куляста": "Кругла", "Циліндрична/Куляста": "Кругла",
    },
}


def canon(char: str, v: str) -> str:
    v = v.strip()
    m = NORM.get(char, {})
    if v in m:
        return m[v]
    return v[:1].upper() + v[1:] if v else v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", required=True)
    ap.add_argument("--skip-book-fill", action="store_true")
    args = ap.parse_args()
    char = args.char
    cfg = CHARS[char]

    src = json.load(open(scratch_file("char_values_source.json"), encoding="utf-8"))
    values = {a: canon(char, v) for a, v in src[char].items()}
    uniq = sorted(set(values.values()))
    print(f"«{char}»: {len(values)} товарів, {len(uniq)} канонічних значень: {uniq[:15]}")

    env = load_env()
    base = get_base_url(env)
    s = requests.Session()
    s.headers["User-Agent"] = "fish-sync-filter-char/1.0"
    auth(s, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])
    rp = s.get(f"{base}/adminLegacy/forms/handlers.php?edit=381&checkcode=yamete_kudasai",
               timeout=60, verify=False)
    tok = re.search(r'GLOBAL_CSRF_TOKEN["\' :=]+["\']([^"\']+)', rp.text)
    tok = tok.group(1) if tok else ""
    H = {"X-Requested-With": "XMLHttpRequest", "X-CSRF-Token": tok,
         "Referer": f"{base}/adminLegacy/forms/handlers.php?edit=381"}

    # 1. довідник
    book = cfg["book"]
    if not book:
        r = s.post(f"{base}/book/createBook", data={"title": char.replace("(ua)", "").strip()},
                   headers=H, timeout=60, verify=False)
        book = r.json()["response"]["bookId"]
        print(f"створено довідник book_{book}")
        time.sleep(THROTTLE)

    # 2. значення довідника
    if not args.skip_book_fill:
        for v in uniq:
            payload = {"action": "save", "id": "addnew", "book": str(book),
                       "checkcode": "yamete_kudasai",
                       "names[title][3]": v, "names[title][1]": v,
                       "names[title][4]": v, "names[title][5]": v, "names[title][6]": v}
            rr = s.post(f"{base}/adminLegacy/savers/books.php", data=payload,
                        headers={**H, "Referer": f"{base}/adminLegacy/forms/books.php/?book={book}"},
                        timeout=60, verify=False)
            ok = rr.status_code == 200 and "error" not in rr.text.lower()[:200]
            print(f"  +{v}: {'ok' if ok else rr.text[:80]}")
            time.sleep(THROTTLE)

    # 3. конверсія у select
    data = {"action": "saveParam", "checkcode": "yamete_kudasai",
            "handler[0][id]": "381", "param[0][id]": cfg["pid"],
            "param[0][title]": char.replace("(ua)", "").strip(),
            "param[0][name]": cfg["name"],
            "param[0][group]": "1106", "param[0][type]": "select",
            "param[0][table]": f"book_{book}",
            "param[0][in_grid]": "1", "param[0][editable]": "1", "param[0][localize]": "1"}
    r = s.post(f"{base}/adminLegacy/params/ajax.php", data=data, headers=H, timeout=60, verify=False)
    print("конверсія:", r.json().get("status"))
    time.sleep(THROTTLE)

    # 4. реімпорт нормалізованих значень
    rows = [f"<tr>{ART_TD}{html_mod.escape(a)}</td><td>{html_mod.escape(v)}</td></tr>"
            for a, v in sorted(values.items())]
    xls = build_xls(rows, ["Артикул", char])
    out = ROOT / "tmp" / "import_filter_char.xls"
    out.write_bytes(xls)
    res = run_import(out, ["article", cfg["name"]], base,
                     env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"],
                     import_type="characteristics", handler="381")
    print("імпорт:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
