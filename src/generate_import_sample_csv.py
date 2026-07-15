"""
Генерує малий CSV для безпечного preview-тесту legacy імпорту Horoshop.

Файл не призначений для фінального масового імпорту. Він потрібен, щоб
перевірити, чи Horoshop коректно читає розділювач, заголовки й мапінг колонок.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from generate_import_csv import BASE_COLUMNS, clean_cell
from horoshop_catalog import build_canonical_products, collect_param_headers, strip_html

OUT = ROOT / "public" / "horoshop_import_sample_5.csv"
REPORT = ROOT / "data" / "horoshop_import_sample_5_report.json"
SAMPLE_SIZE = 5


def is_safe_sample_product(product: dict) -> bool:
    presence = str(product.get("presence") or "").casefold()
    price = product.get("price")
    return (
        int(product.get("display_in_showcase", 1)) == 1
        and price not in (None, "", 0, "0")
        and "немає" not in presence
        and "нет" not in presence
    )


def main() -> None:
    products = build_canonical_products()
    param_headers = collect_param_headers(products)
    headers = BASE_COLUMNS + [f"{name}(ua)" for name in param_headers]
    sample = [product for product in products if is_safe_sample_product(product)][:SAMPLE_SIZE]

    if len(sample) < SAMPLE_SIZE:
        raise RuntimeError(f"Знайдено лише {len(sample)} товарів для safe sample")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
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
            writer.writerow([clean_cell(value) for value in row])

    report = {
        "file": str(OUT),
        "rows": len(sample),
        "columns": len(headers),
        "delimiter": ";",
        "encoding": "utf-8-sig",
        "purpose": "safe legacy import preview only, not final mass import",
        "products": [
            {
                "article": product.get("article", ""),
                "title": product.get("title", ""),
                "category": product.get("parent", ""),
                "price": product.get("price", ""),
                "presence": product.get("presence", ""),
                "params_count": len(product.get("params") or []),
            }
            for product in sample
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
