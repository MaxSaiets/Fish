"""
Генерує Excel-compatible HTML `.xls` для тесту старого Horoshop pricelist importer.

Деякі legacy PHP-імпортери читають `.xls` як HTML-таблицю краще, ніж `.xlsx`.
Файл містить тільки 5 safe sample товарів і не призначений для фінального імпорту.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from generate_import_csv import BASE_COLUMNS, clean_cell
from generate_import_sample_csv import SAMPLE_SIZE, is_safe_sample_product
from horoshop_catalog import build_canonical_products, collect_param_headers, strip_html

OUT = ROOT / "public" / "horoshop_import_sample_5_html.xls"
REPORT = ROOT / "data" / "horoshop_import_sample_5_html_xls_report.json"


def td(value: object) -> str:
    return f"<td>{html.escape(clean_cell(value))}</td>"


def main() -> None:
    products = build_canonical_products()
    param_headers = collect_param_headers(products)
    headers = BASE_COLUMNS + [f"{name}(ua)" for name in param_headers]
    sample = [product for product in products if is_safe_sample_product(product)][:SAMPLE_SIZE]
    if len(sample) < SAMPLE_SIZE:
        raise RuntimeError(f"Знайдено лише {len(sample)} товарів для safe sample")

    rows = ["<tr>" + "".join(td(header) for header in headers) + "</tr>"]
    for product in sample:
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
        rows.append("<tr>" + "".join(td(value) for value in row) + "</tr>")

    content = """<!doctype html>
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
</head>
<body>
<table>
{rows}
</table>
</body>
</html>
""".format(rows="\n".join(rows))
    OUT.write_text(content, encoding="utf-8-sig")

    report = {
        "file": str(OUT),
        "rows": len(sample),
        "columns": len(headers),
        "format": "html-table-with-xls-extension",
        "purpose": "safe legacy import preview only, not final mass import",
        "articles": [product.get("article", "") for product in sample],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
