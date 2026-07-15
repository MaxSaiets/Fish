# -*- coding: utf-8 -*-
"""
Виправлення характеристик махових/болонських вудок на сайті:
  - typ_vudy: "Спінінг" -> "Махова"/"Болонська"/"Телескопічна" (за canonical);
  - очистити AI-вигадки: Тип пропускних кілець, Кількість секцій,
    Транспортна довжина, Тип рукояті (порожня клітинка стирає значення —
    перевірено на casting_test).

Один імпорт характеристик (import_type=characteristics).

  python src/fix_float_rod_chars.py --sample
  python src/fix_float_rod_chars.py
"""
from __future__ import annotations

import argparse
import html as html_mod
import sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from import_parent_brand import ART_TD, build_xls, run_import  # noqa: E402
from sync_content_playwright import load_env  # noqa: E402

HEADERS = ["Артикул", "Тип вудилища", "Тип пропускних кілець",
           "Кількість секцій", "Транспортна довжина", "Тип рукояті"]
FIELDS = ["article", "typ_vudy", "tipPropusknixKlec",
          "klkstSekcy", "transportnaDovzhina", "tipRukojat"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    from horoshop_catalog import build_canonical_products
    prods = build_canonical_products()

    data = []
    for p in prods:
        if p.get("family") != "float_rod":
            continue
        params = {x["name"]: x["value"] for x in (p.get("params") or []) if isinstance(x, dict)}
        typ = params.get("Тип вудилища", "Махова")
        data.append((str(p.get("article")).strip(), typ))

    print(f"float_rod вудок: {len(data)}", flush=True)
    if args.sample:
        keep = {"4095"} | {a for a, _ in data[:4]}
        data = [d for d in data if d[0] in keep]
        print("sample:", data, flush=True)

    rows = []
    for art, typ in data:
        rows.append(
            f"<tr>{ART_TD}{html_mod.escape(art)}</td>"
            f"<td>{html_mod.escape(typ)}</td><td></td><td></td><td></td><td></td></tr>"
        )
    xls = build_xls(rows, HEADERS)
    out = ROOT / "tmp" / "fix_float_rod_chars.xls"
    out.write_bytes(xls)
    print(f"XLS: {out} ({len(rows)} рядків)", flush=True)

    env = load_env()
    base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    res = run_import(out, FIELDS, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"],
                     import_type="characteristics", handler="381")
    print("Результат:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
