"""
Генерує Horoshop-friendly CSV для legacy-імпорту прайсу.

Навіщо окремо від XLSX:
- поточний legacy preview Horoshop прочитав .xlsx як один стовпець;
- CSV із розділювачем `;` та UTF-8 BOM зазвичай стабільніше розкладається
  старими імпортерами по колонках;
- файл не імпортується автоматично, а лише готується для preview/мапінгу.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from horoshop_catalog import build_canonical_products, collect_param_headers, strip_html

OUT = ROOT / "public" / "horoshop_import_legacy.csv"

BASE_COLUMNS = [
    "Артикул",
    "Назва(ua)",
    "Назва модифікації(ua)",
    "Розділ",
    "Цена",
    "Валюта",
    "Відображати",
    "Наявність",
    "Бренд",
    "Опис товару(ua)",
]


def clean_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def main() -> None:
    products = build_canonical_products()
    param_headers = collect_param_headers(products)
    headers = BASE_COLUMNS + [f"{name}(ua)" for name in param_headers]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
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
            writer.writerow([clean_cell(value) for value in row])

    print(f"Записано товарів: {len(products)}")
    print(f"Колонок: {len(headers)}")
    print(f"Файл: {OUT}")


if __name__ == "__main__":
    main()
