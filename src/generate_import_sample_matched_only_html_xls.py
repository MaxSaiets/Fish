"""
Generate a small Excel-compatible HTML `.xls` for Horoshop legacy preview.

This sample contains only product characteristics that already exist in the
`КАТАЛОГ: Товар` template audit. It is intended for safe mapping preview only.
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
from horoshop_catalog import build_canonical_products, strip_html

COMPARE = ROOT / "data" / "import_vs_template_381_compare_20260607.json"
OUT = ROOT / "public" / "horoshop_import_sample_5_template381_matched_only_html.xls"
REPORT = ROOT / "data" / "horoshop_import_sample_5_template381_matched_only_report.json"


def td(value: object) -> str:
    return f"<td>{html.escape(clean_cell(value))}</td>"


def matched_param_headers() -> list[str]:
    compare = json.loads(COMPARE.read_text(encoding="utf-8"))
    return [
        row["import_header"]
        for row in compare["matched_rows"]
        if not row["import_header"].startswith("TEST")
    ]


def main() -> None:
    products = build_canonical_products()
    param_headers = matched_param_headers()
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
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8-sig")

    report = {
        "file": str(OUT),
        "rows": len(sample),
        "columns": len(headers),
        "matched_characteristics": len(param_headers),
        "format": "html-table-with-xls-extension",
        "purpose": "safe legacy import preview only, not final mass import",
        "articles": [product.get("article", "") for product in sample],
        "headers": headers,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
