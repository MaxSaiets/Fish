from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook


ROOT = Path(r"D:\FISH\fish-sync")
ASSETS_REPORT = ROOT / "data" / "horoshop_site_assets_report.json"
OUT_PRODUCTS = ROOT / "public" / "veteran_sport_import.xlsx"
OUT_PHOTOS = ROOT / "public" / "veteran_sport_photo_import.xlsx"
OUT_REPORT = ROOT / "data" / "veteran_sport_import_report.json"


CERTIFICATES = [
    ("VS-ABON-500", "Абонемент у клуб спортивного рибальства «Все для рибалки» 500 грн", 500, "veteran_500"),
    ("VS-ABON-1000", "Абонемент у клуб спортивного рибальства «Все для рибалки» 1000 грн", 1000, "veteran_1000"),
    ("VS-ABON-1500", "Абонемент у клуб спортивного рибальства «Все для рибалки» 1500 грн", 1500, "veteran_1500"),
    ("VS-ABON-2000", "Абонемент у клуб спортивного рибальства «Все для рибалки» 2000 грн", 2000, "veteran_2000"),
]


def description(amount: int) -> str:
    return (
        f"<p><strong>Абонемент у клуб спортивного рибальства «Все для рибалки» на {amount} грн</strong> "
        "можна використати для участі в активностях клубу або як подарунок рибалці.</p>"
        "<p>Після оформлення замовлення менеджер зв'яжеться з вами для підтвердження, "
        "пояснить умови використання та узгодить спосіб отримання.</p>"
        "<ul>"
        "<li>Номінал абонемента фіксований.</li>"
        "<li>Підходить для подарунка або участі в клубних подіях.</li>"
        "<li>Консультація за телефоном: +38067 895 7371.</li>"
        "</ul>"
    )


def main() -> int:
    assets = json.loads(ASSETS_REPORT.read_text(encoding="utf-8"))
    uploaded = assets.get("uploads") or {}
    image_urls = {
        key: str(value.get("uri") or "").strip()
        for key, value in uploaded.items()
        if isinstance(value, dict)
    }

    wb = Workbook()
    ws = wb.active
    ws.title = "Товари"
    ws.append(
        [
            "Артикул",
            "Назва(ua)",
            "Назва модифікації(ua)",
            "Розділ",
            "Цена",
            "Валюта",
            "Відображати",
            "Наявність",
            "Бренд",
            "Опис товару(ua)",
            "Тип(ua)",
            "Номінал(ua)",
        ]
    )

    photo_wb = Workbook()
    photo_ws = photo_wb.active
    photo_ws.title = "Фото"
    photo_ws.append(["Артикул", "Галерея"])

    rows = []
    for article, title, amount, image_key in CERTIFICATES:
        rows.append(
            {
                "article": article,
                "title": title,
                "price": amount,
                "image_url": image_urls.get(image_key, ""),
            }
        )
        ws.append(
            [
                article,
                title,
                title,
                "Подарункові сертифікати / всі",
                amount,
                "UAH",
                "Да",
                "В наявності",
                "Все для рибалки",
                description(amount),
                "Абонемент",
                f"{amount} грн",
            ]
        )
        photo_ws.append([article, image_urls.get(image_key, "")])

    OUT_PRODUCTS.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_PRODUCTS)
    photo_wb.save(OUT_PHOTOS)
    report = {
        "products_import": str(OUT_PRODUCTS),
        "photo_import": str(OUT_PHOTOS),
        "rows": rows,
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
