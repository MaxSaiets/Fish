"""
Генерує YML-фід для Horoshop з даних meta_store + ukrsklad snapshot.

Структура фіду:
  yml_catalog/
    shop/
      categories  (дерево з УкрСкладу TIP)
      offers      (один offer = один варіант з УкрСкладу)

На цьому етапі описи/характеристики беремо з meta_store.models, якщо там
порожньо — вставляємо placeholder. Після підключення Gemini ці поля
заповняться автоматично.

Вивід: D:\\FISH\\fish-sync\\public\\horoshop.xml
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

PRODUCTS_JSON = Path(r"D:\FISH\fish-sync\data\products.json")
META_DB = Path(r"D:\FISH\fish-sync\data\meta_store.sqlite")
OUT_XML = Path(r"D:\FISH\fish-sync\public\horoshop.xml")


def _xml_escape(s: str) -> str:
    return escape(s or "", {'"': "&quot;", "'": "&apos;"})


def _cdata(s: str) -> str:
    if not s:
        return ""
    safe = (s or "").replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def load_meta() -> dict[str, dict]:
    """Повертає {kod: {parent_key, brand, display_name, description_html, common_params}}."""
    out: dict[str, dict] = {}
    if not META_DB.exists():
        return out
    conn = sqlite3.connect(META_DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT v.kod, v.name_raw, v.test_min, v.test_max, v.length_m, v.action,
                   v.delta_params_json, v.pictures_json,
                   m.parent_key, m.family, m.brand, m.model_name, m.display_name, m.type_word,
                   m.source_category,
                   m.description_html, m.common_params_json
            FROM variants v
            JOIN models m ON m.parent_key = v.parent_key
            """
        ).fetchall()
        for r in rows:
            out[r["kod"]] = {
                "parent_key": r["parent_key"],
                "family": r["family"],
                "brand": r["brand"],
                "model_name": r["model_name"],
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
                "name_raw": r["name_raw"],
                "pictures": json.loads(r["pictures_json"] or "[]"),
            }
    finally:
        conn.close()
    return out


def collect_params(meta: dict) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []
    seen: set[str] = set()

    def push(key: str, value: object) -> None:
        text = str(value or "").strip()
        if not key or not text or key in seen:
            return
        params.append((key, text))
        seen.add(key)

    for key, value in (meta.get("common_params") or {}).items():
        push(key, value)
    for key, value in (meta.get("delta_params") or {}).items():
        push(key, value)
    if meta.get("test_min") is not None and meta.get("test_max") is not None:
        push("Кастинг-тест", f"{meta['test_min']:g}-{meta['test_max']:g} г")
    if meta.get("length_m"):
        push("Довжина", f"{meta['length_m']:g} м")
    if meta.get("action"):
        push("Лад", meta["action"])
    return params


def render() -> Path:
    data = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    cats = data["categories"]
    products = data["products"]
    meta = load_meta()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<yml_catalog date="{now}">')
    lines.append("  <shop>")
    lines.append("    <name>Все для рибалки</name>")
    lines.append("    <company>Все для рибалки (Раково)</company>")
    lines.append("    <currencies>")
    lines.append('      <currency id="UAH" rate="1"/>')
    lines.append("    </currencies>")

    # --- Categories (фільтруємо плейсхолдери) ---
    PLACEHOLDER_NAMES = {"Ваш тип товарів чи послуг", "Ваша група товарів чи послуг", "Нова група"}
    used_tips = {p.get("tip") for p in products if p.get("tip") not in (1, 2, 3, 4, 5)}
    lines.append("    <categories>")
    for c in cats:
        if c["name"].strip() in PLACEHOLDER_NAMES:
            continue
        if c["num"] not in used_tips:
            continue
        parent_attr = f' parentId="{c["parent"]}"' if c["parent"] and c["parent"] not in (1, 2, 3, 4, 5) else ""
        lines.append(
            f'      <category id="{c["num"]}"{parent_attr}>{_xml_escape(c["name"])}</category>'
        )
    lines.append("    </categories>")

    # --- Offers ---
    lines.append("    <offers>")
    skipped = 0
    written = 0
    for p in products:
        kod = (p.get("kod") or "").strip()
        name = (p.get("name") or "").strip()
        # Пропускаємо тестові/порожні
        if not kod or not name or name in ("Повна назва товару", "test", "tetg", "Мій товар"):
            skipped += 1
            continue
        if p.get("tip") in (1, 2, 3, 4, 5):  # категорії-плейсхолдери
            skipped += 1
            continue

        m = meta.get(kod, {})
        brand = m.get("brand") or p.get("proizv") or ""
        display_name = m.get("display_name") or name
        description = m.get("description_html") or f"<p>{_xml_escape(name)}</p>"
        price = p.get("cena_r") or p.get("cena_o") or 1
        stock = p.get("stock") or 0
        available = "true"  # import все; наявність оновимо після

        lines.append(f'      <offer id="{_xml_escape(kod)}" available="{available}">')
        lines.append(f"        <name>{_xml_escape(display_name)}</name>")
        lines.append(f"        <name_ua>{_xml_escape(display_name)}</name_ua>")
        lines.append(f"        <price>{price:.2f}</price>")
        lines.append("        <currencyId>UAH</currencyId>")
        lines.append(f"        <categoryId>{p.get('tip', 0)}</categoryId>")
        lines.append(f"        <stock_quantity>{int(stock)}</stock_quantity>")
        lines.append(f"        <article>{_xml_escape(kod)}</article>")
        if brand:
            lines.append(f"        <vendor>{_xml_escape(brand)}</vendor>")
        for pic in (m.get("pictures") or []):
            lines.append(f"        <picture>{_xml_escape(pic)}</picture>")
        lines.append(f"        <description>{_cdata(description)}</description>")
        lines.append(f"        <description_ua>{_cdata(description)}</description_ua>")

        # --- Параметри ---
        # Загальні (з моделі)
        for key, value in collect_params(m):
            lines.append(
                f'        <param name="{_xml_escape(key)}">{_xml_escape(value)}</param>'
            )

        lines.append("      </offer>")
        written += 1

    lines.append("    </offers>")
    lines.append("  </shop>")
    lines.append("</yml_catalog>")

    OUT_XML.parent.mkdir(parents=True, exist_ok=True)
    OUT_XML.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK: written={written} skipped={skipped}")
    print(f"-> {OUT_XML}")
    return OUT_XML


if __name__ == "__main__":
    render()
