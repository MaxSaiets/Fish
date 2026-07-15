from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from horoshop_catalog import build_canonical_products, normalize_spaces


ROOT = Path(r"D:\FISH\fish-sync")
OUT = ROOT / "data" / "horoshop_filter_quality_report.json"

ALWAYS_OK = {
    "Тип",
    "Підтип",
    "Призначення",
    "Країна-виробник",
    "Матеріал",
    "Колір",
    "Розмір",
    "Вага",
    "Довжина",
    "Об'єм",
    "Аромат",
    "Аромат/склад",
    "Кількість в упаковці",
    "Комплектація",
}

NOISY_PARAM_NAMES = {
    "Модель",
    "Розміри",
    "Гарантія",
    "Клас",
    "Метод",
    "Стійкість до корозії",
    "Діапазон температури використання",
    "Кількість варіантів",
}

NOISY_VALUE_FRAGMENTS = (
    "не вказано",
    "невідомо",
    "асотр",
    "деш",
    "кольор.ручка",
)


def main() -> int:
    products = build_canonical_products()
    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    value_issues: list[dict[str, Any]] = []

    for product in products:
        family = normalize_spaces(product.get("family", "")) or "unknown"
        for param in product.get("params") or []:
            name = normalize_spaces(param.get("name", ""))
            value = normalize_spaces(param.get("value", ""))
            if not name:
                continue
            family_counts[family][name] += 1
            key = (family, name)
            if len(examples[key]) < 5:
                examples[key].append(
                    {
                        "article": product.get("article"),
                        "title": product.get("title"),
                        "value": value,
                    }
                )
            lower_value = value.lower()
            if any(fragment in lower_value for fragment in NOISY_VALUE_FRAGMENTS):
                value_issues.append(
                    {
                        "article": product.get("article"),
                        "family": family,
                        "title": product.get("title"),
                        "param": name,
                        "value": value,
                    }
                )

    rare_params: list[dict[str, Any]] = []
    explicitly_noisy: list[dict[str, Any]] = []
    for family, counter in sorted(family_counts.items()):
        family_total = sum(counter.values())
        for name, count in counter.items():
            if name in NOISY_PARAM_NAMES:
                explicitly_noisy.append(
                    {
                        "family": family,
                        "param": name,
                        "count": count,
                        "examples": examples[(family, name)],
                    }
                )
            if count <= 2 and name not in ALWAYS_OK:
                rare_params.append(
                    {
                        "family": family,
                        "param": name,
                        "count": count,
                        "family_param_total": family_total,
                        "examples": examples[(family, name)],
                    }
                )

    report = {
        "total_products": len(products),
        "rare_param_count": len(rare_params),
        "explicitly_noisy_count": len(explicitly_noisy),
        "noisy_value_count": len(value_issues),
        "rare_params": rare_params[:300],
        "explicitly_noisy": explicitly_noisy[:300],
        "noisy_values": value_issues[:300],
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "total_products": report["total_products"],
                "rare_param_count": report["rare_param_count"],
                "explicitly_noisy_count": report["explicitly_noisy_count"],
                "noisy_value_count": report["noisy_value_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"Report: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
