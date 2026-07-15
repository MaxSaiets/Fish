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

from feed_content import build_unique_titles, resolve_description_html

PRODUCTS_JSON = Path(r"D:\FISH\fish-sync\data\products.json")
META_DB = Path(r"D:\FISH\fish-sync\data\meta_store.sqlite")
OUT_XML = Path(r"D:\FISH\fish-sync\public\horoshop.xml")


import re as _re
# XML 1.0 забороняє символи < \x20 крім \t \n \r
_INVALID_XML_RE = _re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def _sanitize(s: str) -> str:
    """Видаляє символи, заборонені в XML 1.0."""
    return _INVALID_XML_RE.sub("", s or "")


def _xml_escape(s: str) -> str:
    return escape(_sanitize(s), {'"': "&quot;", "'": "&apos;"})


def _cdata(s: str) -> str:
    if not s:
        return ""
    safe = _sanitize(s).replace("]]>", "]]]]><![CDATA[>")
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
                   COUNT(*) OVER (PARTITION BY v.parent_key) AS variant_count,
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
                "variant_count": r["variant_count"],
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


# Слова, які НЕ є брендом — type_word'и та загальні описи
_NOT_A_BRAND = {
    "вудочка", "вудка", "вудилище", "удилище", "спінінг", "фідер", "котушка",
    "шнур", "шнури", "ліска", "флюорокарбон", "силікон", "силіконова",
    "мормишка", "балансир", "блешня", "воблер", "гачок", "крючок",
    "годівниця", "поплавок", "прикормка", "бойл", "пелетс", "зернові",
    "повідець", "мотовило", "набір", "конектор", "запасне", "карпове",
}


def _clean_brand(brand: str) -> str:
    """Повертає порожній рядок якщо brand — це не справжній бренд."""
    if not brand:
        return ""
    if brand.lower().strip() in _NOT_A_BRAND:
        return ""
    return brand


def render(
    products_json: Path = PRODUCTS_JSON,
    out_xml: Path = OUT_XML,
    product_filter: set[str] | None = None,
) -> Path:
    from horoshop_catalog import build_canonical_products, write_horoshop_xml

    if products_json == PRODUCTS_JSON and product_filter is None:
        result = write_horoshop_xml(out_xml)
        print(f"OK: written={len(build_canonical_products())} skipped=0")
        print(f"-> {result}")
        return result

    data = json.loads(products_json.read_text(encoding="utf-8"))
    cats = data["categories"]
    products = data["products"]
    if product_filter is not None:
        products = [p for p in products if str(p.get("kod") or "").strip() in product_filter]

    # Дедублікація за артикулом — залишаємо перший запис
    seen_kods: set[str] = set()
    deduped: list = []
    for p in products:
        kod = str(p.get("kod") or "").strip()
        if not kod or kod in seen_kods:
            continue
        seen_kods.add(kod)
        deduped.append(p)
    products = deduped

    meta = load_meta()
    titles = build_unique_titles(products, meta)

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

    # ---------------------------------------------------------------------------
    # Структура сайту: (id, parent_id, name)
    # Головні категорії: parent_id = None
    # ---------------------------------------------------------------------------
    SITE_CATS: list[tuple[int, int | None, str]] = [
        # Головні
        (1000, None, "Херабуна"),
        (1001, None, "Вудилища"),
        (1002, None, "Котушки"),
        (1003, None, "Волосінь та шнури"),
        (1004, None, "Чохли"),
        (1005, None, "Гачки"),
        (1006, None, "Готові монтажі"),
        (1007, None, "Все для монтажу"),
        (1008, None, "Сигналізатори клювання"),
        (1009, None, "Насадочні"),
        (1010, None, "Прикормка"),
        (1011, None, "Пелетси"),
        (1012, None, "Ліквіди і атрактанти"),
        (1013, None, "Відра сумки та органайзери"),
        (1014, None, "Підставки та тримачі"),
        (1015, None, "Підсаки Садки кукани"),
        (1016, None, "Крісла стільці та столи"),
        (1017, None, "PVA матеріали та аксесуари"),
        (1018, None, "Зимова ловля"),
        (1019, None, "Туризм"),
        (1020, None, "Приманки"),
        (1021, None, "Одяг та взуття"),
        # Херабуна
        (1100, 1000, "Вудилища махові"),
        (1101, 1000, "Готові оснастки"),
        (1102, 1000, "Тісто"),
        (1103, 1000, "Аксесуари"),
        (1104, 1000, "Підсак садок"),
        (1105, 1000, "Поплавки"),
        (1106, 1000, "Гачки і повідки"),
        # Вудилища
        (1200, 1001, "Коропові"),
        (1201, 1001, "Фідерні"),
        (1202, 1001, "Спінінгові"),
        (1203, 1001, "Махові"),
        (1204, 1001, "Болонські"),
        (1205, 1001, "Запчастини та аксесуари для вудок"),
        # Котушки
        (1300, 1002, "Коропові"),
        (1301, 1002, "Фідерні"),
        (1302, 1002, "Спінінгові"),
        (1303, 1002, "Безінерційні котушки"),
        (1304, 1002, "Аксесуари до котушок"),
        # Волосінь та шнури
        (1400, 1003, "Волосінь"),
        (1401, 1003, "Повідковий матеріал"),
        (1402, 1003, "Шнури"),
        (1403, 1003, "Флюорокарбон"),
        (1404, 1003, "Готові повідці"),
        # Гачки (Спінінгові гачки — проміжний рівень, як на сайті)
        (1506, 1005, "Спінінгові гачки"),
        (1500, 1506, "Трійники"),
        (1501, 1506, "Двійники"),
        (1502, 1506, "Офсетні"),
        (1503, 1005, "Коропові гачки"),
        # Готові монтажі
        (1600, 1006, "Оранж монтажі"),
        (1601, 1006, "Інші монтажі"),
        # Все для монтажу
        (1700, 1007, "Карабіни вертлюги та кільця"),
        (1701, 1007, "Годівниці"),
        (1702, 1007, "Грузила"),
        (1703, 1007, "Інше для оснащення"),
        # Сигналізатори
        (1800, 1008, "Механічні"),
        (1801, 1008, "Електронні"),
        (1802, 1008, "Кивок"),
        # Насадочні
        (1900, 1009, "Бойли"),
        (1901, 1009, "Поп-ап"),
        (1902, 1009, "Діпи"),
        (1903, 1009, "Зернові насадки"),
        # 1904 Наживка відсутня на сайті → TIP 95,141 mapped to parent 1009
        # Прикормка
        (2000, 1010, "Fanatik"),
        (2001, 1010, "Anvi"),
        (2002, 1010, "Real Fish"),
        (2003, 1010, "Interkril"),
        (2004, 1010, "Інші бренди"),
        (2005, 1010, "Технопланктон"),
        (2006, 1010, "Макуха"),
        (2007, 1010, "Зернові"),
        # Пелетси — підкат "Всі пелетси" відсутня на сайті → TIPs → parent 1011
        # Відра сумки та органайзери
        (2200, 1013, "Коробки органайзери"),
        (2201, 1013, "Сумки"),
        (2202, 1013, "Поводочниці"),
        # Підставки та тримачі
        (2300, 1014, "Род-поди"),
        (2301, 1014, "Підставки та триноги"),
        (2302, 1014, "Аксесуари"),
        # Підсаки, Садки, кукани
        (2400, 1015, "Підсаки"),
        (2401, 1015, "Ручки та голови до підсаків"),
        (2402, 1015, "Садки кукани"),
        # Крісла, стільці та столи
        (2500, 1016, "Крісла"),
        (2501, 1016, "Стільці"),
        # PVA
        (2600, 1017, "PVA матеріали"),
        (2601, 1017, "Інструменти"),
        # Зимова ловля
        (2700, 1018, "Льодобури"),
        (2701, 1018, "Мормишки"),
        (2702, 1018, "Вудилища зимові"),
        (2703, 1018, "Сани та ящики"),
        (2704, 1018, "Жилка зимова"),
        (2705, 1018, "Аксесуари зимові"),
        # Туризм
        (2800, 1019, "Ліхтарі"),
        (2801, 1019, "Посуд"),
        (2802, 1019, "Плити горілки балони"),
        (2803, 1019, "Батарейки"),
        # 2804 Намети та спальники → відсутня на сайті, TIPs → parent 1019
        # Приманки
        (2900, 1020, "Балансири"),
        (2901, 1020, "Блешні"),
        (2902, 1020, "Воблери"),
        # 2903 Силіконові приманки — TIPs → parent 1020 (немає підкат на сайті)
        # 2904 Джиг-головки — TIP 81 → 1703 (Інше для оснащення)
        # 1021 Одяг та взуття — виключено (немає категорій на сайті)
    ]

    # ---------------------------------------------------------------------------
    # TIP (УкрСклад) → ID нової категорії сайту
    # ---------------------------------------------------------------------------
    TIP_TO_CAT_ID: dict[int, int] = {
        # Херабуна
        147: 1100, 150: 1101, 146: 1102, 145: 1103, 152: 1104,
        148: 1105, 151: 1106, 171: 1106,
        206: 1103, 207: 1103, 211: 1103, 214: 1103,
        # Вудилища
        36: 1200, 35: 1201, 9: 1202, 14: 1203, 236: 1205,
        245: 1202,  # Feima → Спінінгові
        # Котушки
        53: 1300, 52: 1301, 200: 1302, 51: 1303, 246: 1303,
        225: 1304, 243: 1302,  # Weida → Спінінгові
        # Волосінь та шнури
        66: 1400, 209: 1400,
        69: 1401, 220: 1401,  # Шок-лідер → Повідковий матеріал
        64: 1402, 215: 1402, 216: 1402, 217: 1402, 218: 1402, 219: 1402, 244: 1402,
        208: 1403, 212: 1403, 213: 1403,
        68: 1404,
        # Чохли (без субкатегорій)
        119: 1004, 241: 2705,
        # Гачки
        174: 1500, 176: 1501, 175: 1502, 78: 1005,
        180: 2705,  # Зимові трійники → Зимова/Аксесуари
        # Готові монтажі
        163: 1600, 247: 1600, 75: 1601,
        # Все для монтажу
        71: 1700, 77: 1701, 76: 1702,
        73: 1703, 229: 1703, 232: 1703,
        # Поплавки → під Херабуна/Поплавки
        80: 1105,
        # Сигналізатори
        226: 1800, 118: 1801, 182: 1802, 227: 1802,
        # Насадочні – Бойли
        91: 1900, 168: 1900, 205: 1900, 265: 1900, 276: 1900,
        # Насадочні – Поп-ап
        156: 1901, 167: 1901, 201: 1901, 202: 1901,
        203: 1901, 204: 1901, 271: 1901, 280: 1901,
        # Насадочні – Діпи, Зернові, Наживка
        283: 1902,
        97: 1903, 162: 1903, 255: 1903, 270: 1903, 272: 1903,
        95: 1009,  # Наживка → Насадочні (батьківська, "Наживка" відсутня на сайті)
        # Прикормка
        194: 2000, 298: 2000,  # Fanatik + Кекс
        90: 2004, 159: 2004, 253: 2004, 275: 2004,
        279: 2004, 286: 2004, 292: 2004, 296: 2004,
        96: 2004,   # Пінотісто/Макуха → Інші бренди
        161: 2004, 259: 2004,  # Пінотісто
        260: 2005,  # Технопланктон
        263: 2006, 297: 2006,  # Макуха
        # Пелетси
        # Пелетси → в батьківську "Пелетси" (підкат по брендах є на сайті, але не в XML)
        93: 1011, 154: 1011, 165: 1011, 169: 1011,
        173: 1011, 191: 1011, 257: 1011, 289: 1011, 290: 1011, 294: 1011,
        # Ліквіди і атрактанти
        94: 1012, 160: 1012, 170: 1012, 192: 1012,
        248: 1012, 249: 1012, 282: 1012, 284: 1012,
        287: 1012, 288: 1012, 295: 1012,
        # Відра, сумки та органайзери
        120: 2200, 122: 2201, 240: 2201, 242: 2202,
        # Підставки та тримачі
        221: 2300, 222: 2301, 223: 2301, 224: 2302,
        # Підсаки, Садки, кукани
        115: 2400, 239: 2401, 117: 2402, 228: 2402,
        # Крісла, стільці та столи
        121: 2501,
        # PVA та інструменти
        79: 2600, 155: 2600,
        111: 2601, 230: 2601, 231: 2601,
        # Зимова ловля
        112: 2700, 237: 2700,
        87: 2701, 181: 2701,
        15: 2702,
        238: 2703,
        210: 2704,
        178: 2705, 143: 2705,
        # Туризм
        131: 2800, 130: 2801, 126: 2802,
        234: 2803,
        128: 1019, 129: 1019, 125: 1019,  # Намети/спальники → Туризм (підкат відсутня на сайті)
        # Приманки
        86: 2900,
        88: 2901, 172: 2901, 179: 2901, 187: 2901, 188: 2901,
        85: 2902,
        83: 1020, 195: 1020, 196: 1020, 197: 1020, 198: 1020, 199: 1020,  # Силікон → Приманки (батьківська)
        81: 1703,   # Джиг-головки → Все для монтажу/Інше для оснащення
        # Одяг та взуття — виключено з фіду (немає категорій на сайті)
        # 134: 3003, 135: 3001, 136: 3000, 137: 3003, 138: 3003, 139: 3002,
        # Решта (різне)
        132: 1703, 141: 1009,  # 141 Наживка → Насадочні
    }
    # Визначаємо які нові cat_id реально використовуються
    used_new_cats: set[int] = set()
    for p in products:
        tip = p.get("tip")
        if tip and tip not in (1, 2, 3, 4, 5):
            cat_id = TIP_TO_CAT_ID.get(tip)
            if cat_id:
                used_new_cats.add(cat_id)
                # Додаємо батьківські категорії теж
                for cid, pid, _ in SITE_CATS:
                    if cid == cat_id and pid:
                        used_new_cats.add(pid)

    lines.append("    <categories>")
    for cid, pid, cname in SITE_CATS:
        if cid not in used_new_cats:
            continue
        if pid:
            lines.append(f'      <category id="{cid}" parentId="{pid}">{_xml_escape(cname)}</category>')
        else:
            lines.append(f'      <category id="{cid}">{_xml_escape(cname)}</category>')
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
        tip = p.get("tip")
        if tip in (1, 2, 3, 4, 5):  # категорії-плейсхолдери
            skipped += 1
            continue
        cat_id = TIP_TO_CAT_ID.get(tip)
        if not cat_id:
            skipped += 1  # TIP не замапований — пропускаємо
            continue

        m = meta.get(kod, {})
        brand = _clean_brand(m.get("brand") or p.get("proizv") or "")
        display_name = titles.get(kod) or (m.get("display_name") or name)
        description = resolve_description_html(m, name)
        price = p.get("cena_r") or p.get("cena_o") or 1
        stock = p.get("stock") or 0
        available = "true"  # import все; наявність оновимо після

        lines.append(f'      <offer id="{_xml_escape(kod)}" available="{available}">')
        lines.append(f"        <name>{_xml_escape(display_name)}</name>")
        lines.append(f"        <name_ua>{_xml_escape(display_name)}</name_ua>")
        lines.append(f"        <price>{price:.2f}</price>")
        lines.append("        <currencyId>UAH</currencyId>")
        lines.append(f"        <categoryId>{cat_id}</categoryId>")
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

    out_xml.parent.mkdir(parents=True, exist_ok=True)
    out_xml.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK: written={written} skipped={skipped}")
    print(f"-> {out_xml}")
    return out_xml


if __name__ == "__main__":
    render()
