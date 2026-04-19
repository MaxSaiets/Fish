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
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv

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

TAG_RE = re.compile(r"<[^>]+>")


def _xe(s: str) -> str:
    return escape(s or "", {'"': "&quot;", "'": "&apos;"})


def _strip_html(s: str) -> str:
    s = TAG_RE.sub(" ", s or "")
    return re.sub(r"\s+", " ", s).strip()


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
                   v.pictures_json,
                   m.brand, m.display_name, m.description_html
            FROM variants v JOIN models m ON m.parent_key = v.parent_key
            """
        ).fetchall()
        for r in rows:
            out[r["kod"]] = {
                "brand": r["brand"],
                "display_name": r["display_name"],
                "description_html": r["description_html"] or "",
                "pictures": json.loads(r["pictures_json"] or "[]"),
                "name_raw": r["name_raw"],
            }
    finally:
        conn.close()
    return out


def render() -> Path:
    data = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    products = data["products"]
    meta = load_meta()
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
        title = m.get("display_name") or name
        description = _strip_html(m.get("description_html") or name)[:5000]

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

    OUT_XML.parent.mkdir(parents=True, exist_ok=True)
    OUT_XML.write_text("\n".join(L), encoding="utf-8")
    print(f"OK: written={written} skipped={skipped} no_image={no_image}")
    print(f"-> {OUT_XML}")
    return OUT_XML


if __name__ == "__main__":
    render()
