from __future__ import annotations

import json
import re
from pathlib import Path

from horoshop_catalog import audit_products, build_canonical_products, collect_param_headers, load_overrides

ROOT = Path(r"D:\FISH\fish-sync")
OUT = ROOT / "data" / "horoshop_audit_report.json"
QUARANTINE_OUT = ROOT / "data" / "horoshop_quarantine_report.json"

LIKELY_NO_BRAND_PREFIXES = (
    "груз",
    "грузило",
    "грузила",
    "булава",
    "горизонт",
    "капля",
    "груша",
    "пуля",
    "пружина",
    "стопор",
    "стопорки",
    "вертлюг",
    "карабін",
    "коромисло",
    "ракета",
    "рогатка",
    "ножиці",
    "знімач",
    "кембрик",
    "петлевяз",
    "пучковяз",
    "мотовило",
    "пва",
    "клей",
    "фіксатор",
    "трубка",
    "конектор",
    "запасне",
    "джиг-головка",
    "елеватор",
    "фідергам",
    "резинка",
    "ризинка",
    "гума",
    "вбивця",
    "донка",
    "макушатник",
    "макушатнік",
    "оснащення",
    "монтаж",
    "кивок",
    "ложка",
    "багор",
    "ремкомплект",
    "жерлиця",
)

LATIN_BRAND_RE = re.compile(r"[A-Za-z]{3,}")
LIKELY_CODE_ONLY_RE = re.compile(r"^(?:[A-ZА-Я]{1,4}[-]?\d[\w-]*|\d+[A-ZА-Я-]*|\w*\d{3,}\w*)$", re.IGNORECASE)
LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.-]{2,}")
GENERIC_LATIN_TOKENS = {
    "black",
    "silver",
    "gold",
    "gold.",
    "copper",
    "medium",
    "rapid",
    "method",
    "pellet",
    "fluoro",
}
NO_BRAND_FEED_PREFIXES = ("макух", "макуха", "мастирка", "пінопласт", "технопланктон")
NO_BRAND_LURE_PREFIXES = ("грушка", "лижа", "блешня асортимент", "тейл- спінер", "тейл-спінер")
NO_BRAND_REEL_PREFIXES = ("катушка", "котушка")
NO_BRAND_BALANCER_PREFIXES = ("балансир", "балансір")
NO_BRAND_MANDULA_PREFIXES = ("cилікон", "силікон", "мандула")
NO_BRAND_WOBBLER_PREFIXES = ("воблер", "бомбер", "коробка")


def _only_generic_latin_tokens(source: str) -> bool:
    tokens = {token.lower() for token in LATIN_TOKEN_RE.findall(source)}
    return bool(tokens) and tokens.issubset(GENERIC_LATIN_TOKENS)


def is_likely_no_brand(product: dict) -> bool:
    source = (product.get("source_name") or "").strip().lower()
    parent = (product.get("parent") or "").strip().lower()
    first_token = source.split()[0] if source.split() else ""
    if source.startswith(LIKELY_NO_BRAND_PREFIXES):
        return True
    if LIKELY_CODE_ONLY_RE.fullmatch(first_token):
        return True
    if "грузила" in parent or "інше для оснащення" in parent:
        return True
    if "готові монтажі" in parent and not LATIN_BRAND_RE.search(source):
        return True
    if "подарункові сертифікати" in parent:
        return True
    if "зимова ловля / аксесуари" in parent and not LATIN_BRAND_RE.search(source):
        return True
    if "зимова ловля / мормишки" in parent and (
        not LATIN_BRAND_RE.search(source) or _only_generic_latin_tokens(source)
    ):
        return True
    if "зимова ловля / вудилища" in parent and not LATIN_BRAND_RE.search(source):
        return True
    if "зимова ловля / сані" in parent and not LATIN_BRAND_RE.search(source):
        return True
    if "зимова ловля / льодобури" in parent and not LATIN_BRAND_RE.search(source):
        return True
    if ("кормушки" in parent or "годівниці" in parent) and not LATIN_BRAND_RE.search(source):
        return True
    if "прикормка / технопланктон" in parent and source.startswith(NO_BRAND_FEED_PREFIXES) and not LATIN_BRAND_RE.search(source):
        return True
    if "приманки / блешні" in parent and source.startswith(NO_BRAND_LURE_PREFIXES) and not LATIN_BRAND_RE.search(source):
        return True
    if "приманки / балансири" in parent and source.startswith(NO_BRAND_BALANCER_PREFIXES) and not LATIN_BRAND_RE.search(source):
        return True
    if "приманки / мандула" in parent and source.startswith(NO_BRAND_MANDULA_PREFIXES) and not LATIN_BRAND_RE.search(source):
        return True
    if "приманки / воблери" in parent and source.startswith(NO_BRAND_WOBBLER_PREFIXES) and not LATIN_BRAND_RE.search(source):
        return True
    if "котушки / безінерційні котушки" in parent and source.startswith(NO_BRAND_REEL_PREFIXES) and not LATIN_BRAND_RE.search(source):
        return True
    if ("гачки / звичайні" in parent or parent == "гачки") and not LATIN_BRAND_RE.search(source):
        return True
    if "коробки органайзери" in parent and (LIKELY_CODE_ONLY_RE.search(source) or not LATIN_BRAND_RE.search(source)):
        return True
    if "повідочниці" in parent and (LIKELY_CODE_ONLY_RE.search(source) or not LATIN_BRAND_RE.search(source)):
        return True
    if "pva матеріали та аксесуари / інструменти" in parent and not LATIN_BRAND_RE.search(source):
        return True
    if "pva матеріали" in parent and not LATIN_BRAND_RE.search(source):
        return True
    return False


def run_audit(limit: int | None = None) -> dict:
    products = build_canonical_products(limit=limit)
    overrides = load_overrides()
    report = audit_products(products)
    missing_brand_all = [product for product in products if not (product.get("brand") or "").strip()]
    likely_no_brand = [product for product in missing_brand_all if is_likely_no_brand(product)]
    likely_inferable_brand = [product for product in missing_brand_all if not is_likely_no_brand(product)]
    report["param_headers"] = collect_param_headers(products)
    report["products_with_zero_params"] = sum(1 for product in products if not product.get("params"))
    report["products_with_two_or_less_params"] = sum(1 for product in products if len(product.get("params", [])) <= 2)
    report["missing_brand_count"] = len(missing_brand_all)
    report["likely_no_brand_count"] = len(likely_no_brand)
    report["likely_inferable_brand_count"] = len(likely_inferable_brand)
    report["sample_titles"] = [product["title"] for product in products[:20]]
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    quarantine = {
        "excluded_by_override": [
            {"article": article, **payload}
            for article, payload in sorted((overrides.get("products") or {}).items())
            if payload.get("exclude")
        ],
        "suspicious_names": [
            {"article": product["article"], "source_name": product["source_name"], "title": product["title"]}
            for product in products
            if product.get("suspicious_name")
        ],
        "low_param_products": [
            {
                "article": product["article"],
                "title": product["title"],
                "parent": product["parent"],
                "param_count": len(product.get("params", [])),
                "brand": product.get("brand", ""),
            }
            for product in products
            if len(product.get("params", [])) <= 2
        ][:200],
        "missing_brand_products": [
            {
                "article": product["article"],
                "source_name": product["source_name"],
                "title": product["title"],
                "parent": product["parent"],
            }
            for product in missing_brand_all
        ][:500],
        "likely_no_brand_products": [
            {
                "article": product["article"],
                "source_name": product["source_name"],
                "title": product["title"],
                "parent": product["parent"],
            }
            for product in likely_no_brand
        ][:300],
        "likely_inferable_brand_products": [
            {
                "article": product["article"],
                "source_name": product["source_name"],
                "title": product["title"],
                "parent": product["parent"],
            }
            for product in likely_inferable_brand
        ][:300],
    }
    QUARANTINE_OUT.write_text(json.dumps(quarantine, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    report = run_audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
