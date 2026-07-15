from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from horoshop_catalog import build_canonical_products, normalize_spaces

ROOT = Path(r"D:\FISH\fish-sync")
OUT = ROOT / "data" / "horoshop_param_distribution_report.json"


def compact_counter(counter: Counter[str], limit: int = 40) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def main() -> None:
    products = build_canonical_products()
    by_parent: dict[str, Counter[str]] = defaultdict(Counter)
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    family_parent: dict[str, Counter[str]] = defaultdict(Counter)
    parent_product_count: Counter[str] = Counter()
    noisy_values: dict[str, Counter[str]] = defaultdict(Counter)

    for product in products:
        parent = normalize_spaces(product.get("parent", ""))
        family = normalize_spaces(product.get("family", "")) or "unknown"
        parent_product_count[parent] += 1
        family_parent[family][parent] += 1
        for param in product.get("params") or []:
            name = normalize_spaces(param.get("name", ""))
            value = normalize_spaces(param.get("value", ""))
            if not name:
                continue
            by_parent[parent][name] += 1
            by_family[family][name] += 1
            if name in {"Тип", "Підтип", "Призначення", "Категорія", "Вид"}:
                noisy_values[f"{family}::{name}"][value] += 1

    report = {
        "total_products": len(products),
        "parents": {
            parent: {
                "product_count": parent_product_count[parent],
                "param_names": compact_counter(counter),
            }
            for parent, counter in sorted(by_parent.items())
        },
        "families": {
            family: {
                "product_count": sum(family_parent[family].values()),
                "top_parents": compact_counter(family_parent[family], 20),
                "param_names": compact_counter(counter, 80),
            }
            for family, counter in sorted(by_family.items())
        },
        "noisy_values": {
            key: compact_counter(counter, 30)
            for key, counter in sorted(noisy_values.items())
            if len(counter) > 8 or sum(counter.values()) > 100
        },
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "total_products": report["total_products"],
        "families": len(report["families"]),
        "parents": len(report["parents"]),
        "out": str(OUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
