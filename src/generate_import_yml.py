"""
Генерує horoshop_import.xml (YML-формат) для імпорту через адмінку.
Категорії — з STRUCTURE (нова структура сайту).
Товари — з UkrSklad products.json, прив'язані до категорій через map_product_to_target_path().
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from horoshop_catalog import build_canonical_products, build_category_tree, build_horoshop_yml_lines

OUT = ROOT / "public" / "horoshop_import.yml"


def main():
    cats, path_to_id = build_category_tree()
    products = build_canonical_products()
    lines = build_horoshop_yml_lines(products, cats, path_to_id)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Категорій: {len(cats)}")
    print(f"Товарів записано: {len(products)}")
    print(f"Файл: {OUT}")


if __name__ == "__main__":
    main()
