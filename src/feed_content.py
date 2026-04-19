from __future__ import annotations

import re

from description_templates import build_description_html

TAG_RE = re.compile(r"<[^>]+>")


def build_variant_title(base_title: str, meta: dict) -> str:
    title = (base_title or "").strip()
    suffixes: list[str] = []

    if meta.get("test_min") is not None and meta.get("test_max") is not None:
        suffixes.append(f"{meta['test_min']:g}-{meta['test_max']:g} г")
    if meta.get("length_m"):
        suffixes.append(f"{meta['length_m']:g} м")
    if meta.get("action"):
        suffixes.append(str(meta["action"]))

    for key in ("Діаметр", "Розмір", "Вага", "Об'єм", "Розривне навантаження", "Кількість в упаковці"):
        value = (meta.get("delta_params") or {}).get(key)
        if value:
            suffixes.append(str(value))

    if not suffixes:
        return title

    marker = " / ".join(dict.fromkeys(suffixes))
    if marker in title:
        return title
    return f"{title} ({marker})"


def build_unique_titles(products: list[dict], meta_map: dict[str, dict]) -> dict[str, str]:
    titles: dict[str, str] = {}
    buckets: dict[str, list[str]] = {}

    for product in products:
        kod = str(product.get("kod") or "").strip()
        if not kod:
            continue
        name = str(product.get("name") or "").strip()
        title = build_variant_title((meta_map.get(kod) or {}).get("display_name") or name, meta_map.get(kod) or {})
        titles[kod] = title
        buckets.setdefault(title, []).append(kod)

    for title, kods in buckets.items():
        if len(kods) < 2:
            continue
        for kod in kods:
            titles[kod] = f"{title} [{kod}]"
    return titles


def resolve_description_html(meta: dict, fallback_name: str) -> str:
    custom = str(meta.get("description_html") or "").strip()
    if custom:
        return custom
    generated = build_description_html(meta).strip()
    if generated:
        return generated
    return f"<p>{fallback_name}</p>"


def strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", text or "")).strip()
