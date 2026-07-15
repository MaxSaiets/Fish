"""
Генерує повний Horoshop legacy-friendly `.xls` як HTML-таблицю.

Цей формат потрібен для старого `/adminLegacy/import/pricelist.php`: CSV він
не приймає, а XLSX може прочитати як одну порожню колонку. HTML-таблиця з
розширенням `.xls` у safe sample preview коректно дала 206 колонок.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from generate_import_csv import BASE_COLUMNS, clean_cell
from horoshop_catalog import build_canonical_products, collect_param_headers, strip_html

OUT = ROOT / "public" / "horoshop_import_legacy_html.xls"


def td(value: object) -> str:
    return f"<td>{html.escape(clean_cell(value))}</td>"


def main() -> None:
    products = build_canonical_products()
    param_headers = collect_param_headers(products)
    headers = BASE_COLUMNS + [f"{name}(ua)" for name in param_headers]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        fh.write("""<!doctype html>
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
</head>
<body>
<table>
""")
        fh.write("<tr>" + "".join(td(header) for header in headers) + "</tr>\n")
        for product in products:
            params = {
                item["name"]: item["value"]
                for item in product.get("params", [])
                if item.get("name")
            }
            title = product.get("title", "")
            row = [
                product.get("article", ""),
                title,
                title,
                product.get("parent", ""),
                product.get("price", "") if product.get("price") else "",
                "UAH",
                "Да" if int(product.get("display_in_showcase", 1)) else "Нет",
                product.get("presence", "Немає в наявності"),
                product.get("brand", ""),
                strip_html(product.get("description", "")),
            ]
            row.extend(params.get(param_name, "") for param_name in param_headers)
            fh.write("<tr>" + "".join(td(value) for value in row) + "</tr>\n")
        fh.write("""</table>
</body>
</html>
""")

    print(f"Записано товарів: {len(products)}")
    print(f"Колонок: {len(headers)}")
    print(f"Файл: {OUT}")
    print("Увага: файл потрібно спершу перевірити у preview, не запускати фінальний імпорт без підтвердження.")


if __name__ == "__main__":
    main()
