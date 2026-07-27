# -*- coding: utf-8 -*-
"""
Повна чистка фільтра "Бренд" (2026-07-16, на вимогу власника: у фільтрі
кольори/смаки/типи товарів замість брендів).

Три типи правок (класифікація зроблена вручну за аудитом назв товарів):
  1) CLEAR    — значення точно НЕ бренд (смак, колір, тип товару, код,
                форма мормишки, модель меблів) → порожнє поле.
  2) MAP      — typo/варіант написання відомого бренду → канонічне значення.
  3) NAMEMAP  — значення-мішанина: рішення по НАЗВІ товару (напр. бренд
                "Carp": "Волосінь Carp Pro..." → CARP PRO, "...Feima" →
                Feima, решта → clear).

Справжні маловідомі ТМ (WIST, Breeze, Kumho, Robin, Legenda, Vast, Kazara,
Stubla, SHIRO, DURALURE, Orange, X-Fish, puffi тощо) НЕ чіпаються.

Канал запису: штатний pricelist-імпорт (колонка "Бренд"; порожня клітинка
ОЧИЩАЄ поле — підтверджено раніше).

  python src/cleanup_brand_filter.py --dry-run
  python src/cleanup_brand_filter.py --sample   # перші 3 рядки
  python src/cleanup_brand_filter.py
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\FISH\fish-sync")
sys.path.insert(0, str(ROOT / "src"))

from import_parent_brand import build_xls, run_import  # noqa: E402
from sync_content_playwright import load_env  # noqa: E402

ART_TD = "<td style=\"mso-number-format:'\\@';\">"

# ── 1) точно НЕ бренди → очистити ────────────────────────────────────────
CLEAR = {
    # типи товарів / загальні слова (укр)
    "Рибальський", "Сумка", "Cумка", "Торба", "Торба Х2", "Катушка",
    "вудлище", "Сінінг", "Вудилища", "Спіннінг", "СпінінгNEW", "Спиннинг",
    "Вуочка", "Вуlочка", "Вдочка", "Маховое", "Фідерні", "Фідерн", "Фідерне",
    "короповий", "Коліно", "Лідкор", "поводок", "гач.", "обол.", "відв.",
    "повід.обол.", "струна", "REELS", "Кормачок", "Брелок-шнурок", "Box",
    "Combo", "Куля", "Конус", "Шумовка", "Вiдцеп", "Спрей", "Пікні",
    "Яйця", "Оснасточка", "стандарт", "в", "на", "упаковці", "наша снасть",
    "Супер Снасть", "кг", "20кг", "6.3", "Харків", "Баласт", "Флет",
    "Ракета", "Бочка-Ракета", "Метод Boat", "Кукан" ,
    # кольори
    "чорний", "хакі", "корич.", "green", "red", "yellow",
    # смаки / наживки / види риб
    "Карась", "Карась-М", "Банан", "Арбуз", "Слива", "ПОЛУНИЦЯ",
    "ТИГРОВИЙ ГОРІХ", "ГОРОХ", "ЧАСНИК", "КОНОПЛЯ", "МОТИЛЬ", "КУКУРУДЗА",
    "МЕД", "КРИЛЬ", "КРІЛЬ", "Халва", "Цукрова Кукурудза", "Карамель",
    "Ваніль", "АНІС", "Молоко", "Натурал", "Натуральна", "Без Добавок",
    "Спеції", "Сухий мотиль", "Тутті-Фрутті", "МАКУХА- ЧАСНИК",
    "МЕД- ПОЛУНИЦЯ", "ЧАСНИК - ЧЕБРЕЦЬ", "ЧАСНИК МАКУХА", "Коліандр Ваніль",
    "Пряже Молоко", "Макуха", "МЕКУХ", "Опариш", "Дрейсена", "Золота Рибка",
    "Білий Амур", "Fruit Mix", "Krill/Halibut", "Krill- Halibut",
    "Pineapple/Pear", "PINEAPPLE\\ PEAR", "Robin\\Red", "SQUID\\ OCTOPUS",
    "Squid\\Octopus", "Salmon/Strawberry", "Salmon- Stravberry",
    "Tiger Nut/Corn", "Tiger nut\\Corn", "Tiger Nut- Corn", "Tuna Extract",
    "Honey\\Stravberry", "Double Garlic",
    # форми мормишок / оснастки
    "Уралка", "Мураха", "Муха", "Оса", "Відьма", "Стрекоза", "Цвяшок",
    "Тополь", "Ризький Банан", "Плавунець", "Плавунець з оком", "Крапаль",
    "Кукалка", "Кокон", "Банан з вушком",
    "Крапля з вушком обмазка з камінчиком", "Кукулка з вушком",
    "Кулька-око", "Мідія з вушком", "Німфаз вушком", "Часничинка з отвором",
    "Шар з отвором спорт", "Шар з зушком гран", "Осінній лист",
    "Осінній бамбук",
    # моделі меблів
    "Рибак Економ", "Рибак Економ d16", "Рибак Економ зі спинкою",
    "Режисер з полицею", "Режисер з мякою полицею", "Режисер без полиці",
    "без полиці", "з полиці", "Вояж Комфорт", "Класик",
    # типи гачків (японська класифікація) та монтажів
    "SODE", "ISEAMA", "CHINU", "BEAK", "KEIRYU", "MARUSEIGO", "BAITHOLDER",
    "AJI", "Barbed", "Double", "Dual", "Fly", "ZIG", "Craft Hook",
    "Master Hooks", "mand carp",
    # коди / розміри / артикули
    "X8", "im8", "hcs3", "sec", "pcs2", "SFV4", "TZ-02", "TZ-08",
    "JC-01", "JC-02", "JC-03", "JC-04", "JC-07", "JC-08", "JC-09", "JC-10",
    "H.BIL228", "H.CRL", "H.ISE147", "H.SDE", "H.UMT", "H.UMT209",
    "C-1", "C-3", "C-4", "C-5", "K-1", "K-1XS", "L-1", "M-1", "Z-1",
    "D", "D-25", "R.", "ST-B", "HL", "KLD", "MH", "BE", "FFC", "3D",
    "4821000003732", "max",
    # загальні англ. слова / матеріали / типи
    "NEW", "SUPER", "Premium", "Pro", "BEST", "KING", "MASTER", "FISHING",
    "Fish", "Carp Fishing", "Carp Line", "Silver Carp", "SILVER", "GOLDEN",
    "ORIGINAL", "LEADER", "LEADERS", "Allround", "Method", "Method Stic Mix",
    "ICE", "Sky", "EVA", "Carbon", "Braid", "FLUOROCARBON", "Флюорокарбон",
    "Флюрокарбон", "Apparel", "Clothes", "sturdiness", "wterterwer",
    "Sport Night", "SALON" ,
    # моделі вудок/загальне
    "Sport Niht", "Fishing-Rod", "Fishing Forever", "Temptation",
}

# ── 2) typo / варіант → канонічний бренд ─────────────────────────────────
MAP = {
    "Kaipso": "Kalipso",
    "Seect": "SELECT",
    "Carpzoom": "Carp Zoom",
    "CZ": "Carp Zoom",
    "BigCatch": "Big Catch",
    "Big": "Big Fish",              # "Ліска Big Fish Feeder ..."
    "RiverTramp": "RIVER TRAMP",
    "AnviFishing": "ANVI FISHING",
    "Heranunafishing": "Herabunafishing",
    "MIFINA": "MIFINE",
    "Eclips": "ECLIPSE",
    "Favorit": "Favorite",
    "MEGASTRAIKE": "MEGASTRIKE",
    "FISHUNTER": "FISHHUNTER",
    "Fishing Ro": "Fishing ROI",
    "SAMS": "Sams Fish",
    "BOYA": "BOYA BY",
    "Джокер": "BOYA BY",            # Джокер = лінійка вудок BOYA
    "VIKING": "Viking Fishing",
    "Afeima": "Feima",
    "Aifeima": "Feima",
    "Foode Fish": "Foodie Fish",
    "Skilful": "GC",                # "Крючок GC Skilful ..."
    "Deft": "GC",                   # "Крючок GC Deft Trap ..."
    "Bully": "GC",                  # "Крючок GC Bully ..."
    "Craft": "Vido",                # "Гачок Vido Craft ..."
    "Чудо планктон": "KORONA",      # "Технопанктон CORONA "Чудо планктон""
    "MicroStar": "Feima",           # "Спінінг MicroStar ... AiFaima"
    "Xsense": "Feima",              # "Спінінг Xsense ... AiFaima"
    "БОМБА": "Бомба",               # нормалізація регістру серії мастирки
}

# ── 3) рішення за назвою товару ──────────────────────────────────────────
def namemap(brand: str, name: str) -> str | None:
    """Повертає нове значення ('' = очистити, None = правило не застосовне)."""
    if brand in {"Carp", "POWER", "WIDE", "PC", "Navigator", "Techno", "SALON"} and not (name or "").strip():
        return None   # назви немає — НЕ вгадуємо, лишаємо як є
    n = (name or "").upper()
    if brand == "Carp":
        if "CARP PRO" in n:
            return "CARP PRO"
        if "FEIMA" in n:
            return "Feima"
        return ""
    if brand == "POWER":
        if "POWER PRO" in n:
            return "Power Pro"
        return ""
    if brand == "WIDE":
        if "FOX" in n:
            return "FOX"
        if "METSUI" in n:
            return "METSUI"
        return ""
    if brand == "PC":
        if "OWNER" in n:
            return "Owner"
        return ""
    if brand == "Navigator":
        if "AFEIMA" in n or "AIFAIMA" in n:
            return "Feima"
        if "MEGASTRIKE" in n:
            return "MEGASTRIKE"
        return ""
    if brand == "Techno":
        if "TECHNO CARP" in n:
            return "Технокарп"
        return ""
    if brand == "SALON":
        if "LEGEND" in n:
            return "LEGENDA"
        return ""
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    src = json.load(open(ROOT / "data" / "country_fix_progress.json", encoding="utf-8"))
    prods = json.load(open(ROOT / "data" / "products.json", encoding="utf-8"))
    names = {str(p.get("kod") or "").strip(): p.get("name", "")
             for p in prods["products"] if str(p.get("kod") or "").strip()}

    rows: list[tuple[str, str]] = []   # (article, new_value)
    stats = Counter()
    for art, v in src.items():
        brand = (v.get("brand") or "").strip()
        if not brand:
            continue
        nm = namemap(brand, names.get(art, ""))
        if nm is not None:
            rows.append((art, nm))
            stats[f"namemap:{brand}->" + (nm or "(clear)")] += 1
        elif brand in MAP:
            rows.append((art, MAP[brand]))
            stats[f"map:{brand}->{MAP[brand]}"] += 1
        elif brand in CLEAR:
            rows.append((art, ""))
            stats[f"clear:{brand}"] += 1

    print(f"усього правок: {len(rows)}")
    for k, c in sorted(stats.items()):
        print(f"  {c:4d}  {k}")

    if args.dry_run:
        return 0
    if args.sample:
        rows = rows[:3]
        print("SAMPLE:", rows)

    html_rows = [
        f"<tr>{ART_TD}{html_mod.escape(a)}</td><td>{html_mod.escape(val)}</td></tr>"
        for a, val in rows
    ]
    xls = build_xls(html_rows, ["Артикул", "Бренд"])
    out = ROOT / "tmp" / f"import_brand_cleanup{'_sample' if args.sample else ''}.xls"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(xls)

    env = load_env()
    base = env.get("HOROSHOP_BASE_URL", "https://vsedliarybalky.com.ua").rstrip("/")
    res = run_import(out, ["article", "brand"], base, env["HOROSHOP_LOGIN"], env["HOROSHOP_PASS"])
    print("Результат:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
