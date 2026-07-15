from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from horoshop_catalog import build_canonical_products, normalize_spaces


ROOT = Path(r"D:\FISH\fish-sync")
OUT = ROOT / "data" / "horoshop_param_quality_report.json"

BAD_NAME_FRAGMENTS = (
    "крюч",
    "полок",
    "ячеек",
    "сеть",
    "удоч",
    "быстр",
    "грузов",
    "набор",
    "сумма",
)

BAD_VALUE_FRAGMENTS = (
    "не вказано",
    "невідомо",
    "тест",
    "test",
    "крюч",
    "ячеек",
    "сеть",
    "удоч",
    "быстр",
)

DUPLICATE_GROUPS = {
    "rod_action": {"Лад", "Стрій"},
    "shelf_count": {"Кількість полок", "Кількість поличок", "Кількість полиць"},
    "compartment_count": {"Кількість ячеек", "Кількість відділень", "Кількість відділів", "Кількість відсіків"},
    "volume": {"Обсяг", "Об'єм", "Об'єм упаковки"},
    "hook_count": {"Кількість крючків", "Кількість гачків"},
    "country": {"Країна виробник", "Країна виробництва", "Країна походження", "Країна-виробник"},
}

BAD_NAME_RE = re.compile("|".join(re.escape(fragment) for fragment in BAD_NAME_FRAGMENTS), re.IGNORECASE)
BAD_VALUE_RE = re.compile("|".join(re.escape(fragment) for fragment in BAD_VALUE_FRAGMENTS), re.IGNORECASE)


def add_example(bucket: list[dict[str, Any]], product: dict[str, Any], param: dict[str, str]) -> None:
    if len(bucket) >= 20:
        return
    bucket.append(
        {
            "article": product.get("article"),
            "title": product.get("title"),
            "parent": product.get("parent"),
            "family": product.get("family"),
            "param": normalize_spaces(param.get("name", "")),
            "value": normalize_spaces(param.get("value", "")),
        }
    )


def main() -> int:
    products = build_canonical_products()
    bad_names: list[dict[str, Any]] = []
    bad_values: list[dict[str, Any]] = []
    duplicate_group_hits: list[dict[str, Any]] = []
    low_param_products: list[dict[str, Any]] = []
    family_param_counts: dict[str, Counter[str]] = defaultdict(Counter)
    parent_param_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for product in products:
        params = product.get("params") or []
        names = {normalize_spaces(param.get("name", "")) for param in params}
        if len(params) < 4:
            low_param_products.append(
                {
                    "article": product.get("article"),
                    "title": product.get("title"),
                    "parent": product.get("parent"),
                    "family": product.get("family"),
                    "param_count": len(params),
                }
            )
        for group, aliases in DUPLICATE_GROUPS.items():
            hit = sorted(name for name in names if name in aliases)
            if len(hit) > 1:
                duplicate_group_hits.append(
                    {
                        "article": product.get("article"),
                        "title": product.get("title"),
                        "parent": product.get("parent"),
                        "family": product.get("family"),
                        "group": group,
                        "params": hit,
                    }
                )
        for param in params:
            name = normalize_spaces(param.get("name", ""))
            value = normalize_spaces(param.get("value", ""))
            if not name:
                continue
            family_param_counts[normalize_spaces(product.get("family", ""))][name] += 1
            parent_param_counts[normalize_spaces(product.get("parent", ""))][name] += 1
            if BAD_NAME_RE.search(name):
                add_example(bad_names, product, param)
            if BAD_VALUE_RE.search(value):
                add_example(bad_values, product, param)

    report = {
        "total_products": len(products),
        "bad_name_count": len(bad_names),
        "bad_value_count": len(bad_values),
        "duplicate_group_count": len(duplicate_group_hits),
        "low_param_product_count": len(low_param_products),
        "low_param_product_pct": round(len(low_param_products) / max(len(products), 1) * 100, 2),
        "bad_names": bad_names,
        "bad_values": bad_values,
        "duplicate_group_hits": duplicate_group_hits[:100],
        "low_param_products": low_param_products[:200],
        "top_params_by_family": {
            family: counter.most_common(20)
            for family, counter in sorted(family_param_counts.items())
        },
        "top_params_by_parent": {
            parent: counter.most_common(20)
            for parent, counter in sorted(parent_param_counts.items())
        },
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "total_products": report["total_products"],
                "bad_name_count": report["bad_name_count"],
                "bad_value_count": report["bad_value_count"],
                "duplicate_group_count": report["duplicate_group_count"],
                "low_param_product_count": report["low_param_product_count"],
                "low_param_product_pct": report["low_param_product_pct"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"Report: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
