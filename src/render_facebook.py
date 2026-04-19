"""
Генерує Facebook Catalog feed (RSS 2.0 з namespace g:).

Цей feed підходить одночасно для:
  - Facebook Commerce Manager (Catalog → Data sources → Use a URL)
  - Instagram Shopping (через той самий каталог)
  - Google Merchant Center (формат сумісний)

Особливості:
  - <g:id> = kod
  - <g:availability> = "in stock" / "out of stock"
  - <g:price> = "0.00 UAH" (formatted)
  - <g:image_link> — перша картинка, <g:additional_image_link> — решта (до 10)
  - <g:link> — посилання на сторінку Horoshop (знаємо домен з .env або параметра)
  - <g:condition>new</g:condition>
  - <g:google_product_category> — для риболовлі: 1115 (Sporting Goods > Outdoor Recreation > Fishing)
  - Опис — без HTML (FB ріже теги, але на всяк випадок strip)

Вивід: D:\\FISH\\fish-sync\\public\\facebook.xml
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from feed_content import build_unique_titles, resolve_description_html, strip_html

ROOT = Path(r"D:\FISH\fish-sync")
PRODUCTS_JSON = ROOT / "data" / "products.json"
META_DB = ROOT / "data" / "meta_store.sqlite"
OUT_XML = ROOT / "public" / "facebook.xml"

load_dotenv(ROOT / ".env")
SHOP_DOMAIN = os.environ.get("SHOP_DOMAIN", "https://vse-dlya-rybalky.com.ua")
SHOP_TITLE = "Все для рибалки"
GOOGLE_PRODUCT_CATEGORY = "Sporting Goods > Outdoor Recreation > Fishing"

PLACEHOLDER_TIPS = {1, 2, 3, 4, 5}
SKIP_NAMES = {"Повна назва товару", "test", "tetg", "Мій товар"}

def _xe(s: str) -> str:
    return escape(s or "", {'"': "&quot;", "'": "&apos;"})


def _strip_html(s: str) -> str:
    return strip_html(s)


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
                   v.pictures_json,
                   m.parent_key, m.family, m.type_word, m.source_category,
                   m.common_params_json, v.delta_params_json,
                   m.brand, m.display_name, m.description_html
            FROM variants v JOIN models m ON m.parent_key = v.parent_key
            """
        ).fetchall()
        for r in rows:
            out[r["kod"]] = {
                "parent_key": r["parent_key"],
                "family": r["family"],
                "type_word": r["type_word"],
                "source_category": r["source_category"],
                "common_params": json.loads(r["common_params_json"] or "{}"),
                "delta_params": json.loads(r["delta_params_json"] or "{}"),
                "brand": r["brand"],
                "display_name": r["display_name"],
                "description_html": r["description_html"] or "",
                "pictures": json.loads(r["pictures_json"] or "[]"),
                "name_raw": r["name_raw"],
                "variant_count": r["variant_count"],
            }
    finally:
        conn.close()
    return out


def render(
    products_json: Path = PRODUCTS_JSON,
    out_xml: Path = OUT_XML,
    product_filter: set[str] | None = None,
) -> Path:
    data = json.loads(products_json.read_text(encoding="utf-8"))
    products = data["products"]
    if product_filter is not None:
        products = [p for p in products if str(p.get("kod") or "").strip() in product_filter]
    meta = load_meta()
    titles = build_unique_titles(products, meta)
    now = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

    L: list[str] = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append('<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">')
    L.append("  <channel>")
    L.append(f"    <title>{_xe(SHOP_TITLE)}</title>")
    L.append(f"    <link>{_xe(SHOP_DOMAIN)}</link>")
    L.append(f"    <description>{_xe(SHOP_TITLE + ' — рибальські снасті')}</description>")
    L.append(f"    <lastBuildDate>{now}</lastBuildDate>")

    written = skipped = no_image = 0
    for p in products:
        kod = (p.get("kod") or "").strip()
        name = (p.get("name") or "").strip()
        if not kod or not name or name in SKIP_NAMES or p.get("tip") in PLACEHOLDER_TIPS:
            skipped += 1
            continue

        m = meta.get(kod, {})
        brand = m.get("brand") or p.get("proizv") or "no-brand"
        title = titles.get(kod) or (m.get("display_name") or name)
        description = _strip_html(resolve_description_html(m, name))[:5000]

        price = p.get("cena_r") or p.get("cena_o") or 0
        stock = p.get("stock") or 0
        availability = "in stock" if stock > 0 else "out of stock"

        pics: list[str] = m.get("pictures") or []
        if not pics:
            no_image += 1
            # FB вимагає image_link — placeholder, інакше товар відхилить
            pics = [f"{SHOP_DOMAIN}/static/no-image.jpg"]

        L.append("    <item>")
        L.append(f"      <g:id>{_xe(kod)}</g:id>")
        if m.get("parent_key"):
            L.append(f"      <g:item_group_id>{_xe(m['parent_key'])}</g:item_group_id>")
        L.append(f"      <g:title>{_xe(title[:150])}</g:title>")
        L.append(f"      <g:description>{_xe(description)}</g:description>")
        L.append(f"      <g:link>{_xe(f'{SHOP_DOMAIN}/p/{kod}')}</g:link>")
        L.append(f"      <g:image_link>{_xe(pics[0])}</g:image_link>")
        for extra in pics[1:10]:
            L.append(f"      <g:additional_image_link>{_xe(extra)}</g:additional_image_link>")
        L.append(f"      <g:availability>{availability}</g:availability>")
        L.append(f"      <g:price>{price:.2f} UAH</g:price>")
        L.append(f"      <g:brand>{_xe(brand)}</g:brand>")
        L.append("      <g:condition>new</g:condition>")
        L.append(f"      <g:google_product_category>{_xe(GOOGLE_PRODUCT_CATEGORY)}</g:google_product_category>")
        L.append("    </item>")
        written += 1

    L.append("  </channel>")
    L.append("</rss>")

    out_xml.parent.mkdir(parents=True, exist_ok=True)
    out_xml.write_text("\n".join(L), encoding="utf-8")
    print(f"OK: written={written} skipped={skipped} no_image={no_image}")
    print(f"-> {out_xml}")
    return out_xml


if __name__ == "__main__":
    render()
