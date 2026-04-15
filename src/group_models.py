"""
Групує товари з products.json у моделі (parent) + варіанти для різних сімейств.

Підтримувані групи:
  - Спінінги і вудки
  - Волосінь / флюрокарбон / шок-лідер
  - Повідці
  - Бойли / поп-ап / зернові / пелетс / мікси / ліквіди
  - Кивки
  - Сигналізатори та суміжні аксесуари
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from catalog_rules import SKIP_NAMES, normalize_key, parse_product

PRODUCTS_JSON = Path(r"D:\FISH\fish-sync\data\products.json")
MODELS_JSON = Path(r"D:\FISH\fish-sync\data\models.json")


@dataclass
class Variant:
    kod: str
    num: int
    name_raw: str
    test_min: float | None = None
    test_max: float | None = None
    length_m: float | None = None
    action: str | None = None
    delta_params: dict[str, str] = field(default_factory=dict)
    extras: list[str] = field(default_factory=list)


@dataclass
class Model:
    parent_key: str
    family: str
    type_word: str
    brand: str
    model_name: str
    category_tip: int
    source_category: str
    common_params: dict[str, str] = field(default_factory=dict)
    variants: list[Variant] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return " ".join(part for part in [self.type_word, self.brand, self.model_name] if part).strip()


def should_skip(product: dict) -> bool:
    name = (product.get("name") or "").strip()
    if not name or name in SKIP_NAMES:
        return True
    category_path = [str(item).strip() for item in product.get("category_path") or [] if str(item).strip()]
    real_categories = [item for item in category_path if item not in {"Ваш тип товарів чи послуг", "Ваша група товарів чи послуг", "Нова група"}]
    return not real_categories


def group_products(products: list[dict]) -> list[Model]:
    models: dict[str, Model] = {}
    product_groups: dict[str, list[dict]] = defaultdict(list)

    for product in products:
        if should_skip(product):
            continue
        parsed = parse_product(product)
        if not parsed:
            continue

        key_base = normalize_key(f"{parsed.family}_{parsed.brand}_{parsed.model_name}") or normalize_key(
            f"{parsed.family}_{product.get('name', '')}"
        )
        product_groups[key_base].append((product, parsed))

    for key_base, items in product_groups.items():
        product, parsed = items[0]
        real_categories = [
            str(item).strip()
            for item in product.get("category_path") or []
            if str(item).strip() and str(item).strip() not in {"Ваш тип товарів чи послуг", "Ваша група товарів чи послуг", "Нова група"}
        ]
        source_category = real_categories[-1] if real_categories else ""
        model = Model(
            parent_key=key_base,
            family=parsed.family,
            type_word=parsed.type_word,
            brand=parsed.brand,
            model_name=parsed.model_name,
            category_tip=int(product.get("tip") or 0),
            source_category=source_category,
            common_params=dict(parsed.common_params),
        )
        for product, parsed in items:
            model.variants.append(
                Variant(
                    kod=str(product.get("kod") or "").strip(),
                    num=int(product.get("num") or 0),
                    name_raw=str(product.get("name") or "").strip(),
                    test_min=parsed.test_min,
                    test_max=parsed.test_max,
                    length_m=parsed.length_m,
                    action=parsed.action,
                    delta_params=dict(parsed.delta_params),
                )
            )
        models[key_base] = model

    return sorted(models.values(), key=lambda item: (item.family, item.brand, item.model_name))


def main() -> None:
    data = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    models = group_products(data["products"])

    payload = {
        "stats": {
            "total_variants": sum(len(model.variants) for model in models),
            "total_models": len(models),
            "avg_variants_per_model": round(
                sum(len(model.variants) for model in models) / max(len(models), 1),
                2,
            ),
        },
        "models": [
            {
                "parent_key": model.parent_key,
                "family": model.family,
                "display_name": model.display_name,
                "type_word": model.type_word,
                "brand": model.brand,
                "model_name": model.model_name,
                "category_tip": model.category_tip,
                "source_category": model.source_category,
                "common_params": model.common_params,
                "variant_count": len(model.variants),
                "variants": [asdict(variant) for variant in model.variants],
            }
            for model in models
        ],
    }
    MODELS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {payload['stats']}")
    print(f"-> {MODELS_JSON}")


if __name__ == "__main__":
    main()
