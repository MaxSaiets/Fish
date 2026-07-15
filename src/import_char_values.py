# -*- coding: utf-8 -*-
"""
Імпорт значень характеристик (після конверсії типу в «Вибір зі списку»).
Джерело: char_values_source.json (витяг з matched-only файла).

  python src/import_char_values.py --chars "Тип воблера"            # одна
  python src/import_char_values.py --chars "Тип воблера,Довжина"    # кілька колонок за раз
"""
from __future__ import annotations

import argparse
import html as html_mod
import io
import json
import sys
from pathlib import Path

# stdout загортає import_parent_brand при імпорті — тут не чіпаємо
ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from import_parent_brand import build_xls, run_import, scratch_file  # noqa: E402
from sync_content_playwright import load_env  # noqa: E402

ART_TD = "<td style=\"mso-number-format:'\\@';\">"

# назва колонки в джерелі → option-value поля в мапінгу імпорту
CHAR_FIELD = {
    "Тип воблера": "typ_voblera",
    "Тип(ua)": "typ",
    "Довжина": "dovzhyna",
    "Вага(ua)": "vaha",
    "Діаметр": "diametr",
    "Розмір(ua)": "rozmir",
    "Колір(ua)": "kolir",
    "Матеріал(ua)": "material",
    "Тип блешні": "typ_bleshni",
    "Плавучість": "plavuchist",
    "Кастинг-тест": "kastynh",
    "Тип котушки": "typ_kotushky",
    "Передаточне число": "peredatochne",
    "Підшипники": "pidshypnyky",
    "Форма(ua)": "forma",
    "Аромат(ua)": "aromat",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chars", required=True, help="список назв через кому (як у джерелі)")
    args = ap.parse_args()
    chars = [c.strip() for c in args.chars.split(",") if c.strip()]

    src = json.load(open(scratch_file("char_values_source.json"), encoding="utf-8"))
    # об'єднання: всі артикули, що мають хоч одне значення
    arts = sorted({a for c in chars for a in src.get(c, {})})
    print(f"Колонок: {len(chars)}, артикулів: {len(arts)}")

    rows = []
    for a in arts:
        cells = "".join(
            f"<td>{html_mod.escape(src.get(c, {}).get(a, ''))}</td>" for c in chars)
        rows.append(f"<tr>{ART_TD}{html_mod.escape(a)}</td>{cells}</tr>")
    xls = build_xls(rows, ["Артикул"] + chars)
    fields = ["article"] + [CHAR_FIELD[c] for c in chars]

    out = ROOT / "tmp" / "import_chars.xls"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(xls)

    env = load_env()
    base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    res = run_import(out, fields, base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"], import_type="characteristics", handler="381")
    print("Результат:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
