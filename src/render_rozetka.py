"""
Генерує YML-фід для Rozetka Marketplace.

Відмінності від Horoshop:
  - Обовʼязково мінімум 3 <param> на товар (інакше імпорт відхиляє)
  - Обовʼязковий <description> (CDATA, до 5000 символів)
  - <vendorCode> замість <article>
  - <available> атрибут "true"/"false"
  - Без <name_ua>/<description_ua> — лише <name>/<description>
  - <param name="..." unit="..."> — Розетка вимагає окремий unit для одиниць виміру
  - <currencyId>UAH</currencyId>
  - <state>new</state>

Доки common_params не дають 3+ полів — добиваємо технічними характеристиками
варіанта (тест/довжина/лад) або падінгом ("Гарантія = 14 днів повернення").

Вивід: D:\\FISH\\fish-sync\\public\\rozetka.xml
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from feed_content import build_unique_titles, resolve_description_html

PRODUCTS_JSON = Path(r"D:\FISH\fish-sync\data\products.json")
META_DB = Path(r"D:\FISH\fish-sync\data\meta_store.sqlite")
OUT_XML = Path(r"D:\FISH\fish-sync\public\rozetka.xml")

PLACEHOLDER_TIPS = {1, 2, 3, 4, 5}
SKIP_NAMES = {"Повна назва товару", "test", "tetg", "Мій товар"}
MIN_PARAMS = 3


def _xe(s: str) -> str:
    return escape(s or "", {'"': "&quot;", "'": "&apos;"})


def _cdata(s: str) -> str:
    if not s:
        return ""
    safe = s.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def load_meta() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not META_DB.exists():
        return out
    conn = sqlite3.connect(META_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT v.kod, v.name_raw, v.test_min, v.test_max, v.length_m, v.action,
                   COUNT(*) OVER (PARTITION BY v.parent_key) AS variant_count,
                   v.delta_params_json, v.pictures_json,
                   m.parent_key, m.family, m.brand, m.model_name, m.display_name, m.type_word,
                   m.source_category,
                   m.description_html, m.common_params_json
            FROM variants v JOIN models m ON m.parent_key = v.parent_key
            """
        ).fetchall()
        for r in rows:
            out[r["kod"]] = {
                "family": r["family"],
                "brand": r["brand"],
                "display_name": r["display_name"],
                "type_word": r["type_word"],
                "source_category": r["source_category"],
                "description_html": r["description_html"] or "",
                "common_params": json.loads(r["common_params_json"] or "{}"),
                "delta_params": json.loads(r["delta_params_json"] or "{}"),
                "test_min": r["test_min"],
                "test_max": r["test_max"],
                "length_m": r["length_m"],
                "action": r["action"],
                "variant_count": r["variant_count"],
                "name_raw": r["name_raw"],
                "pictures": json.loads(r["pictures_json"] or "[]"),
            }
    finally:
        conn.close()
    return out


def build_params(m: dict) -> list[tuple[str, str, str | None]]:
    """
    Повертає список (name, value, unit). Unit окремим полем — Розетка
    кладе його в атрибут <param unit="...">.
    """
    out: list[tuple[str, str, str | None]] = []
    # Variant-specific (з парсера)
    if m.get("test_min") is not None and m.get("test_max") is not None:
        out.append(("Кастинг-тест", f"{m['test_min']:g}-{m['test_max']:g}", "г"))
    if m.get("length_m"):
        out.append(("Довжина", f"{m['length_m']:g}", "м"))
    if m.get("action"):
        out.append(("Лад", m["action"], None))
    # Common (з AI / ручного)
    for k, v in (m.get("common_params") or {}).items():
        if v:
            out.append((k, str(v), None))
    for k, v in (m.get("delta_params") or {}).items():
        if not v:
            continue
        unit = None
        value = str(v)
        if value.endswith(" мм"):
            value = value[:-3]
            unit = "мм"
        elif value.endswith(" м"):
            value = value[:-2]
            unit = "м"
        elif value.endswith(" см"):
            value = value[:-3]
            unit = "см"
        elif value.endswith(" мл"):
            value = value[:-3]
            unit = "мл"
        elif value.endswith(" г"):
            value = value[:-2]
            unit = "г"
        elif value.endswith(" кг"):
            value = value[:-3]
            unit = "кг"
        elif value.endswith(" lb"):
            value = value[:-3]
            unit = "lb"
        elif value.endswith(" шт"):
            value = value[:-3]
            unit = "шт"
        out.append((k, value.strip(), unit))
    return out


def pad_params(params: list[tuple[str, str, str | None]], display_name: str, brand: str, type_word: str) -> list[tuple[str, str, str | None]]:
    """Якщо <3 параметрів — добиваємо безпечними дефолтами."""
    have = {p[0] for p in params}
    fillers = [
        ("Бренд", brand, None) if brand else None,
        ("Тип товару", type_word or "Рибальський товар", None),
        ("Стан", "Новий", None),
    ]
    for f in fillers:
        if f and f[0] not in have and len(params) < MIN_PARAMS:
            params.append(f)
            have.add(f[0])
    return params


def render(
    products_json: Path = PRODUCTS_JSON,
    out_xml: Path = OUT_XML,
    product_filter: set[str] | None = None,
) -> Path:
    data = json.loads(products_json.read_text(encoding="utf-8"))
    cats = data["categories"]
    products = data["products"]
    if product_filter is not None:
        products = [p for p in products if str(p.get("kod") or "").strip() in product_filter]
    meta = load_meta()
    titles = build_unique_titles(products, meta)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    L: list[str] = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append(f'<yml_catalog date="{now}">')
    L.append("  <shop>")
    L.append("    <name>Все для рибалки</name>")
    L.append("    <company>Все для рибалки (Раково)</company>")
    L.append("    <currencies><currency id=\"UAH\" rate=\"1\"/></currencies>")

    # Categories — пропускаємо плейсхолдери
    L.append("    <categories>")
    for c in cats:
        if c["num"] in PLACEHOLDER_TIPS:
            continue
        parent = f' parentId="{c["parent"]}"' if c["parent"] and c["parent"] not in PLACEHOLDER_TIPS else ""
        L.append(f'      <category id="{c["num"]}"{parent}>{_xe(c["name"])}</category>')
    L.append("    </categories>")

    L.append("    <offers>")
    written = skipped = padded = 0
    for p in products:
        kod = (p.get("kod") or "").strip()
        name = (p.get("name") or "").strip()
        if not kod or not name or name in SKIP_NAMES:
            skipped += 1
            continue
        if p.get("tip") in PLACEHOLDER_TIPS:
            skipped += 1
            continue

        m = meta.get(kod, {})
        brand = m.get("brand") or p.get("proizv") or ""
        display_name = titles.get(kod) or (m.get("display_name") or name)
        description = resolve_description_html(m, name)

        price = p.get("cena_r") or p.get("cena_o") or 0
        stock = p.get("stock") or 0
        available = "true" if stock > 0 else "false"

        params = build_params(m)
        if len(params) < MIN_PARAMS:
            params = pad_params(params, display_name, brand, m.get("type_word") or "")
            padded += 1

        L.append(f'      <offer id="{_xe(kod)}" available="{available}">')
        L.append(f"        <name>{_xe(display_name)}</name>")
        L.append(f"        <price>{price:.2f}</price>")
        L.append("        <currencyId>UAH</currencyId>")
        L.append(f"        <categoryId>{p.get('tip', 0)}</categoryId>")
        L.append(f"        <stock_quantity>{int(stock)}</stock_quantity>")
        L.append(f"        <vendorCode>{_xe(kod)}</vendorCode>")
        if brand:
            L.append(f"        <vendor>{_xe(brand)}</vendor>")
        for pic in (m.get("pictures") or []):
            L.append(f"        <picture>{_xe(pic)}</picture>")
        L.append("        <state>new</state>")
        L.append(f"        <description>{_cdata(description)}</description>")
        for pname, pval, punit in params:
            unit_attr = f' unit="{_xe(punit)}"' if punit else ""
            L.append(f'        <param name="{_xe(pname)}"{unit_attr}>{_xe(pval)}</param>')
        L.append("      </offer>")
        written += 1

    L.append("    </offers>")
    L.append("  </shop>")
    L.append("</yml_catalog>")

    out_xml.parent.mkdir(parents=True, exist_ok=True)
    out_xml.write_text("\n".join(L), encoding="utf-8")
    print(f"OK: written={written} skipped={skipped} padded={padded}")
    print(f"-> {out_xml}")
    return out_xml


if __name__ == "__main__":
    render()
