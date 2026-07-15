"""
Generate full Horoshop legacy `.xls` with only template-matched characteristics.

Use this before safe preview when the legacy importer does not expose every
catalog characteristic. The output is not meant for final import without a
preview mapping check and explicit confirmation.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from generate_import_csv import BASE_COLUMNS, clean_cell
from horoshop_catalog import build_canonical_products, strip_html

COMPARE = ROOT / "data" / "import_vs_template_381_compare_20260607.json"
OUT = ROOT / "public" / "horoshop_import_template381_matched_only_html.xls"
MANIFEST = ROOT / "data" / "template381_matched_only_import_manifest_20260607.json"


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

    manifest = {
        "file": str(OUT),
        "products": len(products),
        "columns": len(headers),
        "matched_characteristics": len(param_headers),
        "headers": headers,
        "purpose": "safe preview candidate only, not final mass import",
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
